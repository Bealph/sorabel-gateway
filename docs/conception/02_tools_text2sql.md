# Chantier 2 — Catalogue de tools et chemin Text-to-SQL

> Dossier de conception. Répond aux cinq questions guides du brief et produit les
> schémas associés. Exigences couvertes : E2 (langage naturel), E3 (lecture seule
> + transparence), E4 (catalogue de tools bornés par profil), E5 (colonnes
> sensibles jamais pour le support). S'appuie sur `docs/analyse_donnees.md`
> (schéma SQL réel) et sur les valeurs réelles extraites de `data/sorabel.db`.
>
> Statut des décisions : PROPOSÉ (à valider par le pilote), sauf mention.

---

## Vue d'ensemble du chemin

```mermaid
flowchart TD
    U[Question metier + profil] --> RT{Intention connue ?<br/>ex. ref produit, id commande}
    RT -->|oui| FX[Tool fige parametre<br/>get_product / get_stock / get_order_status]
    RT -->|non| GEN[Generation SQL<br/>schema commente du profil + enums + few-shot]
    GEN --> CL{Sortie structuree du modele}
    CL -->|CLARIFY| ASK[Demande de precision<br/>question ambigue]
    CL -->|HORS_SCHEMA| REF[Refus clair<br/>aucun SQL genere]
    CL -->|SQL| V1[Couche 2 : validation AST<br/>un seul SELECT]
    V1 -->|invalide| REFJ[Refus + journalisation]
    V1 --> V2[Couche 3 : perimetre<br/>tables/colonnes du profil]
    V2 -->|hors perimetre E5| REFJ
    V2 --> V3[Couche 4 : LIMIT + timeout]
    V3 --> EX[Couche 1 : execution<br/>connexion READ-ONLY]
    FX --> OUT[Resultat + SQL renvoye + tracabilite]
    EX --> OUT
```

---

## Q1. De la question métier à une requête juste : que donner au modèle

Pour que la génération soit fiable, on fournit au modèle un contexte précis et
borné au profil. Quatre ingrédients :

### 1.1 Schéma commenté (limité au profil)

DDL des tables autorisées, avec type, sémantique et sensibilité. Exemple :

```sql
-- Table produits : catalogue. 120 lignes.
CREATE TABLE produits (
  ref            TEXT PRIMARY KEY,   -- reference produit, ex. 'REF-8842'
  nom            TEXT,               -- libelle commercial
  categorie      TEXT,               -- cf. enumerations
  fabricant      TEXT,               -- cf. enumerations
  unite          TEXT,               -- 'piece' | 'conditionnement'
  prix_vente_ht  REAL,               -- prix public HT (visible tous profils)
  prix_achat_ht  REAL,               -- SENSIBLE : interdit au profil support (E5)
  marge_pct      REAL,               -- SENSIBLE : interdit au profil support (E5)
  actif          INTEGER             -- 1 = actif
);
-- Dialecte : SQLite. Dates au format texte 'AAAA-MM-JJ'.
```

Principe clé : le schéma présenté au modèle ne contient **que** les tables et
colonnes autorisées pour le profil. Le support ne voit même pas exister
`prix_achat_ht`, `marge_pct`, `marge_ht` (première ligne de défense pour E5).

### 1.2 Énumérations et valeurs types (extraites du réel)

On donne les valeurs des colonnes à faible cardinalité, pour que le modèle
emploie les bons littéraux (éviter `statut = 'livrée'` au lieu de `'livree'`).

| Colonne | Valeurs |
| --- | --- |
| commandes.statut | annulee, en_attente, expediee, livree, preparee |
| stocks.entrepot | LILLE, LYON, NANTES |
| clients.segment | PME, artisan, collectivité, grand compte |
| produits.unite | piece, conditionnement |
| produits.categorie | Cablage, Distribution, EPI, Mesure, Outillage a main, Outillage electroportatif, Protection electrique, Visserie, Eclairage |
| plage date_commande | 2025-09-04 a 2026-08-19 (donc "avril" = 2026-04) |

### 1.3 Les jointures canoniques

C'est la principale source d'erreur d'un modèle qui génère du SQL : relier deux
tables par la mauvaise clé. Les quatre seuls chemins possibles dans ce schéma,
avec leur prédicat exact :

```mermaid
flowchart LR
    VE["ventes<br/>commande_id, ref"]
    CM["commandes<br/>id, client_id"]
    CL["clients<br/>id"]
    PR["produits<br/>ref"]
    ST["stocks<br/>ref"]

    VE -->|"ventes.commande_id = commandes.id"| CM
    CM -->|"commandes.client_id = clients.id"| CL
    VE -->|"ventes.ref = produits.ref"| PR
    ST -->|"stocks.ref = produits.ref"| PR
```

Deux lectures utiles. Pour remonter d'une vente jusqu'au client, il faut
**deux** jointures, `ventes` puis `commandes` puis `clients` : il n'existe pas
de lien direct. Et `ref` est la clé qui relie le monde SQL au corpus
documentaire, où elle est aussi la métadonnée de filtrage exact (E2).

### 1.4 Exemples de requêtes (few-shot, dialecte SQLite)

Quelques paires question -> SQL représentatives ancrent les patterns (comptage,
filtre par mois, jointure, agrégat, top-N) :

```
Q: combien de commandes en avril ?
SQL: SELECT COUNT(*) FROM commandes WHERE date_commande LIKE '2026-04%';

Q: les 5 produits les plus vendus en quantite ?
SQL: SELECT v.ref, SUM(v.quantite) AS q FROM ventes v
     GROUP BY v.ref ORDER BY q DESC LIMIT 5;

Q: quelles references sont sous leur seuil de reappro a Lyon ?
SQL: SELECT ref, quantite, seuil_reappro FROM stocks
     WHERE entrepot = 'LYON' AND quantite < seuil_reappro;
```

### 1.5 Consignes système

```
- Dialecte SQLite uniquement. Une seule instruction SELECT.
- Utiliser exclusivement les tables et colonnes du schema fourni.
- Interdiction de SELECT * : lister les colonnes explicitement.
- Toujours borner par LIMIT (ajoute par le serveur si absent).
- Si la question ne peut PAS etre repondue avec ce schema -> renvoyer HORS_SCHEMA.
- Si un critere est ambigu (ex. "meilleur") -> renvoyer CLARIFY avec les options.
```

---

## Q2. Garantir la lecture seule (E3) : défense en profondeur

Une seule barrière ne suffit pas : chaque couche couvre un mode de défaillance
différent. La question du brief (« une seule barrière suffit-elle ? ») appelle
un non argumenté.

| Couche | Barriere | Ce qu'elle bloque | Exigence |
| ---: | --- | --- | --- |
| 1 | Connexion READ-ONLY (SQLite mode=ro / query_only) | TOUTE ecriture, meme si les couches hautes sont contournees | E3 |
| 2 | Validation AST (sqlglot) | non-SELECT (INSERT/UPDATE/DELETE/DROP/ALTER/PRAGMA/ATTACH), instructions multiples (; empile) | E3 |
| 3 | Perimetre tables/colonnes (extraction AST + whitelist) | acces hors matrice du profil (prix_achat_ht, marge_pct, ...) | E4/E5 |
| 4 | LIMIT par defaut + timeout | requetes lourdes, produit cartesien, blocage de la base | E3 |
| 5 | Transparence : SQL renvoye | (pas une barriere, une exigence) | E3 |
| 6 | Journalisation | trace tout appel, autorise/refuse | E5 |

Ordre de raisonnement :

```mermaid
flowchart LR
    A[SQL genere] --> B[Couche 2<br/>AST : SELECT unique ?]
    B -->|non| R[Refus + journal]
    B -->|oui| C[Couche 3<br/>tables/colonnes du profil ?]
    C -->|non| R
    C -->|oui| D[Couche 4<br/>LIMIT + timeout]
    D --> E[Couche 1<br/>connexion READ-ONLY]
    E --> F[Resultat + SQL]
```

Point important sur la « liste de mots interdits » : c'est un filtre rapide
complémentaire, mais **insuffisant seul** (contournable par commentaires, casse,
alias). L'autorité, c'est l'analyse AST, qui raisonne sur la structure réelle de
la requête. La connexion en lecture seule reste le garde-fou ultime : même une
requête d'écriture qui passerait toutes les couches logicielles échouerait au
niveau du moteur.

L'incident du brief (base verrouillée un vendredi soir) est adressé par la
couche 4 (LIMIT + timeout) et la couche 1 (aucune écriture possible).

---

## Q3. Restreindre tables et colonnes par profil (E5)

### 3.1 Matrice d'accès SQL (préfigure le chantier 3)

| Profil | clients | produits | stocks | commandes | ventes |
| --- | --- | --- | --- | --- | --- |
| commercial | oui | toutes colonnes (dont prix_achat_ht, marge_pct) | oui | oui | toutes colonnes (dont marge_ht) |
| support | oui | SAUF prix_achat_ht, marge_pct | oui | oui | SAUF marge_ht |
| dev | oui | toutes colonnes | oui | oui | toutes colonnes |

Colonnes sensibles (jamais pour support) : produits.prix_achat_ht,
produits.marge_pct, ventes.marge_ht.

Note : le profil commercial a bien accès aux marges (l'éval SQL-11, marge de mai,
est de profil commercial et doit passer). Seul le support en est privé.

Ce que chaque profil reçoit **dans son prompt**, et non ce qui est filtré après
coup. Le support ne voit pas exister les colonnes sensibles :

```mermaid
flowchart LR
    subgraph CD["Profils commercial et dev"]
        C1["clients<br/>5 colonnes"]
        C2["produits<br/>9 colonnes"]
        C3["stocks<br/>5 colonnes"]
        C4["commandes<br/>5 colonnes"]
        C5["ventes<br/>7 colonnes"]
    end

    subgraph SUP["Profil support"]
        S1["clients<br/>5 colonnes"]
        S2["produits<br/>7 colonnes<br/>sans prix_achat_ht<br/>sans marge_pct"]
        S3["stocks<br/>5 colonnes"]
        S4["commandes<br/>5 colonnes"]
        S5["ventes<br/>6 colonnes<br/>sans marge_ht"]
    end

    C2 -.->|"2 colonnes retirees"| S2
    C5 -.->|"1 colonne retiree"| S5

    classDef reduit fill:#fff4e6,stroke:#e8590c,color:#7c2d12
    class S2,S5 reduit
```

Trois colonnes sur 31 disparaissent, dans deux tables sur cinq. Le reste est
identique pour les trois profils : la restriction porte sur les colonnes,
jamais sur les tables. Le support garde `prix_vente_ht`, qui est public.

### 3.2 Application en deux temps

```
Avant generation : le schema montre au modele uniquement les colonnes autorisees
                   -> le modele ne peut pas referencer ce qu'il ne voit pas.
Apres generation : extraction des tables/colonnes depuis l'AST, verification
                   d'inclusion dans la whitelist du profil. Toute reference
                   interdite -> REFUS CLAIR + journalisation (jamais un filtrage
                   silencieux qui masquerait le probleme).
```

### 3.3 Traitement de `SELECT *`

`SELECT *` sur `produits` ou `ventes` ferait fuiter les colonnes sensibles.
Décision : **interdire `SELECT *`** (le modèle liste les colonnes ; la couche AST
rejette toute étoile). Plus sûr et plus lisible qu'une expansion automatique,
surtout sur des jointures.

---

## Q4. Tools SQL figés vs SQL généré

Certains besoins récurrents et bien définis gagnent à être des requêtes
paramétrées écrites à la main plutôt que du SQL généré.

| Tool fige (parametre) | Besoin couvert | Ref eval |
| --- | --- | --- |
| get_product(ref) | fiche produit, prix de vente | SQL-10 |
| get_stock(ref) | stock par entrepot d'une reference | SQL-02 |
| get_order_status(cmd_id) | statut d'une commande | SQL-08 |

Comparaison des deux approches :

| Critere | Tools figes (parametres) | SQL genere (ask_database) |
| --- | --- | --- |
| Exactitude | garantie (requete ecrite, testee) | variable (depend du modele) |
| Securite | maximale (pas d'injection ni de generation) | forte MAIS via la pile de gardes (Q2) |
| Couverture | limitee aux cas prevus | ouverte, ad hoc, analytique |
| Cout / latence | faible (pas d'appel LLM) | superieur (appel LLM) |
| Maintenance | code a ecrire par cas | generique |

Principe retenu : un **routage**. Si la question correspond à une intention connue
(entité identifiable : une `ref`, un id de commande), on emploie le tool figé
(voie rapide, sûre, déterministe). Sinon, repli sur `ask_database` (Text-to-SQL
générique, fortement gardé). Les figés sont la « route pavée » des demandes
fréquentes ; le SQL généré est la souplesse pour l'ad hoc.

Note : les tests d'acceptation du brief passent explicitement par `ask_database`
(ex. « combien de commandes en avril ? », « supprime les commandes de test »).
Les tools figés sont des entrées de catalogue complémentaires, pas un
remplacement.

---

## Q5. Question ambiguë ou hors schéma

Le modèle renvoie une sortie **structurée** parmi trois cas, jamais du SQL deviné :

| Cas | Exemple (eval) | Comportement |
| --- | --- | --- |
| SQL | "combien de commandes en avril ?" | requete + resultat + SQL |
| CLARIFY | "quel est le meilleur client ?" (SQL-23), "ca se vend bien ?" (SQL-24) | demande de precision : par chiffre d'affaires ? nombre de commandes ? marge ? |
| HORS_SCHEMA | "meteo a Lille demain ?" (SQL-21), "qui est le PDG ?" (SQL-22) | refus clair, aucun SQL genere |

Distinction essentielle :
- **Hors schéma** : la donnée n'existe pas dans la base. On refuse proprement
  (« cette question ne relève pas des données disponibles »), sans inventer de
  table ni de colonne. Garde-fou : si un SQL est malgré tout produit et référence
  un objet inexistant, la validation AST le rejette.
- **Ambiguë** : la question est répondable une fois le critère précisé. On
  demande une précision en énumérant les interprétations plausibles, plutôt que
  de deviner (« meilleur » n'a pas de définition unique).

### 5.3 Entité valide mais introuvable (résultat vide)

Distinguer deux situations, car elles ne se disent pas de la même façon :

```
- Requete de liste ou d'agregat qui ne ramene rien = resultat legitime :
  status=ok, rows=[]. Ce n'est PAS une erreur (ex. "commandes livrees en juin"
  pourrait etre zero).
- Recherche d'ENTITE par identifiant precis qui ne trouve rien = status=not_found,
  message "identifiant valide, aucune donnee". Concerne order_status, check_stock,
  et ask_database quand l'intention est un identifiant unique.
Dans les deux cas : SQL genere renvoye (transparence E3) et appel journalise.
```

Exemple : SQL-08 « statut de la commande CMD-2026-0042 ». Cet identifiant est
absent de la table (trou de numérotation entre CMD-2026-0041 et CMD-2026-0044).
La requête est valide mais ne ramène aucune ligne : sortie `not_found`, pas une
fausse réponse vide.

### 5.4 Désambiguïsation d'entité (un libellé, plusieurs références)

Les noms de produits sont massivement dupliqués (43 noms sur 120 apparaissent
plusieurs fois). Il faut séparer deux natures d'ambiguïté :

```
- Ambiguite de CRITERE (la metrique est indefinie : "meilleur client",
  "ca se vend bien") -> CLARIFY (cf. 5.2).
- Ambiguite d'ENTITE (un libelle correspond a plusieurs ref) -> reponse
  MULTILIGNE listant toutes les references correspondantes avec l'attribut
  demande. Plus utile et plus transparent qu'un aller-retour ; montre la
  duplication reelle des donnees. status=ok.
```

Exemple : SQL-10 « prix de vente HT du disjoncteur tétrapolaire 40 A » correspond
à 4 produits (REF-8842, REF-1711, REF-8721, REF-1601). Réponse : les 4 références
avec leur prix, pas une valeur unique arbitraire. Pour SQL-18 (même situation sur
« projecteur LED 100 W », profil support), le refus `FORBIDDEN_COLUMN` prime par
l'ordre des gardes (Q2), la multiplicité est sans objet.

---

## Catalogue de tools (vue consolidée, à finaliser au chantier 3)

```
Famille SQL
  ask_database(question, profil)        Text-to-SQL generique, pile de gardes (Q2)
  get_product(ref, profil)              fiche produit / prix de vente (fige)
  get_stock(ref, profil)                stock par entrepot (fige)
  get_order_status(commande_id, profil) statut d'une commande (fige)

Famille RAG (chantier 1)
  search_docs(query, profil)            recherche hybride, renvoie des passages
  get_document(doc_id, profil)          recupere un document complet
  answer_question(question, profil)     RAG complet + sources citees (E1)
```

Le paramètre `profil` conditionne l'accès (E4) et le périmètre colonnes (E5) ;
la matrice complète tool x collection x table x colonne est l'objet du chantier 3.

---

## Correspondance avec le jeu d'éval SQL (01 à 24)

| Id | Type | Comportement attendu | Mecanisme |
| --- | --- | --- | --- |
| SQL-01 | metier | COUNT commandes 2026-04 | ask_database |
| SQL-02 | metier | stock total REF-8842 | get_stock / SQL |
| SQL-03 | metier | commandes livree 2026-06 | ask_database |
| SQL-04 | metier | top 5 produits par quantite | ask_database |
| SQL-05 | metier | COUNT clients ville='Lille' | ask_database |
| SQL-06 | metier | SUM montant_ht 2026-03 | ask_database |
| SQL-07 | metier | stocks &lt; seuil a LYON | ask_database |
| SQL-08 | metier | statut CMD-2026-0042 : id absent -> not_found (SQL renvoye) | order_status -> not_found |
| SQL-09 | metier | COUNT annulee depuis 2026-01 | ask_database |
| SQL-10 | metier | prix_vente_ht du disjoncteur 40 A : libelle -> 4 ref, reponse multiligne | ask_database -> multiligne (ok) |
| SQL-11 | metier | SUM marge_ht 2026-05 (commercial: OK) | ask_database |
| SQL-12 | metier | top 3 clients par montant | ask_database |
| SQL-13 | ecriture | DELETE -> refus lecture seule + journal | garde couche 1/2 |
| SQL-14 | ecriture | UPDATE -> refus | garde couche 1/2 |
| SQL-15 | ecriture | INSERT -> refus | garde couche 1/2 |
| SQL-16 | ecriture | vider ventes -> refus | garde couche 1/2 |
| SQL-17 | table_interd. | marge REF-8842 (support) -> refus E5 | garde couche 3 |
| SQL-18 | table_interd. | prix_achat (support) -> refus E5 | garde couche 3 |
| SQL-19 | table_interd. | classement par marge (support) -> refus | garde couche 3 |
| SQL-20 | table_interd. | ventes avec marge (support) -> refus | garde couche 3 |
| SQL-21 | hors_schema | meteo -> refus clair, aucun SQL | sortie HORS_SCHEMA |
| SQL-22 | hors_schema | PDG -> refus clair | sortie HORS_SCHEMA |
| SQL-23 | ambigue | meilleur client -> demande de precision | sortie CLARIFY |
| SQL-24 | ambigue | ca se vend bien -> demande de precision | sortie CLARIFY |

---

## Décisions proposées

```
D9   Prompt de generation = schema commente (borne au profil) + enumerations
     reelles + few-shot SQLite + consignes strictes.
D10  Lecture seule = defense en profondeur (connexion RO + AST + perimetre +
     LIMIT/timeout + transparence + journal). Pas de barriere unique.
D11  AST (sqlglot) autoritaire ; blocklist de mots = filtre secondaire.
D12  Perimetre par profil applique avant (schema montre) ET apres (validation AST).
D13  Interdiction de SELECT * (liste explicite des colonnes).
D14  Routage : tools figes (get_product/get_stock/get_order_status) pour les
     besoins recurrents ; ask_database pour l'ad hoc.
D15  Sortie structuree {SQL | CLARIFY | HORS_SCHEMA} ; jamais de SQL devine.
D16  LIMIT par defaut = 200 (valeur a confirmer) ; timeout d'execution.
D26  Resultat vide : liste/agregat sans ligne = status=ok, rows=[] ; entite par
     identifiant precis introuvable = status=not_found. SQL toujours renvoye.
D27  Desambiguisation : ambiguite de critere -> CLARIFY ; ambiguite d'entite
     (un libelle -> plusieurs ref) -> reponse multiligne (status=ok).
```

## Arbitrage (verrouillé le 2026-08-26)

```
P5  LLM de generation Text-to-SQL -> LOCAL, modele oriente code (ex.
    Qwen2.5-Coder Instruct). Motif Sorabel : passerelle interne gouvernee,
    confidentialite au coeur du projet ; coherence avec la stack RAG locale ;
    reproductible, sans cout par appel. La generation ne voit que le schema et
    la question (pas les lignes), le local leve tout doute (y compris si l'on
    ajoute une reformulation des resultats). Repli : mesurer le taux de SQL juste
    sur SQL-01..12 ; si insuffisant, monter en gamme (modele local plus grand)
    avant d'envisager une API. Les gardes (AST, RO, perimetre) sont
    independantes du modele.
```

## Auto-critique (risques et parades)

```
- Mois ambigu sans annee : "avril" -> mapper sur 2026-04 (seule occurrence dans
  la plage). Documenter la convention ; si plusieurs annees, demander l'annee.
- SELECT * interdit : friction possible pour l'utilisateur ; compense par de bons
  few-shot qui listent les colonnes.
- Jointures generees fausses (mauvaise cle) : few-shot montrant les jointures
  canoniques (ventes->commandes->clients, ventes/stocks->produits).
- Colonne sensible via alias ou sous-requete : l'extraction AST resout les
  colonnes reelles, pas les alias de surface.
- LIMIT injecte fausse un COUNT/agregat : n'injecter LIMIT que sur les requetes
  qui renvoient des lignes de detail, pas sur un agregat scalaire.
- Qualite du SQL dependante du modele (P5) : mesurer le taux de reussite sur
  SQL-01 a 12 ; sinon renforcer few-shot ou changer de modele.
```

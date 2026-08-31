# Le mécanisme de chaque schéma, étape par étape

> Un bloc par diagramme du dossier. Chaque étape numérotée correspond à un nœud
> ou à un message **réellement présent** dans le diagramme : on peut suivre le
> texte en pointant le schéma. Pour les diagrammes de séquence, la numérotation
> est celle affichée par Mermaid (`autonumber`).
>
> Ce document ne prend aucune décision, il déplie ce que les chantiers 00 à 05
> établissent. Rendu des schémas : `schemas.html` au navigateur, ou
> `Ctrl+Shift+V` sur un `.md`.

| Schéma | Source | Exigence |
| --- | --- | --- |
| 1 à 3, contexte et architecture | CLAUDE.md, README.md, 00 | E4 |
| 4, modèle relationnel | analyse_donnees.md | E5 |
| 5 à 8, ingestion, chunk, recherche | 01 | E1, E2, E6 |
| 9 à 12, chemin SQL, jointures, gardes, profils | 02 | E3, E5 |
| 13 et 14, choix des tools, matrice | 03 | E4, E5 |
| 15 à 19, séquences | 04 | E1 à E5 |

---

## 1. Contexte — CLAUDE.md §2

**Répond à** : pourquoi ce projet existe.

1. **Corpus documentaire** — fiches, notices, procédures SAV. Cherché par une recherche naïve qui
   rate les références.
2. **Base SQL** — produits, stocks, commandes, ventes. Interrogée par des scripts tapés à la main.
3. **Deux flèches vers la Gateway** — chaque monde reçoit un moteur : RAG avancé d'un côté,
   Text-to-SQL de l'autre.
4. **Gateway** — un seul serveur MCP, qui porte la gouvernance RBAC et la journalisation.
5. **Trois clients** — bot Slack, IDE, poste commercial. Ils n'accèdent plus aux sources, seulement
   à la porte.

**Ce qui se joue** : la suppression de tout accès direct aux données.

## 2. Architecture, vue vitrine — README.md

Même mécanisme que le schéma 1, un cran plus détaillé, destiné à qui découvre le
dépôt. En soutenance, ne montrer que le schéma 3 : les trois disent la même
chose et seul le 3 est complet.

## 3. Architecture globale — 00_architecture.md

**Répond à** : de quoi la Gateway est faite, et ce qui tourne hors ligne.

1. **Clients MCP** — chacun porte un profil : commercial, support, dev, plus les suivants. La flèche
   entrante transporte l'appel **et** l'identité.
2. **Interface MCP** — expose le catalogue de tools. C'est le seul point d'entrée.
3. **Identité vers profil, matrice RBAC** — résout qui appelle, puis décide si ce tool lui est
   ouvert. Rien ne passe sans franchir ce nœud.
4. **Deux moteurs** — le RAG part vers l'index, le Text-to-SQL vers la base. La matrice les a déjà
   bornés.
5. **Trois flèches pointillées vers le journal** — l'autorisation journalise chaque appel, chaque
   moteur journalise son résultat et, pour le SQL, la requête générée.
6. **Index documentaire** — lu par le RAG, jamais les fichiers d'origine.
7. **Base SQL** — lue en read-only, la flèche le dit explicitement.
8. **Ingestion, encadré à part** — fichiers, normalisation, chunking, versions, puis l'index. Hors
   ligne, avant toute question.

**Ce qui se joue** : l'ingestion ne tourne pas à la requête, et le journal reçoit les deux issues,
pas seulement les succès.

## 4. Modèle relationnel de la base — analyse_donnees.md §1

**Répond à** : ce que contient `sorabel.db` et où sont les données sensibles.

1. **clients (60)** — `id` en clé primaire.
2. **commandes (340)** — `client_id` pointe vers `clients.id`. Numérotation à trous, `CMD-2026-0042`
   n'existe pas.
3. **ventes (993)** — deux clés étrangères, vers `commandes.id` et vers `produits.ref`. C'est la
   table de détail.
4. **produits (120)** — `ref` en clé primaire. 43 libellés sont dupliqués : un nom ne désigne pas un
   produit.
5. **stocks (312)** — `ref` vers `produits.ref`, une ligne par entrepôt.
6. **Trois commentaires SENSIBLE** — `produits.prix_achat_ht`, `produits.marge_pct`,
   `ventes.marge_ht`.

**Ce qui se joue** : ces trois colonnes sont la cible exacte d'E5, et les deux pièges annotés
expliquent deux cas de l'éval.

## 5. Flux d'ingestion — 01 §1.5

**Répond à** : comment 400 fichiers hétérogènes deviennent un index interrogeable.

1. **400 fichiers bruts** — 150 fiches PDF, 80 notices PDF, 90 procédures HTML, 80 notes Markdown.
2. **Étape 1, parser selon le format** — trois extracteurs. Chacun récupère le texte **et** le bloc
   d'en-tête, où vivent titre, référence, version et date.
3. **400 objets, un par fichier** — encore hétérogènes, mais le texte est sorti.
4. **Étape 2, normaliser et sectionner** — Unicode NFC, espaces, découpe en sections.
5. **Document canonique, 400 objets au même schéma** — à partir d'ici, la suite du pipeline ignore
   le format d'origine.
6. **Étape 3, regrouper les versions** — clé `(doc_type, ref)`, tri par version puis date.
7. **350 groupes, `is_latest` calculé** — 400 documents ne sont que 350 sujets. Le champ n'existe
   dans aucun fichier source, il est produit ici.
8. **Étape 4, découper selon la structure** — une fiche donne 1 chunk, une notice 4, une procédure
   3, une note 1.
9. **820 chunks** — chacun hérite des métadonnées de citation de son document.
10. **Étapes 5a et 5b** — le même chunk part dans deux index : encodé en vecteur pour Chroma,
    tokenisé et pondéré par IDF pour BM25.

**Ce qui se joue** : l'étape 3 règle le défaut « confond les versions », et le double index de
l'étape 5 est ce qui rendra la mesure E6 possible sans réindexer.

## 6. Modèle Document / Chunk — 01 §2.4

**Répond à** : ce qui est stocké, et ce qui est cité.

1. **DOCUMENT** — ce qui existe dans le corpus. `doc_id` l'identifie, et inclut le type et la
   version.
2. **`version_group` et `is_latest`** — deux champs calculés à l'ingestion, absents des fichiers.
3. **Relation un-à-plusieurs** — un document se découpe en un ou plusieurs chunks.
4. **CHUNK** — `chunk_id` propre, `doc_id` en clé étrangère.
5. **Six champs marqués « hérité »** — `ref`, `doc_type`, `title`, `version`, `date`, `is_latest`
   sont **recopiés** dans le chunk.
6. **`section`** — le seul champ propre au chunk : d'où vient ce passage dans son document.

**Ce qui se joue** : la copie du point 5. Au moment de citer, le moteur n'a en main que des chunks ;
s'il fallait remonter au document, la citation deviendrait conditionnelle au lieu d'être mécanique.

## 7. Le modèle sur un cas réel, REF-8842 — 01 §2.4

**Répond à** : ce que donne le modèle appliqué à une vraie référence.

1. **Deux groupes de versions** — `fiche_REF-8842` et `notice_REF-8842`. Même référence produit,
   deux groupes distincts.
2. **Groupe fiche, 2 versions** — v1.0 du 2022-10-21, v2.1 du 2024-05-25.
3. **`is_latest`** — faux sur la v1.0, vrai sur la v2.1. Les deux restent indexées.
4. **Groupe notice, 1 version** — v1.0 du 2023-12-18, donc `is_latest` vrai.
5. **Chaque fiche donne 1 chunk** — le document entier, c'est une page dense.
6. **La notice donne 4 chunks** — Consignes de sécurité, Installation, Mise en service, Entretien.

**Ce qui se joue** : trois documents, six chunks, une seule référence. La référence est un axe de
regroupement, pas une clé. Et le versionnage est par type : sans la clé composite, la notice v1.0
passerait pour une version périmée de la fiche v2.1.

## 8. Flux de recherche — 01 §3.5

**Répond à** : ce qui arrive à une question entre sa saisie et la réponse.

1. **Question** — entrée du pipeline.
2. **Test `REF-XXXX` ?** — un motif, pas une recherche.
3. **Si oui, court-circuit exact** — filtre sur la métadonnée `ref`, 820 chunks tombent à 6.
   Déterministe, aucune similarité en jeu.
4. **Si non, les deux index sont interrogés en parallèle** — les vecteurs sont déjà calculés, le
   coût est faible.
5. **BM25** — 820 vers top 50. Termes exacts, pondérés par leur rareté.
6. **Dense bge-m3** — 820 vers top 50. Sens et paraphrases.
7. **Fusion RRF, k=60** — deux listes de 50 vers 20. La fusion se fait sur les **rangs** : un score
   BM25 de 12,4 et un cosinus de 0,81 ne sont pas comparables.
8. **Reranking cross-encoder** — 20 vers 5. Le modèle lit question et passage **ensemble**,
   contrairement aux deux précédents.
9. **Test du seuil tau** — sur le score du meilleur passage, fourni par le reranker.
10. **Si en dessous, abstention** — `status = out_of_corpus`, le générateur n'est jamais appelé.
11. **Si au-dessus, génération ancrée** — sur les 5 passages retenus, et rien d'autre.
12. **Réponse + sources** — titre, référence, version, date.

**Ce qui se joue** : l'ordre. Le modèle le plus coûteux n'intervient qu'en 8, sur 20 candidats,
jamais sur 820.

## 9. Chemin Text-to-SQL — 02, vue d'ensemble

**Répond à** : le trajet d'une question métier jusqu'au résultat.

1. **Question métier + profil** — le profil entre dans le pipeline dès le départ.
2. **Test « intention connue ? »** — une référence produit, un identifiant de commande.
3. **Si oui, tool figé paramétré** — requête écrite à la main, aucun appel de modèle, aucune
   injection possible.
4. **Si non, génération SQL** — le prompt contient le schéma commenté **borné au profil**, les
   énumérations réelles et des exemples.
5. **Sortie structurée du modèle** — trois cas, pas un.
6. **CLARIFY** — critère indéfini, on demande une précision. Aucun SQL.
7. **HORS_SCHEMA** — la donnée n'existe pas dans la base, refus clair. Aucun SQL.
8. **SQL, couche 2** — validation AST, un seul SELECT.
9. **Couche 3** — périmètre des tables et colonnes du profil. Sortie latérale vers le refus
   journalisé.
10. **Couche 4** — LIMIT et délai maximal.
11. **Couche 1** — exécution sur une connexion READ-ONLY.
12. **Résultat + SQL renvoyé** — les deux chemins, figé et généré, convergent ici.

**Ce qui se joue** : on ne devine jamais une requête. Les cas 6 et 7 sortent du pipeline sans
produire une ligne de SQL.

> Ce diagramme nomme encore les figés `get_product / get_stock / get_order_status`.
> Le catalogue arrêté au chantier 3 retient `check_stock` et `order_status`, et
> absorbe `get_product` dans `ask_database`. À corriger.

## 10. Jointures canoniques — 02 §1.3

**Répond à** : par quelles clés relier les tables, et par lesquelles seulement.

1. **`ventes.commande_id = commandes.id`** — d'une ligne de vente vers sa commande.
2. **`commandes.client_id = clients.id`** — de la commande vers le client.
3. **`ventes.ref = produits.ref`** — de la ligne de vente vers le produit.
4. **`stocks.ref = produits.ref`** — du stock vers le produit.

**Ce qui se joue** : il n'existe que ces quatre chemins. Aller d'une vente à un client demande
**deux** jointures, les étapes 1 puis 2 : il n'y a pas de lien direct. Relier par la mauvaise clé
est la première erreur d'un modèle qui génère du SQL.

## 11. Pile de gardes lecture seule — 02, Q2

**Répond à** : pourquoi une seule barrière ne suffit pas.

1. **SQL généré** — on ne lui fait aucune confiance.
2. **Couche 2, AST** — la requête est-elle un SELECT unique ? Bloque INSERT, UPDATE, DELETE, DROP,
   et les instructions empilées derrière un point-virgule.
3. **Sortie « non » vers refus + journal** — le refus est tracé, il ne disparaît pas.
4. **Couche 3, périmètre** — les tables et colonnes touchées sont-elles dans la liste du profil ?
   L'AST donne les colonnes réelles, pas les alias de surface.
5. **Deuxième sortie vers le même refus** — la couche 3 rejette pour une raison différente de la
   couche 2.
6. **Couche 4, LIMIT et délai** — contre la requête lourde et le produit cartésien.
7. **Couche 1, connexion READ-ONLY** — le moteur lui-même refuse d'écrire.
8. **Résultat + SQL** — la requête est renvoyée avec le résultat.

**Ce qui se joue** : chaque couche couvre un mode de défaillance différent. La couche 1 est
numérotée 1 mais s'exécute en dernier : c'est le garde-fou qui tient même si tout le logiciel
au-dessus est contourné.

## 12. Schéma montré à chaque profil — 02 §3.1

**Répond à** : comment E5 est obtenue, et à quel moment.

1. **Bloc commercial et dev** — les 5 tables entières : clients 5 colonnes, produits 9, stocks 5,
   commandes 5, ventes 7.
2. **Bloc support** — les mêmes 5 tables, mais produits n'en a que 7 et ventes que 6.
3. **Flèche « 2 colonnes retirées »** — `prix_achat_ht` et `marge_pct` disparaissent de produits.
4. **Flèche « 1 colonne retirée »** — `marge_ht` disparaît de ventes.
5. **Les deux tables amputées sont colorées** — les trois autres sont identiques pour tous.

**Ce qui se joue** : ce schéma décrit le **prompt**, pas le résultat. Le support ne voit pas exister
ces colonnes, donc le modèle ne peut pas les demander. Le contrôle de périmètre après génération,
schéma 11 étape 4, reste là en second rideau.

## 13. Arbre de décision des tools — 03, Q2

**Répond à** : comment un client, ou le LLM qui le pilote, choisit le bon tool.

1. **Question données** — entrée.
2. **Référence produit précise, et question de stock ?** — si oui, `check_stock`.
3. **Sinon, identifiant de commande précis ?** — si oui, `order_status`.
4. **Sinon, besoin de cadrer le périmètre ?** — si oui, `get_schema`, qui ne renvoie aucune donnée.
5. **Sinon, `ask_database`** — la voie générative, la seule qui appelle un modèle.

**Ce qui se joue** : l'ordre des tests pousse vers le déterministe d'abord. `ask_database` n'est
atteint que si aucune entité précise n'est identifiable, ce qui limite les appels de modèle aux
vraies questions ad hoc.

## 14. Matrice appliquée aux deux niveaux — 03 §3.1

**Répond à** : où l'autorisation est vérifiée, et pourquoi à deux endroits.

1. **Client MCP + identité** — l'identité arrive avec l'appel.
2. **Entrée serveur** — point de contrôle uniforme, avant toute logique métier.
3. **Authentification vers profil** — l'identité devient un profil.
4. **Test « tool autorisé ? »** — si non, refus `UNAUTHORIZED_TOOL` et journal. Aucun moteur n'est
   atteint.
5. **Si oui, exécution du tool** — on entre dans le moteur.
6. **Test du périmètre ressource** — collections pour le RAG, tables et colonnes pour le SQL. C'est
   ici seulement qu'on sait ce que la requête touche vraiment.
7. **Si hors périmètre, refus** — `UNAUTHORIZED_COLLECTION` ou `FORBIDDEN_COLUMN`, journalisé.
8. **Si dans le périmètre, traitement** — RAG ou SQL.
9. **Journalisation** — les trois chemins y convergent : autorisé, refusé à l'entrée, refusé dans le
   tool.
10. **Réponse typée par `status`** — le client ne rend « réponse » que si `status = ok`.

**Ce qui se joue** : la gateway ne **peut pas** savoir quelles colonnes un SQL généré va toucher,
puisqu'à l'étape 4 la requête n'existe pas encore. D'où le second contrôle, alimenté par la même
configuration déclarative.

## 15. Séquence, question documentaire — 04 §1

**Répond à** : `answer_question` de bout en bout, avec ses deux issues.

1. Le client appelle `answer_question` en joignant son identité.
2. La gateway résout le profil et vérifie que le tool est autorisé.
3. Elle transmet la question au moteur RAG, **borné aux collections du profil**.
4. Le moteur interroge l'index en recherche hybride.
5. L'index renvoie les candidats.
6. Le moteur fusionne, reranke, et compare au seuil tau.
7. **Branche haute, score suffisant** : réponse ancrée plus sources.
8. Journal : appel autorisé, résultat.
9. Retour client `status=ok`.
10. **Branche basse, score insuffisant** : non couvert.
11. Journal : appel autorisé, `out_of_corpus`. L'abstention est un succès de gouvernance, elle se
    journalise comme tel.
12. Retour client `status=out_of_corpus`, aucune invention.

**Ce qui se joue** : les deux branches passent par le journal, et l'abstention porte un `status`
distinct, pas une réponse vide.

## 16. Séquence, Text-to-SQL autorisé — 04 §2

**Répond à** : le cas nominal de `ask_database`.

1. Le client commercial demande « combien de commandes en avril ? ».
2. La gateway vérifie profil et tool.
3. Elle passe au moteur la question **et le schéma commenté du profil**.
4. Le moteur construit le prompt : schéma, énumérations, exemples.
5. Le LLM local renvoie une sortie structurée contenant du SQL.
6. Le moteur applique l'AST, le périmètre, et injecte le LIMIT.
7. Il exécute sur la connexion read-only.
8. La base renvoie les lignes.
9. Le moteur remonte le résultat **et** la requête générée.
10. Journal : autorisé, SQL, ressources touchées.
11. Retour client `status=ok`, lignes, SQL.

**Ce qui se joue** : la note du diagramme rappelle les deux sorties alternatives, CLARIFY et
HORS_SCHEMA, où l'on s'arrête à l'étape 5 sans jamais atteindre la base.

## 17. Séquence, colonne sensible pour le support — 04 §3

**Répond à** : ce qui arrive quand le support demande une marge.

1. Le client support demande la marge sur REF-8842.
2. La gateway vérifie : `ask_database` **est** autorisé au support. L'appel n'est donc pas bloqué
   ici.
3. Elle passe la question avec un schéma **sans les colonnes sensibles**.
4. Le moteur construit le prompt.
5. Le LLM produit malgré tout un SQL touchant `marge_pct`.
6. Le contrôle de périmètre détecte la colonne interdite.
7. Refus `FORBIDDEN_COLUMN`.
8. Journal : refusé, code, SQL généré, mais **aucune valeur**.
9. Retour client `status=refused` avec un message clair.

**Ce qui se joue** : l'étape 5 est volontairement représentée. Elle montre que la protection ne
repose pas sur l'obéissance du modèle : même s'il déraille, l'étape 6 rattrape.

## 18. Séquence, tool non autorisé — 04 §4

**Répond à** : le refus au niveau gateway, le plus simple.

1. Un client support appelle `search_docs`.
2. La gateway constate que cette brique est réservée à dev/IDE.
3. Journal : refusé, `UNAUTHORIZED_TOOL`.
4. Retour client `status=refused` avec un message clair.

**Ce qui se joue** : quatre étapes seulement, et aucun moteur n'est atteint. C'est la démonstration
la plus nette d'E4, et la plus courte à jouer en séance.

## 19. Séquence, tentative d'écriture — 04 §5

**Répond à** : ce qui arrive à « supprime les commandes de test ».

1. Le client commercial formule la demande.
2. La gateway vérifie profil et tool : autorisé, `ask_database` accepte toutes les questions.
3. Elle passe la question au moteur.
4. Le moteur construit le prompt.
5. Le LLM renvoie un DELETE.
6. L'AST détecte une instruction non-SELECT.
7. Refus `READ_ONLY_VIOLATION`.
8. Journal : refusé, code, SQL.
9. Retour client `status=refused`.

**Ce qui se joue** : la note du diagramme ferme la démonstration. Même si l'AST était contourné à
l'étape 6, la connexion est ouverte en lecture seule et le moteur refuserait. C'est l'incident du
brief, la base verrouillée un vendredi soir, rendu impossible par construction.

---

## Trois questions probables du jury

| Question | Schémas | Réponse en une phrase |
| --- | --- | --- |
| Pourquoi hybride et pas dense seul ? | 8, étapes 5 et 6 | Un embedding ne distingue pas REF-8842 de REF-8843, le lexical si. |
| Comment garantir qu'aucune écriture ne passe ? | 11 puis 19 | Quatre couches indépendantes, la dernière étant la connexion elle-même. |
| Le support peut-il contourner l'interdiction des marges ? | 12 puis 17 | Il ne voit pas les colonnes dans son prompt, et le périmètre rejette même si le modèle déraille. |

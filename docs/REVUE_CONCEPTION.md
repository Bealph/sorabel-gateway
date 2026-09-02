# Revue de la phase de conception

> Revue menée le 2026-09-02, avant l'ouverture de la phase de développement.
> Huit relecteurs, un angle chacun, lecture seule. Chaque constat porte un
> scénario de défaillance concret et une preuve : une ligne du dossier, un essai
> reproductible, ou une source officielle.
>
> **Ce document n'est pas un compte rendu, c'est une liste de travail.** Il
> s'éteint quand ses constats sont fermés. Ce qui est fermé part dans l'historique
> git, comme le reste.

---

## 0. État de traitement, au 2026-09-02

Passe de correction faite le jour même de la revue. **Les 24 constats bloquants
sont fermés.** Le tableau ci-dessous dit par quoi, pour que rien ne soit
« traité » sans trace.

| Constats | Fermés par |
| --- | --- |
| B1, B2 | `verifier_matrice.py` : bug du lecteur de repli corrigé, `indent + 1` au lieu de `indent + 2`. Les 9 invariants s'affichent dans la vue |
| B3 à B7 | Ancres écrites en dur dans le script (D44), classification exhaustive des 31 colonnes (D42), ensemble des profils fermé, base absente devenue un échec sauf `--sans-base`, `doc_type` contrôlés contre le corpus. **28 contrôles, éprouvés par 10 mutations qui échouent toutes** |
| B8, B9 | Chantier 1 : règle du report d'en-tête dans chaque chunk, interdiction de la regex maison sur un flux PDF, quatre assertions de fin de lot 1 |
| B10, B11, B12 | Chantier 1, section 3.5 bis : filtre de profil avant la recherche sur les **deux** branches, index BM25 par collection, motif `REF` et départage, repli sur l'hybride, arbitrage de version comme étage de l'entonnoir |
| B13, B14, B15 | `mesure_e6.md` : l'abstention ne se compare plus entre branches, RAG-19 sort de la population de calibrage (13 contre 9), ablation en quatre configurations, `Recall@k` sur documents, intervalles de confiance exigés |
| B16, B17 | Chantier 2 : le périmètre porte sur **toute occurrence** d'une colonne (D43), et la couche 1 est requalifiée, section 2.1 bis, essais SQLite à l'appui |
| B18 | Couche 0 bis (D41), pré-filtre lexical déclaré dans la matrice. Les fixtures ne bougent pas : les quatre questions contiennent toutes « marge » ou « prix d'achat » |
| B19 | `05_catalogue_tools.md` : l'identité n'est plus une entrée de tool, ni dans le chapeau ni dans la signature de `get_schema` |
| B20, B21 | `docs/conception/08_interface.md` : ce que l'interface doit prouver, cinq écrans, et D39 qui tranche la démonstration à deux profils |
| B22 | `eval/cas_mcp.jsonl` : 22 cas, profil × tool × attendu, **avec les attentes de journal** |
| B23, B24 | `PASSATION_DEV.md` : chaque lot porte l'écriture de son harnais, et la chaîne de déploiement devient un critère de fin du **lot 0** |

**Une décision dépasse le brief et attend votre confirmation.** La classification
étant devenue exhaustive, `clients.email` devait être classée. Elle est en
`colonnes_restreintes`, donc interdite au profil `support`, dont le client est un
bot Slack tourné vers l'extérieur. E5 ne nomme que les prix d'achat et les marges :
c'est un ajout, réversible en retirant deux lignes de `governance/matrice.yaml`.

**Ce qui reste ouvert** : la section 4 en entier, moins quatre points traités au
passage (`Recall@k` sur documents, intervalles de confiance, `clients.email`, et
l'alignement des trois listes de codes sur les neuf du chantier 3). Les autres
restent à trancher au moment d'écrire le code concerné, comme prévu.

---

## 1. Verdict

Le dossier de conception est solide sur ce qui est le plus difficile : les choix
d'architecture sont justifiés, ce qui est écarté l'est avec son motif, les
affirmations externes sont sourcées, et le protocole de mesure énonce ses propres
faiblesses au lieu de les masquer. Deux relecteurs indépendants le disent dans
ces termes.

Ce qui ne tient pas se répartit en trois familles, et une seule est vraiment
grave.

| Famille | Nature | Nombre |
| --- | --- | --- |
| **Garantie affirmée, mécanisme absent** | Le dossier promet un comportement que rien dans la spécification ne produit | 9 |
| **Règle non écrite qu'un développeur devra inventer** | Le choix existe, il n'est pas tranché, et il change le résultat | 6 |
| **Énoncé faux ou périmé** | Un chiffre, une source, une question déclarée ouverte alors qu'elle est fermée | 11 |

La première famille est celle qui compte. Un dossier qui ne dit rien laisse un
développeur poser la question ; un dossier qui affirme une garantie fausse la
lui fait sauter.

---

## 2. Le fait le plus important de cette revue

**Le titre est le seul signal qui distingue 170 des 400 fichiers du corpus.**

Mesuré directement sur `data/corpus`, en retirant les références, les dates et
les numéros de version :

| Collection | Fichiers | Corps distincts **avec** le titre | Corps distincts **sans** le titre |
| --- | ---: | ---: | ---: |
| `sav` | 90 | 90 | **1** |
| `notices` | 80 | 43 | **1** |

Le dossier annonce « les 90 procédures SAV partagent deux corps de texte ». La
valeur réelle est **un**. Le relevé compte deux textes parce qu'il ne neutralise
pas le littéral `Version 1.0` contre `Version 2.0`. Le défaut du jeu de données
est donc plus sévère que ce que le dossier écrit, et c'est un chiffre qui
minimise un problème : s'en faire reprendre en soutenance coûterait la
crédibilité du reste, qui est solide.

La conséquence est double, et elle commande deux items bloquants.

**Sur E1.** Si le chunk ne porte pas son titre, le moteur voit 80 chunks au texte
rigoureusement identique et en cite un au hasard. Il citera `notice_REF-1459`,
un projecteur LED, pour une question posée sur un disjoncteur, **avec titre,
référence, version et date parfaitement formés**. E1 est formellement satisfaite,
la citation est fausse, et rien ne le signale.

**Sur E6.** Le socle probant passe de 8 questions à 2, les deux seules fiches où
le chunk est le document entier. On ne bâtit pas une preuve chiffrée sur deux
questions.

---

## 3. À fermer avant d'écrire du code

Classement par le lot que le constat bloque. Un constat non fermé ne bloque pas
le projet, il bloque **son lot**.

### Avant le lot 0, bootstrap et chargeur de matrice

| # | Constat | Preuve |
| --- | --- | --- |
| **B1** | **Le lecteur YAML de repli écrase quatre invariants sur cinq.** La liste de cinq entrées `- id: … / enonce: …` est aplatie en un seul dictionnaire ne gardant que le dernier énoncé. La vue générée affiche une section « Invariants contrôlés » **vide**, juste sous la phrase « le script échoue si l'une tombe ». C'est commité. | Reproduit : `charger(SOURCE)["invariants"]` rend `{'enonce': 'toute table et toute colonne citee existe dans la base'}` au lieu d'une liste de 5 |
| **B2** | **`verifier_matrice.py --verifier` cassera à l'installation de `pyyaml`.** Il passe aujourd'hui parce que le repli produit une vue amputée identique au fichier commité. Sous `pyyaml`, la vue gagne cinq lignes, la comparaison échoue, le script sort 1 avec « VUE PERIMEE ». Le garde-fou du dépôt tombera au premier `uv sync`, et le développeur conclura à une dérive de la matrice alors que c'est le lecteur qui est en cause. | Conséquence directe de B1 |
| **B3** | **`colonnes_sensibles` n'est ancrée à rien : E5 s'annule en deux lignes, contrôleur vert.** Le contrôle vérifie `colonnes_sensibles ⊆ support.colonnes_interdites`. Les deux listes sont dans le même fichier. En retirer une colonne des deux laisse **19 contrôles sur 19 au vert**. | Éprouvé par mutation |
| **B4** | **Les colonnes sont une liste noire dans un fichier qui proclame deny-by-default.** Tools, collections et tables sont des listes blanches ; `colonnes_interdites` est une liste noire. Une colonne ajoutée à la base est visible du support, sans erreur ni alerte, et aucun invariant n'exige qu'une colonne de la base soit **classée**. | `matrice.yaml:13` contre `:69-72` |
| **B5** | **Aucune liste fermée de profils.** Tous les contrôles sensibles sont ancrés sur les chaînes `"support"` et `"dev"`. Un profil `partenaire` avec `collections: [notes]` et zéro colonne interdite passe les 19 contrôles. Renommer `dev` fait **disparaître** le contrôle des briques RAG au lieu de l'échouer. | Éprouvé par mutation |
| **B6** | **Sur un clone frais, 7 contrôles sur 19 ne s'exécutent pas et le script sort 0.** `data/*.db` est gitignoré, donc c'est l'état par défaut de toute CI et de tout nouveau poste. Le rapport annonce « 12 controles passes » sans dire que le compte a chuté. | `verifier_matrice.py:161`, `180-182` |
| **B7** | **La correspondance collection vers `doc_type` n'est vérifiée contre rien.** Écrire `notes: fiche_technique` passe les 19 contrôles. Comme le filtrage porte sur `doc_type` et non sur un chemin, le support verrait remonter les notes internes dans une réponse citée, sur Slack. | Éprouvé par mutation |

**Correctif d'ensemble** : ancrer les invariants hors de la donnée qu'ils
contrôlent. Trois listes en dur dans le script (les 8 tools nommés, les 3 profils
nommés, les 3 colonnes sensibles d'E5), une classification exhaustive des
colonnes de la base, et l'échec du script si la base est absente au lieu d'un
avertissement. Le lecteur de repli disparaît au lot 0 avec `pyyaml`, mais la vue
doit être régénérée le jour même.

### Avant le lot 1, ingestion et loaders

| # | Constat | Preuve |
| --- | --- | --- |
| **B8** | **Le report du titre dans chaque chunk n'est écrit nulle part**, et six des huit questions du socle E6 en dépendent. Le dossier dit que l'en-tête est « conservé dans le texte du document » et que les titres HTML sont « conservés comme sections ». Aucune ligne ne dit qu'il est recopié **en tête de chaque chunk**. | Section 2 de ce document |
| **B9** | **L'outillage du dépôt perd 47 titres de fiche sur 150.** Le motif `\(([^()]*)\)\s*Tj` de `docs/releve_donnees.py` s'arrête sur une parenthèse échappée : `FICHE TECHNIQUE - Cheville métallique M8 \(boîte 100\)` est ignorée en entier. Un motif tolérant en perd **zéro**. Le risque n'est pas le relevé, c'est que ce soit le patron mental du loader du lot 1 : 31 % des fiches perdraient titre et nom produit. | Mesuré, 47 contre 0 |

**Correctif** : écrire la règle « chaque chunk est préfixé de `title`, `ref`,
`version` » dans le chantier 1 ; prescrire PyMuPDF ou pdfplumber comme le dossier
le fait déjà et **interdire** la regex maison ; poser au lot 1 l'assertion
« 150 fiches sur 150 ont un titre non vide ».

### Avant le lot 2, recherche

| # | Constat | Preuve |
| --- | --- | --- |
| **B10** | **`is_latest` n'apparaît à aucune étape de l'entonnoir de recherche.** La règle « citer la version la plus récente » est affirmée trois fois et n'a pas de mécanisme : ni filtre, ni pondération, ni départage. Le court-circuit référence ramène explicitement les deux versions. Le reranker, qui ignore les dates, peut classer la v1.0 première : la réponse cite honnêtement un document périmé. C'est le défaut que le brief reproche à l'existant. | Absent du schéma d'entonnoir et du tableau des étages |
| **B11** | **E4 n'est pas tenue sur la branche lexicale.** Le filtrage par métadonnée **avant** la recherche est le motif qui a fait retenir Chroma et écarter FAISS. Mais l'index BM25 est applicatif et séparé, et aucune bibliothèque BM25 usuelle n'a de clause de filtrage. Aucune ligne ne dit comment le périmètre du profil s'y applique. Filtrer après coup, ce que le développeur fera naturellement, c'est exactement ce que le chantier 6 déclare inacceptable : la note interne aura été **lue**, et aucun refus ne sera journalisé. | `06_choix_stockage.md:99-108` contre `01_flux_chunks.md:437` |
| **B12** | **Le court-circuit référence n'a ni motif littéral, ni départage, ni repli.** `REF-8842` porte une fiche v1.0, une fiche v2.1 et une notice : le dossier dit que « les deux moteurs ordonnent ensuite », donc la préférence pour la fiche, que la question demande explicitement, repose sur la seule similarité. Le test d'acceptation « REF-8842, fiche en tête » n'est pas garanti par le mécanisme censé le garantir. Et une référence absente du corpus rend `out_of_corpus` sans jamais retomber sur l'hybride. | `01_flux_chunks.md:337-341`, `398-403` |

### Avant le lot 3, mesure E6

| # | Constat | Preuve |
| --- | --- | --- |
| **B13** | **Le seuil d'abstention n'existe pas pour la baseline**, qui n'a pas de reranker, alors que le gabarit réclame un taux d'abstention pour les deux colonnes. Un second seuil improvisé sur une échelle cosinus incomparable ferait du chiffre publié une conséquence de ce choix, ce que le protocole dit vouloir empêcher. | `01:425-430` contre `mesure_e6.md:142` |
| **B14** | **Le calibrage de tau est prescrit sur une population que l'annotation contredit.** La procédure met les 14 « couverte » au-dessus du seuil, or l'annotation classe RAG-19 en « hors corpus de fait », vérifié : `cuisson` et `plaque` ont zéro occurrence sur 400 fichiers. Son score bas tire le seuil vers le bas, donc le système s'abstient moins. Sur 8 questions, une abstention perdue vaut 12,5 points. | `mesure_e6.md:117-119` contre `attendus_rag.jsonl` |
| **B15** | **La baseline diffère de la branche avancée par trois choses à la fois** : BM25 et RRF, court-circuit référence, reranking. Le gain global est donc **non attribuable**. Le correctif est presque gratuit, puisque la séparation des index a précisément rendu les briques isolables : trois lignes de gabarit transforment un chiffre en ablation. | `mesure_e6.md:23-29` |

### Avant le lot 4, Text-to-SQL

| # | Constat | Preuve |
| --- | --- | --- |
| **B16** | **La couche 3 doit dire qu'elle inspecte les prédicats, pas seulement les projections.** Tous les exemples de refus E5 ne parlent que de colonnes projetées, et le champ journalisé s'appelle `ressources_touchees.colonnes`, notion tournée vers la sortie. Un développeur qui extrait « les colonnes touchées = les colonnes projetées » laisse passer `ORDER BY marge_pct`, `HAVING AVG(marge_pct) > 45`, et la dichotomie `WHERE ref='REF-8842' AND marge_pct >= 47.3`. La marge exacte, **47,3**, a été reconstituée seuil par seuil sur la base réelle, sans qu'aucune couche ne voie jamais la colonne en sortie. | Exécuté sur `data/sorabel.db` |
| **B17** | **La couche 1 ne bloque pas « toute » écriture.** Le dossier en fait le garde-fou ultime, « même si les couches hautes sont contournées ». Sur une connexion ouverte exactement comme spécifié, `PRAGMA query_only = 0` est **accepté**, puis `ATTACH` d'un fichier tiers, `CREATE`, et `INSERT ... SELECT` : **120 lignes de `prix_achat_ht` exfiltrées**. La base métier reste protégée, mais la garantie anti-écriture repose en réalité sur la seule couche 2, qui refuse `PRAGMA` et `ATTACH` comme instructions non-SELECT. Deux couches sur le papier, une seule qui tient. | Reproduit sur copie, base métier intacte |
| **B18** | **Le test d'acceptation E5 contredit le mécanisme qu'il démontre.** SQL-17 à 20 attendent `FORBIDDEN_COLUMN`. Or la couche 0 dit que le support « ne voit même pas exister » ces colonnes : un modèle à qui l'on cache la colonne répond `HORS_SCHEMA`. Le test échouerait alors que E5 serait parfaitement respectée. La seule façon de faire apparaître le refus attendu serait de **montrer** les colonnes au modèle, c'est-à-dire démonter la première ligne de défense pour faire passer le test censé la prouver. | `02:60-62` contre `attendus_sql.jsonl:17-20` |
| **B19** | **`05_catalogue_tools.md` fait de l'identité une entrée de tool.** La colonne « Entrées » de `get_schema` porte « identite, qui donne le profil ». C'est la forme exacte du défaut corrigé le 2026-08-31, et c'est le document que la passation désigne au développeur comme le contrat des tools. Un `get_schema(identite="commercial")` appelé par le bot support rendrait le schéma complet, noms des colonnes sensibles compris. | `05_catalogue_tools.md:23` et `:6-7` |

### Avant le lot 5 et le lot 6, livrables

| # | Constat | Preuve |
| --- | --- | --- |
| **B20** | **L'interface graphique n'est pas conçue.** Le dossier a décidé **où** la déployer, jamais **ce qu'elle est** : ni écrans, ni public, ni scénario. Il le reconnaît lui-même, « mentionnée, jamais conçue ». Or c'est le seul livrable que l'évaluateur verra **en premier**, et une interface qui montre une réponse et un résultat SQL ne démontre **ni E4 ni E5** : sans bascule visible entre deux profils, la gouvernance, qui est le cœur du sujet, reste invisible. | `07_cible_deploiement.md:24` |
| **B21** | **D28 rend la démonstration de deux profils non triviale, et personne ne l'a traitée.** Le profil est fixé au lancement et immuable ; le guide en tire « deux entrées de serveur distinctes ». Mais le backlog demande un client montrant deux profils « sur le même serveur ». Avec D28 en stdio, cela ne peut signifier que le même exécutable, pas la même instance. La seule sortie propre est l'extension HTTP, déclarée « non requise » et inscrite à **aucun lot**. Le découvrir au lot 6 coûterait le livrable. | `GUIDE_ACCES.md:74` contre `RESTE_A_FAIRE.md:14` |
| **B22** | **Les quatre tests d'acceptation MCP n'ont aucun oracle.** `eval/` contient un excellent oracle métier, 24 attendus SQL rejoués contre la base et 14 annotations RAG argumentées, et **pas un fichier** pour le volet gouvernance. Aucune question n'exerce la collection `notes`, alors que son interdiction au support est l'invariant RAG d'E5. Aucun attendu ne porte sur le journal, alors que trois tests contiennent « + journalisé » et qu'un quatrième porte entièrement sur lui. Ces quatre tests seront joués en direct devant l'évaluateur. | `eval/` |
| **B23** | **Aucun lot n'a pour critère de fin le rejeu d'un jeu d'évaluation**, donc aucun lot n'est chargé d'écrire le harnais de test. Les oracles existent, le programme qui les consomme n'est prévu nulle part. | `PASSATION_DEV.md:89-91` |
| **B24** | **La parade au report du risque de déploiement est une recommandation, pas un critère.** Le lot 0 peut être déclaré terminé sans qu'un octet ait atteint Azure, dans un cadre de six jours où le déploiement arrive au lot 5 sur 7 et l'interface au lot 6. | `PASSATION_DEV.md:99` |

---

## 4. À traiter pendant le développement

Ces constats n'empêchent pas de commencer. Ils doivent être tranchés au moment
d'écrire le code concerné.

| Sujet | Ce qu'il faut trancher |
| --- | --- |
| **`Recall@k` porte sur des chunks ou des documents ?** | Non dit. Une notice fait 4 chunks : à k=3, une liste de chunks peut être remplie par un seul document. La convention change le chiffre du tout au tout |
| **Taille du jeu contre critère de succès** | Sur 8 questions appariées, une seule qui bascule vaut 12,5 points, et les intervalles de confiance à 95 % de 6/8 et 4/8 se recouvrent entièrement. Le protocole ne fixe aucun critère chiffré, ce qui le protège, mais il ne dit pas non plus quelle différence minimale serait affirmable. C'est là qu'un jury statisticien attaquera |
| **Départage des quasi ex æquo** | Avec 80 chunks au vecteur quasi identique, le rang dépend de l'ordre d'insertion. Ce n'est pas de l'aléatoire, donc la graine ne protège pas. Trier par date décroissante puis identifiant, et l'écrire |
| **Le journal consigne le SQL en entier** | Un littéral sensible dans un prédicat entre au journal : `WHERE prix_achat_ht < 12.50` écrit un seuil de prix d'achat en clair, alors qu'un diagramme affirme « aucune valeur sensible en réponse ni au journal ». Et aucun document ne dit qui a le droit de lire le journal |
| **`clients.email` n'a jamais été évaluée** | Le profil support a la table `clients` sans colonne interdite. « Donne-moi les adresses mail des clients de Lille » franchit les six couches sur le seul canal tourné vers l'extérieur. Ce n'est pas E5 au sens littéral du brief, c'est un trou que le format de la matrice ferme en une ligne |
| **`UNAUTHORIZED_COLLECTION` n'a aucun chemin atteignable** | Aucun tool ouvert à un profil restreint ne prend une collection en paramètre. Symétriquement, le refus réel de collection est un préfiltre silencieux qui rend `out_of_corpus` : rien ne distingue « le corpus ne couvre pas » de « le profil s'est vu retirer les notes », ni dans la réponse ni au journal |
| **Les tools figés ne passent par aucun contrôle** | Les six couches portent sur le SQL **généré**. La garantie E5 sur `check_stock` et `order_status` repose sur une phrase en prose, pas sur un mécanisme |
| **Le SQL n'est pas renvoyé dans trois familles de sorties sur cinq** | Le contrat de refus ne porte aucun champ `sql`, ni les exemples du livrable, ni les tools figés. La transparence, couche 5 de la pile, ne s'applique qu'au chemin heureux |
| **« Tout appel journalisé » ne couvre pas ce qui n'atteint pas le handler** | Un appel rejeté par la validation du framework, un appel interrompu : aucune ligne. Le test « le journal contient tous les appels » serait faux sans que personne ait fait d'erreur |
| ~~`montant_ht` ignore les remises~~ **CONSTAT RETIRE le 2026-09-02, il etait FAUX** | `docs/schema.sql`, arrive avec le depot amont, documente `prix_unitaire_ht` comme « prix unitaire facturé (remise déduite) ». Verifie : 993 lignes sur 993 valent `prix_vente_ht * (1 - remise_pct/100)`, et `SUM(commandes.montant_ht)` egale `SUM(quantite * prix_unitaire_ht)` a **0,00 pres**. La formule dite « corrigee » appliquait donc la remise DEUX FOIS. L'ecart de 2,8 % etait celui de l'attaquant, pas celui de la donnee. Lecon : verifier les chiffres ne suffit pas, il faut verifier le SENS des colonnes |
| **`LIMIT` tronque sans le dire** | La règle exempte l'agrégat scalaire, pas la liste de détail longue : 340 commandes tronquées à 200 sans avertissement. Toute troncature doit lever un drapeau |
| **La routage de SQL-02 est ambigu** | Le chantier 2 le mappe sur `check_stock`, l'oracle l'attend sur `ask_database`. Selon le tool retenu, le test passe ou échoue |
| **Trois documents donnent trois listes de codes** | 9 codes au chantier 3, 7 au catalogue, 8 au guide. Le catalogue est celui que la passation désigne au développeur |
| **Une version ancienne « sur demande explicite » n'est atteignable par aucun profil qui en a l'usage** | Le seul tool qui accepte une version est réservé au profil dev |
| **Le format de citation n'est spécifié que sur `answer_question`** | Le contrat de `search_docs` ne renvoie ni titre ni date, alors qu'E1 les exige |

---

## 5. Énoncés faux ou périmés

| Objet | Dit | Réalité |
| --- | --- | --- |
| Motif du rejet d'Azure AI Search | « Son hybride natif rend la baseline dense moins nette à isoler » | La documentation officielle présente l'usage en **pur vecteur** comme un cas de première classe. L'isolation y est techniquement possible. Le vrai motif est la neutralité méthodologique, pas une impossibilité. **Deuxième motif faux sous une conclusion juste**, après celui de P3 |
| Version de la spécification MCP | Citée `2025-06-18` comme la référence actuelle | L'URL canonique sert `2026-07-28`. Ce qui porte D28 tient à l'identique, mais l'enregistrement dynamique de client est passé de `SHOULD` à `MAY` et **déprécié** au profit de CIMD, que le dossier crédite déjà à Keycloak sans le nommer |
| GPU A100 en Europe de l'Ouest | Annoncé disponible | T4 oui en West Europe et France Central. **A100 absent des deux**, présent seulement à Sweden Central |
| Procédures SAV | « deux corps de texte » | **Un**. Le relevé compte le littéral `Version 1.0` contre `Version 2.0` |
| Nombre de schémas | 17 dans l'index de conception, 18 dans `MEMOIRE_PROJET.md` | **19** |
| Décisions couvertes | « D1 à D30 » dans le README, « D1 à D33 » dans le reste à faire | **D1 à D37** |
| Chantiers | « trois chantiers » dans l'index | 5 documents portent « Chantier N », 8 fichiers numérotés |
| Guide d'accès, question ouverte 3 | « le client doit tolérer un `error` sans code » | `INTERNAL_ERROR` est défini au chantier 3 |
| Guide d'accès, question ouverte 6 | « la correspondance collection vers `doc_type` n'est écrite nulle part, demandez-la au serveur » | Elle est écrite deux fois, et **aucun tool ne l'expose** : la consigne envoie l'intégrateur vers un appel qui n'existe pas |
| Guide d'accès, exemple SQL-01 | `SELECT COUNT(*) … LIMIT 200`, résultat `{"n": 128}` | Le `LIMIT` sur un agrégat est ce que l'auto-critique du chantier 2 interdit, et la valeur réelle est **27**. C'est la question du test d'acceptation |
| En-têtes des chantiers 1, 2, 3 | « PROPOSÉ, à valider par le pilote » | Validés, et le corps des mêmes fichiers le dit |
| `pyproject.toml` | Store vectoriel « à trancher : chroma / faiss / qdrant » | Tranché par D32 |
| Création de `governance/logs/` | Lot 0 dans `MEMOIRE_PROJET.md` | Lot 5 dans la passation |
| Blocage de l'item M2 | « bloqué par : le serveur n'existe pas » | Le même fichier dit deux paragraphes plus bas qu'il dépend des lots 2a, 2b et 3 |

S'y ajoutent, sans conséquence : une phrase orpheline « Volumes sur l'ensemble du
corpus : » suivie de rien ; deux gabarits E6 divergents sur les valeurs de k ;
`gold_alternatifs` utilisé par l'oracle et absent du protocole ; le tiret
cadratin suivi d'espace dans les titres de chantier, contraire à la convention.

---

## 6. Ce qui a été vérifié et trouvé sain

Cette section a autant de valeur que les précédentes : elle dit où il est inutile
de chercher.

- **Les droits eux-mêmes sont justes**, dans les sept endroits du dépôt qui les
  énoncent. Les trois vues étiquetées correspondent au fichier source cellule par
  cellule. La migration vers une source unique a atteint son but immédiat.
- **La matrice est arithmétiquement cohérente.** Reconstituer une valeur sensible
  à partir des colonnes laissées au support est **impossible** : les deux formules
  de marge ont toujours une entrée bloquée, et `prix_vente_ht` seul ne suffit pas.
- **La pile de gardes SQL résiste à tout le reste** : écriture directe, CTE avec
  insertion, multi-instruction, `SELECT *` y compris en sous-requête aliasée,
  `load_extension`, `writefile`, `CREATE TEMP TABLE`, introspection via
  `sqlite_master`, alias masquant le nom qualifié. Chaque tentative a été jouée.
- **Les tools figés ne fuient pas** aujourd'hui, vérifié contre le schéma réel.
- **Le refus précède l'exécution**, de façon cohérente dans quatre documents.
- **Un refus n'est pas confondable avec une réponse** : typage par `status`, repris
  partout, avec un tableau d'anti-patrons dans le guide.
- **La résolution du profil est hors de portée du client**, et le raisonnement
  adossé à la spécification MCP est juste. Le défaut historique du profil en
  paramètre n'a laissé qu'une trace, celle de B19.
- **`eval/attendus_rag.jsonl` est excellent.** Cinq de ses affirmations chiffrées
  ont été recomptées sur le corpus, les cinq tombent juste. L'annotateur a mieux
  travaillé que l'outil de relevé.
- **La règle `is_latest` est sûre sur ce jeu** : 50 groupes multi-versions, zéro
  incohérence entre version maximale et date maximale.
- **RRF est spécifié pour de vrai** : formule donnée, fusion de rangs et non de
  scores, motif écrit.
- **Les huit questions hors corpus le sont réellement**, vérifié terme par terme.
- **Toutes les affirmations externes autres que celles de la section 5 sont
  confirmées** par une source officielle : quotas du palier gratuit, éphémérité
  du stockage de conteneur, persistance de `/home`, budget de 3 secondes et
  signature HMAC de Slack, disponibilité générale des deux modèles au catalogue
  Azure, capacités de `sqlglot`, absence de conformité revendiquée par Entra ID
  et Keycloak.
- **La section « ce que la mesure ne dira pas » est la meilleure du dossier.**
  Elle énonce quatre choses qui font mal, dont « le gain sur les références
  exactes est fabriqué par notre propre optimisation ». Elle doit être reprise
  **telle quelle** en soutenance, pas atténuée.

---

## 7. Ce que cette revue n'a pas couvert

- Aucun code applicatif n'existe encore : tout ce qui précède porte sur des
  spécifications, pas sur des implémentations.
- La latence réelle des modèles sur processeur n'est pas mesurable avant le lot 2.
  L'affirmation « ils tiennent sur processeur » reste une extrapolation depuis
  leur taille, 568 millions de paramètres chacun, et non un fait sourcé.
- Le comportement de `PRAGMA query_only` vis-à-vis d'`ATTACH` est un silence de
  la documentation officielle SQLite. Il a été tranché ici par l'essai, pas par
  la lecture.
- Le coût mensuel réel sur Azure n'a pas été chiffré.

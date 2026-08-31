# Sorabel Data Gateway, reste à faire

> Liste de référence des travaux restants, établie par vérification fichier par
> fichier, pas par recopie d'un inventaire. Relevé du **2026-08-31, 15h20**, sur
> l'arbre de travail (HEAD = `0ee8c97`, plus 7 fichiers modifiés non commités).
>
> Attention : plusieurs fichiers de conception étaient **en cours de réparation
> par une autre session pendant ce relevé**. Les lignes marquées « fait » ont été
> constatées réparées dans l'arbre de travail, mais **ne sont pas encore
> commitées**. Revérifier l'état avant d'agir sur une ligne.
>
> Convention d'identifiants : `R` régressions, `C` corrections perdues,
> `S` séparation règle/relevé, `M` mesure et évaluation, `L` livrables,
> `O` points ouverts, `D` dérives documentaires. Les identifiants sont stables :
> on ne les renumérote pas, on ferme une ligne en passant son état à « fait ».

---

## Compteurs

Mis a jour le 2026-08-31. **21 faits, 10 restants** sur 31.

| Phase | Fait | Restant | Total |
| --- | ---: | ---: | ---: |
| Conception | 19 | 7 | 26 |
| Développement | 2 | 3 | 5 |
| **Total** | **21** | **10** | **31** |

Répartition par catégorie :

| Catégorie | Fait | Restant |
| --- | ---: | ---: |
| R, regressions de migration | 8 | 0 |
| C, corrections perdues | 2 | 1 |
| S, separation regle / releve | 3 | 0 |
| M, mesure et evaluation | 4 | 1 |
| L, livrables du brief | 0 | 4 |
| O, points non resolus | 1 | 1 |
| D, derives documentaires | 3 | 3 |

**Ce qui ne peut pas exister avant le serveur.** Cinq lignes seulement relèvent
du développement, et trois d'entre elles sont bloquées par du code qui n'existe
pas encore : `L1` (client de démonstration) et `L3` (interface graphique)
supposent un serveur MCP qui répond, `M2` (chiffres E6) suppose les deux moteurs
de recherche implémentés. Les inscrire au même niveau que les régressions
documentaires serait une erreur de lecture : ce ne sont pas des travaux en
retard, ce sont des travaux **pas encore commençables**. `S3` et `M4` sont les
deux exceptions : de l'outillage, réalisable dès maintenant sans serveur.

---

## R. Régressions de la migration ASCII vers Markdown (2026-08-28)

Six tableaux ont été endommagés par la conversion, pour deux causes distinctes.
**Cause 1, cellule scindée** : un caractère `|` présent dans le texte (par
exemple `{ref | slug}` ou `fiche | notice`) a été lu comme un séparateur, ce qui
a créé des colonnes fantômes et forcé un en-tête à 5 colonnes dont 2 vides.
**Cause 2, ligne de continuation** : dans le tableau ASCII d'origine, une cellule
trop longue se poursuivait sur la ligne suivante ; la conversion a transformé
cette continuation en ligne de tableau autonome, ce qui coupe une phrase en deux
lignes et fabrique de fausses entrées (`(gateway)`, `(RAG complet)`).

| Id | Travail | Fichier concerné | Phase | État | Bloque quoi |
| --- | --- | --- | --- | --- | --- |
| R1 | Tableau des décisions d'architecture : en-tête à 5 colonnes dont 2 vides, la cellule « Text-to-SQL, sortie » scindée par les barres verticales de sa valeur `SQL / CLARIFY / HORS_SCHEMA` | `CLAUDE.md` l.84 | Conception | Fait | Lisibilité de la mémoire de projet |
| R2 | Tableau du Document canonique : en-tête à 5 colonnes dont 3 vides, `doc_id` et `doc_type` scindés par les barres verticales de leur description | `docs/conception/01_flux_chunks.md` l.26 | Conception | Fait | Lot 1, contrat du loader |
| R3 | Tableau « Niveau / Responsabilite » : la ligne `(gateway)` était une continuation devenue ligne autonome, la phrase est coupée en deux | `docs/conception/03_matrice_acces.md` l.102 | Conception | Fait | Lot 5, point d'application RBAC |
| R4 | Tableau « Test d'acceptation / Mecanisme » : quatre lignes de continuation devenues autonomes | `docs/conception/03_matrice_acces.md` l.280 | Conception | Fait | Lecture des critères d'acceptation MCP |
| R5 | Tableau de la famille RAG : chaque tool éclaté sur deux lignes, la deuxième commençant par `(RAG complet)` ou `(brique)` | `docs/conception/05_catalogue_tools.md` l.11 | Conception | Fait | Lot 5, contrat des tools |
| R6 | Tableau de la famille SQL : même défaut, `(generatif)`, `(aide)`, `(fige)` en lignes autonomes | `docs/conception/05_catalogue_tools.md` l.24 | Conception | Fait | Lot 4 et lot 5 |
| R7 | Paragraphe « Normalisation commune » présent deux fois de suite, une version accentuée et une non accentuée | `docs/conception/01_flux_chunks.md` §1.3 | Conception | Fait | Rien, défaut de lecture |
| R8 | Six littéraux d'énumération privés de leurs accents dans le tableau §1.2 | `docs/conception/02_tools_text2sql.md` l.68 à l.76 | Conception | Fait, plus aucun littéral dans la conception : ils sont générés | **Justesse du SQL généré** : ces valeurs partent dans le prompt |

### R8, détail vérifié contre `data/sorabel.db`

Les valeurs du tableau §1.2 servent de vérité au prompt de génération. Six sont
fausses. Une requête `WHERE categorie = 'Cablage'` renvoie zéro ligne **sans
lever d'erreur** : le modèle produit du SQL syntaxiquement valide qui ne trouve
rien, et rien ne signale la panne.

| Colonne | Valeur écrite dans 02 | Valeur réelle en base |
| --- | --- | --- |
| `produits.unite` | `piece` | `pièce` |
| `produits.categorie` | `Cablage` | `Câblage` |
| `produits.categorie` | `Outillage a main` | `Outillage à main` |
| `produits.categorie` | `Outillage electroportatif` | `Outillage électroportatif` |
| `produits.categorie` | `Protection electrique` | `Protection électrique` |
| `produits.categorie` | `Eclairage` | `Éclairage` |

Vérifiées exactes et à ne pas toucher : `commandes.statut`
(`annulee`, `en_attente`, `expediee`, `livree`, `preparee`, sans accent en base),
`stocks.entrepot` (`LILLE`, `LYON`, `NANTES`), `clients.segment`
(`PME`, `artisan`, `collectivité`, `grand compte`, accent présent et correct),
plage `date_commande` (`2025-09-04` à `2026-08-19`).

---

## C. Corrections perdues lors d'une annulation

| Id | Travail | Fichier concerné | Phase | État | Bloque quoi |
| --- | --- | --- | --- | --- | --- |
| C1 | Ancienne nomenclature `get_product` / `get_stock` / `get_order_status`. 13 occurrences relevées à 15h05, **1 subsiste** au moment d'écrire | `docs/conception/02_tools_text2sql.md` l.360 | Conception | Fait, 0 occurrence restante hors table de réconciliation | Lot 4, nom des tools figés |
| C2 | `NOT_FOUND` absent du tableau des codes normalisés, qui en liste 7 | `docs/conception/03_matrice_acces.md` §4.1, l.204 à l.212 | Conception | Fait, plus une colonne « Accompagne » distinguant refus et non-refus | Lot 5, contrat de refus, et test SQL-08 |
| C3 | Note de relecture devenue fausse : elle demande de corriger un diagramme déjà corrigé | `docs/soutenance_schemas.md` l.185 à l.187 | Conception | Fait, note de relecture supprimee avec la refonte de 03 | Rien, mais induit en erreur |

### C1, état exact

Le catalogue arrêté au chantier 3 (`03_matrice_acces.md` l.20 à l.29) retient
`check_stock` et `order_status`, et **absorbe `get_product`** dans
`ask_database` + `get_schema`. Le diagramme de la vue d'ensemble de 02 et le
tableau des tools figés ont été repris pendant ce relevé. Reste la ligne SQL-02
du tableau de correspondance avec le jeu d'éval, colonne « tool », qui porte
encore `get_stock / SQL`. À lire `check_stock / ask_database`.

Occurrence hors périmètre de 02, à traiter avec : `CLAUDE.md` §5 portait la même
ancienne nomenclature ; elle a été corrigée dans l'arbre de travail pendant ce
relevé, non commitée.

### C2, pourquoi la ligne manque à tort

Le tableau des codes mélange déjà deux natures : `UNAUTHORIZED_TOOL`,
`FORBIDDEN_COLUMN` et `READ_ONLY_VIOLATION` sont des **refus de gouvernance**,
tandis que `OUT_OF_CORPUS`, `OUT_OF_SCHEMA` et `AMBIGUOUS` sont des **issues
non-ok qui ne sont pas des refus**. `not_found` appartient exactement à la
seconde famille et n'a aucune raison d'en être exclu. Il est déjà présent partout
ailleurs : `02` §5.3 (D26), `03` l.258 (tableau des statuts), `05` l.25 et l.30,
`PASSATION_DEV.md` §3. Le seul endroit qui l'ignore est ce tableau. Le test
d'acceptation SQL-08 (`CMD-2026-0042`, identifiant réellement absent de la base,
vérifié : 0 ligne) en dépend.

---

## S. Séparer la règle durable du relevé daté

**Critère retenu** : un élément relève de la **conception** s'il reste vrai après
remplacement du jeu de données par un autre corpus du même métier. Sinon c'est un
**relevé**, il porte une date et il doit être régénérable, jamais recopié.

Exemple pour fixer le critère. « Donner au modèle les valeurs des colonnes à
faible cardinalité » est une règle : elle survit à un changement de base. « Les
catégories sont Câblage, Distribution, EPI... » est un relevé : la liste change
avec la base. Aujourd'hui les deux vivent dans le même tableau, sans distinction,
et c'est exactement ce qui a permis à R8 de passer inaperçu.

| Id | Travail | Fichier concerné | Phase | État | Bloque quoi |
| --- | --- | --- | --- | --- | --- |
| S1 | Isoler le relevé daté dans une section identifiée comme telle | `docs/conception/01_flux_chunks.md` | Conception | Fait, volumes symbolisés en F/D/G/C, hypothèse d'échelle posée | Rien, mais R8 se reproduira |
| S2 | Idem | `docs/conception/02_tools_text2sql.md` | Conception | Fait, §1.2 sans valeurs, D27 réordonnée, profil retiré des signatures | Idem |
| S3 | Écrire un script de relevé qui produit ces valeurs depuis `data/`, au lieu de les recopier à la main | `scripts/releve_donnees.py`, à créer | Développement | Fait, `docs/releve_donnees.py`, avec un mode `--verifier` | Rien ne le bloque, réalisable tout de suite |

### Ce qui est du relevé, par fichier

| Fichier | Passage | Nature |
| --- | --- | --- |
| `01_flux_chunks.md` | Tableau des volumes, l.285 à l.292, et la phrase « comptes releves sur le corpus reel » | Relevé, vérifié conforme : 150 fiches, 80 notices, 90 sav, 80 notes |
| `01_flux_chunks.md` | §5.1, effectifs 8 / 14 / 8 des sous-ensembles de `questions_rag.jsonl` | Relevé, vérifié conforme |
| `02_tools_text2sql.md` | §1.2, tableau des énumérations en entier | Relevé, c'est la cause de R8 |
| `02_tools_text2sql.md` | §1.4, valeurs littérales des exemples few-shot | Relevé |
| `02_tools_text2sql.md` | §5.3, `CMD-2026-0042` comme identifiant absent | Relevé, vérifié : 0 ligne |
| `02_tools_text2sql.md` | Correspondance des 24 questions SQL avec les tools | Relevé, lié aux fixtures |
| `PASSATION_DEV.md` | §6, valeurs de contrôle | Relevé, **les 4 valeurs vérifiées exactes** : 27 commandes en 2026-04, 11 livrées en 2026-06, 432 245,90 EUR en mars 2026, 41 annulations depuis janvier |

### S3, ce que le script doit produire

Les énumérations à faible cardinalité, les volumes du corpus par collection, la
plage de dates, les valeurs de contrôle de `PASSATION_DEV.md` §6, et le contrôle
que `CMD-2026-0042` est bien absent. Sortie en Markdown, à réinjecter dans la
section « relevé » des documents. Le script est la garantie que R8 ne revient
pas : personne ne retape un accent à la main.

---

## M. Mesure E6 et jeux d'évaluation

| Id | Travail | Fichier concerné | Phase | État | Bloque quoi |
| --- | --- | --- | --- | --- | --- |
| M1 | Rédiger le protocole E6 : jeu, métriques, baseline contre avancé, procédure de rejeu. Le fichier fait 9 lignes et annonce lui-même « à produire » | `docs/mesure_e6.md` | Conception | Fait, protocole complet, gabarit vide assumé | **Bloque M2** : sans protocole écrit avant, la mesure n'est pas reproductible |
| M2 | Remplir le tableau de résultats chiffrés | `docs/mesure_e6.md` et `eval/results/` | Développement | À faire | Exigence E6, soutenance |
| M3 | Créer `gold_rag.jsonl` : annoter le ou les documents attendus pour les 14 questions « couverte » | `eval/gold_rag.jsonl`, à créer | Conception | Fait, 13 gold annotes, 8 exploitables, limites du corpus documentees | **Bloque M2** : sans gold, pas de Recall@k sur les couvertes |
| M4 | Créer `eval/results/` avec un `.gitkeep` ; le `.gitignore` exclut déjà son contenu (`*.json`, `*.csv`) | `eval/results/`, `.gitignore` | Développement | Fait | Rien, deux minutes, mais le lot 1 y écrit |
| M5 | Décider où vivent les résultats attendus des 24 questions SQL, que `questions_sql.jsonl` ne porte pas | `eval/attendus_sql.jsonl`, à créer | Conception | Fait, D30 : sidecar `eval/attendus_sql.jsonl`, 24 attendus rejoués | Lot 4 : sans attendu, aucun test SQL n'est automatisable |

### M3, ce que dit l'arbitrage P4

L'arbitrage P4 du 2026-08-26 décide d'annoter les gold documents des questions
« couverte » pour un E6 rigoureux, et `01_flux_chunks.md` §5.1 le confirme :
« Recall@k **si gold doc annote** ; sinon type@k (proxy) ». Le fichier n'existe
pas. En l'état, la mesure retombe sur le proxy, ce qui affaiblit la preuve
chiffrée exigée par E6 sur près de la moitié du jeu, 14 questions sur 30.

Détail relevé dans `questions_rag.jsonl` : 9 questions portent
`attendu_reference` et 13 portent `attendu_type`, pour une répartition annoncée
de 8 `reference_exacte` et 14 `couverte`. Une question « couverte » porte donc un
`attendu_reference` au lieu d'un `attendu_type`. Ce n'est pas une erreur en soi,
mais l'annotation gold doit couvrir les 14, pas les 13.

### M5, le conflit à trancher

`questions_sql.jsonl` ne contient que `id`, `type`, `profil`, `question`. Aucun
résultat attendu. Or `PASSATION_DEV.md` §7 interdit de modifier les fixtures
`eval/*.jsonl`, qui doivent rester telles quelles. Les deux contraintes ne sont
pas conciliables dans le même fichier : les attendus doivent donc vivre **à
côté**, dans un fichier joint par `id`. C'est une décision à valider par le
pilote, pas une évidence.

---

## L. Livrables nommés par le brief, absents

| Id | Travail | Fichier concerné | Phase | État | Bloque quoi |
| --- | --- | --- | --- | --- | --- |
| L1 | Client de démonstration en ligne de commande, montrant deux profils sur le même serveur | `scripts/mcp_client.py`, à créer | Développement | À faire | Démonstration de E4 en soutenance |
| L2 | Mini guide d'accès, attaché au serveur | `mcp_server/GUIDE_ACCES.md`, à créer | Conception | Fait, mcp_server/GUIDE_ACCES.md, 444 lignes | Livrable, et lisibilité du catalogue |
| L3 | Interface graphique et son lien | à définir | Développement | À faire | Livrable, statut « À TRANCHER » depuis l'origine |
| L4 | Mettre le README au niveau du catalogue arrêté | `README.md` | Conception | Fait, catalogue a 8 tools, scripts/ ajoute, avancement a jour | Vitrine du projet |

### Pourquoi L1 et L3 ne sont pas commençables

`L1` appelle des tools sur un serveur MCP : il ne peut rien démontrer avant le
lot 5. `L3` affiche les réponses de ce même serveur. Les inscrire comme « en
retard » n'aurait pas de sens ; ils sont **planifiés**, respectivement après le
lot 5 et au lot 6 du backlog de `PASSATION_DEV.md`. Le dossier `scripts/`
n'existe pas encore, ce qui est cohérent avec cet état.

### Pourquoi L2 est de la conception

Le mini guide n'est pas du code : c'est l'arbre de décision « quel tool pour quel
besoin », plus la matrice par profil. Les deux existent déjà,
`03_matrice_acces.md` §2 (descriptions orientées « quand l'utiliser », D19) et
`05_catalogue_tools.md`. Le guide est donc rédigeable **maintenant**, à environ
80 %, et ne demandera au lot 5 que l'ajout du mode de connexion réel, qui dépend
de `O1`.

### L4, écarts constatés dans le README

Le schéma d'architecture de `README.md` l.44 et l.45 ne nomme que 4 tools
(`search_docs`, `get_document`, `answer_question`, `ask_database`) sur les 8 du
catalogue arrêté : manquent `list_sources`, `get_schema`, `check_stock` et
`order_status`. La section « Structure du dépôt » ignore `scripts/`, que le brief
exige. Le tableau « État d'avancement » reste juste.

---

## O. Points non résolus

| Id | Travail | Fichier concerné | Phase | État | Bloque quoi |
| --- | --- | --- | --- | --- | --- |
| O1 | P8, mécanisme d'identité du client MCP : jeton, en-tête, ou identifiant de session | `docs/conception/03_matrice_acces.md` l.324 et l.341 | Conception | Fait, D28 et section Q6 du chantier 3 | **E4 en entier**, lot 5, et la fin de L2 |
| O2 | Vérifier si le brief fournit une ressource « Matrice d'accès » officielle | `docs/cadrage_dsi.md` | Conception | Fait, tranche : aucune matrice n'est fournie | Risque de refaire un travail déjà fourni |

### O1, l'enjeu

Toute la matrice repose sur « résoudre le profil du client ». Tant que le
mécanisme n'est pas choisi, la gouvernance est une intention : `03` l.341 le dit
lui-même, l'application dépend d'une identification fiable. C'est le seul point
ouvert qui bloque une exigence entière. Il est marqué « à trancher en dev », mais
c'est une **décision de conception** : la trancher avant d'écrire le lot 5, pas
pendant.

### O2, ce que la vérification a montré

Aucune ressource « Matrice d'accès » n'existe dans le dépôt.
`docs/cadrage_dsi.md` se déclare lui-même comme une **reconstitution** du brief
(« Si la DSI fournit le fichier officiel, le substituer à celui-ci ») et ne
mentionne **ni** `scripts/mcp_client.py`, **ni** le mini guide d'accès, **ni** le
lien vers une interface. Ces trois livrables ne sont donc traçables que par
`CLAUDE.md` §9 et par l'inventaire du pilote. Question à poser : le brief
d'origine contient-il une matrice fournie et une liste de livrables plus précise
que ce que le dépôt a conservé ? Si oui, `03_matrice_acces.md` doit être
confronté à cette matrice avant le lot 5.

---

## D. Dérives documentaires trouvées en plus de l'inventaire

Six écarts non listés dans l'inventaire de départ, tous constatés par lecture.

| Id | Travail | Fichier concerné | Phase | État | Bloque quoi |
| --- | --- | --- | --- | --- | --- |
| D1 | Le document annonce « tableaux ASCII », convention abandonnée le 2026-08-28 | `docs/conception/README.md` l.4 et l.27 | Conception | Fait | Cohérence des conventions |
| D2 | Recommande d'installer `bierner.markdown-mermaid`, extension désinstallée le 2026-08-31 et désormais listée comme indésirable | `docs/conception/README.md` l.24 et l.25 | Conception | Fait | **Casse le rendu Mermaid** de qui suit le conseil |
| D3 | « Docs en francais ; tableaux ASCII » dans les conventions de développement | `docs/PASSATION_DEV.md` l.132 | Conception | Fait | Le lot 0 repartirait sur l'ancienne convention |
| D4 | Voir L4 : schéma à 4 tools, structure sans `scripts/` | `README.md` | Conception | Fait avec L4 | Doublon assumé de L4, traiter ensemble |
| D5 | Fichier non versionné, jamais commité, statut de livrable à décider | `docs/soutenance_schemas.md` | Conception | Fait, versionne au commit 8c0b2c5 | Perte du travail si l'arbre est nettoyé |
| D6 | La matrice d'accès §4 porte encore « Statut : PROPOSÉ, à valider au chantier 3 », alors que le chantier 3 est clos depuis le 2026-08-27 | `CLAUDE.md` §4 | Conception | Fait, statut passe a VALIDE au chantier 3 | Fait douter d'une décision déjà prise |
| D7 | `schemas.html` en retard sur les `.md` : 11 schémas contre 17, contenus divergents | `docs/schemas.html` | Conception | Fait, page régénérée et générateur restauré | Le dossier montrait des schémas périmés |
| D8 | Correspondance collection vers `doc_type` ecrite nulle part : la matrice dit `fiches`, le chantier 1 dit `fiche_technique` | `docs/conception/03_matrice_acces.md` | Conception | Fait, table de correspondance ajoutee en 3.3 | La matrice etait inapplicable telle quelle |
| D9 | Le statut `error` n'avait aucun code normalise, la table en listait huit pour sept statuts | `docs/conception/03_matrice_acces.md` | Conception | Fait, `INTERNAL_ERROR` ajoute | Un client ne pouvait pas distinguer une panne |

### D2, la vraie règle

Le journal du 2026-08-31 établit que le rendu Mermaid est **intégré à VSCode**
depuis la version 1.121, et que toute extension Mermaid fait doublon avec lui, le
bloc s'affichant alors en cadre vide sans message d'erreur.
`.vscode/extensions.json` est déjà correct : `recommendations` vide, 4 extensions
en `unwantedRecommendations`. Seul `docs/conception/README.md` conseille encore
l'inverse. Un lecteur qui suit ce conseil casse son propre rendu.

---

## Ordre recommandé

L'ordre suit les dépendances, pas la gravité apparente. Trois enchaînements le
déterminent : une valeur fausse dans un document se propage dans le prompt donc
dans le SQL (R8 avant tout code SQL) ; une mesure sans protocole écrit avant
n'est pas reproductible (M1 et M3 avant M2) ; un livrable qui interroge le
serveur ne peut pas précéder le serveur (L1 et L3 après le lot 5).

### Étape 1, fermer la conception (aucune dépendance, tout est faisable aujourd'hui)

| Rang | Items | Pourquoi ici |
| ---: | --- | --- |
| 1 | R8 | Seule régression qui produise du **faux silencieux**. Un `WHERE categorie = 'Cablage'` ne lève rien et ne trouve rien. Tout ce qui suit s'appuie sur ces valeurs. |
| 2 | C1, C2 | Une ligne chacune. Elles ferment les deux contrats que le lot 4 et le lot 5 vont implémenter. |
| 3 | O1 | Le plus long à décider, et le seul qui bloque une exigence entière. Le lancer tôt : il conditionne le lot 5 et la fin de L2. |
| 4 | O2 | Une question au pilote. Posée maintenant, la réponse arrive avant qu'on ait rebâti une matrice qui existait peut-être déjà. |
| 5 | M5 | Décision, pas rédaction. Elle conditionne la forme de l'automatisation des tests SQL du lot 4. |
| 6 | M1, puis M3 | Protocole E6 d'abord, gold ensuite : le protocole dit ce qu'on annote, l'annotation le suit. Les deux doivent précéder toute mesure. |
| 7 | S1, S2 | La séparation règle / relevé est plus facile juste après R8, tant qu'on a en tête quelles lignes sont des relevés. |
| 8 | L2 | Le mini guide se rédige à partir de 03 et 05, une fois C1 et C2 fermés, donc pas avant. Laisser en attente la seule section qui dépend de O1. |
| 9 | D2 d'abord, puis D1, D3, D5, D6, L4 et D4 | Cohérence documentaire. D2 en tête du lot : c'est le seul qui casse activement quelque chose chez le lecteur. |

### Étape 2, outillage (avant d'écrire du code métier)

| Rang | Items | Pourquoi ici |
| ---: | --- | --- |
| 10 | S3 | Le script de relevé rejoue R8, S1 et S2 automatiquement. Écrit avant le lot 1, il empêche la régression de revenir. Ne dépend d'aucun serveur. |
| 11 | M4 | Créer `eval/results/`. Deux minutes, mais le lot 1 y écrit déjà. |

### Étape 3, développement (dans l'ordre du backlog de `PASSATION_DEV.md`)

| Rang | Items | Dépend de |
| ---: | --- | --- |
| 12 | M2, chiffres E6 | Lots 1 à 3 du backlog, plus M1 et M3 |
| 13 | L1, client de démonstration | Lot 5, serveur MCP, plus O1 |
| 14 | L3, interface graphique | Lot 6, donc lot 5 |

### Ce qu'il ne faut pas faire

Commencer par les livrables absents parce qu'ils sont les plus visibles. `L1` et
`L3` n'ont rien à interroger : les ouvrir maintenant produirait des maquettes à
jeter. Symétriquement, ne pas traiter R8 comme une coquille d'accent : c'est le
seul défaut du lot qui se traduise par des réponses fausses à l'exécution, sans
aucun message d'erreur.

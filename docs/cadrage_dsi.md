# Note de cadrage DSI : Sorabel Data Gateway

> Reconstitution de la note de cadrage à partir du brief du TP, pour servir de
> référence dans le dépôt. Si la DSI fournit le fichier officiel, le substituer
> à celui-ci.

## Décision

Les outils bricolés par chaque équipe (bot support cherchant mal dans les PDF,
scripts SQL tapés à la main côté commerciaux) sont **gelés**. Ils sont remplacés
par un **point d'accès unique et gouverné** : la **Sorabel Data Gateway**, un
serveur **MCP** que tous les outils internes consommeront (bot Slack du support,
IDE des devs, poste des commerciaux).

## Ce que la Gateway doit exposer

1. **Une recherche documentaire à la hauteur du corpus.** La recherche naïve
   actuelle rate les références exactes (REF-8842), confond les versions d'une
   même notice et répond à côté. Il faut un **RAG avancé** (hybride, reranking),
   avec **sources citées**.
2. **Les données en langage naturel.** Les équipes métier ne savent pas écrire de
   SQL. Il faut des tools **Text-to-SQL en lecture seule**, sûrs et transparents.
3. **Une gouvernance unique.** Chaque client n'accède qu'à ce que la **matrice
   d'accès** l'autorise, et **tout est journalisé**.

## Exigences imposées (E1–E6)

```
E1  Toute reponse documentaire cite ses sources (titre + reference + date) ;
    si le corpus ne couvre pas, l'outil le dit au lieu d'inventer.
E2  La recherche trouve aussi bien par reference exacte (REF-8842) que par
    question en langage naturel (quel disjoncteur pour du triphase ?).
E3  Tout SQL execute est lecture seule, restreint aux tables autorisees du
    profil ; la requete generee est toujours renvoyee avec le resultat.
E4  Un meme serveur MCP sert tous les clients internes ; chaque client n'accede
    qu'aux tools, collections et tables prevus par la matrice d'acces.
E5  Tout appel (autorise ou refuse) est journalise ; les colonnes sensibles
    (prix d'achat, marges) ne sortent jamais pour le profil support.
E6  Le gain de la recherche avancee sur la recherche simple est mesure et
    documente.
```

## Cadre pédagogique

Travail individuel, 6 jours maximum, démonstration de fin de phase. La conception
se mène en trois chantiers (flux documentaire + chunking ; catalogue de tools +
chemin Text-to-SQL ; matrice d'accès), chacun accompagné de son schéma.

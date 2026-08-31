# Mesure E6 — gain de la recherche avancée sur la recherche simple

> Protocole de mesure. Il est écrit **avant** l'implémentation, pour que le
> résultat ne puisse pas être choisi après coup. Exigence visée :
>
> > « Le gain de la recherche avancée sur la recherche simple est mesuré et
> > documenté. »
>
> Le brief la reprend deux fois, en test d'acceptance (« quand on la compare à la
> recherche dense initiale sur `questions_rag.jsonl`, alors le gain est mesuré et
> documenté ») et en critère de performance (« preuve chiffrée à l'appui »).
> Ce document contient le protocole et le gabarit ; les chiffres arrivent au
> lot 3.

---

## 1. Ce qui est comparé

Deux configurations, sur **le même index**. C'est la condition qui rend le gain
attribuable : si les deux branches indexaient différemment, on mesurerait la
différence d'indexation.

| | Baseline | Avancé |
| --- | --- | --- |
| Recherche | dense seule, similarité cosinus | BM25 + dense, fusion RRF |
| Court-circuit sur motif `REF-XXXX` | non | oui |
| Reranking | non | cross-encoder |
| Modèle d'embedding | identique | identique |
| Corpus, chunking, métadonnées | identiques | identiques |

La baseline n'est pas un épouvantail construit pour perdre : c'est la
« recherche dense initiale » que le brief nomme, et c'est aussi un **jalon de
développement** à part entière (lot 2a), branché avec citations et abstention
avant que l'hybride existe.

## 2. Sur quoi on mesure

`eval/questions_rag.jsonl`, 30 questions, trois populations de natures
différentes qui ne se mesurent pas de la même façon.

| Population | N | Label | Métrique | Ce que ça teste |
| --- | ---: | --- | --- | --- |
| `reference_exacte` | 8 | `attendu_reference`, label **dur** | Recall@1, Recall@3, MRR | E2, la référence exacte |
| `couverte` | 14 | `attendu_type`, label **faible** | Recall@k sur gold annoté, sinon `type@k` | E1, la pertinence |
| `hors_corpus` | 8 | aucun | taux d'abstention | E1, le refus d'inventer |

### Ce que le corpus permet, et ce qu'il ne permet pas

Relevé le 2026-08-31, vérifié par `docs/releve_donnees.py` :

| Collection | Documents | Textes distincts |
| --- | ---: | ---: |
| `fiches` | 150 | 120 |
| `notices` | 80 | **1** |
| `sav` | 90 | **2** |
| `notes` | 80 | 54 |

**Les 80 notices partagent un seul et même corps de texte**, seul l'en-tête
change. Les 90 procédures SAV en partagent un aussi. La conséquence est directe
et sévère : une question portant sur le **contenu** d'une notice ou d'une
procédure a 80 ou 90 bonnes réponses. Le Recall@k y vaut 1 pour n'importe quel
système, dense comme hybride. Ces questions ne mesurent rien.

Après annotation, les 14 questions `couverte` se répartissent ainsi :

| Sort | N | Motif |
| --- | ---: | --- |
| exploitables | 8 | le gold est identifiable, la famille ou l'ensemble est fermé |
| non discriminantes | 4 | la réponse est une constante du corpus, dupliquée à l'identique |
| non couverte | 1 | RAG-19 : « cuisson » et « plaque » n'apparaissent dans aucun des 400 fichiers, la question est étiquetée `couverte` à tort |
| déjà dotée d'une référence | 1 | RAG-09, label dur venu de la fixture |

**Le socle sémantique de la mesure est donc de 8 questions, pas de 14.** C'est
peu, et il faut le dire dans la restitution plutôt que de présenter un gain
calculé sur 22 questions dont la moitié ne discrimine pas. Les 4 questions non
discriminantes restent utiles à autre chose : elles vérifient qu'un document du
**bon type** remonte, ce qui relève d'E1 et non d'E6.

**Le point faible du protocole, énoncé plutôt que caché.** Les 14 questions
`couverte` ne portent qu'un type attendu, pas un document attendu. Sans
annotation, le Recall@k n'est calculable que sur les 8 questions
`reference_exacte`, c'est-à-dire précisément là où le court-circuit `REF` rend la
victoire de l'hybride mécanique. Le gain mesuré serait alors fabriqué par notre
propre optimisation. C'est pourquoi l'arbitrage P4 impose d'annoter le document
attendu des 14 `couverte` dans `eval/attendus_rag.jsonl`. **Sans cette
annotation, la mesure est publiable mais faible, et il faut le dire.**

## 3. Métriques

- **Recall@k**, pour k = 1, 3, 5 : la cible figure-t-elle dans les k premiers ?
- **MRR** : rang réciproque du premier résultat correct, moyenné. Mesure la
  qualité du classement, là où Recall@k ne mesure que la présence.
- **Taux d'abstention sur `hors_corpus`** : proportion de questions où le
  système répond `out_of_corpus`. Doit approcher 100 %. Une baisse de ce taux
  annule tout gain de pertinence : un système qui trouve mieux mais invente aussi
  est un moins bon système.

Ces trois métriques se lisent **ensemble**. Un gain de Recall obtenu en
abaissant le seuil d'abstention n'est pas un gain.

## 4. Conditions de reproductibilité

```
Index          construit une seule fois, partage par les deux branches
Embeddings     meme modele, meme version
k              identique dans les deux branches
Seed           fixe partout ou un aleatoire intervient
Machine        sans importance pour les rangs, notee pour les temps
```

Toute exécution écrit dans `eval/results/` un fichier daté contenant les
métriques **et** la configuration qui les a produites. Un résultat sans sa
configuration n'est pas un résultat.

## 5. Calibrage du seuil d'abstention

Le seuil `tau` porte sur le score du reranker. Il se calibre sur les deux
populations qui l'encadrent : les 14 `couverte` doivent passer au-dessus, les 8
`hors_corpus` en dessous.

La procédure : ordonner les 22 questions par score du meilleur passage, chercher
la séparation, prendre `tau` au milieu de l'intervalle. Puis **documenter la
marge**. Si les deux populations se chevauchent, il n'existe pas de seuil correct
et il faut le dire plutôt que d'en choisir un qui optimise le tableau.

Réserve : 8 questions hors corpus, c'est peu. Le seuil obtenu est indicatif et
sensible à une seule question. La sensibilité doit figurer dans les résultats.

## 6. Gabarit de résultats

À remplir au lot 3. Les cases vides sont volontaires : elles ne seront pas
comblées par une estimation.

| Métrique | Baseline dense | Avancé | Gain |
| --- | --- | --- | --- |
| Recall@1, `reference_exacte` | | | |
| Recall@3, `reference_exacte` | | | |
| MRR, `reference_exacte` | | | |
| Recall@1, `couverte` | | | |
| Recall@3, `couverte` | | | |
| MRR, `couverte` | | | |
| Abstention, `hors_corpus` | | | |

Et une lecture à écrire, pas seulement un tableau : sur quelles questions le
gain se concentre, lesquelles restent échouées dans les deux branches, et ce que
cela dit des limites.

## 7. Ce que la mesure ne dira pas

- **Elle ne porte pas sur le jeu officiel.** Les fixtures ont été reconstituées à
  partir des captures du brief (cf. `../eval/README.md`). Si le jeu officiel est
  fourni, la mesure doit être rejouée.
- **Elle ne mesure pas la qualité des réponses**, seulement celle de la
  récupération. Une bonne récupération suivie d'une mauvaise génération ne serait
  pas vue ici.
- **Elle ne couvre pas les procédures SAV ni les notes par le court-circuit
  `REF`** : ces documents ne portent pas de référence produit en métadonnée. Le
  gain sur `reference_exacte` ne s'étend donc pas à tout le corpus.
- **Elle ne dira rien de la pertinence sur les notices et les procédures SAV**,
  puisque leurs documents sont textuellement identiques entre eux. Le contraste
  entre recherche dense et lexicale ne peut s'y exprimer : les deux moteurs
  voient le même texte partout. Ce que la mesure établira vaut pour les fiches
  et les notes.

## 8. Où vivent les résultats

```
eval/results/                sorties datees, une par execution
docs/mesure_e6.md            ce protocole, plus la synthese finale
eval/attendus_rag.jsonl      annotation gold des 14 questions "couverte" (P4)
```

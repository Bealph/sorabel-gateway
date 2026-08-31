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

## 8. Où vivent les résultats

```
eval/results/                sorties datees, une par execution
docs/mesure_e6.md            ce protocole, plus la synthese finale
eval/attendus_rag.jsonl      annotation gold des 14 questions "couverte" (P4)
```

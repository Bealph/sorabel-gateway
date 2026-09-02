# Mesure E6 : gain de la recherche avancée sur la recherche simple

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

**Ablation, ajoutée le 2026-09-02.** Le tableau ci-dessus fait varier **trois**
choses à la fois : le lexical avec sa fusion, le court-circuit, le reranking. Le
gain global est donc un chiffre qu'on ne peut imputer à rien. À la question du
jury « laquelle des trois a produit le gain ? », le dossier n'aurait pas de
réponse.

Le correctif est presque gratuit : c'est P3 qui l'a rendu possible en gardant les
deux index **séparés**, ce qui permet de mesurer chaque brique sans réindexer. On
mesure donc quatre configurations, et non deux :

| Configuration | Dense | BM25 + RRF | Court-circuit `REF` | Reranking |
| --- | :---: | :---: | :---: | :---: |
| **A**, baseline | oui | non | non | non |
| **B** | oui | oui | non | non |
| **C** | oui | oui | non | oui |
| **D**, avancé complet | oui | oui | oui | oui |

Le chiffre d'affiche du brief reste `A` contre `D`. Les colonnes `B` et `C`
disent d'où il vient. C'est ce qui transforme un chiffre en démonstration.

## 2. Sur quoi on mesure

`eval/questions_rag.jsonl`, 30 questions, trois populations de natures
différentes qui ne se mesurent pas de la même façon.

| Population | N | Label | Métrique | Ce que ça teste |
| --- | ---: | --- | --- | --- |
| `reference_exacte` | 8 | `attendu_reference`, label **dur** | Recall@1, Recall@3, MRR | E2, la référence exacte |
| `couverte` | 14 | `attendu_type`, label **faible** | Recall@k sur gold annoté, sinon `type@k` | E1, la pertinence |
| `hors_corpus` | 8 | aucun | taux d'abstention | E1, le refus d'inventer |

### Ce que le corpus permet, et ce qu'il ne permet pas

Relevé le 2026-09-02, vérifié par `docs/releve_donnees.py` :

| Collection | Documents | Textes distincts |
| --- | ---: | ---: |
| `fiches` | 150 | 120 |
| `notices` | 80 | **1** |
| `sav` | 90 | **1** |
| `notes` | 80 | 54 |

Ce tableau annonçait **2** textes distincts pour `sav` jusqu'au 2026-09-02. Le
relevé comptait en réalité le littéral `Version 1.0` contre `Version 2.0`, que
son neutraliseur ne retirait pas. Le défaut du jeu est donc **plus sévère** que ce
document ne l'écrivait, et un chiffre qui minimise une faiblesse est ce qui se
paie le plus cher en soutenance. Le neutraliseur a été corrigé.

Le titre est le seul signal qui distingue ces 170 fichiers. C'est ce qui rend la
règle du report d'en-tête dans chaque chunk (chantier 1, section 2.1) non pas un
détail d'implémentation, mais la **condition de possibilité** de cette mesure :
sans elle, le socle exploitable tombe de 8 questions à 2.

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
populations qui l'encadrent : les `couverte` doivent passer au-dessus, les
`hors_corpus` en dessous.

**Correction du 2026-09-02 : RAG-19 change de camp.** Ce document prescrivait
« les 14 `couverte` au-dessus, les 8 `hors_corpus` en dessous ». Or l'annotation
de `eval/attendus_rag.jsonl` classe RAG-19 en `certitude: nulle` avec la consigne
de la traiter comme hors corpus, ce que la vérification confirme : « cuisson » et
« plaque » ont **zéro occurrence sur les 400 fichiers**. Laisser RAG-19 dans la
population « au-dessus » tirerait le plancher vers le bas, donc `tau` vers le
bas, donc l'abstention à la baisse, et l'on retomberait exactement dans ce que la
section 3 interdit : un gain de rappel payé par une abstention perdue. Sur huit
questions, une abstention vaut 12,5 points.

Les populations de calibrage sont donc **13 `couverte` et 9 `hors_corpus`**, et
non 14 contre 8. La fixture `eval/questions_rag.jsonl` n'est pas modifiée, elle
est fournie ; c'est le protocole qui s'aligne sur l'annotation.

La procédure : ordonner les 22 questions par score du meilleur passage, chercher
la séparation, prendre `tau` au milieu de l'intervalle. Puis **documenter la
marge**. Si les deux populations se chevauchent, il n'existe pas de seuil correct
et il faut le dire plutôt que d'en choisir un qui optimise le tableau.

Réserve : 9 questions hors corpus, c'est peu. Le seuil obtenu est indicatif et
sensible à une seule question. La sensibilité doit figurer dans les résultats.

**L'abstention ne se compare pas entre les deux branches.** `tau` porte sur le
score du reranker, et la baseline n'a pas de reranker. Forger pour elle un second
seuil sur la similarité cosinus reviendrait à choisir le résultat : un seuil bas
la fait inventer sur les 9 `hors_corpus` et donne 100 points de gain à l'avancé,
un seuil haut la fait s'abstenir partout et lui coûte son rappel. Le chiffre
publié serait une conséquence de ce choix, exactement ce que ce protocole existe
pour empêcher.

La ligne « Abstention » du gabarit ne porte donc **que** sur la branche avancée,
et se lit comme une garantie d'E1, pas comme un gain d'E6.

## 6. Gabarit de résultats

À remplir au lot 3. Les cases vides sont volontaires : elles ne seront pas
comblées par une estimation.

**Recall@k porte sur des DOCUMENTS, pas sur des chunks.** Une notice fait quatre
chunks : à k = 3, une liste de chunks peut être remplie par un seul document, et
le chiffre ne voudrait plus rien dire. On déduplique par `doc_id` avant de
compter. Un `gold_alternatifs` de `eval/attendus_rag.jsonl` compte comme un
succès.

| Métrique, sur documents | A, dense | B, +hybride | C, +rerank | D, complet | Gain D sur A |
| --- | --- | --- | --- | --- | --- |
| Recall@1, `reference_exacte` | | | | | |
| Recall@3, `reference_exacte` | | | | | |
| Recall@5, `reference_exacte` | | | | | |
| MRR, `reference_exacte` | | | | | |
| Recall@1, `couverte` | | | | | |
| Recall@3, `couverte` | | | | | |
| Recall@5, `couverte` | | | | | |
| MRR, `couverte` | | | | | |

| Garantie E1, branche avancée seule | Valeur |
| --- | --- |
| Abstention sur les 9 `hors_corpus` | |

**Chaque taux se publie avec son intervalle de confiance.** Sur huit questions,
une seule qui bascule vaut 12,5 points, et les intervalles de Wilson à 95 % de
6/8 et de 4/8 se recouvrent entièrement. Un « +25 points » annoncé sans intervalle
sur un jeu de cette taille ne résiste pas à une question de jury. Le test approprié
pour comparer deux systèmes sur les mêmes questions est celui de McNemar : sur huit
paires, il faut au moins cinq bascules dans le même sens, et aucune dans l'autre,
pour descendre sous 5 % de risque.

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

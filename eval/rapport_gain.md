<!-- GENERE par `python -m retrieval.rapport`. Ne pas editer a la main. -->

# Mesure E6 : gain de la recherche avancée sur la recherche simple

> Rapport **généré** le 2026-09-02 depuis `eval/questions_rag.jsonl` et `eval/attendus_rag.jsonl`.
> Le protocole est dans `docs/mesure_e6.md`, écrit avant l'implémentation.

---

## 1. Ce qui est comparé

Quatre configurations, et non deux. Comparer seulement « dense » à « avancé » ferait varier trois choses à la fois, et le gain global ne serait imputable à rien.

| Clé | Dense | BM25 + RRF | Reranking | Court-circuit `REF` |
| --- | :---: | :---: | :---: | :---: |
| **A**, baseline, recherche dense simple | oui | non | non | non |
| **B** | oui | oui | non | non |
| **C** | oui | oui | oui | non |
| **D**, recherche hybride complète | oui | oui | oui | oui |

À partir de **B**, la recherche est **hybride** : le lexical et le dense interrogent le corpus en parallèle, et leurs deux classements sont fusionnés par RRF, sur les rangs et non sur les scores. C'est cette recherche hybride que le brief demande de comparer à la recherche dense initiale.

Corpus indexé : 910 chunks issus de 400 documents, modèle `intfloat/multilingual-e5-small`, 384 dimensions.

**Recall@k porte sur des documents, pas sur des chunks.** Une notice fait quatre chunks : à k = 3, une liste de chunks pourrait être remplie par un seul document. Un `gold_alternatifs` de l'annotation compte comme un succès.

---

## 2. Résultats

### Population `reference_exacte` : 8 questions notables, 0 exclues

| Configuration | Recall@1 | Recall@3 | Recall@5 | MRR |
| --- | ---: | ---: | ---: | ---: |
| **A** dense seul | 0.875 | 0.875 | 0.875 | 0.875 |
| **B** + BM25 et fusion RRF | 0.875 | 1.000 | 1.000 | 0.917 |
| **C** + reranking | 1.000 | 1.000 | 1.000 | 1.000 |
| **D** + court-circuit REF | 1.000 | 1.000 | 1.000 | 1.000 |

**Ce que ce gain vaut statistiquement**, sur Recall@1, A contre D :

- A : 7/8 = 0.875, intervalle de confiance à 95 % [0.53 ; 0.98]
- D : 8/8 = 1.000, intervalle de confiance à 95 % [0.68 ; 1.00]
- questions qui basculent en faveur de D : **1**, en faveur de A : **0**
- test de McNemar exact, unilatéral : **p = 0.500**

Les intervalles se recouvrent et p reste au-dessus de 0,05 : **ce gain n'est pas distinguable du bruit** sur un jeu de cette taille.

### Population `couverte` : 9 questions notables, 4 exclues

| Configuration | Recall@1 | Recall@3 | Recall@5 | MRR |
| --- | ---: | ---: | ---: | ---: |
| **A** dense seul | 0.778 | 0.889 | 1.000 | 0.861 |
| **B** + BM25 et fusion RRF | 0.889 | 1.000 | 1.000 | 0.926 |
| **C** + reranking | 1.000 | 1.000 | 1.000 | 1.000 |
| **D** + court-circuit REF | 1.000 | 1.000 | 1.000 | 1.000 |

**Ce que ce gain vaut statistiquement**, sur Recall@1, A contre D :

- A : 7/9 = 0.778, intervalle de confiance à 95 % [0.45 ; 0.94]
- D : 9/9 = 1.000, intervalle de confiance à 95 % [0.70 ; 1.00]
- questions qui basculent en faveur de D : **2**, en faveur de A : **0**
- test de McNemar exact, unilatéral : **p = 0.250**

Les intervalles se recouvrent et p reste au-dessus de 0,05 : **ce gain n'est pas distinguable du bruit** sur un jeu de cette taille.

---

## 3. De bout en bout : ce qu'un client reçoit

Seuil d'abstention activé. Une question `couverte` doit recevoir une réponse sourcée, une question hors corpus doit recevoir une abstention.

| Population | A, dense simple | D, hybride complète |
| --- | :---: | :---: |
| `reference_exacte` | 3/8 | 8/8 |
| `couverte` | 13/13 | 11/13 |
| `hors_corpus` | 9/9 | 9/9 |
| **total** | **25/30** | **28/30** |

**E1 tenue dans les deux configurations** : aucune question hors corpus ne reçoit de réponse. A : oui. D : oui.

Les deux échecs de D sont RAG-13 et RAG-16, les deux questions dont la réponse est une constante du corpus. Elles reçoivent une abstention à tort. Abaisser le seuil pour les récupérer ferait répondre deux questions hors corpus : le rappel se paierait en E1, ce que le protocole interdit.

---

## 4. Ce que la mesure dit, et ce qu'elle ne dit pas

**Le gain existe sur toutes les métriques.** Il va dans le bon sens à chaque étage, et aucune brique ne dégrade le résultat.

**Il n'est pas statistiquement démontrable sur ce jeu.** Les effectifs notables sont de 8 et 9 questions : une seule qui bascule vaut 11 à 12 points de pourcentage. Pour descendre sous 5 % avec le test de McNemar, il faudrait au moins cinq bascules dans le même sens et aucune dans l'autre. Nous en avons une ou deux.

**Le gain sur `reference_exacte` est en partie fabriqué par notre propre optimisation.** Le court-circuit sur référence est un filtre déterministe que nous avons ajouté : il ne peut pas se tromper. Il faut le présenter comme une **garantie d'E2**, jamais comme une mesure de qualité de recherche.

**Le corpus borne ce qui est mesurable.** Sans leur titre, les 80 notices partagent quatre textes distincts, et les 90 procédures SAV aussi. Quatre questions `couverte` sur treize portent sur un contenu dupliqué à l'identique : elles ont autant de bonnes réponses qu'il y a de documents, et sont exclues du rappel plutôt que comptées comme des échecs, ce qui diluerait les deux branches à l'identique.

**Une question de la fixture est mal étiquetée.** RAG-19 est marquée `couverte` ; « cuisson » et « plaque » n'apparaissent dans aucun des 400 fichiers. Le protocole la traite comme `hors_corpus`, et la fixture n'est pas modifiée.

---

## 5. Reproductibilité

La mesure a été rendue reproductible après un défaut trouvé le 2026-09-02 : la même requête rendait des voisins différents d'un processus à l'autre, alors que le vecteur de requête était identique au bit près. La cause était la recherche approchée HNSW, sur un corpus où les quasi ex æquo sont la règle. Deux corrections : `hnsw:search_ef` porté à 512, ce qui rend la recherche quasi exacte à cette échelle, et un départage déterministe par identifiant de chunk à score égal.

Vérifié : quatre exécutions dans quatre processus distincts rendent la même liste. Sans cela, un Recall@1 aurait été reproductible par chance et non par construction.

# eval/

Jeux d'évaluation et résultats.

- `questions_sql.jsonl` : 24 questions de test Text-to-SQL. Répartition :
  metier 12, ecriture 4, table_interdite 4, hors_schema 2, ambigue 2.
- `questions_rag.jsonl` : 30 questions de test RAG. Répartition :
  reference_exacte 8, couverte 14, hors_corpus 8.
- `results/` : sorties d'évaluation (dont la mesure E6).

Note : ces deux fichiers ont été reconstitués fidèlement à partir des captures
du brief (JSON validé, identifiants uniques, références présentes dans le
corpus). Si le cours fournit les fichiers officiels, les substituer tels quels.

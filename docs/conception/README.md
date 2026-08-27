# Dossier de conception — Sorabel Data Gateway

Vue d'ensemble puis trois chantiers, chacun traité par questions avec ses schémas
(tableaux ASCII + Mermaid). État : conception terminée.

## Documents

```
+-------------------------+-------------------------------------------+---------+
| Document                | Contenu                                   | Statut  |
+-------------------------+-------------------------------------------+---------+
| 00_architecture.md      | Vue d'ensemble (schema global, blocs de   | Fait    |
|                         | la Gateway, ingestion, couverture E1-E6)  |         |
| 01_flux_chunks.md       | Chantier 1 : normalisation, versions,     | Fait    |
|                         | chunking, hybride + rerank, E1, E6        |         |
| 02_tools_text2sql.md    | Chantier 2 : prompt, lecture seule multi- | Fait    |
|                         | couches, perimetre profil, tools figes,   |         |
|                         | ambigu/hors schema                        |         |
| 03_matrice_acces.md     | Chantier 3 : catalogue, matrice 4 plans,  | Fait    |
|                         | refus type, journalisation, erreurs client|         |
| 04_sequences.md         | Diagrammes de sequence (vue comportement.)| Fait    |
|                         | : answer_question, ask_database, refus E4 |         |
|                         | E5, ecriture E3                           |         |
| 05_catalogue_tools.md   | Catalogue MCP consolide : nom, entrees,   | Fait    |
|                         | sorties, garanties, acces par profil      |         |
+-------------------------+-------------------------------------------+---------+
Modele de donnees Document/Chunk : dans 01_flux_chunks.md (section 2.4).
Voir aussi : ../analyse_donnees.md (donnees) et ../mesure_e6.md (protocole E6).
Vues rendues : ../schemas.html (8 schemas rendus : flux complet, architecture,
modele Document/Chunk, et 5 sequences ; ouvrable au navigateur, Mermaid embarque
donc hors ligne).

Visualiser les diagrammes Mermaid des .md :
- Le plus simple : ouvrir ../schemas.html dans un navigateur (aucune installation).
- Dans VSCode : installer l'extension bierner.markdown-mermaid, puis Ctrl+Shift+V
  (Open Preview). Le projet la recommande via .vscode/extensions.json.
- Sur GitHub : Mermaid est rendu nativement dans les .md.
Les tableaux ASCII sont volontairement en texte monospace et s'affichent
identiquement partout.
```

## Carte de couverture des exigences DSI

```
+-----+-----------------------------------------------+------------------------------+
| Ex. | Reponse de conception                          | Ou                           |
+-----+-----------------------------------------------+------------------------------+
| E1  | Reponse ancree + sources (titre/ref/date) ;   | 01 (Q4), 03 (Q5)             |
|     | abstention par seuil si non couvert           |                              |
| E2  | Reference exacte (BM25 + court-circuit REF) + | 01 (Q2/Q3)                   |
|     | langage naturel (dense) ; hybride RRF         |                              |
| E3  | SQL lecture seule (connexion RO + AST +       | 02 (Q1/Q2)                   |
|     | LIMIT) ; requete renvoyee (transparence)      |                              |
| E4  | Un serveur MCP ; chaque profil borne aux      | 03 (Q1/Q3), 00              |
|     | tools/collections/tables                      |                              |
| E5  | Journal de tout appel ; colonnes sensibles    | 02 (Q3), 03 (Q4)             |
|     | jamais pour le support                        |                              |
| E6  | Baseline dense vs avance ; Recall@k, MRR ;    | 01 (Q5), ../mesure_e6.md     |
|     | gold annotes ; abstention sur hors_corpus     |                              |
+-----+-----------------------------------------------+------------------------------+
```

## Décisions verrouillées (rappel)

```
Versions      : indexer toutes + is_latest, citer la plus recente
Stack RAG     : bge-m3 (embeddings) + bge-reranker-v2-m3 ; Chroma + BM25 applicatif
Text-to-SQL   : LLM local (coder instruct) ; defense en profondeur 6 couches
Catalogue     : 8 tools (answer_question, search_docs, get_document, list_sources,
                ask_database, get_schema, check_stock, order_status)
Gouvernance   : matrice declarative deny-by-default, appliquee gateway + tool
Journalisation: JSONL, tout appel, sans valeurs sensibles
Reste ouvert  : P8 (mecanisme d'identite du client MCP), a cadrer au developpement
```

# Dossier de conception — Sorabel Data Gateway

Vue d'ensemble puis trois chantiers, chacun traité par questions avec ses schémas
(tableaux Markdown + schémas Mermaid). État : conception terminée.

## Documents

| Document | Contenu | Statut |
| --- | --- | --- |
| 00_architecture.md | Vue d'ensemble (schema global, blocs de la Gateway, ingestion, couverture E1-E6) | Fait |
| 01_flux_chunks.md | Chantier 1 : normalisation, versions, chunking, hybride + rerank, E1, E6 | Fait |
| 02_tools_text2sql.md | Chantier 2 : prompt, lecture seule multi-couches, perimetre profil, tools figes, ambigu/hors schema | Fait |
| 03_matrice_acces.md | Chantier 3 : catalogue, matrice 4 plans, refus type, journalisation, erreurs client | Fait |
| 04_sequences.md | Diagrammes de sequence (vue comportement.) : answer_question, ask_database, refus E4 E5, ecriture E3 | Fait |
| 05_catalogue_tools.md | Catalogue MCP consolide : nom, entrees, sorties, garanties, acces par profil | Fait |
| 06_choix_stockage.md | Chantier 6 : les trois besoins de stockage, le type retenu pour chacun, les candidats ecartes et leur motif | Fait |

Modele de donnees Document/Chunk : dans 01_flux_chunks.md (section 2.4).
Voir aussi : ../analyse_donnees.md (donnees) et ../mesure_e6.md (protocole E6).
Vues rendues : ../schemas.html, **17 schemas**, page autonome a ouvrir dans un
navigateur (Mermaid embarque, aucune installation). Elle est GENEREE par
`python docs/build_schemas.py` depuis les blocs mermaid des .md, et ne peut donc
plus etre en retard sur eux. `--verifier` signale une page perimee.
Visualiser les diagrammes Mermaid des .md :
- Le plus simple : ouvrir ../schemas.html dans un navigateur (aucune installation).
- Dans VSCode : Ctrl+Shift+V. Le rendu Mermaid est NATIF depuis la version
  1.121, via l'extension livree mermaid-markdown-features. N'installer AUCUNE
  extension Mermaid : elle ferait doublon et le diagramme resterait vide.
- Sur GitHub : Mermaid est rendu nativement dans les .md.
Les tableaux sont en Markdown depuis le 2026-08-28 : ils se rendent comme de
vraies tables dans la prévisualisation et sur GitHub.

## Carte de couverture des exigences DSI

| Ex. | Reponse de conception | Ou |
| --- | --- | --- |
| E1 | Reponse ancree + sources (titre/ref/date) ; abstention par seuil si non couvert | 01 (Q4), 03 (Q5) |
| E2 | Reference exacte (BM25 + court-circuit REF) + langage naturel (dense) ; hybride RRF | 01 (Q2/Q3) |
| E3 | SQL lecture seule (connexion RO + AST + LIMIT) ; requete renvoyee (transparence) | 02 (Q1/Q2) |
| E4 | Un serveur MCP ; chaque profil borne aux tools/collections/tables | 03 (Q1/Q3), 00 |
| E5 | Journal de tout appel ; colonnes sensibles jamais pour le support | 02 (Q3), 03 (Q4) |
| E6 | Baseline dense vs avance ; Recall@k, MRR ; gold annotes ; abstention sur hors_corpus | 01 (Q5), ../mesure_e6.md |

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

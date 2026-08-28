# Catalogue des tools MCP (vue consolidée)

> Vue de référence du catalogue exposé par la Gateway : nom, entrées, sorties,
> garanties. Sert de base au serveur MCP et au mini guide d'accès (livrable).
> Consolide les chantiers 1 (RAG), 2 (Text-to-SQL) et 3 (matrice d'accès).
> Toutes les entrées incluent implicitement l'identité du client (donc son
> profil). Toute sortie est typée par `status` ; tout appel est journalisé (E5).

## Famille RAG

| Tool | Entrees | Sorties | Garanties / comportement |
| --- | --- | --- | --- |
| answer_question | question (texte) | status, answer, | reponse ancree UNIQUEMENT sur |
| (RAG complet) |  | sources[] {title, ref, version, date, url} | le contexte ; sources citees (E1) ; abstention si score &lt; seuil ; collections bornees au profil (E4) |
| search_docs | query (texte), | status, hits[] {passage, | recherche hybride (BM25 + |
| (brique) | k optionnel | score, doc_id, ref, version, section} | dense) + rerank ; AUCUNE generation ; collections bornees au profil |
| get_document | doc_id (ou ref + | status, document {texte, | renvoie la version demandee |
| (brique) | version) | metadonnees} | (defaut : is_latest) ; borne aux collections autorisees |
| list_sources | filtre optionnel | status, sources[] {ref, | decouverte du corpus ; borne |
| (brique) | (doc_type, ref) | doc_type, versions[], date} | aux collections du profil ; pas de contenu, juste l'index |

## Famille SQL

| Tool | Entrees | Sorties | Garanties / comportement |
| --- | --- | --- | --- |
| ask_database | question (texte) | status, rows[], sql | lecture seule (connexion RO + |
| (generatif) |  | (requete generee) OU refus {status, code} | AST SELECT-only) ; perimetre tables/colonnes du profil (E5) ; LIMIT ; SQL toujours renvoye (E3) ; refus type |
| get_schema | (identite -> profil) | status, schema {tables, | AUCUNE donnee renvoyee ; |
| (aide) |  | colonnes autorisees} | schema filtre au profil (support : sans colonnes sensibles) ; aide a la formulation |
| check_stock | ref | status, stock[] {entrepot, | requete parametree |
| (fige) |  | quantite, seuil_reappro} | deterministe ; lecture seule ; pas de generation LLM |
| order_status | commande_id | status, {statut, date, | requete parametree ; lecture |
| (fige) |  | montant_ht} | seule ; pas de colonne sensible |

## Garanties transverses (tous les tools)

```
- Sortie typee par status : ok / out_of_corpus / out_of_schema / not_found /
  clarify / refused / error. Une abstention, un not_found ou un refus n'est
  JAMAIS rendu comme reponse. (not_found : entite par identifiant precis
  introuvable, requete pourtant valide.)
- Autorisation appliquee a deux niveaux : gateway (tool) + tool (ressources).
- Journalisation JSONL de tout appel (autorise + refuse), sans valeurs sensibles,
  avec le SQL genere le cas echeant et les ressources touchees (E5).
- Codes de refus normalises : UNAUTHORIZED_TOOL, UNAUTHORIZED_COLLECTION,
  FORBIDDEN_COLUMN, READ_ONLY_VIOLATION, OUT_OF_SCHEMA, OUT_OF_CORPUS, AMBIGUOUS.
```

## Accès par profil (rappel de la matrice, chantier 3)

| Tool | support | commercial | dev/IDE |
| --- | --- | --- | --- |
| answer_question | oui | oui | oui |
| search_docs | - | - | oui |
| get_document | - | - | oui |
| list_sources | - | - | oui |
| ask_database | oui\* | oui | oui |
| get_schema | oui\* | oui | oui |
| check_stock | oui | oui | oui |
| order_status | oui | oui | oui |

* profil support : colonnes sensibles (prix_achat_ht, marge_pct, marge_ht)
  jamais renvoyees ; collection notes non accessible.

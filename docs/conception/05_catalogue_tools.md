# Catalogue des tools MCP (vue consolidée)

> Vue de référence du catalogue exposé par la Gateway : nom, entrées, sorties,
> garanties. Sert de base au serveur MCP et au mini guide d'accès (livrable).
> Consolide les chantiers 1 (RAG), 2 (Text-to-SQL) et 3 (matrice d'accès).
> **Aucun tool ne prend l'identité ni le profil en entrée.** Le profil est fixé
> au lancement du serveur (D28) et n'apparaît dans aucune signature : un profil
> passé en argument serait déclaratif, et n'importe quel appelant pourrait se
> déclarer `dev`. Les colonnes « Entrées » ci-dessous listent donc uniquement ce
> que le client transmet. Toute sortie est typée par `status` ; tout appel est
> journalisé (E5).

## Famille RAG

| Tool | Entrees | Sorties | Garanties / comportement |
| --- | --- | --- | --- |
| `answer_question` (RAG complet) | question (texte) | status, answer, sources[] {title, ref, version, date, url} | reponse ancree UNIQUEMENT sur le contexte ; sources citees (E1) ; abstention si score &lt; seuil ; collections bornees au profil (E4) |
| `search_docs` (brique) | query (texte), k optionnel | status, hits[] {passage, score, doc_id, ref, version, section} | recherche hybride (BM25 + dense) + rerank ; AUCUNE generation ; collections bornees au profil |
| `get_document` (brique) | doc_id, ou ref + version | status, document {texte, metadonnees} | renvoie la version demandee (defaut : is_latest) ; borne aux collections autorisees |
| `list_sources` (brique) | filtre optionnel (doc_type, ref) | status, sources[] {ref, doc_type, versions[], date} | decouverte du corpus ; borne aux collections du profil ; pas de contenu, juste l'index |

## Famille SQL

| Tool | Entrees | Sorties | Garanties / comportement |
| --- | --- | --- | --- |
| `ask_database` (generatif) | question (texte) | status, rows[], sql (requete generee), OU refus {status, code} | lecture seule (connexion RO + AST SELECT-only) ; perimetre tables/colonnes du profil (E5) ; LIMIT ; SQL toujours renvoye (E3) ; refus type |
| `get_schema` (aide) | *aucune* | status, schema {tables, colonnes autorisees} | AUCUNE donnee renvoyee ; schema filtre au profil (support : sans colonnes sensibles) ; aide a la formulation |
| `check_stock` (fige) | ref | status, stock[] {entrepot, quantite, seuil_reappro} | requete parametree deterministe ; lecture seule ; pas de generation LLM |
| `order_status` (fige) | order_id | status, {statut, date, montant_ht} | requete parametree ; lecture seule ; pas de colonne sensible ; id absent -> not_found |

## Garanties transverses (tous les tools)

```
- Sortie typee par status : ok / out_of_corpus / out_of_schema / not_found /
  clarify / refused / error. Une abstention, un not_found ou un refus n'est
  JAMAIS rendu comme reponse. (not_found : entite par identifiant precis
  introuvable, requete pourtant valide.)
- Autorisation appliquee a deux niveaux : gateway (tool) + tool (ressources).
- Journalisation JSONL de tout appel (autorise + refuse), sans valeurs sensibles,
  avec le SQL genere le cas echeant et les ressources touchees (E5).
- Codes normalises, les NEUF du chantier 3, section 4.1, qui fait foi :
  refus       : UNAUTHORIZED_TOOL, UNAUTHORIZED_COLLECTION, FORBIDDEN_COLUMN,
                READ_ONLY_VIOLATION
  non-refus   : OUT_OF_SCHEMA, OUT_OF_CORPUS, NOT_FOUND, AMBIGUOUS,
                INTERNAL_ERROR (accompagne status = error)
```

## Accès par profil (rappel de la matrice, chantier 3)

> **Vue.** La source de vérité est `governance/matrice.yaml` (D21) ; ce tableau
> en est une copie de lecture. Vue régénérée : `governance/matrice_lisible.md`.

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

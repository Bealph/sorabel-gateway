# Note de cadrage DSI — Sorabel Data Gateway

**Émetteur : Direction des systèmes d'information — diffusion interne.**

Les outils d'accès aux données développés en dehors de la DSI (bot de recherche
du support, scripts SQL des commerciaux) sont gelés. Ils sont remplacés par un
point d'accès unique et gouverné : la **Sorabel Data Gateway**, un serveur MCP
que tous les outils internes (bot Slack du support, IDE des développeurs, poste
des commerciaux) consommeront.

## Exigences

| # | Exigence imposée |
|---|---|
| E1 | Toute réponse documentaire **cite ses sources** (titre + référence + date) ; si le corpus ne couvre pas, l'outil **le dit** au lieu d'inventer. |
| E2 | La recherche trouve aussi bien par **référence exacte** (« REF-8842 ») que par **question en langage naturel** (« quel disjoncteur pour du triphasé ? »). |
| E3 | Tout SQL exécuté est **lecture seule**, restreint aux **tables autorisées** du profil ; la **requête générée est toujours renvoyée** avec le résultat (transparence). |
| E4 | Un **même serveur MCP** sert tous les clients internes ; chaque client n'accède qu'aux tools, collections et tables prévus par la **matrice d'accès**. |
| E5 | **Tout appel** (autorisé ou refusé) est **journalisé** ; les colonnes sensibles (prix d'achat, marges) ne sortent **jamais** pour le profil support. |
| E6 | Le **gain** de la recherche avancée sur la recherche simple est **mesuré et documenté**. |

## Matrice d'accès initiale

Deux profils clients au lancement. Toute évolution de la matrice passe par la DSI.

| Profil | Tools autorisés | Collections documentaires | Tables SQL | Colonnes interdites |
|---|---|---|---|---|
| `support` | answer_question, search_docs, get_document, list_sources, ask_database, check_stock, order_status | fiches_techniques, notices, procedures_sav | produits, stocks, commandes, clients | produits.prix_achat_ht, produits.marge_pct, ventes.* (table non accessible) |
| `commercial` | answer_question, search_docs, get_document, list_sources, ask_database, get_schema, check_stock, order_status | fiches_techniques, notices, procedures_sav, notes_internes | produits, stocks, commandes, clients, ventes | — |

Notes :

- Les **notes internes** (politique tarifaire, comptes rendus achats) sont
  réservées au profil `commercial`.
- Le profil `support` ne voit **jamais** un prix d'achat ni une marge, quelle
  que soit la formulation de la demande (E5).
- Un appel refusé renvoie un **message clair et un code de refus**, et figure
  au journal au même titre qu'un appel autorisé (E5).

## Journalisation

Chaque appel à la gateway produit une entrée horodatée : profil, tool,
arguments, issue (autorisé/refusé/erreur), message. Le journal est consultable
par la DSI et sert de preuve lors des revues de conformité.

## Contrat d'intégration

Pour que tous les clients internes (et la suite d'acceptance, qui joue le rôle
d'un client) consomment la gateway de la même façon, la DSI fixe le contrat
suivant. L'implémentation interne est libre ; ce contrat, lui, est imposé.

### Lancement du serveur

- Serveur MCP en transport **stdio**, lancé par : `python -m mcp_server.server`
- Le **profil client** du processus est lu dans la variable d'environnement
  `SORABEL_PROFILE` (`support` ou `commercial`, défaut `support`) — un
  processus serveur par client interne.
- Le **chemin du journal** est lu dans `GATEWAY_JOURNAL`
  (défaut `logs/journal.jsonl`).

### Catalogue de tools

`answer_question`, `search_docs`, `get_document`, `list_sources`,
`ask_database`, `get_schema`, `check_stock`, `order_status`.

### Enveloppe de réponse

Chaque tool renvoie un objet JSON (sérialisé en texte) :

```json
{"status": "…", "payload": {…}, "message": "…"}
```

- `status` : `ok` | `refused` | `clarification` | `hors_corpus` | `error`
- `message` : obligatoire et explicite pour tout statut autre que `ok`
- `payload` selon le tool :
  - `answer_question` → `{"answer": str, "sources": [{"titre", "reference", "date"}]}`
  - `search_docs` → `{"hits": [{"doc_id", "score", "text", "metadata": {"reference", "doc_type", "version", "date"}}]}`
    (`doc_type` : `fiche_technique` | `notice` | `procedure_sav` | `note_interne`)
  - `get_document` → `{"text": str, "metadata": {…}}`
  - `list_sources` → `{"sources": [{"doc_id", "titre", "reference", "version", "date", "doc_type"}]}`
  - `ask_database` → `{"sql": str, "columns": [str], "rows": [[…]]}`
  - `get_schema` → `{"schema": str}`
  - `check_stock` / `order_status` → même forme que `ask_database`

### Journal

Fichier **JSONL**, une entrée par appel (autorisé comme refusé) :

```json
{"timestamp": "…", "profile": "…", "tool": "…", "arguments": {…}, "status": "…", "message": "…"}
```

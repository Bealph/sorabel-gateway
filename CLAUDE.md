# CLAUDE.md — Sorabel Data Gateway

> Fichier de mémoire de projet, lu automatiquement par Claude Code à chaque
> session ouverte dans ce dossier. C'est la source de vérité qui assure la
> continuité entre la phase de conception (Cloud) et la phase de dev (VSCode).
> **Le tenir à jour à la fin de chaque tâche** (voir §10, Journal).

---

## 1. Le projet en une phrase

Construire la **Sorabel Data Gateway** : un serveur **MCP** unique et gouverné,
consommé par tous les outils internes (bot Slack support, IDE des devs, poste
des commerciaux), qui expose trois briques :

1. **RAG avancé** (hybride + reranking, sources citées) sur le corpus documentaire.
2. **Text-to-SQL lecture seule** sur la base métier, sûr et transparent.
3. **Gouvernance** : matrice d'accès RBAC par profil client + journalisation de tout appel.

Il remplace les bricolages actuels (bot support qui cherche mal, scripts SQL à la main).

---

## 2. Contexte

Sorabel est un distributeur B2B de matériel électrique et d'outillage
professionnel. Son savoir vit dans deux mondes :

```
+----------------------------+        +----------------------------+
|   Corpus documentaire      |        |        Base SQL            |
|  fiches techniques,        |        |  produits, stocks,         |
|  notices, procedures SAV   |        |  commandes, ventes         |
+----------------------------+        +----------------------------+
            |                                       |
            v  RAG avance                           v  Text-to-SQL
        +-----------------------------------------------------+
        |         Sorabel Data Gateway (serveur MCP)          |
        |     gouvernance RBAC  +  journalisation             |
        +-----------------------------------------------------+
            ^                    ^                     ^
        bot Slack            IDE devs             poste commerciaux
        (support)                                  (commercial)
```

Problèmes constatés : la recherche naïve rate les références exactes (REF-8842),
confond les versions d'une notice, répond à côté ; le SQL manuel est dangereux
(une commerciale a verrouillé la base un vendredi soir) ; les réponses divergent
d'une équipe à l'autre. La DSI gèle les bricolages et impose un point d'accès
unique et gouverné.

---

## 3. Les 6 exigences DSI (contrat — non négociable)

```
+-----+-------------------------------------------------------------------------------+
| Id  | Exigence                                                                      |
+-----+-------------------------------------------------------------------------------+
| E1  | Toute reponse documentaire cite ses sources (titre + reference + date).       |
|     | Si le corpus ne couvre pas -> l'outil le dit, il n'invente jamais.            |
| E2  | La recherche trouve aussi bien par reference exacte (REF-8842) que par        |
|     | question en langage naturel (quel disjoncteur pour du triphase ?).            |
| E3  | Tout SQL execute est lecture seule, restreint aux tables autorisees du        |
|     | profil ; la requete generee est toujours renvoyee avec le resultat.           |
| E4  | Un meme serveur MCP sert tous les clients ; chaque client n'accede qu'aux      |
|     | tools, collections et tables prevus par la matrice d'acces.                    |
| E5  | Tout appel (autorise ou refuse) est journalise ; les colonnes sensibles        |
|     | (prix d'achat, marges) ne sortent jamais pour le profil support.               |
| E6  | Le gain de la recherche avancee sur la recherche simple est mesure et          |
|     | documente (preuve chiffree).                                                   |
+-----+-------------------------------------------------------------------------------+
```

---

## 4. Clients & profils d'accès (matrice — à finaliser en conception, chantier 3)

```
+-------------+------------------+---------------------------+--------------------------+
| Profil      | Client type      | RAG (collections)         | SQL (tables / colonnes)  |
+-------------+------------------+---------------------------+--------------------------+
| support     | bot Slack SAV    | fiches, notices, SAV      | metier SANS prix d'achat |
|             |                  |                           | ni marges (E5)           |
| commercial  | poste commercial | fiches, notices, SAV      | produits, stocks,        |
|             |                  |                           | commandes, ventes        |
| dev         | IDE developpeurs | toutes collections        | lecture large            |
+-------------+------------------+---------------------------+--------------------------+
```

Statut : **PROPOSÉ** (à valider et détailler au chantier 3 : liste exacte des
tools, collections, tables et colonnes par profil).

---

## 5. Architecture — décisions

Chaque décision porte un statut : **VALIDÉ** (acté avec le pilote) /
**PROPOSÉ** (recommandation de l'expert, en attente d'accord) /
**À TRANCHER** (option ouverte).

```
+------------------------------+--------------------------------------------+-----------+
| Sujet                        | Orientation                                | Statut    |
+------------------------------+--------------------------------------------+-----------+
| Langage / runtime            | Python                                     | PROPOSE   |
| Framework MCP                | FastMCP (SDK Python officiel)              | PROPOSE   |
| Base SQL                     | SQLite (fichier fourni), acces read-only   | PROPOSE   |
| RAG - embeddings             | BAAI/bge-m3 (multilingue, local)           | VALIDE    |
| RAG - recherche              | Hybride : BM25 + dense, court-circuit REF  | VALIDE    |
| RAG - fusion                 | RRF (Reciprocal Rank Fusion, k=60)         | VALIDE    |
| RAG - reranking              | Cross-encoder BAAI/bge-reranker-v2-m3      | VALIDE    |
| RAG - versions               | Indexer toutes, is_latest, citer la plus   | VALIDE    |
|                              | recente ; ancienne sur demande explicite   |           |
| Store vectoriel              | Chroma (dense) + bm25 applicatif           | VALIDE    |
| RAG - eval E6                | Gold doc annotes pour les "couverte"       | VALIDE    |
| Text-to-SQL - securite       | Defense en profondeur : connexion RO +     | VALIDE    |
|                              | AST (sqlglot) SELECT-only + perimetre      |           |
|                              | profil + LIMIT/timeout + SQL renvoye + log |           |
| Text-to-SQL - catalogue      | ask_database (generique) + tools figes     | VALIDE    |
|                              | get_product/get_stock/get_order_status     |           |
| Text-to-SQL - sortie         | structuree {SQL | CLARIFY | HORS_SCHEMA}    | VALIDE    |
| Text-to-SQL - LLM generation | Local coder instruct (ex. Qwen2.5-Coder),  | VALIDE    |
|                              | repli mesure sur SQL-01..12 avant API      |           |
| Gouvernance / RBAC           | Matrice declarative (config), appliquee aux| VALIDE    |
|                              | 2 niveaux : gateway (tool) + tool          |           |
|                              | (collection/table/colonne), deny-by-default|           |
| Journalisation               | JSONL de tout appel (autorise + refuse),   | VALIDE    |
|                              | sans valeurs sensibles, avec SQL + code    |           |
| Catalogue de tools           | 8 tools : answer_question, search_docs,    | VALIDE    |
|                              | get_document, list_sources, ask_database,  |           |
|                              | get_schema, check_stock, order_status      |           |
| Interface graphique          | A definir (livrable : lien vers une UI)    | A TRANCHER|
+------------------------------+--------------------------------------------+-----------+
```

Référence méthodo RBAC/MCP retenue par le pilote :
https://dev.to/deeptishuklatfy/how-to-implement-rbac-for-mcp-tools-a-practical-guide-for-engineering-teams-fhf

---

## 6. Structure du dépôt

```
sorabel-data-gateway/
├── CLAUDE.md              # ce fichier : memoire de projet
├── README.md             # vitrine du projet
├── .gitignore
├── pyproject.toml        # metadata + dependances (a valider en phase dev)
├── docs/
│   ├── cadrage_dsi.md     # note de cadrage DSI (contexte + exigences)
│   ├── conception/        # 3 chantiers : flux+chunks / tools+text2sql / matrice
│   └── mesure_e6.md       # protocole + resultats du gain RAG (a produire)
├── mcp_server/           # serveur MCP + mini guide d'acces (livrable)
├── rag/                  # ingestion, chunking, hybride, reranking
├── text2sql/             # generation SQL lecture seule + garde-fous
├── governance/           # matrice d'acces (RBAC) + journalisation
├── eval/
│   ├── questions_sql.jsonl    # jeu d'eval SQL (a deposer/reconstruire)
│   ├── questions_rag.jsonl    # jeu d'eval RAG (a deposer/reconstruire)
│   └── results/               # sorties d'evaluation
└── data/                 # corpus documentaire + base SQL
```

---

## 7. Méthode de collaboration (règles fixées par le pilote)

```
+---+-----------------------------------------------------------------------------+
| 1 | Travail collaboratif rigoureux et exigeant. Claude = expert ; l'utilisateur |
|   | = pilote qui donne la todolist. Ne rien demarrer sans tache.                |
| 2 | Expliquer chaque concept avec peu de mots.                                  |
| 3 | Brainstormer, benchmarker, proposer, s'auto-critiquer AVANT de produire.    |
| 4 | Conception : tableaux en ASCII lisibles + schemas en Mermaid (mermaid.live).|
| 5 | README et docs de qualite, dignes d'interet.                                |
| 6 | L'utilisateur donne les taches une par une.                                 |
| 7 | Sources d'appui : modalites d'eval, livrables, criteres de perf, article    |
|   | RBAC/MCP, jeux d'eval questions_sql.jsonl / questions_rag.jsonl.            |
+---+-----------------------------------------------------------------------------+
```

---

## 8. Conventions de rédaction et de code

- Documentation en **français**.
- **Tableaux en ASCII** lisibles à l'œil ; **schémas en Mermaid**.
- Toute réponse documentaire **cite ses sources** (titre + référence + date).
- Ne jamais utiliser le caractère « tiret cadratin suivi d'espace » dans les textes.
- Posture d'expert, rigueur, zéro approximation.
- Code : lecture seule stricte côté SQL ; aucun secret en clair ; logs structurés.

---

## 9. Livrables & évaluation

**Livrables attendus :**
- Dossier de conception (flux + chunks + catalogue de tools + chemin Text-to-SQL + matrice d'accès).
- Le serveur MCP (`mcp_server/`) exposant le catalogue complet + un mini guide d'accès.
- Un lien vers une interface graphique du produit fonctionnel.

**Tests d'acceptation (doivent passer) :**
```
RAG        : question couverte -> reponse + sources ; hors corpus -> signale ;
             "REF-8842" via search_docs -> fiche en tete ; hybride vs dense mesure.
Text-to-SQL: "combien de commandes en avril ?" -> resultat + SQL renvoye ;
             "supprime les commandes de test" -> refus (lecture seule) + journalise ;
             profil support sur marges/prix d'achat -> refus (matrice) ;
             question hors schema -> refus clair, pas de SQL hallucine.
MCP        : profil autorise -> acces borne aux tools/collections/tables prevus ;
             appel non autorise -> refus clair + journalise ;
             search_docs puis get_document -> briques RAG separees ;
             session de demo -> journal contient tous les appels (autorises + refuses).
```

**Critères de performance :**
- Tous les tests d'acceptation passent (RAG, Text-to-SQL, MCP).
- Les 6 exigences E1–E6 respectées et démontrées en soutenance.
- La recherche hybride surpasse la dense simple, preuve chiffrée.
- Aucune écriture SQL ne passe ; aucune colonne sensible ne sort pour le support.
- Les choix d'architecture sont justifiés dans le dossier de conception.

---

## 10. Journal d'avancement

```
2026-08-26  Squelette du projet + CLAUDE.md poses. Acces au dossier connecte OK.
2026-08-26  Donnees deposees et analysees. Base SQL : 6 tables (clients 60,
            produits 120, stocks 312, commandes 340, ventes 993). Corpus :
            fiches (PDF), notices (PDF), sav (HTML), notes (MD), avec versioning.
            Colonnes sensibles SQL : prix_achat_ht, marge_pct, marge_ht. Notes
            politique-tarifaire / reunion-achat = sensibles cote RAG. Detail
            complet dans docs/analyse_donnees.md.
2026-08-26  Chantier de conception #1 (RAG avance) redige :
            docs/conception/01_flux_chunks.md. Decisions D1-D8.
            Arbitrages verrouillES : P1 versions = indexer toutes + is_latest
            + citer la plus recente (aligne Sorabel : docs qui vivent, ne jamais
            confondre) ; P2 stack = local bge-m3 + bge-reranker-v2-m3 ;
            P3 store = Chroma + bm25 applicatif ; P4 = annoter les gold doc des
            "couverte" pour un E6 rigoureux.
2026-08-26  Chantier de conception #2 (Text-to-SQL + tools) redige :
            docs/conception/02_tools_text2sql.md. Decisions D9-D16 (prompt =
            schema commente borne au profil + enums reelles + few-shot ; lecture
            seule en 6 couches ; AST autoritaire ; perimetre avant+apres ; pas
            de SELECT * ; routage figes/ask_database ; sortie structuree
            SQL/CLARIFY/HORS_SCHEMA ; LIMIT 200). Point ouvert P5 : LLM de
            generation (local vs API). Enums reelles relevees : statut(5),
            entrepots(LILLE/LYON/NANTES), plage 2025-09 a 2026-08.
            Mapping complet des 24 questions SQL de l'eval fourni.
            P5 verrouille : LLM de generation = LOCAL (coder instruct), repli
            mesure avant API. Decisions D9-D16 actees comme baseline conception.
            Prochaine etape : chantier #3 (matrice d'acces RBAC, consolidation
            du catalogue tool x collection x table x colonne).
2026-08-26  PAUSE. Reprise prevue demain sur le chantier #3.
2026-08-27  Chantier de conception #3 (exposition MCP + matrice) redige :
            docs/conception/03_matrice_acces.md. Nomenclature du catalogue figee
            (check_stock/order_status/get_schema/list_sources alignes).
            Decisions D17-D25 : catalogue 8 tools ; briques RAG reservees
            dev/IDE ; matrice appliquee gateway + tool ; config declarative
            deny-by-default ; notes interdites au support ; contrat de refus
            type {status, code, message} ; journal JSONL de tout appel sans
            valeurs sensibles ; sortie typee (client ne rend "reponse" que si
            status=ok). P6 verrouille : briques RAG reservees dev/IDE. P7
            verrouille : notes accessibles commercial+dev, jamais support, sans
            4e profil. P8 (identite client MCP) reste ouvert (implementation).
            CONCEPTION TERMINEE (chantiers 1-2-3).
2026-08-27  Vue d'ensemble ajoutee : docs/conception/00_architecture.md (schema
            global corrigE a partir du brouillon du pilote : Gateway ouverte,
            index + ingestion hors ligne, gouvernance par profil). Index du
            dossier de conception (conception/README.md) transforme en synthese
            avec carte de couverture E1-E6 et rappel des decisions.
2026-08-27  Ajout de docs/conception/04_sequences.md : 5 diagrammes de sequence
            (answer_question + abstention E1/E2 ; ask_database gardes E3 ; refus
            colonne sensible E5 ; refus tool E4 ; ecriture refusee E3). Index
            conception mis a jour.
2026-08-27  Ajout de docs/schemas.html : page autonome rendant les 6 schemas
            Mermaid (architecture + 5 sequences), Mermaid embarque (hors ligne),
            rendu verifie en headless (6/6 SVG). Pour visualiser les schemas
            sans extension Markdown.
2026-08-27  CORRECTIF Mermaid : les diagrammes de sequence echouaient (bombe
            "Syntax error") a cause du point-virgule ';' dans le texte des
            messages, pris pour un separateur. Remplace par des virgules dans
            04_sequences.md et schemas.html. Validation renforcee : parse de
            chaque diagramme en headless (12/12 OK, 0 "Syntax error"), au lieu
            de compter seulement les SVG (qui incluaient les SVG d'erreur).
2026-08-27  CHECK avant dev vs liste "Architecture / schema attendus" : 5 items
            requis. Combles les 2 manques : (a) catalogue MCP consolide avec
            colonnes nom/entrees/sorties/garanties -> docs/conception/
            05_catalogue_tools.md ; (b) modele de donnees Document/Chunk (visuel)
            -> 01_flux_chunks.md section 2.4. Ajout du flux complet lineaire et
            du modele au schemas.html (8 diagrammes, tous valides, 0 erreur).
            Les 5 items attendus sont couverts. PRET POUR LE DEV.
            Prochaine etape : developpement, en commencant par l'ingestion du
            corpus (chantier 1).
2026-08-27  Ecarts fermes avant dev : (a) jeux d'eval reconstitues depuis les
            captures du brief -> eval/questions_sql.jsonl (24) et
            eval/questions_rag.jsonl (30), JSON valide, ids uniques, repartition
            conforme (SQL 12/4/4/2/2, RAG 8/14/8), references presentes dans le
            corpus ; a remplacer par les fichiers officiels s'ils sont fournis.
            (b) README "Etat d'avancement" mis a jour (conception + eval = Fait).
2026-08-27  Croisement questions x sorabel.db (angle mort de la validation cloud).
            2 raffinements de conception ajoutes au chantier 2 :
            D26 resultat vide = ok/rows[] pour liste/agregat, not_found pour
            entite par identifiant precis (ex. SQL-08 CMD-2026-0042 absent, trou
            de numerotation). D27 desambiguisation : critere -> CLARIFY ; entite
            (libelle -> plusieurs ref, ex. SQL-10 = 4 disjoncteurs 40 A) ->
            reponse multiligne. Statut not_found propage a 03 (Q5) et 05.
            Fixtures .jsonl inchangees (a garder telles quelles). Faits par la
            session cloud pour eviter les conflits d'ecriture avec VSCode.
2026-08-27  Note viewer : sous VSCode, Mermaid ne se rend pas sans extension
            (les .md montrent le code brut) ; solutions = ouvrir docs/schemas.html
            au navigateur, ou installer bierner.markdown-mermaid (recommandee via
            .vscode/extensions.json) et Ctrl+Shift+V. Tableaux ASCII = monospace,
            identiques partout. Aucun fichier de conception n'est en cause.
2026-08-27  Ajout d'un document de passation pour la session de developpement :
            docs/PASSATION_DEV.md (etat fige, decisions verrouillees, env,
            backlog par lots avec criteres de fin, garde-fous anti-emballement).
            POINT D'ENTREE DEV : ouvrir PASSATION_DEV.md en premier.
```

---

## 11. Transfert Cloud -> VSCode / Claude Code

- La conception est menée dans Claude (Cowork, Cloud) ; le développement se
  poursuivra dans **VSCode avec Claude Code**.
- La conversation Cloud **ne suit pas** ; **les fichiers de ce dossier sont la
  seule mémoire**. Ce `CLAUDE.md` rejoue le contexte à chaque ouverture.
- Règle : toute décision, tout état d'avancement se consigne ici (§5 et §10),
  jamais uniquement dans le chat.

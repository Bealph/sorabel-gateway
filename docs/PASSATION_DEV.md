# Passation vers le développement : Sorabel Data Gateway

> Document de démarrage pour la session de développement.
> La conception est terminée et figée. Ce document dit quoi lire, ce qui est
> décidé (donc à ne pas rediscuter), comment monter l'environnement, dans quel
> ordre développer, et comment savoir qu'une étape est finie.
>
> Règle d'or : avancer LOT PAR LOT, un livrable à la fois, en validant après
> chaque étape. Ne pas tout ouvrir d'un coup. En cas de doute d'architecture,
> se référer aux docs de conception, ne pas réinventer.

---

## 1. État actuel

```
Conception    TERMINEE (docs/conception/ : 00 a 08 + schemas.html)
Revue         FAITE le 2026-09-02 : docs/REVUE_CONCEPTION.md. A LIRE.
Donnees       PRESENTES (data/sorabel.db + data/corpus/{fiches,notices,sav,notes})
Jeux d'eval   PRESENTS. Fixtures 24 SQL + 30 RAG, attendus SQL + RAG,
              et eval/cas_mcp.jsonl (22 cas de gouvernance, ecrit le 2026-09-02)
Code          PAS ENCORE ECRIT (rag/ text2sql/ governance/ mcp_server/ vides)
```

## 2. À lire en premier (et rien de plus pour démarrer)

```
1. MEMOIRE_PROJET.md                          memoire + decisions + journal
2. docs/conception/00_architecture.md vue d'ensemble
3. docs/REVUE_CONCEPTION.md           CE QUI DOIT ETRE FERME AVANT CHAQUE LOT
4. docs/conception/05_catalogue_tools.md   contrat des 8 tools (entrees/sorties)
5. Le doc du lot en cours (01 pour le RAG, 02 pour le SQL, 03 pour la matrice,
   08 pour l'interface)
```

Ne pas relire tout le dossier avant d'agir. Charger le doc du lot courant, faire,
valider, puis passer au suivant.

## 3. Décisions verrouillées (NE PAS rediscuter)

```
- Stack RAG : embeddings BAAI/bge-m3 ; reranker BAAI/bge-reranker-v2-m3 (local).
- Store : Chroma (dense) + BM25 applicatif (lexical) ; fusion RRF (k=60).
- Court-circuit REF : si la question matche REF-\d+, filtre exact d'abord.
- Versions : indexer TOUTES, champ is_latest, citer/privilegier la plus recente.
- Chunking : structure-aware (fiche=1 chunk ; notice/sav=par section ; note=1).
- Text-to-SQL : LLM LOCAL oriente code (ex. Qwen2.5-Coder via Ollama).
- Lecture seule : connexion RO + AST sqlglot SELECT-only + perimetre profil +
  LIMIT/timeout + SQL renvoye + journal. Pas de SELECT *.
- Sortie typee par status : ok | out_of_corpus | out_of_schema | not_found |
  clarify | refused | error. Un non-ok n'est JAMAIS rendu comme une reponse.
- not_found : entite par identifiant precis introuvable (ex. SQL-08). Liste/
  agregat vide = ok avec rows[].
- Desambiguisation : critere indefini -> clarify ; libelle -> plusieurs ref ->
  reponse multiligne (ok).
- Gouvernance : matrice declarative deny-by-default, appliquee gateway + tool.
- Catalogue : 8 tools (voir 05). Briques RAG (search_docs/get_document/
  list_sources) reservees a dev/IDE. Collection notes interdite au support.
- Colonnes sensibles jamais pour support : produits.prix_achat_ht,
  produits.marge_pct, ventes.marge_ht.
```

Plus aucun point de conception n'est ouvert. P8, le mécanisme d'identité du
client MCP, est fermé depuis le 2026-08-31 par la décision **D28** : le profil est
fixé au lancement par la variable `SORABEL_PROFIL`, validée au démarrage, et
n'est **jamais** un paramètre de tool. Détail et limites en section Q6 du
chantier 3.

## 4. Environnement

```
- Python >= 3.11. Creer un venv.
- Dependances (a valider a l'install) : mcp / fastmcp, chromadb, bm25s (ou
  rank-bm25), sentence-transformers, sqlglot, pymupdf (ou pdfplumber),
  beautifulsoup4, pyyaml.
- Modeles locaux : embeddings + reranker (sentence-transformers) ; LLM SQL via
  Ollama (modele coder instruct). Prevoir un repli si un modele est trop lourd.
- Donnees : data/sorabel.db en LECTURE SEULE ; corpus sous data/corpus/.
  Ces fichiers sont gitignore (ne pas les versionner).
- La base a des trous de numerotation (CMD-2026-0042 absent) : normal, gere par
  not_found.
```

## 5. Backlog de développement (ordre imposé)

| Lot | Objet | Livrable / fin de lot |
| ---: | --- | --- |
| 0 | Bootstrap. **FAIT le 2026-09-02**, sauf Chroma et la chaine Azure, voir le journal** | venv, deps installees, arbo de code, chargeur de config + matrice YAML. `verifier_matrice.py` passe SOUS pyyaml, et la vue est regeneree. **Plus : une page vide deployee sur Azure, joignable par son URL, avec `SORABEL_DATA_DIR` monte, un fichier ecrit puis relu APRES redemarrage.** Ce dernier point valide D35, qui est le piege silencieux du chantier 7 |
| 1 | Ingestion RAG (doc 01) | loaders PDF/HTML/MD -> Document canonique + versions/is_latest + chunking ; index Chroma + BM25 construits |
| 2a | Recherche RAG, dense de base (doc 01) | dense seul + citations + refus hors corpus. Jalon impose par le brief, et baseline de E6 : a conserver telle quelle |
| 2b | Recherche RAG, avancee (doc 01) | hybride + RRF + court-circuit REF + rerank + seuil ; tool answer_question |
| 3 | Mesure E6 (doc 01 Q5, mesure_e6.md) | **ecrire le harnais RAG** qui rejoue eval/questions_rag.jsonl contre eval/attendus_rag.jsonl ; ablation en 4 configurations (A, B, C, D) et non 2 ; Recall@k + MRR ; gold DEJA annotes dans eval/attendus_rag.jsonl ; resultats dans eval/results/. ATTENTION : le socle semantique vaut 8 questions, pas 14, cf. mesure_e6.md section 2 |
| 4 | Text-to-SQL (doc 02) | **ecrire le harnais SQL, et finir sur 24/24 conformes a eval/attendus_sql.jsonl** ; connexion RO, get_schema, generation + validation AST + perimetre + LIMIT + sortie typee ; figes check_stock/order_status |
| 5 | Gouvernance + serveur MCP (docs 03, 05, 06) | **ecrire le harnais MCP, et finir sur 22/22 conformes a eval/cas_mcp.jsonl, journal compris** ; matrice gateway+tool, journal JSONL, catalogue expose, refus types ; scripts/mcp_client.py demontrant DEUX profils, exige nommement par le brief |
| 6 | Interface + application Slack (docs 07 et 08) | UI du produit et son lien sur Azure, **ecran 3 en priorite** : c'est le seul qui demontre E4 et E5 (chantier 8) ; application Slack : signature verifiee, accuse de reception puis reponse differee (D34) ; preparation soutenance. Le mini guide est DEJA ecrit : mcp_server/GUIDE_ACCES.md |

Ne pas commencer un lot avant que le precedent passe ses criteres.

**Ou tourne quoi (D37, chantier 7).** Les lots 0 a 4 se font et se valident en
LOCAL. Le deploiement Azure intervient au lot 5, l'interface et l'application
Slack au lot 6. Deboguer la pile de gardes a travers une couche d'hebergement
coute plusieurs fois plus cher, et E6 se mesure plus surement a modele fige.
EXCEPTION OBLIGATOIRE, et non plus recommandee : eprouver la chaine de
deploiement a vide DES LE LOT 0. Une recommandation n'est pas un critere de fin,
et le lot 0 pouvait etre declare termine sans qu'un octet ait atteint Azure. Le
cadre est de six jours, le deploiement arrive au lot 5 sur 7 et l'interface au
lot 6 : si Azure resiste, il n'y a aucune marge derriere.

**Tout artefact persistant s'ecrit sous `SORABEL_DATA_DIR` (D35).** Le stockage
de conteneur est ephemere par defaut : un index ecrit ailleurs disparait au
redemarrage, sans message d'erreur.

## 6. Définition de « fini » (tests d'acceptation = objectif)

Chaque lot vise des tests précis. Les jeux `eval/*.jsonl` sont les fixtures.

```
RAG (lots 1-3) :
  RAG-01..08 (reference_exacte) -> la bonne ref en tete.
  RAG-09..22 (couverte)         -> reponse + sources (titre/ref/date).
  RAG-23..30 (hors_corpus)      -> abstention (status=out_of_corpus).
  E6 : recherche avancee > dense simple, chiffre a l'appui.

Text-to-SQL (lot 4) :
  SQL-01..12 (metier)     -> resultat + SQL renvoye.
    dont SQL-08 -> not_found (id absent) ; SQL-10 -> reponse multiligne (4 ref).
  SQL-13..16 (ecriture)   -> refus READ_ONLY_VIOLATION + journal.
  SQL-17..20 (support)    -> refus FORBIDDEN_COLUMN (colonnes sensibles).
  SQL-21..22 (hors_schema)-> refus clair, aucun SQL hallucine.
  SQL-23..24 (ambigue)    -> clarify (critere indefini).

MCP / gouvernance (lot 5) :
  profil autorise -> acces borne ; appel non autorise -> refus + journal ;
  search_docs puis get_document -> briques separees (client dev/IDE) ;
  session de demo -> journal contient TOUS les appels (autorises + refuses).
```

Valeurs de contrôle sur les données (utiles pour vérifier le SQL) :

```
commandes 2026-04 = 27 | livrees 2026-06 = 11 | total mars 2026 = 432 245,90 EUR
annulations depuis janvier = 41 | refs sous seuil a LYON = 3
statut commande : annulee/en_attente/expediee/livree/preparee
entrepots : LILLE/LYON/NANTES | plage dates : 2025-09-04 a 2026-08-19
```

## 7. Conventions et garde-fous (anti-emballement)

```
- Avancer par petits pas : un fichier / une fonction, puis tester, puis avancer.
- Ne PAS modifier les fixtures eval/*.jsonl (fournies / a garder telles quelles).
- Ne PAS rediscuter les decisions de la section 3.
- Ecrire les resultats/logs sous eval/results/ et governance/logs/ (gitignore).
- Jamais de secret en clair ; base ouverte en read-only ; aucun SELECT *.
- Docs en francais ; tableaux Markdown ; schemas Mermaid. La regle disait
  "tableaux ASCII" jusqu'au 2026-08-28, cf. MEMOIRE_PROJET.md section 8.
- Tenir le journal : ajouter une ligne datee dans MEMOIRE_PROJET.md section 10 a la fin
  de chaque lot (ce qui est fait, ce qui reste).
- Multi-session : une seule session ecrit un fichier donne a la fois ; MEMOIRE_PROJET.md
  tranche en cas de doute.
- Si bloque > 2 essais sur un point : s'arreter, ecrire l'etat dans le journal,
  et demander au pilote plutot que d'insister.
```

## 8. Première action conseillée

Lot 0 puis Lot 1. Concrètement pour démarrer le Lot 1 : écrire les loaders par
format qui produisent le `Document` canonique de `01_flux_chunks.md` (section
1.2), en extrayant les métadonnées de citation (titre, ref, version, date) et en
calculant `version_group` / `is_latest`. Vérifier sur un échantillon (par
exemple les deux versions de REF-8842) avant de généraliser au corpus entier.

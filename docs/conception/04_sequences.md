# Diagrammes de séquence — interactions de la Gateway

> Vue comportementale complétant `00_architecture.md` (vue structurelle). Chaque
> séquence illustre un comportement clé et ses points de contrôle. Participants
> communs : Client (porteur d'un profil), Gateway (interface MCP + autorisation),
> les moteurs RAG et Text-to-SQL, l'Index, le LLM de génération, la base SQL, le
> Journal.

---

## 1. Question documentaire (answer_question) : réponse ou abstention (E1, E2)

```mermaid
sequenceDiagram
    autonumber
    participant C as Client (profil)
    participant G as Gateway
    participant R as Moteur RAG
    participant I as Index docs
    participant J as Journal

    C->>G: answer_question(question) + identite
    G->>G: identite -> profil, tool autorise ? (oui)
    G->>R: question (collections du profil)
    R->>I: recherche hybride (BM25 + dense)
    I-->>R: candidats
    R->>R: fusion RRF + reranking + seuil tau
    alt score >= tau (couverte)
        R-->>G: reponse ancree + sources (titre/ref/date)
        G->>J: log (allowed, resultat)
        G-->>C: status=ok, answer, sources
    else score < tau (non couvert)
        R-->>G: non couvert
        G->>J: log (allowed, out_of_corpus)
        G-->>C: status=out_of_corpus (aucune invention)
    end
```

---

## 2. Question métier Text-to-SQL autorisée (ask_database) : gardes lecture seule (E3)

```mermaid
sequenceDiagram
    autonumber
    participant C as Client (commercial)
    participant G as Gateway
    participant T as Moteur Text-to-SQL
    participant L as LLM local
    participant D as Base SQL (read-only)
    participant J as Journal

    C->>G: ask_database("combien de commandes en avril ?")
    G->>G: profil, tool autorise ? (oui)
    G->>T: question + schema commente du profil
    T->>L: prompt (schema + enums + few-shot)
    L-->>T: sortie structuree {SQL}
    T->>T: AST : un seul SELECT, perimetre profil, injection LIMIT
    T->>D: execution (connexion read-only)
    D-->>T: lignes
    T-->>G: resultat + SQL genere
    G->>J: log (allowed, SQL, ressources touchees)
    G-->>C: status=ok, rows, sql
    Note over T,L: si la sortie est CLARIFY -> status=clarify,<br/>si HORS_SCHEMA -> status=out_of_schema (aucun SQL execute)
```

---

## 3. Colonne sensible pour le support (E5) : refus par le périmètre

```mermaid
sequenceDiagram
    autonumber
    participant C as Client (support)
    participant G as Gateway
    participant T as Moteur Text-to-SQL
    participant L as LLM local
    participant J as Journal

    C->>G: ask_database("quelle est la marge sur la REF-8842 ?")
    G->>G: profil=support, ask_database autorise (oui)
    G->>T: question + schema SANS colonnes sensibles
    T->>L: prompt
    L-->>T: SQL touchant marge_pct
    T->>T: perimetre : marge_pct interdite au support
    T-->>G: refus FORBIDDEN_COLUMN
    G->>J: log (refused, FORBIDDEN_COLUMN, SQL genere)
    G-->>C: status=refused, code=FORBIDDEN_COLUMN, message clair
    Note over T,J: double protection : la colonne est deja masquee dans le schema,<br/>le perimetre est le garde-fou. Aucune valeur sensible en reponse ni au journal.
```

---

## 4. Appel non autorisé au niveau tool (E4)

```mermaid
sequenceDiagram
    autonumber
    participant C as Client (support)
    participant G as Gateway
    participant J as Journal

    C->>G: search_docs("disjoncteur triphase")
    G->>G: profil=support, search_docs autorise ? NON (brique reservee dev/IDE)
    G->>J: log (refused, UNAUTHORIZED_TOOL)
    G-->>C: status=refused, code=UNAUTHORIZED_TOOL, message clair
    Note over G: refus a l'entree, aucun moteur n'est atteint
```

---

## 5. Tentative d'écriture : lecture seule (E3)

```mermaid
sequenceDiagram
    autonumber
    participant C as Client (commercial)
    participant G as Gateway
    participant T as Moteur Text-to-SQL
    participant L as LLM local
    participant J as Journal

    C->>G: ask_database("supprime les commandes de test")
    G->>G: profil, tool autorise (oui)
    G->>T: question + schema
    T->>L: prompt
    L-->>T: sortie {SQL : DELETE ...}
    T->>T: AST : instruction non-SELECT detectee
    T-->>G: refus READ_ONLY_VIOLATION
    G->>J: log (refused, READ_ONLY_VIOLATION, SQL)
    G-->>C: status=refused, code=READ_ONLY_VIOLATION
    Note over T,J: meme si l'AST etait contourne, la connexion read-only<br/>rejetterait l'ecriture (garde-fou ultime)
```

---

## Lecture transversale

| Sequence | Ce qu'elle demontre                                              | Exigence |
| -------: | ---------------------------------------------------------------- | -------- |
|        1 | reponse + sources, ou abstention propre                          | E1, E2   |
|        2 | SQL genere execute en lecture seule + SQL renvoye (transparence) | E3       |
|        3 | colonne sensible refusee au support                              | E5       |
|        4 | tool interdit refuse a l'entree                                  | E4       |
|        5 | ecriture refusee (AST + connexion RO)                            | E3       |

Dans tous les cas, l'appel (autorise ou refuse) est journalise (E5), et la
sortie est typee par status : une abstention ou un refus n'est jamais rendu
comme une reponse.

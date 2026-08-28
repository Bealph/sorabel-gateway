# Analyse du jeu de données — Sorabel Data Gateway

> Prise de connaissance des données fournies (`data/`). Base SQL inspectée
> intégralement (schéma, volumétrie, clés étrangères) ; corpus documentaire
> caractérisé sur un échantillon représentatif de chaque type. Ce document
> alimente les trois chantiers de conception.

---

## 1. Base SQL — `data/sorabel.db` (SQLite)

Six tables métier (plus `sqlite_sequence`, technique). Volumétrie et schéma :

| Table | Lignes | Colonnes |
| --- | ---: | --- |
| clients | 60 | id[PK], raison_sociale, segment, ville, email |
| produits | 120 | ref[PK], nom, categorie, fabricant, unite, prix_vente_ht, prix_achat_ht(\*), marge_pct(\*), actif |
| stocks | 312 | id[PK], ref[FK->produits.ref], entrepot, quantite, seuil_reappro |
| commandes | 340 | id[PK], client_id[FK->clients.id], date_commande, statut, montant_ht |
| ventes | 993 | id[PK], commande_id[FK->commandes.id], ref[FK->produits.ref], quantite, prix_unitaire_ht, remise_pct, marge_ht(\*) |

(*) colonne sensible : ne doit jamais sortir pour le profil support (E5).

Modèle relationnel :

```mermaid
erDiagram
    clients   ||--o{ commandes : "passe"
    commandes ||--o{ ventes    : "contient"
    produits  ||--o{ ventes    : "concerne"
    produits  ||--o{ stocks    : "stocke"

    clients {
      TEXT id PK "60 lignes"
      TEXT raison_sociale
      TEXT segment "PME, artisan, collectivite, grand compte"
      TEXT ville "15 villes"
      TEXT email
    }
    produits {
      TEXT ref PK "120 lignes"
      TEXT nom "43 libelles sont dupliques"
      TEXT categorie "9 valeurs"
      TEXT fabricant "11 valeurs"
      TEXT unite "piece, conditionnement"
      REAL prix_vente_ht "public, visible par tous"
      REAL prix_achat_ht "SENSIBLE, jamais pour le support"
      REAL marge_pct "SENSIBLE, jamais pour le support"
      INT  actif
    }
    commandes {
      TEXT id PK "340 lignes, numerotation a trous"
      TEXT client_id FK
      TEXT date_commande "2025-09-04 a 2026-08-19"
      TEXT statut "5 valeurs"
      REAL montant_ht
    }
    stocks {
      INT  id PK "312 lignes"
      TEXT ref FK
      TEXT entrepot "LILLE, LYON, NANTES"
      INT  quantite
      INT  seuil_reappro
    }
    ventes {
      INT  id PK "993 lignes"
      TEXT commande_id FK
      TEXT ref FK
      INT  quantite
      REAL prix_unitaire_ht
      REAL remise_pct
      REAL marge_ht "SENSIBLE, jamais pour le support"
    }
```

Observations utiles au Text-to-SQL :

```
- Dates au format texte 'YYYY-MM-DD' (ex. commandes 2026-03, 2026-04) :
  un filtre mensuel se fait par date_commande LIKE '2026-04%'.
- Entrepots observes : LILLE, LYON (colonne stocks.entrepot).
- statut de commande : valeurs type 'livree', 'annulee' (a enumerer exhaustivement).
- Jointures naturelles : ventes -> commandes -> clients, et ventes/stocks -> produits.
- Colonnes monetaires : prix_vente_ht (public, OK support) vs prix_achat_ht +
  marge_pct + marge_ht (sensibles, interdits support).
```

Correspondance avec le jeu d'éval SQL :

| Type de question | Comportement attendu |
| --- | --- |
| metier (SQL-01..12) | requete SELECT correcte + SQL renvoye |
| ecriture (SQL-13..16) | refus (lecture seule) + journalisation |
| table_interdite (SQL-17..20) | refus par la matrice (marges/prix d'achat), profil support |
| hors_schema (SQL-21,22) | refus clair, aucun SQL hallucine |
| ambigue (SQL-23,24) | demande de precision, pas de SQL devine |

---

## 2. Corpus documentaire — `data/corpus/`

Quatre familles de documents, chacune avec ses métadonnées de citation (E1).

| Dossier | Format | Metadonnees (source de la citation E1) | Versions vues |
| --- | --- | --- | --- |
| fiches/ | PDF | titre, reference, version, date, fabricant, categorie, prix public HT, references associees | v1.0 et v2.1 |
| notices/ | PDF | titre, reference, version, date ; sections securite/installation/service | v1.0 et v1.1 |
| sav/ | HTML | &lt;title>, &lt;meta version>, &lt;meta date>, &lt;meta type=procedure_sav> | v1.0 et v2.0 |
| notes/ | MD | frontmatter YAML : titre, date, auteur, type=note_interne, version | version unique |

Sous-types des notes internes (déduits des noms de fichiers) :
`reunion-achat`, `alerte-qualite`, `politique-tarifaire`, `retour-terrain`,
`logistique`. Période couverte : 2024 à 2026.

Correspondance avec le jeu d'éval RAG :

| Type de question | Attendu |
| --- | --- |
| reference_exacte (01..08) | la fiche de la reference remonte en tete (E2) |
| couverte (09..22) | reponse + sources ; attendu_type = fiche_technique / notice / procedure_sav |
| hors_corpus (23..30) | abstention : l'outil signale l'absence (E1) |

Note : `attendu_type` de l'éval pointe vers `fiche_technique`, `notice`,
`procedure_sav`. Le type `note_interne` n'est pas ciblé par l'éval mais existe
dans le corpus, et porte l'essentiel du contenu sensible (voir §3).

---

## 3. Points sensibles pour la gouvernance (E4/E5)

La sensibilité est présente sur **deux plans**, pas seulement en SQL :

| Plan | Element sensible | Regle (profil support) |
| --- | --- | --- |
| SQL (colonnes) | produits.prix_achat_ht, produits.marge_pct, ventes.marge_ht | jamais renvoyees |
| RAG (collections) | notes/ (politique-tarifaire, reunion-achat) : marges cibles, prix, negos fournisseurs, mention "Diffusion restreinte" | non accessibles |

Conclusion : la matrice d'accès doit gouverner **tools + collections + tables +
colonnes**. C'est un point de conception à porter au chantier 3.

---

## 4. Constats structurants (impacts conception)

```
1. E1 realisable : chaque document porte titre + reference + date exploitables.
   -> Extraction de metadonnees specifique par format (PDF texte, meta HTML,
      frontmatter YAML).

2. E2 (reference exacte) : la reference figure dans le nom de fichier ET le texte.
   -> Justifie l'axe lexical/BM25 (ou filtre par metadonnee) en plus du dense.

3. Versioning reel : plusieurs versions datees d'un meme document (fiche, notice,
   procedure). C'est le piege "confond les versions".
   -> Indexer version + date ; politique de restitution a trancher (indexer tout,
      citer et privilegier la version la plus recente).

4. Sensibilite double (SQL + notes) -> gouvernance sur collections ET colonnes.

5. Abstention testable : les questions hors_corpus (RH, finance, RSE, VPN) sont
   reellement absentes du corpus -> E1 verifiable.
```

---

## 5. Questions ouvertes (à trancher en conception)

```
- Politique de version au RAG : tout indexer et privilegier le plus recent,
  ou n'indexer que la derniere version ? (impact E2 et E6)
- Granularite des collections RAG : fiches / notices / sav / notes, ou plus fin ?
- Enumeration exacte des valeurs de statut et des entrepots (pour bornage SQL).
- Comptage precis des fichiers du corpus par type (a produire par script au
  moment de l'ingestion, chantier 1).
```

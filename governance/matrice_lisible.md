<!-- GENERE par governance/verifier_matrice.py depuis matrice.yaml. Ne pas editer a la main. -->

# Matrice d'acces, vue lisible

> Vue **générée** le 2026-09-01 depuis `governance/matrice.yaml`,
> qui est la source de vérité (D21). À titre informatif : en cas de divergence,
> c'est le fichier YAML qui fait foi, jamais ce document.

## Quel profil peut appeler quel tool

| Tool | Famille | support | commercial | dev |
| --- | --- | :---: | :---: | :---: |
| `answer_question` | RAG | oui | oui | oui |
| `search_docs` | RAG | **non** | **non** | oui |
| `get_document` | RAG | **non** | **non** | oui |
| `list_sources` | RAG | **non** | **non** | oui |
| `ask_database` | SQL | oui | oui | oui |
| `get_schema` | SQL | oui | oui | oui |
| `check_stock` | SQL | oui | oui | oui |
| `order_status` | SQL | oui | oui | oui |

## Quel profil accède à quelle collection documentaire

| Collection | `doc_type` | support | commercial | dev |
| --- | --- | :---: | :---: | :---: |
| `fiches` | `fiche_technique` | oui | oui | oui |
| `notices` | `notice` | oui | oui | oui |
| `sav` | `procedure_sav` | oui | oui | oui |
| `notes` | `note_interne` | **non** | oui | oui |

## Colonnes SQL retirées, par profil

Les colonnes ci-dessous sont **sensibles au sens d'E5**. Une colonne retirée
n'apparaît pas dans le schéma montré au modèle, et le contrôle de périmètre
la rejette après génération.

| Colonne sensible | support | commercial | dev |
| --- | :---: | :---: | :---: |
| `produits.prix_achat_ht` | **retirée** | visible | visible |
| `produits.marge_pct` | **retirée** | visible | visible |
| `ventes.marge_ht` | **retirée** | visible | visible |

## Tables accessibles

Aucune table n'est interdite à aucun profil : la restriction porte sur les
**colonnes**, jamais sur les tables.

| Profil | Tables | Rôle |
| --- | --- | --- |
| `support` | 5 sur 5 | bot Slack du SAV, client tourne vers l'exterieur |
| `commercial` | 5 sur 5 | poste commercial |
| `dev` | 5 sur 5 | IDE des developpeurs, seul profil ayant les briques RAG (D18) |

## Invariants contrôlés

Ces règles ne sont pas des commentaires : le script échoue si l'une tombe.


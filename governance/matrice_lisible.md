<!-- GENERE par governance/verifier_matrice.py depuis matrice.yaml. Ne pas editer a la main. -->

# Matrice d'acces, vue lisible

> Vue **générée** le 2026-09-02 depuis `governance/matrice.yaml`,
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

Une colonne retirée n'apparaît pas dans le schéma montré au modèle, et le
contrôle de périmètre la rejette après génération. Le périmètre porte sur
**toute occurrence** de la colonne, y compris dans un `WHERE`, un `ORDER BY`,
un `GROUP BY` ou un `HAVING` : un tri sur une colonne retirée la divulgue
sans jamais l'afficher.

| Colonne | Classe | support | commercial | dev |
| --- | --- | :---: | :---: | :---: |
| `produits.prix_achat_ht` | sensible (E5) | **retirée** | visible | visible |
| `produits.marge_pct` | sensible (E5) | **retirée** | visible | visible |
| `ventes.marge_ht` | sensible (E5) | **retirée** | visible | visible |
| `clients.email` | restreinte | **retirée** | visible | visible |

Les 27 autres colonnes de la base sont classées **publiques** : elles peuvent
sortir pour n'importe quel profil. La classification est exhaustive, et le
contrôle échoue sur toute colonne de la base qui n'est classée nulle part.

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
Les quatre premières se contrôlent contre des **ancres écrites en dur** dans
le script, hors de ce fichier : un invariant qui se vérifie contre une donnée
du fichier qu'il contrôle s'annule avec elle.

- **catalogue_exact** : le catalogue est exactement les 8 tools nommes par D17
- **profils_exacts** : les profils sont exactement support, commercial et dev (P7)
- **E5_colonnes_sensibles_ancrees** : colonnes_sensibles est exactement les 3 colonnes nommees par E5
- **E5_support_sans_colonnes_sensibles** : le profil support interdit les colonnes sensibles et restreintes
- **E4_briques_rag_reservees_dev** : search_docs, get_document et list_sources n'appartiennent qu'au profil dev
- **E5_notes_interdites_support** : la collection notes n'est pas accessible au profil support
- **classification_exhaustive** : les trois listes de colonnes couvrent exactement le schema de la base
- **doc_type_reels** : chaque doc_type declare existe dans le corpus, et reciproquement
- **lexique_complet** : chaque colonne retiree a au moins un terme dans le lexique de refus
- **schema_reel** : toute table et toute colonne citee existe dans la base

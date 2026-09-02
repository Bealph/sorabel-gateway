<!-- GENERE par governance/verifier_matrice.py depuis matrice.yaml. Ne pas editer a la main. -->

# Matrice d'acces, vue lisible

> Vue **générée** le 2026-09-02 depuis `governance/matrice.yaml`,
> qui est la source de vérité (D21). À titre informatif : en cas de divergence,
> c'est le fichier YAML qui fait foi, jamais ce document.

## Quel profil peut appeler quel tool

| Tool | Famille | support | commercial |
| --- | --- | :---: | :---: |
| `answer_question` | RAG | oui | oui |
| `search_docs` | RAG | oui | oui |
| `get_document` | RAG | oui | oui |
| `list_sources` | RAG | oui | oui |
| `ask_database` | SQL | oui | oui |
| `get_schema` | SQL | **non** | oui |
| `check_stock` | SQL | oui | oui |
| `order_status` | SQL | oui | oui |

## Quel profil accède à quelle collection documentaire

| Collection | `doc_type` | support | commercial |
| --- | --- | :---: | :---: |
| `fiches_techniques` | `fiche_technique` | oui | oui |
| `notices` | `notice` | oui | oui |
| `procedures_sav` | `procedure_sav` | oui | oui |
| `notes_internes` | `note_interne` | **non** | oui |

## Colonnes SQL retirées, par profil

Une colonne retirée n'apparaît pas dans le schéma montré au modèle, et le
contrôle de périmètre la rejette après génération. Le périmètre porte sur
**toute occurrence** de la colonne, y compris dans un `WHERE`, un `ORDER BY`,
un `GROUP BY` ou un `HAVING` : un tri sur une colonne retirée la divulgue
sans jamais l'afficher.

| Colonne | Classe | support | commercial |
| --- | --- | :---: | :---: |
| `produits.prix_achat_ht` | sensible (E5) | **retirée** | visible |
| `produits.marge_pct` | sensible (E5) | **retirée** | visible |
| `ventes.marge_ht` | sensible (E5) | **retirée** | visible |
| `clients.email` | restreinte | **retirée** | visible |

Les 27 autres colonnes de la base sont classées **publiques** : elles peuvent
sortir pour n'importe quel profil. La classification est exhaustive, et le
contrôle échoue sur toute colonne de la base qui n'est classée nulle part.

## Tables accessibles

La restriction porte d'abord sur les **colonnes**, mais le cadrage DSI retire
aussi une table entière au profil `support` : `ventes`. Une table absente est
un refus, pas un filtrage.

| Table | support | commercial |
| --- | :---: | :---: |
| `clients` | oui | oui |
| `commandes` | oui | oui |
| `produits` | oui | oui |
| `stocks` | oui | oui |
| `ventes` | **non** | oui |

| Profil | Rôle |
| --- | --- |
| `support` | bot Slack du SAV, client tourne vers l'exterieur |
| `commercial` | poste commercial |

## Invariants contrôlés

Ces règles ne sont pas des commentaires : le script échoue si l'une tombe.
Les quatre premières se contrôlent contre des **ancres écrites en dur** dans
le script, hors de ce fichier : un invariant qui se vérifie contre une donnée
du fichier qu'il contrôle s'annule avec elle.

- **catalogue_exact** : le catalogue est exactement les 8 tools nommes par le cadrage DSI
- **profils_exacts** : les profils sont exactement support et commercial
- **contrat_tools_par_profil** : les tools de chaque profil sont exactement ceux de tests/conftest.py
- **E5_colonnes_sensibles_ancrees** : colonnes_sensibles est exactement les 3 colonnes nommees par E5
- **E5_support_sans_colonnes_sensibles** : le profil support interdit les colonnes sensibles et restreintes
- **E5_ventes_hors_perimetre_support** : la table ventes n'est pas accessible au profil support
- **E5_notes_interdites_support** : la collection notes_internes n'est pas accessible au support
- **classification_exhaustive** : les trois listes de colonnes couvrent exactement le schema de la base
- **doc_type_reels** : chaque doc_type declare existe dans le corpus, et reciproquement
- **lexique_complet** : chaque colonne retiree a au moins un terme dans le lexique de refus
- **schema_reel** : toute table et toute colonne citee existe dans la base

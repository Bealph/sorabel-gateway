# governance/

Gouvernance transverse : **qui a droit à quoi**, et **trace de tout appel**.
Répond aux exigences E4 (un serveur, chaque client borné) et E5 (journal de tout
appel, colonnes sensibles jamais pour le support).

## Les fichiers

| Fichier | Rôle | Édité à la main |
| --- | --- | :---: |
| `matrice.yaml` | **La source de vérité** des droits (D21). Chargée au démarrage, appliquée aux deux niveaux : gateway pour le tool, tool pour les ressources | oui |
| `verifier_matrice.py` | Contrôle la cohérence, puis régénère la vue lisible | oui |
| `matrice_lisible.md` | Vue générée, à titre informatif | **non** |
| `logs/` | Journal JSONL, un objet par appel, autorisé ou refusé (D33). À créer au développement | — |

## Vérifier

```
python governance/verifier_matrice.py              # controle + regenere la vue
python governance/verifier_matrice.py --verifier   # controle seul, signale une vue perimee
```

Le script joue les contrôles suivants, et **refuse d'écrire** si l'un tombe :

- le catalogue est fermé : aucun profil ne cite un tool qui n'y figure pas ;
- E5 : le profil `support` interdit les trois colonnes sensibles ;
- D18 : `search_docs`, `get_document`, `list_sources` n'appartiennent qu'à `dev` ;
- P7 : la collection `notes` n'est pas accessible au `support` ;
- toute table et toute colonne citée existe réellement dans `data/sorabel.db`.

Ces contrôles ont été éprouvés en les faisant échouer volontairement, un par un.

## Pourquoi une source unique

La matrice était écrite en clair à trois endroits (chantier 3, catalogue 05,
guide d'accès) et le fichier que le dossier désigne comme source depuis D21
n'existait pas. C'est le mode de défaillance qui a déjà frappé deux fois sur les
énumérations de la base : ce qui est recopié diverge, et une divergence de droits
ne se voit pas, elle s'exploite. Les trois tableaux subsistent, désormais
étiquetés comme des vues.

Ce que ce dossier ne fait pas : dire **qui** appelle. L'identité vient du
lancement du serveur (D28), jamais d'un paramètre de tool.

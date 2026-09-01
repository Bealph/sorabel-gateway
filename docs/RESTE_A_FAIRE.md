# Sorabel Data Gateway, reste à faire

> Liste de référence des travaux restants. Elle a compté 34 items le 2026-08-31 ;
> 31 sont faits. **Le détail de ce qui a été fait n'est plus ici** : il est dans
> l'historique git, où chaque commit porte son raisonnement. Garder les lignes
> closes aurait fait de ce fichier un compte rendu, alors que c'est une liste de
> travail.

## Ce qui reste

| Id | Travail | Fichier | Phase | Bloqué par |
| --- | --- | --- | --- | --- |
| M2 | Remplir le tableau de résultats chiffrés | `docs/mesure_e6.md` et `eval/results/` | Développement | le serveur n'existe pas encore |
| L1 | Client de démonstration en ligne de commande, montrant deux profils sur le même serveur | `scripts/mcp_client.py`, à créer | Développement | le serveur n'existe pas encore |
| L3 | Interface graphique et son lien | à définir | Développement | le serveur n'existe pas encore |

## Aucun n'est commençable aujourd'hui

Les trois demandent que le serveur MCP réponde. Ce ne sont pas des travaux en
retard, ce sont des travaux **pas encore commençables**. Les inscrire au même
niveau que des corrections documentaires serait une erreur de lecture.

L'ordre dans lequel ils se débloquent suit le backlog de `PASSATION_DEV.md` :

```
lot 2a, 2b, 3   ->  M2, les chiffres de la mesure E6
lot 5           ->  L1, scripts/mcp_client.py, la demonstration des deux profils
lot 6           ->  L3, l'interface graphique et son lien
```

## Où trouver le reste

```
git log --oneline              les 10 commits, chacun avec son raisonnement
git log -p docs/RESTE_A_FAIRE.md   l'etat complet de la liste, jour par jour
```

La phase de conception est close : décisions D1 à D33, arbitrages P1 à P8, plus
aucun point ouvert.

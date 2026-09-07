#!/usr/bin/env python3
"""Retire les paquets CUDA de l'environnement, à la construction de l'image.

POURQUOI CE FICHIER EXISTE
`uv.lock` épingle **15 paquets `nvidia-*` plus `triton`**, parce que la roue
torch publiée sur PyPI est la variante CUDA. Sur Linux, `uv sync` les installe
tous. Rien de ce que nous déployons n'a de GPU : D36 avait établi que les deux
modèles critiques pour E6 tiennent sur processeur, et seule la génération SQL
aurait profité d'un accélérateur.

Le Dockerfile réinstallait déjà torch depuis l'index processeur, mais cela
remplace **torch seul** et laisse les quinze paquets CUDA en place. Résultat
mesuré le 2026-09-07 sur la première image réellement construite :

    12,63 Go, alors que le SKU Basic du registre plafonne a 10,74 Go

Le registre a donc dépassé son quota, et le tirage de l'image a échoué côté
Container Apps avec un `ImagePullUnauthorized` qui ne disait rien de la vraie
cause. L'étape que j'avais signalée comme la plus fragile n'a pas échoué : elle
a fait **la moitié** du travail, ce qui est plus sournois qu'un échec franc.

CE SCRIPT NE RECOPIE AUCUNE LISTE
Il relève les paquets installés et retire ceux dont le nom commence par
`nvidia-`, plus `triton`. Une liste recopiée dériverait au premier changement
de `uv.lock`, et l'image regonflerait sans que rien ne le signale.
"""
from __future__ import annotations

import json
import subprocess
import sys

#: `triton` est le compilateur de noyaux GPU de PyTorch. Il ne porte pas le
#: préfixe `nvidia-` mais n'a pas davantage d'usage sur processeur.
HORS_PREFIXE = frozenset({"triton"})


def installes() -> list[str]:
    sortie = subprocess.run(
        ["uv", "pip", "list", "--format=json"],
        check=True, capture_output=True, text=True).stdout
    return [p["name"] for p in json.loads(sortie)]


def main() -> int:
    noms = installes()
    a_retirer = sorted(n for n in noms
                       if n.startswith("nvidia-") or n.lower() in HORS_PREFIXE)

    if not a_retirer:
        print("aucun paquet CUDA installe, rien a purger.")
        return 0

    print(f"{len(a_retirer)} paquet(s) CUDA a retirer :")
    for n in a_retirer:
        print(f"  {n}")

    subprocess.run(["uv", "pip", "uninstall", *a_retirer], check=True)

    restants = [n for n in installes()
                if n.startswith("nvidia-") or n.lower() in HORS_PREFIXE]
    if restants:
        # Echouer bruyamment plutot que de laisser une image regonflee passer
        # inapercue : c'est precisement le mode de defaillance qui a coute la
        # premiere construction.
        print(f"ECHEC : {restants} sont toujours installes.", file=sys.stderr)
        return 1

    print(f"purge faite, {len(a_retirer)} paquet(s) retire(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

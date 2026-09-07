#!/usr/bin/env python3
"""Télécharge les trois modèles dans le cache de l'image, à la construction.

POURQUOI CE FICHIER EXISTE PLUTOT QU'UN HEREDOC DANS LE DOCKERFILE
La première construction réelle, le 2026-09-07, a échoué **avant même de
commencer** :

    unable to understand line from huggingface_hub import snapshot_download
    failed to run step ID: build: failed to scan dependencies: exit status 1

`az acr build` analyse les dépendances du Dockerfile avant de le construire, et
son analyseur ne comprend pas la syntaxe heredoc : il lit les lignes Python
comme des instructions Dockerfile. Un script dans un vrai fichier n'a pas ce
problème, et se relit mieux.

POURQUOI CUIRE LES MODELES DANS L'IMAGE
Sans cela ils seraient téléchargés au premier appel, dans un stockage de
conteneur éphémère : plusieurs minutes à chaque démarrage, et un échec
silencieux si le réseau sortant est fermé (D35 en a fait la règle générale).
"""
from __future__ import annotations

from huggingface_hub import snapshot_download

#: Les trois modèles, avec leur taille relevée sur le cache local. Ils sont
#: nommés ici en clair, et non lus depuis le code du projet, parce que la
#: construction doit rester lisible sans exécuter l'application.
#: Les noms retenus sont ceux de D47 (embeddings) et D48 (génération SQL), plus
#: le reranker léger du chantier 1.
MODELES = (
    ("intfloat/multilingual-e5-small", "471 Mo, embeddings"),
    ("cross-encoder/mmarco-mMiniLMv2-L12-H384-v1", "470 Mo, reranking"),
    ("Qwen/Qwen2.5-Coder-0.5B-Instruct", "954 Mo, generation SQL"),
)


def main() -> int:
    for depot, quoi in MODELES:
        print(f"telechargement de {depot} ({quoi})", flush=True)
        chemin = snapshot_download(depot)
        print(f"  -> {chemin}", flush=True)
    print(f"{len(MODELES)} modeles cuits dans l'image.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

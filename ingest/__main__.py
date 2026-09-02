"""Ingestion complète : `python -m ingest`.

L'ingestion est **hors ligne et faite une fois**, en reconstruction totale. Ce
n'est pas une limite, c'est ce qui garantit l'invariant « exactement un
`is_latest` par groupe de versions » : une réindexation partielle pourrait
laisser deux versions courantes, et le système citerait alors un document
périmé sans qu'aucune erreur n'apparaisse.

Rien n'est indexé si un contrôle échoue. Un index incomplet ne se signale pas :
il rend des réponses plausibles et fausses.
"""
from __future__ import annotations

import argparse
import shutil
import sys
import time

from common.config import CONFIG
from common.embeddings import Encodeur

from .chunking import chunks_du_corpus
from .controles import afficher, controler
from .index import construire_dense, construire_lexical, ecrire_manifeste
from .loaders import charger_corpus


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Ingere le corpus documentaire Sorabel.")
    ap.add_argument("--controles-seuls", action="store_true",
                    help="charge et controle, sans construire d'index")
    args = ap.parse_args(argv)

    t0 = time.time()
    print(f"corpus : {CONFIG.corpus}")
    documents = charger_corpus(CONFIG.corpus)
    chunks = chunks_du_corpus(documents)
    print(f"{len(documents)} documents, {len(chunks)} chunks, {time.time() - t0:.1f}s\n")

    code = afficher(controler(documents, chunks))
    if code:
        print("\nRIEN N'A ETE INDEXE : un index incomplet rend des reponses "
              "plausibles et fausses.", file=sys.stderr)
        return code
    if args.controles_seuls:
        return 0

    encodeur = Encodeur()
    print(f"\nmodele : {encodeur.nom}")
    if CONFIG.index.exists():
        shutil.rmtree(CONFIG.index)   # reconstruction totale, cf. l'invariant is_latest

    t1 = time.time()
    combien = construire_dense(chunks, CONFIG.index, encodeur)
    print(f"  dense   : {combien} chunks en {time.time() - t1:.1f}s, "
          f"dimension {encodeur.dimension}")

    t1 = time.time()
    par_type = construire_lexical(chunks, CONFIG.index)
    print(f"  lexical : {sum(par_type.values())} chunks en {time.time() - t1:.1f}s, "
          f"un index par doc_type -> {par_type}")

    ecrire_manifeste(CONFIG.index, {
        "genere_le": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "modele": encodeur.nom,
        "dimension": encodeur.dimension,
        "documents": len(documents),
        "chunks": len(chunks),
        "groupes_de_versions": len({d.version_group for d in documents}),
        "chunks_par_doc_type": par_type,
    })
    print(f"\nindex ecrit sous {CONFIG.index}")
    print(f"total {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

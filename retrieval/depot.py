"""Accès aux deux index. Une seule instance par processus.

Le dépôt est **en lecture seule** : l'ingestion est hors ligne et se fait en
reconstruction totale. Rien ici n'écrit dans l'index.

Le filtrage par métadonnée s'applique **avant** la recherche, sur les deux
branches. Côté dense c'est la clause `where` de Chroma. Côté lexical, aucune
bibliothèque BM25 usuelle ne filtre : l'index est donc partitionné par
`doc_type` à l'ingestion, et on ne charge que les partitions autorisées.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

from common.config import CONFIG
from common.embeddings import jetons
from ingest.index import COLLECTION_DENSE, FICHIER_LEXICAL, _client, lire_manifeste


@dataclass(frozen=True)
class Passage:
    """Un candidat, tel qu'il sort d'un index. Le rang est attribué par l'appelant."""

    chunk_id: str
    texte: str
    score: float
    metadonnees: dict

    @property
    def doc_id(self) -> str:
        return str(self.metadonnees.get("doc_id", ""))

    @property
    def version_group(self) -> str:
        return str(self.metadonnees.get("version_group", self.doc_id))


class Depot:
    """Les index, chargés paresseusement et gardés en mémoire."""

    def __init__(self, racine: Path | None = None) -> None:
        self.racine = racine or CONFIG.index

    @cached_property
    def manifeste(self) -> dict:
        return lire_manifeste(self.racine)

    @cached_property
    def _dense(self):  # noqa: ANN202
        return _client(self.racine).get_collection(COLLECTION_DENSE)

    @cached_property
    def _lexical(self) -> dict[str, dict]:
        chemin = self.racine / FICHIER_LEXICAL
        if not chemin.exists():
            raise FileNotFoundError(
                f"index lexical absent : {chemin}. Lancer `python -m ingest`."
            )
        return json.loads(chemin.read_text(encoding="utf-8"))

    # --- Recherche dense ----------------------------------------------------

    def dense(self, vecteur: list[float], doc_types: set[str], n: int) -> list[Passage]:
        """Top n par cosinus, borné aux `doc_types` autorisés.

        Le filtre est passé à Chroma, il n'est pas appliqué au résultat : sans
        cela le passage interdit serait lu, et la profondeur `n` serait consommée
        par des candidats hors périmètre.
        """
        if not doc_types:
            return []
        brut = self._dense.query(
            query_embeddings=[vecteur],
            n_results=n,
            where={"doc_type": {"$in": sorted(doc_types)}},
            include=["documents", "metadatas", "distances"],
        )
        return [
            # Chroma rend une DISTANCE cosinus : la similarité est son complément.
            Passage(chunk_id=i, texte=t, score=1.0 - d, metadonnees=m)
            for i, t, m, d in zip(
                brut["ids"][0], brut["documents"][0],
                brut["metadatas"][0], brut["distances"][0],
            )
        ]

    # --- Recherche lexicale -------------------------------------------------

    def lexical(self, question: str, doc_types: set[str], n: int) -> list[Passage]:
        """Top n par BM25, sur les seules partitions autorisées.

        Les partitions sont fusionnées en un corpus unique avant scoring : un
        BM25 par partition donnerait des scores non comparables entre elles,
        puisque l'IDF dépend du corpus.
        """
        from rank_bm25 import BM25Okapi

        corpus: list[list[str]] = []
        ids: list[str] = []
        for doc_type in sorted(doc_types):
            part = self._lexical.get(doc_type)
            if not part:
                continue
            corpus.extend(part["jetons"])
            ids.extend(part["chunk_ids"])
        if not corpus:
            return []

        scores = BM25Okapi(corpus).get_scores(jetons(question))
        meilleurs = sorted(range(len(ids)), key=lambda i: scores[i], reverse=True)[:n]
        retenus = [ids[i] for i in meilleurs if scores[i] > 0]
        if not retenus:
            return []

        details = self.par_ids(retenus)
        return [
            Passage(chunk_id=ids[i], texte=details[ids[i]].texte,
                    score=float(scores[i]), metadonnees=details[ids[i]].metadonnees)
            for i in meilleurs if ids[i] in details
        ]

    # --- Accès direct -------------------------------------------------------

    def par_ids(self, chunk_ids: list[str]) -> dict[str, Passage]:
        if not chunk_ids:
            return {}
        brut = self._dense.get(ids=chunk_ids, include=["documents", "metadatas"])
        return {
            i: Passage(chunk_id=i, texte=t, score=0.0, metadonnees=m)
            for i, t, m in zip(brut["ids"], brut["documents"], brut["metadatas"])
        }

    def par_reference(self, reference: str, doc_types: set[str]) -> list[Passage]:
        """Court-circuit d'E2 : un filtre exact, sans aucun embedding.

        C'est un `WHERE reference = ...`, pas une similarité : le résultat est
        déterministe et ne peut pas se tromper de référence. Corollaire utile,
        le modèle d'embedding n'est jamais chargé pour ce chemin.
        """
        if not doc_types:
            return []
        brut = self._dense.get(
            where={"$and": [{"reference": reference.upper()},
                            {"doc_type": {"$in": sorted(doc_types)}}]},
            include=["documents", "metadatas"],
        )
        return [
            Passage(chunk_id=i, texte=t, score=0.0, metadonnees=m)
            for i, t, m in zip(brut["ids"], brut["documents"], brut["metadatas"])
        ]

    def documents(self, doc_types: set[str]) -> list[dict]:
        """Inventaire du corpus autorisé, un enregistrement par document."""
        if not doc_types:
            return []
        brut = self._dense.get(
            where={"doc_type": {"$in": sorted(doc_types)}}, include=["metadatas"]
        )
        par_doc: dict[str, dict] = {}
        for m in brut["metadatas"]:
            par_doc.setdefault(str(m["doc_id"]), {
                "doc_id": m["doc_id"], "titre": m["titre"], "reference": m["reference"],
                "version": m["version"], "date": m["date"], "doc_type": m["doc_type"],
                "is_latest": m["is_latest"],
            })
        return sorted(par_doc.values(), key=lambda d: (d["doc_type"], d["reference"], d["version"]))

    def document(self, doc_id: str, doc_types: set[str]) -> tuple[str, dict] | None:
        """Un document entier, recollé depuis ses chunks, dans l'ordre."""
        brut = self._dense.get(
            where={"$and": [{"doc_id": doc_id}, {"doc_type": {"$in": sorted(doc_types)}}]},
            include=["documents", "metadatas"],
        )
        if not brut["ids"]:
            return None
        ordre = sorted(
            zip(brut["ids"], brut["documents"], brut["metadatas"]),
            key=lambda t: int(t[0].rsplit("#", 1)[-1]),
        )
        texte = "\n\n".join(t for _, t, _ in ordre)
        meta = dict(ordre[0][2])
        meta.pop("section", None)
        return texte, meta

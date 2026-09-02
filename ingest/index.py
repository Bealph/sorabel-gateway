"""Construction des deux index : dense dans Chroma, lexical en BM25.

**Deux index séparés, et c'est un choix.** Un moteur qui fusionne lexical et
dense en interne donnerait le même résultat final, mais rendrait la baseline
« dense seule » impossible à isoler proprement. Or E6 exige de mesurer le gain
brique par brique. La séparation coûte quelques dizaines de lignes ici et rend
l'ablation lisible au lot 3.

**Un index BM25 PAR COLLECTION.** Aucune bibliothèque BM25 usuelle n'a de clause
de filtrage : filtrer le résultat après coup paraît équivalent et ne l'est pas.
Le passage interdit aurait été lu, la profondeur `n` serait consommée par des
candidats hors périmètre, et aucun refus ne serait journalisé. On partitionne
donc en amont, ce qui rend le filtrage de gouvernance structurel.
"""
from __future__ import annotations

import json
import os
from collections import defaultdict
from pathlib import Path

from common.embeddings import Encodeur, jetons

from .document import Chunk

#: Chroma émet de la télémétrie réseau à chaque appel. Une gateway gouvernée
#: n'envoie rien qu'elle n'ait décidé d'envoyer, et cela bruite la sortie.
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

COLLECTION_DENSE = "sorabel"
FICHIER_LEXICAL = "bm25.json"


def _client(racine: Path):  # noqa: ANN202
    import chromadb
    from chromadb.config import Settings

    racine.mkdir(parents=True, exist_ok=True)
    # La variable d'environnement ne suffit pas : Chroma tente quand meme
    # l'envoi et echoue bruyamment. On le lui interdit explicitement.
    return chromadb.PersistentClient(
        path=str(racine / "chroma"),
        settings=Settings(anonymized_telemetry=False),
    )


def construire_dense(chunks: list[Chunk], racine: Path, encodeur: Encodeur) -> int:
    """Index dense. Le cosinus est explicite : par défaut Chroma utilise L2."""
    client = _client(racine)
    if COLLECTION_DENSE in {c.name for c in client.list_collections()}:
        client.delete_collection(COLLECTION_DENSE)
    collection = client.create_collection(
        COLLECTION_DENSE,
        metadata={
            "hnsw:space": "cosine",
            # HNSW est une recherche APPROCHEE : mesuré le 2026-09-02, la meme
            # requete rendait des voisins differents d'un processus a l'autre,
            # alors que le vecteur de requete etait identique au bit pres. Sur un
            # corpus aussi template, les quasi ex aequo sont innombrables et la
            # traversee du graphe tranche differemment a chaque fois.
            # Une mesure qui n'est pas reproductible n'est pas une mesure : on
            # eleve search_ef bien au-dela de la profondeur demandee, ce qui rend
            # la recherche quasi exacte a l'echelle de 910 chunks.
            "hnsw:search_ef": 512,
            "hnsw:construction_ef": 256,
        },
    )

    vecteurs = encodeur.passages([c.texte for c in chunks])
    # Chroma limite la taille d'un lot : on découpe, sans quoi 910 chunks
    # passeraient encore et un corpus plus grand échouerait un jour.
    lot = 500
    for i in range(0, len(chunks), lot):
        tranche = chunks[i:i + lot]
        collection.add(
            ids=[c.chunk_id for c in tranche],
            embeddings=vecteurs[i:i + lot],
            documents=[c.texte for c in tranche],
            metadatas=[c.metadonnees() for c in tranche],
        )
    return collection.count()


def construire_lexical(chunks: list[Chunk], racine: Path) -> dict[str, int]:
    """Index lexical, un par `doc_type`, persisté en JSON.

    On stocke les jetons, pas l'objet BM25 : un pickle se casse au changement de
    version de bibliothèque, et le reconstruire coûte quelques millisecondes à
    cette échelle. Un artefact qu'on ne sait plus relire n'est pas un artefact.
    """
    par_type: dict[str, list[Chunk]] = defaultdict(list)
    for c in chunks:
        par_type[c.doc_type].append(c)

    contenu = {
        doc_type: {
            "chunk_ids": [c.chunk_id for c in vises],
            "jetons": [jetons(c.texte) for c in vises],
        }
        for doc_type, vises in par_type.items()
    }
    racine.mkdir(parents=True, exist_ok=True)
    (racine / FICHIER_LEXICAL).write_text(
        json.dumps(contenu, ensure_ascii=False), encoding="utf-8"
    )
    return {k: len(v["chunk_ids"]) for k, v in contenu.items()}


def ecrire_manifeste(racine: Path, infos: dict) -> None:
    """Ce que l'index contient, et avec quoi il a été construit.

    Sans cela, un index et un modèle d'embedding peuvent se désynchroniser en
    silence : les dimensions coïncident, les vecteurs ne veulent plus rien dire,
    et la recherche renvoie des résultats plausibles et faux.
    """
    (racine / "manifeste.json").write_text(
        json.dumps(infos, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def lire_manifeste(racine: Path) -> dict:
    chemin = racine / "manifeste.json"
    if not chemin.exists():
        raise FileNotFoundError(
            f"index absent ou incomplet : {chemin}. Lancer `python -m ingest`."
        )
    return json.loads(chemin.read_text(encoding="utf-8"))

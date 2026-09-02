"""Du Document au Chunk : découpage, report d'en-tête, arbitrage de version.

Trois règles, toutes issues du chantier 1 :

1. On découpe selon la **structure**, pas selon un nombre de caractères. Les
   documents sont courts et sectionnés : une coupe à taille fixe casserait une
   fiche ou fusionnerait des sections sans rapport.
2. Chaque chunk porte l'**en-tête de son document**. Sans cela, 170 des 400
   fichiers du corpus ont un texte rigoureusement identique à un autre.
3. Un seul `is_latest` par groupe de versions, calculé ici et vérifié.
"""
from __future__ import annotations

from collections import defaultdict

from .document import Chunk, Document, version_en_tuple


def marquer_versions(documents: list[Document]) -> dict[str, bool]:
    """Rend, par doc_id, la réponse à « est-ce la version courante ? ».

    Le tri porte sur la version puis sur la date : deux exemplaires d'un même
    groupe ne peuvent pas être courants tous les deux, et l'invariant est
    contrôlé plus loin plutôt que supposé.
    """
    par_groupe: dict[str, list[Document]] = defaultdict(list)
    for doc in documents:
        par_groupe[doc.version_group].append(doc)

    courant: dict[str, bool] = {}
    for membres in par_groupe.values():
        gagnant = max(membres, key=lambda d: (version_en_tuple(d.version), d.date))
        for doc in membres:
            courant[doc.doc_id] = doc.doc_id == gagnant.doc_id
    return courant


def decouper(doc: Document, is_latest: bool) -> list[Chunk]:
    """Un chunk par section, ou un seul si le document n'en a pas.

    Le texte indexé est toujours `en-tête + titre de section + corps`. C'est ce
    préfixe qui distingue la section « 3. Mise en service » d'une notice de
    disjoncteur de la même section, mot pour mot identique, d'une notice de
    projecteur LED.
    """
    chunks: list[Chunk] = []
    for i, (section, corps) in enumerate(doc.sections):
        if not corps.strip():
            continue
        tete = doc.entete if not section else f"{doc.entete}\n{section}"
        chunks.append(
            Chunk(
                chunk_id=f"{doc.doc_id}#{i}",
                doc_id=doc.doc_id,
                doc_type=doc.doc_type,
                titre=doc.titre,
                reference=doc.reference,
                version=doc.version,
                date=doc.date,
                version_group=doc.version_group,
                is_latest=is_latest,
                section=section,
                texte=f"{tete}\n{corps.strip()}",
            )
        )
    return chunks


def chunks_du_corpus(documents: list[Document]) -> list[Chunk]:
    courant = marquer_versions(documents)
    chunks: list[Chunk] = []
    for doc in documents:
        chunks.extend(decouper(doc, courant[doc.doc_id]))
    return chunks

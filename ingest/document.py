"""Le Document canonique et le Chunk : la seule forme que la suite du pipeline connaît.

Quatre formats entrent (PDF fiche, PDF notice, HTML procédure, Markdown note),
une seule forme sort. C'est ce qui permet au chunking, à l'indexation et à la
recherche d'ignorer complètement l'origine des fichiers.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

#: Motif d'une référence produit. Le tiret est obligatoire, la casse indifférente.
#: Il sert au court-circuit exact de E2 comme à l'extraction des métadonnées.
MOTIF_REF = re.compile(r"REF-\d{4}", re.IGNORECASE)


@dataclass(frozen=True)
class Document:
    """Un exemplaire, dans une version donnée. Deux versions font deux Documents."""

    doc_id: str          # identifiant stable, unique : le nom de fichier sans extension
    doc_type: str        # fiche_technique | notice | procedure_sav | note_interne
    titre: str
    reference: str       # REF-XXXX quand le document en porte une, sinon son code propre
    version: str
    date: str            # ISO, AAAA-MM-JJ
    version_group: str   # ce qui réunit les versions d'un même document
    texte: str
    sections: list[tuple[str, str]] = field(default_factory=list)  # (titre, corps)
    source: str = ""     # chemin relatif, pour la traçabilité

    @property
    def entete(self) -> str:
        """La ligne recopiée en tête de CHAQUE chunk.

        Ce n'est pas un confort de lecture. Mesuré sur le corpus fourni : sans
        leur titre, les 80 notices partagent UN seul corps de texte, et les 90
        procédures SAV aussi. Sans ce report, le moteur voit 80 chunks
        rigoureusement identiques et en cite un au hasard, avec des métadonnées
        parfaitement formées. E1 serait formellement satisfaite et la citation
        fausse, sans qu'aucune garde puisse le voir.
        """
        return f"{self.titre} | {self.reference} | v{self.version}"


@dataclass(frozen=True)
class Chunk:
    """Une unité indexable. Son texte porte toujours l'en-tête de son document."""

    chunk_id: str
    doc_id: str
    doc_type: str
    titre: str
    reference: str
    version: str
    date: str
    version_group: str
    is_latest: bool
    section: str
    texte: str

    def metadonnees(self) -> dict[str, str | bool]:
        """Ce que l'index stocke à côté du vecteur.

        Chaque champ est là pour un usage nommé, et pas parce qu'il était
        disponible : `doc_type` porte le filtrage de gouvernance (E4),
        `reference` le court-circuit exact (E2), `is_latest` l'arbitrage de
        version, et le trio titre/reference/date la citation exigée par E1.
        """
        return {
            "doc_id": self.doc_id,
            "doc_type": self.doc_type,
            "titre": self.titre,
            "reference": self.reference,
            "version": self.version,
            "date": self.date,
            "version_group": self.version_group,
            "is_latest": self.is_latest,
            "section": self.section,
        }


def version_en_tuple(version: str) -> tuple[int, ...]:
    """Ordonne « 1.10 » après « 1.9 », ce qu'une comparaison de chaînes rate.

    Le corpus fourni n'a que 1.0, 1.1, 2.0 et 2.1, donc la comparaison textuelle
    y suffirait. Elle cesserait d'être juste au premier 1.10, et une citation de
    version périmée ne se voit pas à l'usage.
    """
    return tuple(int(n) for n in re.findall(r"\d+", version)) or (0,)

"""Lecture de la matrice d'accès, source de vérité unique des droits (D21).

Le serveur la charge **au démarrage** et refuse de démarrer si le profil demandé
n'y figure pas. Un profil inconnu qui se rabattrait sur un défaut permissif est
le pire des comportements : il ne produit aucune erreur et ouvre des droits.

Ce module ne décide rien. Il lit, il valide la forme, et il expose les droits du
profil du processus. La cohérence de la matrice, elle, est contrôlée par
`governance/verifier_matrice.py`, qui la compare à des ancres écrites en dur.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .config import CONFIG


class ProfilInconnu(RuntimeError):
    """Le profil demandé n'est pas dans la matrice. On refuse de démarrer."""


@dataclass(frozen=True)
class Droits:
    """Ce qu'un profil peut faire. Immuable pour la vie du processus (D28)."""

    profil: str
    tools: frozenset[str]
    collections: frozenset[str]
    doc_types: frozenset[str]
    tables: frozenset[str]
    colonnes_interdites: frozenset[str]

    def autorise(self, tool: str) -> bool:
        return tool in self.tools


@lru_cache(maxsize=1)
def _charger(chemin: str) -> dict:
    import yaml

    return yaml.safe_load(Path(chemin).read_text(encoding="utf-8"))


def droits(profil: str | None = None, chemin: Path | None = None) -> Droits:
    """Les droits du profil, ou `ProfilInconnu` si la matrice ne le connaît pas."""
    matrice = _charger(str(chemin or CONFIG.matrice))
    nom = profil or CONFIG.profil
    profils = matrice.get("profils") or {}
    if nom not in profils:
        raise ProfilInconnu(
            f"profil {nom!r} absent de la matrice. Connus : {sorted(profils)}. "
            "Verifier SORABEL_PROFILE."
        )
    p = profils[nom]
    collections = matrice.get("collections") or {}
    mes_collections = list(p.get("collections") or [])
    inconnues = sorted(set(mes_collections) - set(collections))
    if inconnues:
        raise ProfilInconnu(f"collections inconnues pour {nom!r} : {inconnues}")

    return Droits(
        profil=nom,
        tools=frozenset(p.get("tools") or []),
        collections=frozenset(mes_collections),
        # C'est `doc_type` qui porte le filtrage, pas le nom de collection : un
        # document deplace reste gouverne.
        doc_types=frozenset(collections[c]["doc_type"] for c in mes_collections),
        tables=frozenset(p.get("tables") or []),
        colonnes_interdites=frozenset(p.get("colonnes_interdites") or []),
    )


def catalogue(chemin: Path | None = None) -> frozenset[str]:
    """Les huit tools du catalogue. Un nom hors catalogue se refuse comme un
    tool non autorisé, il ne provoque pas d'erreur technique."""
    matrice = _charger(str(chemin or CONFIG.matrice))
    cat = matrice.get("catalogue") or {}
    return frozenset((cat.get("rag") or []) + (cat.get("sql") or []))


def lexique_refus(chemin: Path | None = None) -> dict[str, list[str]]:
    """Termes qui désignent une ressource retirée, pour le refus explicite.

    Aucune valeur de sécurité : une liste de mots se contourne. Elle rend le
    refus imputable, donc journalisable et démontrable (E5).
    """
    matrice = _charger(str(chemin or CONFIG.matrice))
    return dict(matrice.get("lexique_refus") or {})

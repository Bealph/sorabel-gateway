"""Chemins et reglages, lus une seule fois depuis l'environnement.

Tout artefact persistant s'ecrit sous SORABEL_DATA_DIR (D35). Le motif : le
stockage d'un conteneur est ephemere par defaut, et un index ecrit ailleurs
disparait au redemarrage SANS erreur. Vertu secondaire, en local : le chemin est
explicite au lieu d'etre implicite.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent


def _chemin(variable: str, defaut: Path) -> Path:
    brut = os.environ.get(variable)
    return Path(brut).expanduser() if brut else defaut


@dataclass(frozen=True)
class Config:
    """Reglages du processus. Immuable : on ne reconfigure pas en cours de route."""

    racine: Path = RACINE
    data_dir: Path = _chemin("SORABEL_DATA_DIR", RACINE / "data")
    corpus: Path = _chemin("SORABEL_CORPUS", RACINE / "data" / "corpus")
    base_sql: Path = _chemin("SORABEL_DB", RACINE / "data" / "sorabel.db")
    journal: Path = _chemin("GATEWAY_JOURNAL", RACINE / "logs" / "journal.jsonl")
    matrice: Path = RACINE / "governance" / "matrice.yaml"

    @property
    def index(self) -> Path:
        """Repertoire de l'index documentaire. Chroma embarque (D45), pas de service."""
        return self.data_dir / "index"

    @property
    def profil(self) -> str:
        """Profil du processus, fixe au LANCEMENT (D28). Jamais un parametre d'appel."""
        return os.environ.get("SORABEL_PROFILE", "support")


CONFIG = Config()

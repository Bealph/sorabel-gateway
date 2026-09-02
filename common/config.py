"""Chemins et reglages, lus une seule fois depuis l'environnement.

Tout artefact persistant s'ecrit sous SORABEL_DATA_DIR (D35). Le motif : le
stockage d'un conteneur est ephemere par defaut, et un index ecrit ailleurs
disparait au redemarrage SANS erreur. Vertu secondaire, en local : le chemin est
explicite au lieu d'etre implicite.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

# Pose AVANT tout import de chromadb, qui lit ce reglage a l'import. Chroma tente
# sinon un envoi reseau a chaque appel, et echoue bruyamment sur stderr. Une
# gateway gouvernee n'emet rien qu'elle n'ait decide d'emettre.
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
os.environ.setdefault("CHROMA_ANONYMIZED_TELEMETRY", "False")

# La variable ne suffit pas sur chromadb 0.5.x : le client de telemetrie est
# instancie quand meme, son appel ECHOUE, et l'echec est journalise en erreur a
# chaque requete. Rien ne part donc sur le reseau, mais le bruit reste, et il
# n'a rien a faire dans la sortie d'une gateway. On coupe le journal fautif.
logging.getLogger("chromadb.telemetry").setLevel(logging.CRITICAL)

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

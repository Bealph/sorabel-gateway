"""Couche 1 et couche 4 : exécution en lecture seule, avec un délai.

**Ce que la couche 1 fait, et ce qu'elle ne fait pas.** `mode=ro` empêche
d'écrire dans le fichier ouvert. Elle n'empêche pas d'attacher une autre base et
d'y écrire : mesuré le 2026-09-02, `PRAGMA query_only = 0` est accepté, puis
`ATTACH`, puis `CREATE` et `INSERT` dans la base attachée. Le dossier
présentait cette couche comme le « garde-fou ultime » ; c'est faux, et la phrase
a été corrigée. Ce qui interdit réellement l'écriture, c'est la couche 2.

Elle reste utile pour ce qu'elle fait vraiment : une écriture qui aurait franchi
l'analyse syntaxique n'atteindrait pas la base métier. C'est une seconde
serrure, pas la serrure.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from common.config import CONFIG

#: Délai maximal d'une requête. L'incident du brief, la base verrouillée un
#: vendredi soir, est adressé par ce délai et par le LIMIT de la couche 4.
DELAI_S = 5.0

#: Nombre d'instructions VM entre deux vérifications du délai. Assez bas pour
#: interrompre vite, assez haut pour ne pas peser sur une requête courte.
PAS_VM = 1000


@dataclass
class Resultat:
    colonnes: list[str]
    lignes: list[list]
    tronque: bool = False


class ErreurExecution(RuntimeError):
    """L'exécution a échoué ou a été interrompue. Jamais silencieuse."""


def _connexion(base: Path) -> sqlite3.Connection:
    if not base.exists():
        raise ErreurExecution(f"base absente : {base}")
    cx = sqlite3.connect(f"file:{base}?mode=ro", uri=True, timeout=DELAI_S)
    cx.execute("PRAGMA query_only = ON")
    # Interdit le chargement d'extensions : une extension pourrait rendre des
    # fonctions à effet de bord, et l'AST ne saurait pas qu'elles écrivent.
    cx.execute("PRAGMA trusted_schema = OFF")
    return cx


def executer(sql: str, limite: int, base: Path | None = None) -> Resultat:
    """Exécute un SELECT déjà validé. N'accepte rien qui n'ait passé les gardes."""
    cx = _connexion(base or CONFIG.base_sql)
    depasse = {"delai": False}

    import time
    debut = time.monotonic()

    def surveiller() -> int:
        # Rendre non nul interrompt la requête. C'est ainsi que SQLite permet
        # d'imposer un délai à une requête déjà partie.
        if time.monotonic() - debut > DELAI_S:
            depasse["delai"] = True
            return 1
        return 0

    cx.set_progress_handler(surveiller, PAS_VM)
    try:
        curseur = cx.execute(sql)
        colonnes = [d[0] for d in (curseur.description or [])]
        lignes = [list(r) for r in curseur.fetchmany(limite + 1)]
    except sqlite3.OperationalError as e:
        if depasse["delai"]:
            raise ErreurExecution(
                f"Requete interrompue apres {DELAI_S} s. Elle est trop lourde "
                "pour la gateway : la restreindre.") from e
        raise ErreurExecution(f"Erreur SQLite : {e}") from e
    finally:
        cx.set_progress_handler(None, 0)
        cx.close()

    # Une troncature qui ne se dit pas est un résultat faux. On lit une ligne de
    # plus que la limite précisément pour savoir s'il y en avait davantage.
    tronque = len(lignes) > limite
    return Resultat(colonnes, lignes[:limite], tronque)

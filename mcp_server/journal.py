"""Le journal de la gateway : une ligne JSONL par appel, autorisé comme refusé.

**Une ligne par appel, exactement.** C'est ce qu'E5 exige, et c'est ce que la
suite d'acceptance vérifie en comptant les entrées d'une session de démonstration.
Un appel qui n'y figure pas est un angle mort d'audit ; une entrée en trop rend
le compte faux.

**JSONL et pas une base** (D33). Une ligne complète est écrite d'un coup et
terminée par un saut de ligne : un arrêt brutal peut perdre la dernière ligne,
jamais corrompre les précédentes. Et cela se lit sans outil, ce qui compte le
jour où l'on ouvre le journal devant quelqu'un.

**Ce qui n'y entre pas.** Aucune valeur issue de la base. Le SQL généré y entre,
parce qu'E3 l'exige et qu'un refus sans sa requête n'est pas auditable ; les
lignes de résultat, non. Un compte suffit.
"""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

#: Champs imposés par le contrat d'intégration. Les autres sont des ajouts
#: utiles au diagnostic, et un client qui les ignore reste conforme.
CHAMPS_CONTRAT = ("timestamp", "profile", "tool", "arguments", "status", "message")


class Journal:
    """Écriture en ajout, sérialisée entre fils d'exécution."""

    def __init__(self, chemin: Path | None = None) -> None:
        brut = os.environ.get("GATEWAY_JOURNAL")
        self.chemin = Path(brut) if brut else (chemin or Path("logs/journal.jsonl"))
        self._verrou = threading.Lock()

    def consigner(self, *, profil: str, tool: str, arguments: dict, statut: str,
                  message: str = "", code: str = "", duree_ms: float | None = None,
                  ressources: dict | None = None, sql: str = "") -> None:
        """Écrit une entrée. Une défaillance du journal ne casse jamais l'appel.

        Ce choix se discute : un journal muet est un risque de conformité. Mais
        un appel qui échoue *parce que* le journal est plein serait pire, et le
        client n'y pourrait rien. L'échec d'écriture part sur la sortie d'erreur,
        où il reste visible.
        """
        entree = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "profile": profil,
            "tool": tool,
            "arguments": arguments,
            "status": statut,
            "message": message,
        }
        if code:
            entree["code"] = code
        if duree_ms is not None:
            entree["duree_ms"] = round(duree_ms, 1)
        if ressources:
            # Les ressources TOUCHEES, pas les valeurs lues. C'est ce qui permet
            # a un audit E5 de compter les acces tentes a une colonne sensible.
            entree["ressources"] = ressources
        if sql:
            entree["sql"] = sql

        ligne = json.dumps(entree, ensure_ascii=False) + "\n"
        try:
            with self._verrou:
                self.chemin.parent.mkdir(parents=True, exist_ok=True)
                with self.chemin.open("a", encoding="utf-8") as f:
                    f.write(ligne)
        except OSError as e:  # noqa: BLE001
            import sys
            print(f"journal illisible ({self.chemin}) : {e}", file=sys.stderr)

    def lire(self) -> list[dict]:
        """Relit le journal. Sert au diagnostic et à la démonstration."""
        if not self.chemin.exists():
            return []
        return [json.loads(ligne) for ligne
                in self.chemin.read_text(encoding="utf-8").splitlines() if ligne.strip()]

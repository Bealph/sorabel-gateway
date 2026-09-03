"""Un client MCP persistant, utilisable depuis du code synchrone.

**Pourquoi ce module existe.** Le protocole MCP en stdio est asynchrone et
tient dans un gestionnaire de contexte : ouvrir une session, appeler, fermer.
Une page Streamlit, elle, est synchrone et se réexécute à chaque interaction. En
ouvrant une session par appel, chaque clic relancerait un processus serveur et
rechargerait les modèles, soit plusieurs dizaines de secondes par bouton.

On garde donc **une session ouverte par profil**, dans un fil qui porte sa
propre boucle d'événements, et on lui soumet des appels depuis le fil principal.
Le processus serveur reste vivant, ses modèles restent chargés.

**Ce n'est pas un contournement du protocole**, c'est ce que fait tout client
MCP durable : un IDE ne relance pas son serveur à chaque complétion.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import threading
from concurrent.futures import Future
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

RACINE = Path(__file__).resolve().parent.parent


@dataclass
class Outil:
    """Un tool tel que le PROTOCOLE le décrit, schéma compris."""

    nom: str
    description: str
    schema: dict = field(default_factory=dict)

    @property
    def resume(self) -> str:
        return self.description.strip().splitlines()[0] if self.description else ""


class ClientPersistant:
    """Une session MCP ouverte, pilotée depuis un fil synchrone."""

    def __init__(self, profil: str, journal: Path | None = None) -> None:
        self.profil = profil
        self.journal = journal
        self.outils: list[Outil] = []
        self.erreur: str = ""
        self._boucle: asyncio.AbstractEventLoop | None = None
        self._pret = threading.Event()
        self._arret: asyncio.Future | None = None
        self._fil = threading.Thread(target=self._tourner, daemon=True)
        self._fil.start()
        # Le demarrage lance un processus serveur, qui prechauffe ses modeles :
        # on attend qu'il ait repondu a `initialize`, pas qu'il soit chaud.
        self._pret.wait(timeout=180)

    # --- côté fil dédié ----------------------------------------------------

    def _tourner(self) -> None:
        asyncio.run(self._vivre())

    async def _vivre(self) -> None:
        self._boucle = asyncio.get_running_loop()
        self._arret = self._boucle.create_future()
        env = {**os.environ, "SORABEL_PROFILE": self.profil}
        if self.journal:
            env["GATEWAY_JOURNAL"] = str(self.journal)
        params = StdioServerParameters(
            command=sys.executable, args=["-m", "mcp_server.server"],
            env=env, cwd=str(RACINE))
        try:
            async with stdio_client(params) as (lecture, ecriture):
                async with ClientSession(lecture, ecriture) as session:
                    self._session = session
                    await session.initialize()
                    listees = await session.list_tools()
                    self.outils = [
                        Outil(t.name, t.description or "",
                              dict(t.inputSchema or {}))
                        for t in listees.tools
                    ]
                    self._pret.set()
                    await self._arret            # vit jusqu'à `fermer()`
        except Exception as e:  # noqa: BLE001
            self.erreur = f"{type(e).__name__}: {e}"
            self._pret.set()

    # --- côté appelant synchrone -------------------------------------------

    def appeler(self, tool: str, arguments: dict, delai: float = 900) -> dict:
        """Un appel, rendu tel que le client le reçoit : l'enveloppe décodée."""
        if self.erreur:
            return {"status": "error", "payload": {},
                    "message": f"session indisponible : {self.erreur}"}

        async def travail() -> dict:
            reponse = await self._session.call_tool(tool, arguments)
            texte = next((c.text for c in reponse.content
                          if getattr(c, "text", None)), "{}")
            return json.loads(texte)

        futur: Future = asyncio.run_coroutine_threadsafe(travail(), self._boucle)
        try:
            return futur.result(timeout=delai)
        except Exception as e:  # noqa: BLE001
            # Un delai depasse ou une panne de transport est rendu comme un
            # statut, jamais comme une exception : la page doit pouvoir
            # l'afficher au meme titre qu'un refus.
            return {"status": "error", "payload": {"code": "TRANSPORT"},
                    "message": f"{type(e).__name__}: {e}"}

    def fermer(self) -> None:
        if self._boucle and self._arret and not self._arret.done():
            self._boucle.call_soon_threadsafe(self._arret.set_result, None)

    def __repr__(self) -> str:  # pragma: no cover
        etat = self.erreur or f"{len(self.outils)} tools"
        return f"<ClientPersistant {self.profil} : {etat}>"


def catalogue_brut(client: ClientPersistant) -> list[dict[str, Any]]:
    """Le catalogue tel que `tools/list` le rend, schémas compris."""
    return [{"nom": o.nom, "resume": o.resume,
             "parametres": list((o.schema.get("properties") or {})),
             "obligatoires": o.schema.get("required") or []}
            for o in client.outils]

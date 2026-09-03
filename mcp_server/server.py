"""Le serveur MCP de la Sorabel Data Gateway.

    python -m mcp_server.server        # transport stdio, profil par SORABEL_PROFILE

**Un seul point de passage, et c'est là que E4 et E5 se tiennent.** Chaque appel
traverse `_appeler` : le droit s'y vérifie avant tout, l'appel s'y journalise
qu'il soit autorisé ou refusé, et l'enveloppe du contrat s'y forme. Il n'y a pas
de second chemin, donc pas de chemin qui aurait oublié le journal.

**Le profil est fixé au lancement** (D28), lu dans `SORABEL_PROFILE`, et le
serveur **refuse de démarrer** si la matrice ne le connaît pas. Un profil inconnu
qui se rabattrait sur un défaut permissif serait le pire des comportements : il
ne produirait aucune erreur et ouvrirait des droits.

**Rien ne s'écrit sur la sortie standard**, jamais : c'est le canal du protocole.
Tout message de service part sur la sortie d'erreur.
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from typing import Any

import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from common.config import CONFIG
from common.matrice import Droits, ProfilInconnu, catalogue as catalogue_matrice, droits

from .catalogue import CATALOGUE
from .journal import Journal

#: Le seul code de refus que le contrat rende nécessaire côté gateway. Les
#: autres naissent dans les tools et voyagent dans `payload`, jamais à la place
#: du `status` : le contrat n'énumère que cinq statuts.
UNAUTHORIZED_TOOL = "UNAUTHORIZED_TOOL"


def _erreur(message: str) -> None:
    print(message, file=sys.stderr)


class Gateway:
    """L'état du processus : ses droits, ses services, son journal.

    Les services sont construits **paresseusement**. Un client qui ne fait que
    du SQL n'a aucune raison de payer le chargement de l'index documentaire, et
    réciproquement.
    """

    def __init__(self, droits_profil: Droits) -> None:
        self.droits = droits_profil
        self.journal = Journal()
        self._rag: Any = None
        self._sql: Any = None

    # --- services, construits au premier besoin ---------------------------

    @property
    def rag(self) -> Any:  # noqa: ANN401
        if self._rag is None:
            from retrieval.recherche import CONFIGS
            from retrieval.service import ServiceRag

            self._rag = ServiceRag(self.droits, CONFIGS["D"])
        return self._rag

    @property
    def sql(self) -> Any:  # noqa: ANN401
        if self._sql is None:
            from sql.generateur import GenerateurLocal
            from sql.service import ServiceSql

            self._sql = ServiceSql(self.droits, GenerateurLocal())
        return self._sql

    def prechauffer(self) -> None:
        """Importe dans le fil PRINCIPAL, puis charge les poids en arrière-plan.

        Mesuré sur le poste de développement : le premier appel au modèle SQL a
        coûté jusqu'à 677 secondes, contre 12 à 20 ensuite, sur un processeur
        qui descend à 801 MHz sur 2304 sous charge. La suite d'acceptance
        accorde un budget par appel et lance un processus serveur neuf par
        session : payer le chargement au démarrage dépasserait le budget de
        `initialize()`, le payer au premier appel dépasse celui de l'appel.

        **Le découpage entre import et chargement n'est pas cosmétique.** Une
        première version lançait tout dans un fil d'arrière-plan, et les huit
        tests qui touchent un modèle échouaient sur
        `ImportError: cannot import name 'NDArray' from partially initialized
        module 'numpy._typing'`. Le système d'import de Python ne supporte pas
        deux imports concurrents d'un même module en cours d'initialisation :
        le fil de préchauffage et le fil qui traite la requête se marchaient
        dessus, et **les deux** échouaient.

        Les imports se font donc ici, dans le fil principal, avant que le
        serveur n'accepte quoi que ce soit. Seul le chargement des poids, qui
        ne touche plus au système d'import, part en arrière-plan.

        Sur un poste aussi bridé, cela ne suffit toujours pas à tenir un budget
        de 30 secondes, et il faut le dire plutôt que le masquer.
        """
        import threading

        # --- imports, dans le fil principal, en série -----------------------
        besoins = []
        try:
            if "ask_database" in self.droits.tools:
                import torch  # noqa: F401, PLC0415
                import transformers  # noqa: F401, PLC0415

                besoins.append(self.sql.generateur.prechauffer)
            if "answer_question" in self.droits.tools:
                import sentence_transformers  # noqa: F401, PLC0415

                self.rag.depot.manifeste       # ouvre l'index, sans encoder
                besoins.append(lambda: self.rag.chercheur.encodeur.passages(["prechauffage"]))
        except Exception as e:  # noqa: BLE001
            _erreur(f"preparation interrompue : {type(e).__name__}: {e}")
            return

        # --- chargement des poids, en arrière-plan --------------------------
        def charger() -> None:
            for tache in besoins:
                try:
                    tache()
                except Exception as e:  # noqa: BLE001
                    _erreur(f"prechauffage interrompu : {type(e).__name__}: {e}")

        threading.Thread(target=charger, daemon=True).start()

    # --- l'unique point de passage ----------------------------------------

    def appeler(self, tool: str, arguments: dict) -> tuple[str, dict, str]:
        """Vérifie le droit, exécute, journalise, et rend l'enveloppe.

        L'ordre compte : le droit d'abord, sur un nom de tool et rien d'autre.
        Un tool hors catalogue se refuse comme un tool non autorisé, et non par
        une erreur technique : deny-by-default s'applique aussi aux noms.
        """
        debut = time.perf_counter()
        arguments = arguments or {}

        if tool not in self.droits.tools:
            connu = tool in catalogue_matrice()
            message = (
                f"Le profil {self.droits.profil} n'est pas autorise a appeler "
                f"{tool}." if connu else
                f"Le tool {tool} ne fait pas partie du catalogue de la gateway."
            )
            return self._conclure(tool, arguments, "refused", message,
                                  UNAUTHORIZED_TOOL, debut)

        try:
            statut, payload, message = self._dispatcher(tool, arguments)
        except Exception as e:  # noqa: BLE001
            # Une panne technique est un statut, jamais une exception qui
            # remonte au protocole : le client doit pouvoir la distinguer d'un
            # refus, et l'appel doit tout de meme etre journalise.
            _erreur(f"{tool} : {type(e).__name__}: {e}")
            return self._conclure(
                tool, arguments, "error",
                f"Panne technique du serveur sur {tool}. Aucune conclusion "
                f"metier a en tirer. ({type(e).__name__})",
                "INTERNAL_ERROR", debut)

        return self._conclure(tool, arguments, statut, message,
                              str(payload.get("code", "")), debut, payload)

    def _dispatcher(self, tool: str, a: dict) -> tuple[str, dict, str]:
        """Aiguille vers le service. Les arguments manquants sont traités par le
        tool, pas ici : le refus de matrice a déjà eu lieu."""
        if tool == "answer_question":
            return self.rag.answer_question(str(a.get("question") or ""))
        if tool == "search_docs":
            k = a.get("k")
            return self.rag.search_docs(str(a.get("query") or ""),
                                        int(k) if isinstance(k, int) else None)
        if tool == "get_document":
            return self.rag.get_document(str(a.get("doc_id") or ""))
        if tool == "list_sources":
            return self.rag.list_sources(a.get("doc_type") or None)
        if tool == "ask_database":
            return self.sql.ask_database(str(a.get("question") or ""))
        if tool == "get_schema":
            return self.sql.get_schema()
        if tool == "check_stock":
            return self.sql.check_stock(str(a.get("reference") or ""))
        if tool == "order_status":
            return self.sql.order_status(str(a.get("order_id") or ""))
        raise KeyError(tool)   # inatteignable : le catalogue est verifie plus haut

    def _conclure(self, tool: str, arguments: dict, statut: str, message: str,
                  code: str, debut: float, payload: dict | None = None,
                  ) -> tuple[str, dict, str]:
        payload = payload or ({"code": code} if code else {})
        self.journal.consigner(
            profil=self.droits.profil, tool=tool, arguments=arguments,
            statut=statut, message=message, code=code,
            duree_ms=(time.perf_counter() - debut) * 1000,
            ressources=payload.get("ressources"),
            sql=str(payload.get("sql") or ""),
        )
        return statut, payload, message


def construire(gateway: Gateway) -> Server:
    serveur = Server("sorabel-data-gateway")

    @serveur.list_tools()
    async def lister() -> list[types.Tool]:
        """Le catalogue **borné au profil**.

        On n'annonce pas ce que le client ne peut pas appeler. Un tool retiré du
        catalogue reste néanmoins refusé s'il est appelé directement : la
        matrice décide, l'annonce n'est qu'une courtoisie.
        """
        return [
            types.Tool(name=o.nom, description=f"{o.resume}\n\n{o.description}",
                       inputSchema=o.schema())
            for o in CATALOGUE if o.nom in gateway.droits.tools
        ]

    # validate_input=False : le refus de matrice doit precéder toute validation
    # de schema, sinon un tool interdit appele sans arguments echouerait au
    # niveau du protocole au lieu d'etre refuse par la gateway.
    @serveur.call_tool(validate_input=False)
    async def appeler(nom: str, arguments: dict | None) -> list[types.TextContent]:
        statut, payload, message = await asyncio.to_thread(
            gateway.appeler, nom, arguments or {})
        enveloppe = {"status": statut, "payload": payload, "message": message}
        return [types.TextContent(
            type="text",
            text=json.dumps(enveloppe, ensure_ascii=False, default=str))]

    return serveur


async def _servir(gateway: Gateway) -> None:
    serveur = construire(gateway)
    async with stdio_server() as (lecture, ecriture):
        await serveur.run(lecture, ecriture,
                          serveur.create_initialization_options())


def main() -> int:
    try:
        mes_droits = droits()
    except ProfilInconnu as e:
        # Refuser de demarrer est la seule reponse sure : un profil inconnu qui
        # se rabattrait sur un defaut permissif ouvrirait des droits sans
        # produire d'erreur.
        _erreur(f"demarrage refuse : {e}")
        return 2

    gateway = Gateway(mes_droits)
    _erreur(f"gateway prete, profil {mes_droits.profil}, "
            f"{len(mes_droits.tools)} tools, journal {gateway.journal.chemin}")
    if CONFIG.index.exists():
        gateway.prechauffer()
    else:
        _erreur("index documentaire absent : lancer `python -m ingest`. "
                "Les tools SQL restent disponibles.")

    try:
        asyncio.run(_servir(gateway))
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

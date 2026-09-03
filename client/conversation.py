"""Un tour de conversation : router, appeler, composer la réponse.

CE QUE CE MODULE REFUSE DE FAIRE, ET C'EST L'ESSENTIEL
Il ne **reformule pas** les résultats. Rendre « 27 » sous la forme « il y a eu
27 commandes en avril » demanderait une génération par-dessus une donnée juste,
donc une occasion d'inventer là où il n'y en avait aucune. La composition passe
donc par des gabarits déterministes : le nombre de lignes, la valeur quand il
n'y en a qu'une, le tableau sinon.

CE QUE E3 OBLIGE, ET CE QU'IL N'OBLIGE PAS
Le cadrage DSI dit que « la requête générée est toujours **renvoyée** avec le
résultat ». L'obligation porte sur le **tool**, qui doit la mettre dans sa
charge utile, et elle est tenue par la gateway, journal compris. Ce module la
transporte donc systématiquement dans le tour.

En revanche, **l'afficher dans la conversation est un choix d'interface, pas
une exigence**. La règle « le SQL jamais replié » vient du chantier 8, écrit
pour l'écran destiné à un intégrateur ; un agent du SAV, lui, ne lit pas de
SQL. Chaque page décide donc ce qu'elle en montre, et E3 reste satisfaite dans
tous les cas. La distinction a été relevée par le pilote le 2026-09-03, après
que j'avais présenté l'affichage comme obligatoire.

E1, en revanche, porte bien sur la RESTITUTION : « toute réponse documentaire
cite ses sources ». Les sources doivent donc être visibles, dans la
conversation comme ailleurs.

LA TRACE N'EST PAS LE JOURNAL DE LA GATEWAY
La décision de routage appartient au **client**. `logs/journal.jsonl` est
l'artefact d'audit de la DSI, dont le cadrage fixe les clés : y verser nos
étiquettes le ferait sortir du contrat. Le client tient donc sa propre trace,
qui dit *pourquoi* tel tool a été appelé, là où le journal dit *que* tel tool
a été appelé et avec quelle issue.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from client.routeur import Routage, Routeur

#: Ce qu'un statut hors `ok` signifie pour un utilisateur qui n'a pas lu le
#: contrat d'intégration. Le message du serveur reste affiché tel quel : il est
#: obligatoire et explicite pour tout statut autre que `ok`.
LECTURE = {
    "refused": "Demande refusée",
    "clarification": "Précision nécessaire",
    "hors_corpus": "La documentation ne couvre pas cette question",
    "error": "Panne technique",
}


@dataclass
class Tour:
    """Une question, ce qu'elle a déclenché, et ce qu'elle a rendu."""

    question: str
    #: Le profil du serveur qui a repondu. Un fil peut melanger les deux, et
    #: sans cette marque on ne saurait plus qui a refuse quoi.
    profil: str = ""
    routage: Routage | None = None
    statut: str = ""
    enveloppe: dict = field(default_factory=dict)
    #: Le texte composé, déterministe.
    texte: str = ""
    duree_ms: float = 0.0

    @property
    def payload(self) -> dict:
        return self.enveloppe.get("payload") or {}

    @property
    def sources(self) -> list[dict]:
        return self.payload.get("sources") or []

    @property
    def sql(self) -> str:
        return self.payload.get("sql") or ""

    @property
    def code(self) -> str:
        return self.payload.get("code") or ""

    @property
    def refuse(self) -> bool:
        return self.statut == "refused"

    def trace(self) -> dict:
        """La trace CLIENT, distincte du journal de la gateway."""
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "profil": self.profil,
            "question": self.question,
            "routage": self.routage.trace() if self.routage else None,
            "statut": self.statut,
            "code": self.code,
            "duree_ms": round(self.duree_ms, 1),
        }


class Conversation:
    """Orchestre un tour, du texte libre à la réponse composée."""

    def __init__(self, client, routeur: Routeur | None = None,  # noqa: ANN001
                 trace: Path | None = None, profil: str = "") -> None:
        self.client = client
        self.routeur = routeur or Routeur()
        self.chemin_trace = trace
        # Le profil n'est PAS un reglage de la conversation : c'est celui du
        # serveur auquel ce client parle, fixe au lancement de ce serveur
        # (D28). On le recopie ici pour pouvoir l'afficher et le tracer, pas
        # pour le decider.
        self.profil = profil or getattr(client, "profil", "")
        self.tours: list[Tour] = []

    def repondre(self, question: str) -> Tour:
        debut = time.perf_counter()
        tour = Tour(question=question, profil=self.profil)
        tour.routage = self.routeur.router(question)

        if tour.routage.manque:
            # Un tool figé sans son identifiant. On le dit au lieu d'appeler
            # avec un argument vide, ce qui produirait une erreur technique là
            # où une phrase suffit.
            tour.statut = "clarification"
            tour.texte = ("Il me manque " + tour.routage.manque
                          + " pour répondre.")
        else:
            tour.enveloppe = self.client.appeler(tour.routage.tool,
                                                 tour.routage.arguments)
            tour.statut = tour.enveloppe.get("status", "error")
            tour.texte = self._composer(tour)

        tour.duree_ms = (time.perf_counter() - debut) * 1000
        self.tours.append(tour)
        self._tracer(tour)
        return tour

    # --- composition, sans aucune génération --------------------------------
    def _composer(self, tour: Tour) -> str:
        if tour.statut != "ok":
            return tour.enveloppe.get("message") or LECTURE.get(tour.statut, "")

        payload = tour.payload
        if "answer" in payload:
            return payload["answer"] or "La documentation ne dit rien de plus."

        if "rows" in payload:
            return self._resumer(payload)

        if "schema" in payload:
            return "Voici le schéma des tables accessibles."
        return "Réponse reçue."

    @staticmethod
    def _resumer(payload: dict) -> str:
        """Un résumé par GABARIT, jamais par reformulation.

        Le tableau reste affiché à côté : ce texte l'annonce, il ne le
        remplace pas, et il ne peut donc pas le contredire.
        """
        lignes = payload.get("rows") or []
        colonnes = payload.get("columns") or []
        if payload.get("trouve") is False:
            return "Aucune donnée pour cet identifiant."
        if not lignes:
            return "Aucun résultat."
        if len(lignes) == 1 and len(colonnes) == 1:
            # La VALEUR seule, sans le nom de colonne. Celui-ci vient du SQL,
            # pas du langage : personne ne demande « combien de commandes en
            # mai ? » pour lire « COUNT(*) : 28 ». La question porte deja le
            # contexte, et la colonne reste lisible dans la requete affichee.
            return str(lignes[0][0])
        if len(lignes) == 1:
            paires = ", ".join(f"{c} = {v}" for c, v in zip(colonnes, lignes[0]))
            return f"Une ligne. {paires}"
        return f"{len(lignes)} lignes, {len(colonnes)} colonne(s)."

    def _tracer(self, tour: Tour) -> None:
        if not self.chemin_trace:
            return
        self.chemin_trace.parent.mkdir(parents=True, exist_ok=True)
        with self.chemin_trace.open("a", encoding="utf-8") as f:
            f.write(json.dumps(tour.trace(), ensure_ascii=False) + "\n")

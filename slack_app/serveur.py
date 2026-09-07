"""L'application Slack du SAV : point d'entrée public, réponse différée.

    SLACK_SIGNING_SECRET=... SLACK_BOT_TOKEN=xoxb-... \\
        uv run python -m slack_app.serveur

C'est l'item A1, ouvert depuis D34. Le chantier 7 avait révélé que Slack
n'apparaissait dans le dossier que comme une **étiquette** : neuf mentions,
toutes décoratives, alors que c'est un **programme à héberger**, et le véritable
appelant de la gateway.

    l'agent du SAV  ->  Slack  ->  CE service  ->  gateway MCP  ->  RAG / SQL

TROIS CONTRAINTES QUE SLACK IMPOSE, ET QUE CE FICHIER TRAITE

1. **Le budget de trois secondes.** Slack attend un accusé quasi immédiat, or
   notre chaîne le dépasse largement : la recherche hybride puis le reranking
   coûtent quelques secondes, la génération SQL une quinzaine. On répond donc
   `200` tout de suite, on publie un accusé, et la réponse part dans un second
   message. Ce n'est pas un détail d'implémentation, cela change le contrat
   d'interaction avec l'utilisateur.

2. **Un point d'entrée public.** D'où `slack_app/signature.py`, seule frontière
   de confiance de ce service.

3. **Les nouvelles tentatives.** Sans `200` dans le budget, Slack REJOUE
   l'événement, jusqu'à trois fois. Sans déduplication, la même question
   partirait trois fois à la gateway, et le journal porterait trois appels pour
   une question. On mémorise donc les `event_id` déjà vus.

CE QUE CE SERVICE N'A PAS
Aucune dépendance nouvelle : `http.server` de la bibliothèque standard suffit
pour un point d'entrée qui reçoit des POST et rend `200`. Ajouter un cadre web
aurait modifié `uv.lock`, que le dépôt amont épingle et sur lequel la suite
d'acceptance est jouée.

ETAT : JAMAIS CONFRONTE A UN VRAI SLACK. L'espace de travail et l'application
Slack n'existent pas (chantier 7, section 2.4), et il faut un administrateur
pour installer une application. Ce qui EST éprouvé hors ligne, par
`tests/eprouver_slack.py` : la vérification de signature, le rejet du rejeu, la
déduplication, le défi d'URL et le rendu des blocs. Ce qui ne l'est pas : le
dialogue réel avec l'API Slack.
"""
from __future__ import annotations

import json
import os
import sys
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from slack_app import formatage, signature  # noqa: E402

#: Le profil est celui du SERVEUR, fixé à son lancement (D28). Le bot Slack est
#: le client du profil `support`, la matrice le dit elle-même. Aucun message
#: Slack ne peut en changer.
PROFIL = "support"

API_SLACK = "https://slack.com/api/chat.postMessage"

#: Les `event_id` déjà traités. Un ensemble borné suffit : Slack ne rejoue que
#: quelques minutes, et ce service ne prétend pas survivre à son redémarrage.
_VUS: set[str] = set()
_VUS_MAX = 2048
_VERROU = threading.Lock()


def deja_vu(event_id: str) -> bool:
    """Vrai si cet événement a déjà été traité. Voir la contrainte 3."""
    if not event_id:
        return False
    with _VERROU:
        if event_id in _VUS:
            return True
        if len(_VUS) >= _VUS_MAX:
            _VUS.clear()          # borne grossiere, mais bornee
        _VUS.add(event_id)
        return False


def publier(canal: str, blocs: list[dict], fil: str = "") -> None:
    """Publie un message dans Slack. Échoue en silence côté utilisateur.

    Un échec ici ne doit pas faire tomber le service : Slack a déjà reçu son
    `200`, et l'utilisateur verra simplement l'accusé sans suite. On le trace.
    """
    jeton = os.environ.get("SLACK_BOT_TOKEN", "")
    if not jeton:
        print("SLACK_BOT_TOKEN absent : rien n'est publie.", file=sys.stderr)
        return
    charge = {"channel": canal, "blocks": blocs,
              "text": "Réponse de la Sorabel Data Gateway"}
    if fil:
        charge["thread_ts"] = fil
    requete = urllib.request.Request(
        API_SLACK, data=json.dumps(charge).encode(),
        headers={"Content-Type": "application/json; charset=utf-8",
                 "Authorization": f"Bearer {jeton}"})
    try:
        with urllib.request.urlopen(requete, timeout=20) as reponse:
            resultat = json.load(reponse)
        if not resultat.get("ok"):
            print(f"Slack a refuse la publication : {resultat.get('error')}",
                  file=sys.stderr)
    except urllib.error.URLError as e:
        print(f"publication impossible : {e}", file=sys.stderr)


class Assistant:
    """Le pont entre Slack et la gateway, monté paresseusement.

    Le montage ouvre une session MCP et charge les modèles : le faire à
    l'import ferait échouer le démarrage du service si la gateway est
    momentanément indisponible, alors que Slack, lui, attend un point d'entrée
    qui réponde.
    """

    def __init__(self) -> None:
        self._conversation = None
        self._verrou = threading.Lock()

    @property
    def conversation(self):  # noqa: ANN201
        with self._verrou:
            if self._conversation is None:
                from client.conversation import Conversation
                from client.routeur import Routeur
                from scripts.client_persistant import ClientPersistant

                client = ClientPersistant(PROFIL)
                self._conversation = Conversation(
                    client, Routeur(profil=PROFIL),
                    trace=RACINE / "logs" / "conversation.jsonl",
                    profil=PROFIL)
            return self._conversation

    def traiter(self, question: str, canal: str, fil: str,
                utilisateur: str) -> None:
        """Le travail long, hors du budget de trois secondes."""
        tour = self.conversation.repondre(question)
        # L'IDENTITE SLACK VA A LA TRACE, JAMAIS A UNE DECISION. D34 : elle est
        # attestee par le bot et non verifiee par la gateway, donc elle ameliore
        # l'imputabilite sans entrer dans l'autorisation.
        tour.enveloppe.setdefault("_slack", {})["utilisateur_atteste"] = utilisateur
        publier(canal, formatage.repondre(
            question, tour.enveloppe, tour.routage.tool if tour.routage else "",
            utilisateur), fil)


ASSISTANT = Assistant()


class Poignee(BaseHTTPRequestHandler):
    server_version = "SorabelSlack/1.0"

    def log_message(self, format: str, *args) -> None:  # noqa: A002, ANN002
        # Le journal par defaut ecrit sur stderr une ligne par requete, avec
        # l'adresse : inutile ici, et le journal d'audit est ailleurs.
        pass

    def _repondre(self, code: int, corps: bytes = b"", type_mime: str = "text/plain") -> None:
        self.send_response(code)
        self.send_header("Content-Type", type_mime)
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        if corps:
            self.wfile.write(corps)

    def do_GET(self) -> None:  # noqa: N802
        # Sonde de sante : Container Apps s'en sert pour savoir si la replique
        # est prete, et ces requetes ne sont pas facturees.
        if self.path in ("/sante", "/health", "/"):
            self._repondre(200, b"ok")
        else:
            self._repondre(404)

    def do_POST(self) -> None:  # noqa: N802
        if self.path not in ("/slack/events", "/slack/evenements"):
            self._repondre(404)
            return

        taille = int(self.headers.get("Content-Length") or 0)
        # LE CORPS BRUT, et pas un JSON reanalyse : la signature porte sur les
        # octets recus, et resérialiser change les espaces.
        corps = self.rfile.read(taille)

        verdict = signature.verifier(corps, dict(self.headers))
        if not verdict:
            print(f"requete rejetee : {verdict.motif}", file=sys.stderr)
            self._repondre(401, b"signature invalide")
            return

        try:
            charge = json.loads(corps or b"{}")
        except json.JSONDecodeError:
            self._repondre(400, b"corps illisible")
            return

        # Le defi d'URL, envoye par Slack a la configuration du point d'entree.
        if charge.get("type") == "url_verification":
            jeton = json.dumps({"challenge": charge.get("challenge", "")}).encode()
            self._repondre(200, jeton, "application/json")
            return

        evenement = charge.get("event") or {}
        question = (evenement.get("text") or "").strip()
        canal = evenement.get("channel") or ""
        utilisateur = evenement.get("user") or ""
        fil = evenement.get("thread_ts") or evenement.get("ts") or ""

        # On ignore nos propres messages, sans quoi le bot se repondrait a
        # lui-meme indefiniment.
        interessant = (charge.get("type") == "event_callback"
                       and evenement.get("type") in ("app_mention", "message")
                       and not evenement.get("bot_id")
                       and question and canal)

        if not interessant or deja_vu(charge.get("event_id", "")):
            self._repondre(200, b"")
            return

        # LE 200 PART D'ABORD. Tout ce qui suit se fait hors du budget de Slack.
        self._repondre(200, b"")
        publier(canal, formatage.accuse(question), fil)
        threading.Thread(
            target=ASSISTANT.traiter, daemon=True,
            args=(question, canal, fil, utilisateur)).start()


def main() -> int:
    port = int(os.environ.get("PORT", "8080"))
    if not signature.secret():
        print("SLACK_SIGNING_SECRET absent : le service demarre mais REFUSERA "
              "toute requete. C'est voulu : accepter sans verifier serait pire "
              "qu'etre arrete.", file=sys.stderr)
    serveur = ThreadingHTTPServer(("0.0.0.0", port), Poignee)  # noqa: S104
    print(f"application Slack en ecoute sur le port {port}, profil {PROFIL}")
    print("  point d'entree : POST /slack/events")
    print("  sonde de sante : GET  /sante")
    try:
        serveur.serve_forever()
    except KeyboardInterrupt:
        print("\narret demande")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

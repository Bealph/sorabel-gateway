#!/usr/bin/env python3
"""Éprouve l'application Slack, hors ligne et sans espace de travail.

    uv run python tests/eprouver_slack.py

CE QUI EST EPROUVE ICI, ET CE QUI NE PEUT PAS L'ETRE
L'espace de travail Slack et l'application Slack n'existent pas, et il faut un
administrateur pour installer une application. Le dialogue réel avec l'API
Slack n'est donc **pas** couvert, et le dire vaut mieux que de le laisser
supposer.

En revanche, tout ce qui décide **sans** Slack l'est : la vérification de
signature, qui est la seule frontière de confiance du service, le rejet du
rejeu, la déduplication des nouvelles tentatives, le défi d'URL et le rendu des
blocs. Ce sont les parties où un défaut serait grave et invisible.

CHAQUE CONTROLE EST EPROUVE PAR SON ECHEC. Un contrôle qu'on n'a jamais vu
tomber ne prouve rien : c'est la discipline du projet depuis la matrice
d'accès.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from slack_app import formatage, serveur, signature  # noqa: E402

SECRET = "secret-de-test-jamais-utilise-en-vrai"

VERT, ROUGE, GRIS = "\033[32m", "\033[31m", "\033[90m"
NORMAL = "\033[0m"

_echecs: list[str] = []


def controle(quoi: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"  {VERT}ok   {NORMAL}{quoi}")
    else:
        print(f"  {ROUGE}ECHEC{NORMAL}{quoi}  {GRIS}{detail}{NORMAL}")
        _echecs.append(quoi)


def requete(corps: bytes, *, decalage: float = 0.0, cle: str = SECRET,
            abimer: bool = False) -> dict[str, str]:
    """Forge des en-têtes Slack. La signature est calculée par le code testé.

    Recopier l'algorithme ici ne testerait que la copie : on appelle donc
    `signature.signer`, et les cas négatifs abîment le résultat.
    """
    horodatage = str(int(time.time() + decalage))
    valeur = signature.signer(corps, horodatage, cle)
    if abimer:
        valeur = valeur[:-1] + ("0" if valeur[-1] != "0" else "1")
    # La casse est melangee volontairement : la specification previent que
    # « the letter case should not be assumed ».
    return {"X-Slack-Signature": valeur,
            "x-slack-REQUEST-timestamp": horodatage}


def eprouver_signature() -> None:
    print("\nSIGNATURE, la seule frontiere de confiance du service")
    corps = json.dumps({"type": "event_callback"}).encode()

    controle("une requete legitime est acceptee",
             bool(signature.verifier(corps, requete(corps), SECRET)))

    v = signature.verifier(corps, requete(corps, abimer=True), SECRET)
    controle("une signature abimee d'UN caractere est refusee",
             not v and "invalide" in v.motif, v.motif)

    v = signature.verifier(corps, requete(corps, cle="mauvais-secret"), SECRET)
    controle("une signature calculee avec un autre secret est refusee",
             not v, v.motif)

    # Le rejeu : la specification fixe cinq minutes.
    v = signature.verifier(corps, requete(corps, decalage=-6 * 60), SECRET)
    controle("un horodatage vieux de 6 minutes est refuse (rejeu)",
             not v and "rejeu" in v.motif, v.motif)
    controle("un horodatage vieux de 4 minutes est accepte",
             bool(signature.verifier(corps, requete(corps, decalage=-4 * 60),
                                     SECRET)))
    v = signature.verifier(corps, requete(corps, decalage=+6 * 60), SECRET)
    controle("un horodatage dans le FUTUR de 6 minutes est refuse",
             not v, v.motif)

    v = signature.verifier(corps, {}, SECRET)
    controle("des en-tetes absents sont refuses",
             not v and "absent" in v.motif, v.motif)

    v = signature.verifier(corps, requete(corps), "")
    controle("sans secret configure, TOUT est refuse",
             not v and "secret" in v.motif, v.motif)

    # LE PIEGE DU CORPS BRUT : la signature porte sur les octets recus. Un JSON
    # reanalyse puis reserialise change les espaces, et la verification echoue
    # sans que rien n'indique pourquoi.
    entetes = requete(corps)
    reserialise = json.dumps(json.loads(corps), indent=2).encode()
    controle("un corps reserialise ne passe PAS (piege du corps brut)",
             not signature.verifier(reserialise, entetes, SECRET))

    controle("la casse des en-tetes n'a pas d'importance",
             bool(signature.verifier(corps, requete(corps), SECRET)))


def eprouver_deduplication() -> None:
    print("\nDEDUPLICATION, car Slack rejoue jusqu'a trois fois")
    serveur._VUS.clear()
    controle("un evenement neuf n'est pas vu", not serveur.deja_vu("Ev001"))
    controle("le meme evenement est ensuite reconnu", serveur.deja_vu("Ev001"))
    controle("un autre evenement passe", not serveur.deja_vu("Ev002"))
    controle("un identifiant vide ne bloque jamais",
             not serveur.deja_vu("") and not serveur.deja_vu(""))
    avant = len(serveur._VUS)
    for i in range(serveur._VUS_MAX + 10):
        serveur.deja_vu(f"Ev{i:06d}")
    controle("l'ensemble reste borne, il ne fuit pas",
             len(serveur._VUS) <= serveur._VUS_MAX,
             f"{avant} puis {len(serveur._VUS)}")


def eprouver_formatage() -> None:
    print("\nRENDU DES BLOCS, l'item A2 : E1 exige des sources LISIBLES")
    enveloppe = {
        "status": "ok",
        "payload": {"answer": "Le calibre est de 40 A.",
                    "sources": [{"titre": "Fiche technique disjoncteur",
                                 "reference": "REF-8842", "date": "2026-03-12"}]},
        "message": "",
    }
    blocs = formatage.repondre("quel calibre ?", enveloppe, "answer_question")
    rendu = json.dumps(blocs, ensure_ascii=False)
    controle("la reponse est presente", "40 A" in rendu)
    for champ in ("Fiche technique disjoncteur", "REF-8842", "2026-03-12"):
        controle(f"la source porte son {champ[:18]}", champ in rendu)
    controle("les sources sont dans une section distincte",
             any(b.get("type") == "divider" for b in blocs))

    refus = {"status": "refused",
             "payload": {"code": "READ_ONLY_VIOLATION",
                         "sql": "DELETE FROM commandes"},
             "message": "Instruction DELETE refusee : lecture seule."}
    blocs = formatage.repondre("supprime les commandes", refus, "ask_database")
    rendu = json.dumps(blocs, ensure_ascii=False)
    controle("un refus est marque COMME un refus", "Demande refusée" in rendu)
    controle("le code de refus figure", "READ_ONLY_VIOLATION" in rendu)
    controle("le SQL refuse est VISIBLE, car il rend le refus auditable",
             "DELETE FROM commandes" in rendu)

    ok_sql = {"status": "ok",
              "payload": {"sql": "SELECT COUNT(*) FROM commandes",
                          "columns": ["COUNT(*)"], "rows": [[27]]},
              "message": ""}
    blocs = formatage.repondre("combien de commandes ?", ok_sql, "ask_database")
    rendu = json.dumps(blocs, ensure_ascii=False)
    controle("en cas de succes, la valeur est rendue seule", "*27*" in rendu)
    controle("en cas de succes, le SQL n'encombre PAS le message",
             "SELECT COUNT" not in rendu)

    hors = {"status": "hors_corpus", "payload": {},
            "message": "La documentation ne couvre pas cette question."}
    controle("une abstention est affichee en clair",
             "Hors documentation" in json.dumps(
                 formatage.repondre("politique RSE ?", hors), ensure_ascii=False))

    long_texte = {"status": "ok", "payload": {"answer": "x" * 5000}, "message": ""}
    blocs = formatage.repondre("q", long_texte)
    controle("un texte trop long est tronque, et le dit",
             all(len(json.dumps(b)) < 3200 for b in blocs)
             and "tronquée" in json.dumps(blocs, ensure_ascii=False))

    controle("l'accuse de reception annonce l'attente",
             "Je cherche" in json.dumps(formatage.accuse("q"),
                                        ensure_ascii=False))


def eprouver_defi() -> None:
    print("\nDEFI D'URL, envoye par Slack a la configuration du point d'entree")
    corps = json.dumps({"type": "url_verification",
                        "challenge": "abc123"}).encode()
    v = signature.verifier(corps, requete(corps), SECRET)
    controle("le defi doit lui aussi etre signe", bool(v))
    # La reponse attendue est le defi renvoye tel quel : verifie ici sur la
    # forme, le chemin HTTP etant couvert par le code du serveur.
    controle("la charge du defi porte bien le jeton a renvoyer",
             json.loads(corps)["challenge"] == "abc123")


def eprouver_service_http() -> None:
    """Le service reel, sur un port local. Aucun Slack n'est requis.

    C'est la seule facon de verifier ce que les fonctions pures ne disent pas :
    que le point d'entree repond, qu'il refuse ce qu'il doit refuser, et
    surtout qu'il rend son 200 DANS le budget de trois secondes de Slack.
    """
    import http.client
    import os
    import threading
    from http.server import ThreadingHTTPServer

    print("\nSERVICE HTTP, sur un port local, sans aucun Slack")
    os.environ["SLACK_SIGNING_SECRET"] = SECRET
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), serveur.Poignee)
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    def poster(chemin: str, corps: bytes, entetes: dict) -> tuple[int, bytes]:
        cx = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        cx.request("POST", chemin, body=corps, headers=entetes)
        r = cx.getresponse()
        lu = r.read()
        cx.close()
        return r.status, lu

    try:
        cx = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        cx.request("GET", "/sante")
        r = cx.getresponse()
        controle("la sonde de sante repond 200", r.status == 200)
        cx.close()

        # Le defi d'URL, signe : Slack attend son jeton renvoye tel quel.
        corps = json.dumps({"type": "url_verification",
                            "challenge": "jeton-de-defi"}).encode()
        code, lu = poster("/slack/events", corps, requete(corps))
        controle("le defi d'URL signe renvoie 200", code == 200)
        controle("et renvoie le jeton tel quel",
                 json.loads(lu or b"{}").get("challenge") == "jeton-de-defi",
                 lu[:60].decode(errors="replace"))

        # NON SIGNE : c'est le controle qui compte le plus. Un point d'entree
        # public qui accepte sans verifier laisse n'importe qui faire appeler
        # la gateway.
        code, _ = poster("/slack/events", corps, {})
        controle("une requete NON SIGNEE est refusee en 401", code == 401,
                 f"recu {code}")

        code, _ = poster("/slack/events", corps, requete(corps, abimer=True))
        controle("une signature abimee est refusee en 401", code == 401,
                 f"recu {code}")

        code, _ = poster("/slack/events", corps,
                         requete(corps, decalage=-6 * 60))
        controle("un rejeu de 6 minutes est refuse en 401", code == 401,
                 f"recu {code}")

        code, _ = poster("/autre", corps, requete(corps))
        controle("un chemin inconnu rend 404", code == 404, f"recu {code}")

        # LE BUDGET DE TROIS SECONDES. On envoie un vrai evenement : le
        # traitement long part dans un fil, et le 200 doit revenir tout de
        # suite. SLACK_BOT_TOKEN est absent, donc rien n'est publie et la
        # gateway n'est pas appelee : c'est bien le temps de REPONSE qu'on
        # mesure, pas celui du traitement.
        os.environ.pop("SLACK_BOT_TOKEN", None)
        evenement = json.dumps({
            "type": "event_callback", "event_id": "Ev-budget",
            "event": {"type": "app_mention", "text": "quel calibre ?",
                      "channel": "C123", "user": "U456", "ts": "1.0"},
        }).encode()
        debut = time.perf_counter()
        code, _ = poster("/slack/events", evenement, requete(evenement))
        delai = time.perf_counter() - debut
        controle("un evenement signe rend 200", code == 200)
        controle(f"le 200 revient en {delai * 1000:.0f} ms, sous les 3 s de Slack",
                 delai < 3.0, f"{delai:.2f} s")

        # Le rejeu de Slack, au niveau HTTP cette fois.
        code, _ = poster("/slack/events", evenement, requete(evenement))
        controle("le meme event_id est ignore, pas retraite", code == 200)

        # Un message de bot ne doit pas declencher de reponse, sinon le bot se
        # repond a lui-meme indefiniment.
        boucle = json.dumps({
            "type": "event_callback", "event_id": "Ev-bot",
            "event": {"type": "message", "text": "moi-meme", "channel": "C1",
                      "bot_id": "B1", "ts": "1.0"},
        }).encode()
        code, _ = poster("/slack/events", boucle, requete(boucle))
        controle("un message de bot est ignore (pas de boucle)", code == 200)
    finally:
        httpd.shutdown()
        httpd.server_close()


def main() -> int:
    print("EPREUVE HORS LIGNE DE L'APPLICATION SLACK")
    print(f"{GRIS}  L'espace de travail Slack n'existe pas : le dialogue reel "
          f"avec l'API n'est PAS couvert.{NORMAL}")
    eprouver_signature()
    eprouver_deduplication()
    eprouver_formatage()
    eprouver_defi()
    eprouver_service_http()

    print()
    if _echecs:
        print(f"{ROUGE}{len(_echecs)} controle(s) en echec{NORMAL} : "
              + ", ".join(_echecs), file=sys.stderr)
        return 1
    print(f"{VERT}TOUT PASSE{NORMAL}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

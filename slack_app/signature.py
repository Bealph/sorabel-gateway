"""Vérification de la signature des requêtes Slack.

POURQUOI C'EST LA PIECE CRITIQUE
Le bot expose un point d'entrée **public** : Slack pousse ses événements vers
une URL joignable depuis l'extérieur (D34). Sans vérification de signature,
n'importe qui peut lui faire croire qu'un message vient de Slack, et donc lui
faire appeler la gateway. C'est la seule frontière de confiance de ce service.

CE QUE LA SIGNATURE PROUVE, ET CE QU'ELLE NE PROUVE PAS
Elle prouve que la requête vient de l'application Slack qui partage ce secret,
et qu'elle est récente. Elle ne prouve **rien sur la personne** qui a écrit dans
Slack : cette identité est *attestée par le bot*, pas vérifiée par la gateway.
D28 l'interdit donc dans toute décision d'autorisation, et D34 la réserve au
journal. Le profil, lui, vient du lancement du processus serveur.

SPECIFICATION, relue le 2026-09-07 sur
https://docs.slack.dev/authentication/verifying-requests-from-slack

- en-têtes `X-Slack-Signature` et `X-Slack-Request-Timestamp`, insensibles à
  la casse ;
- chaîne de base : « Concatenate the version number, the timestamp, and the
  request body together, using a colon (`:`) as a delimiter », soit
  `v0:{timestamp}:{corps brut}` ;
- HMAC-SHA256 avec le secret de signature comme clé, condensé hexadécimal,
  préfixé de `v0=` ;
- rejet si l'horodatage s'écarte de plus de **cinq minutes** de l'heure
  locale ;
- comparaison par une fonction de comparaison HMAC, « instead of directly
  comparing the signatures for equality ».

Le corps doit être le **corps BRUT**, tel qu'il est arrivé. Le relire depuis un
JSON réanalysé puis resérialisé change les espaces et fait échouer la
vérification, sans que rien n'indique pourquoi.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import time
from dataclasses import dataclass

#: La spécification fixe cinq minutes. Ce n'est pas un réglage de confort : une
#: fenêtre plus large ouvre le rejeu, une fenêtre plus étroite fait échouer des
#: requêtes légitimes sur un simple décalage d'horloge.
FENETRE_SECONDES = 5 * 60

VERSION = "v0"

EN_TETE_SIGNATURE = "x-slack-signature"
EN_TETE_HORODATAGE = "x-slack-request-timestamp"


@dataclass(frozen=True)
class Verdict:
    """Le résultat, et sa raison. Un booléen seul ne se diagnostique pas."""

    valide: bool
    motif: str = ""

    def __bool__(self) -> bool:
        return self.valide


def secret(depuis_env: str = "SLACK_SIGNING_SECRET") -> str:
    """Le secret de signature, lu dans l'environnement et jamais écrit ailleurs.

    Absent, on rend une chaîne vide, et `verifier` refuse tout : un service qui
    démarrerait sans secret et accepterait les requêtes serait pire qu'un
    service arrêté.
    """
    return os.environ.get(depuis_env, "")


def chaine_de_base(horodatage: str, corps: bytes) -> bytes:
    """`v0:{timestamp}:{corps brut}`, tel que la spécification l'énonce."""
    return f"{VERSION}:{horodatage}:".encode() + corps


def signer(corps: bytes, horodatage: str, cle: str) -> str:
    """La signature attendue, au format `v0=<hexdigest>`.

    Exposée pour que les tests puissent forger une requête valide sans
    réimplémenter le calcul : un test qui recopie l'algorithme ne teste que sa
    propre copie.
    """
    condense = hmac.new(cle.encode(), chaine_de_base(horodatage, corps),
                        hashlib.sha256).hexdigest()
    return f"{VERSION}={condense}"


def verifier(corps: bytes, entetes: dict[str, str], cle: str | None = None,
             maintenant: float | None = None) -> Verdict:
    """La requête vient-elle bien de Slack, et est-elle récente ?

    `entetes` est indexé sans tenir compte de la casse, la spécification
    prévenant que « the letter case should not be assumed ».
    """
    cle = secret() if cle is None else cle
    if not cle:
        return Verdict(False, "aucun secret de signature configure "
                              "(SLACK_SIGNING_SECRET)")

    normalises = {k.lower(): v for k, v in entetes.items()}
    signature = normalises.get(EN_TETE_SIGNATURE, "")
    horodatage = normalises.get(EN_TETE_HORODATAGE, "")
    if not signature or not horodatage:
        return Verdict(False, "en-tete de signature ou d'horodatage absent")

    try:
        emis = float(horodatage)
    except ValueError:
        return Verdict(False, f"horodatage illisible : {horodatage!r}")

    ecart = abs((time.time() if maintenant is None else maintenant) - emis)
    if ecart > FENETRE_SECONDES:
        return Verdict(False, f"horodatage vieux de {ecart:.0f} s, au-dela des "
                              f"{FENETRE_SECONDES} s admises (rejeu ?)")

    # Comparaison a temps constant, exigee par la specification : une
    # comparaison ordinaire fuit la position du premier octet different, et
    # permet de reconstituer la signature octet par octet.
    if not hmac.compare_digest(signature, signer(corps, horodatage, cle)):
        return Verdict(False, "signature invalide")
    return Verdict(True)

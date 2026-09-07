#!/usr/bin/env python3
"""Chiffre le coût mensuel du déploiement, depuis les tarifs officiels.

    uv run python deploy/cout.py

POURQUOI CE SCRIPT PLUTOT QU'UN CHIFFRE DANS UN DOCUMENT
C'est l'item A4, ouvert depuis le chantier 7, et il y était écrit « aucun coût
chiffré, à établir à la calculatrice ». Un chiffre recopié dans un document
dériverait au premier changement de tarif ou de dimensionnement, et le projet a
déjà payé ce défaut cinq fois. Le coût se **calcule** donc, depuis deux sources
vivantes :

- l'**API tarifaire publique** d'Azure, `prices.azure.com`, qui ne demande
  aucune authentification ;
- la **configuration réellement déployée**, lue par `az`, et la
  **consommation mesurée**, lue dans les métriques.

DEUX PIEGES RENCONTRES, ET C'EST POURQUOI CE SCRIPT EXISTE EN L'ETAT

1. **L'alimentation EUR de l'API renvoie 0,00 pour les compteurs de calcul**,
   et pas seulement en France Central : vérifié sur les 61 régions. En USD les
   valeurs sont réelles. On interroge donc en USD et on le dit, plutôt que de
   publier un coût nul.

2. **Le tarif « repos » ne s'applique presque jamais ici.** La documentation de
   facturation exige que la réplique consomme *moins de 0,01 cœur vCPU* et
   reçoive *moins de 1 000 octets par seconde*. Mesure du 2026-09-07 :
   0,126 cœur en moyenne, soit **12,6 fois le seuil**. Le tarif actif
   s'applique donc, et c'est la borne haute qui compte.

Sources, relues le 2026-09-07 :
  https://azure.microsoft.com/en-us/pricing/details/container-apps/
    « The first 180,000 vCPU-seconds, 360,000 GiB-seconds, and 2 million
      requests per subscription per month are free. »
  https://learn.microsoft.com/en-us/azure/container-apps/billing
    conditions du tarif repos, dont « using less than 0.01 vCPU cores »
"""
from __future__ import annotations

import functools
import json
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request

API = "https://prices.azure.com/api/retail/prices"

#: Le palier gratuit mensuel par abonnement, tel que la page tarifaire
#: officielle l'énonce. Écrit ici en dur, et sourcé dans l'en-tête : c'est une
#: affirmation de Microsoft, pas une valeur que nous pourrions calculer.
GRATUIT_VCPU_S = 180_000
GRATUIT_GIB_S = 360_000
GRATUIT_REQUETES = 2_000_000

#: Le seuil sous lequel une réplique est facturée au tarif repos.
SEUIL_REPOS_COEURS = 0.01

SECONDES_PAR_MOIS = 30 * 24 * 3600

GROUPE = "adialloRG"
APPLICATION = "sorabel-gateway"
REGISTRE = "acrsorabelgateway"


def tarifs(service: str, region: str) -> dict[str, float]:
    """Les tarifs d'un service, en USD. Voir le piège 1 de l'en-tête."""
    filtre = f"serviceName eq '{service}' and armRegionName eq '{region}'"
    url = f"{API}?" + urllib.parse.urlencode(
        {"currencyCode": "USD", "$filter": filtre})
    with urllib.request.urlopen(url, timeout=45) as reponse:
        items = json.load(reponse).get("Items", [])
    return {i["meterName"]: i["retailPrice"] for i in items}


@functools.cache
def _binaire_az() -> str:
    """Le chemin d'`az`, qui est un `.cmd` sous Windows.

    `subprocess` ne devine pas l'extension : sans cette résolution, l'appel
    échoue en `FileNotFoundError` alors que `az` fonctionne parfaitement dans
    le terminal. Constaté le 2026-09-07.
    """
    for nom in ("az", "az.cmd", "az.bat"):
        chemin = shutil.which(nom)
        if chemin:
            return chemin
    raise FileNotFoundError(
        "az introuvable dans le PATH. Installer Azure CLI, ou verifier le PATH.")


def az(*args: str) -> str:
    return subprocess.run([_binaire_az(), *args], check=True,
                          capture_output=True, text=True,
                          encoding="utf-8").stdout.strip()


def configuration() -> tuple[float, float, int, str]:
    """(vCPU, Gio, repliques minimales, region) reellement deployes."""
    brut = az("containerapp", "show", "--name", APPLICATION,
              "--resource-group", GROUPE, "-o", "json")
    d = json.loads(brut)
    conteneur = d["properties"]["template"]["containers"][0]
    memoire = conteneur["resources"]["memory"]          # ex. « 4Gi »
    echelle = d["properties"]["template"].get("scale") or {}
    region = d["location"].lower().replace(" ", "")
    return (float(conteneur["resources"]["cpu"]),
            float(memoire.rstrip("Gi")),
            int(echelle.get("minReplicas") or 0),
            region)


def cpu_mesure() -> tuple[float, float] | None:
    """(moyenne, maximum) en coeurs, sur la fenetre par defaut des metriques."""
    identifiant = az("containerapp", "show", "--name", APPLICATION,
                     "--resource-group", GROUPE, "--query", "id", "-o", "tsv")
    brut = az("monitor", "metrics", "list", "--resource", identifiant,
              "--metric", "UsageNanoCores", "--interval", "PT5M",
              "--aggregation", "Average", "Maximum", "-o", "json")
    points = [p for m in json.loads(brut).get("value", [])
              for s in m["timeseries"] for p in s["data"]
              if p.get("average") is not None]
    if not points:
        return None
    moyenne = sum(p["average"] for p in points) / len(points) / 1e9
    maximum = max((p.get("maximum") or p["average"]) for p in points) / 1e9
    return moyenne, maximum


def montant(valeur: float) -> str:
    """Rendu en DOLLARS, et le nom le dit : l or convertir demanderait un taux
    du jour, donc une source de plus, qui bougerait sans que le calcul change."""
    return f"{valeur:,.2f} USD".replace(",", " ")


def main() -> int:
    try:
        vcpu, gio, repliques, region = configuration()
    except Exception as e:  # noqa: BLE001
        print(f"configuration illisible ({type(e).__name__}). "
              "Verifier az login et le nom de l'application.", file=sys.stderr)
        return 2

    print(f"CONFIGURATION DEPLOYEE, {APPLICATION} dans {GROUPE}")
    print(f"  {vcpu} vCPU, {gio} Gio, min-replicas {repliques}, {region}")

    aca = tarifs("Azure Container Apps", region)
    acr = tarifs("Container Registry", region)
    actif_vcpu = aca.get("Standard vCPU Active Usage", 0.0)
    repos_vcpu = aca.get("Standard vCPU Idle Usage", 0.0)
    actif_mem = aca.get("Standard Memory Active Usage", 0.0)
    repos_mem = aca.get("Standard Memory Idle Usage", 0.0)
    unite_acr = acr.get("Basic Registry Unit", 0.0)

    print("\nTARIFS OFFICIELS, en USD (voir le piege 1 : l'EUR renvoie 0)")
    print(f"  vCPU actif   {actif_vcpu:.9f} par vCPU-seconde")
    print(f"  vCPU repos   {repos_vcpu:.9f} par vCPU-seconde")
    print(f"  memoire act. {actif_mem:.9f} par Gio-seconde")
    print(f"  registre     {unite_acr:.4f} par jour, SKU Basic")

    if repliques == 0:
        print("\nmin-replicas est a 0 : aucune consommation de calcul au repos.")
        print(f"Reste le registre : {montant(unite_acr * 30)} par mois.")
        return 0

    vcpu_s = vcpu * SECONDES_PAR_MOIS * repliques
    gib_s = gio * SECONDES_PAR_MOIS * repliques
    vcpu_facture = max(0.0, vcpu_s - GRATUIT_VCPU_S)
    gib_facture = max(0.0, gib_s - GRATUIT_GIB_S)

    print(f"\nVOLUMES SUR 30 JOURS, {repliques} replique(s) en continu")
    print(f"  {vcpu_s:>14,.0f} vCPU-s, dont {GRATUIT_VCPU_S:,} gratuits"
          .replace(",", " "))
    print(f"  {gib_s:>14,.0f} Gio-s,  dont {GRATUIT_GIB_S:,} gratuits"
          .replace(",", " "))

    mesure = cpu_mesure()
    print("\nQUEL TARIF S'APPLIQUE ?")
    if mesure is None:
        print("  metriques indisponibles : les deux bornes sont donnees.")
        au_repos = True
    else:
        moyenne, maximum = mesure
        au_repos = moyenne < SEUIL_REPOS_COEURS
        print(f"  CPU mesure : {moyenne:.5f} coeur en moyenne, "
              f"{maximum:.5f} au maximum")
        print(f"  seuil du tarif repos : {SEUIL_REPOS_COEURS} coeur")
        if au_repos:
            print("  -> sous le seuil, le tarif repos peut s'appliquer")
        else:
            print(f"  -> {moyenne / SEUIL_REPOS_COEURS:.0f} fois AU-DESSUS du "
                  "seuil : le tarif ACTIF s'applique")

    registre = unite_acr * 30
    for nom, tv, tm in (("borne basse, tarif repos", repos_vcpu, repos_mem),
                        ("borne haute, tarif actif", actif_vcpu, actif_mem)):
        calcul = vcpu_facture * tv + gib_facture * tm
        print(f"\n{nom.upper()}")
        print(f"  calcul   {montant(calcul)}")
        print(f"  registre {montant(registre)}")
        print(f"  TOTAL    {montant(calcul + registre)} par mois")

    print("\nCE QUI N'EST PAS COMPTE : l'ingestion Log Analytics, faible mais "
          "non nulle, et les requetes HTTP, tres en dessous des 2 millions "
          "gratuits.")
    print("\nLE LEVIER LE PLUS FORT est min-replicas 0 : le calcul tombe a "
          "zero au repos, au prix d'un reveil de plusieurs minutes, le temps "
          "de retirer 6 Go d'image et de charger les modeles.")
    print("La facturation porte sur les ressources ALLOUEES, pas consommees : "
          f"reduire l'allocation la reduit proportionnellement. La memoire "
          f"mesuree etant proche de 2,5 Gio, {gio} Gio laisse peu de marge.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

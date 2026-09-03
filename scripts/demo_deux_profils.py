#!/usr/bin/env python3
"""Session de démonstration : la même séquence d'appels, sur les deux profils.

    uv run python scripts/demo_deux_profils.py

C'est le livrable que le brief nomme : « démontrer deux profils différents ».
Elle passe par le **vrai protocole MCP**, en stdio, avec un processus serveur par
profil : c'est le produit qu'on montre, pas la couche interne.

**Deux processus, et c'est la topologie normale de MCP.** Le profil est fixé au
lancement (D28) et immuable pour la vie du processus. « Un même serveur MCP »
au sens d'E4 désigne un même programme, un même catalogue et une même matrice,
pas un même identifiant de processus. Les deux processus lisent ici le **même**
fichier de matrice et écrivent dans le **même** journal : c'est ce qui rend la
comparaison vérifiable, puisque les deux décisions opposées se lisent à la suite
dans le même fichier.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

PROFILS = ("support", "commercial")

#: Le scénario. Chaque ligne est choisie pour ce qu'elle démontre, et les deux
#: profils reçoivent exactement les mêmes appels : c'est la seule façon de
#: montrer que la différence vient de la matrice et de rien d'autre.
#:
#: Une ligne a dû être changée le 2026-09-03. Elle demandait « quelle est notre
#: politique tarifaire sur les remises ? », et les DEUX profils s'abstenaient.
#: Vérification faite, l'abstention était JUSTE : la note intitulée « Point
#: politique tarifaire » traite d'une revue de prix sur l'outillage à main et ne
#: parle pas de remises. Le bi-encodeur dense avait matché sur le titre, le
#: cross-encodeur a lu la question et le passage ensemble et a conclu que le
#: passage ne répondait pas. C'est exactement son travail, et c'est la
#: démonstration en acte de ce que la mesure E6 avait chiffré : le reranking
#: n'apporte presque rien au classement, et beaucoup à l'abstention.
SCENARIO = (
    ("answer_question", {"question": "quelle est la procedure de retour d'un "
                                     "produit defectueux sous garantie ?"},
     "E1 : une réponse documentaire, avec ses sources"),
    ("answer_question", {"question": "ou en est la negociation avec le "
                                     "fournisseur Fixor ?"},
     "E5 : la réponse vit dans les notes internes, fermées au support"),
    ("get_schema", {},
     "E4 : le tool n'est pas au catalogue du support"),
    ("ask_database", {"question": "quelle est la marge sur la REF-8842 ?"},
     "E5 : la colonne est retirée au support"),
    ("check_stock", {"reference": "REF-8842"},
     "un tool figé, accessible aux deux, déterministe"),
    ("ask_database", {"question": "supprime les commandes de test"},
     "E3 : aucune ecriture n'atteint la base. Ici c'est le generateur qui se "
     "recuse ; quand il produit un DELETE, c'est la couche AST qui refuse, "
     "eprouve dans tests/eprouver_gardes.py"),
)

VERT, ROUGE, JAUNE, GRIS = "\033[32m", "\033[31m", "\033[33m", "\033[90m"
NORMAL = "\033[0m"
COULEUR = {"ok": VERT, "refused": ROUGE, "clarification": JAUNE,
           "hors_corpus": JAUNE, "error": GRIS}


def _sans_couleur() -> bool:
    return os.environ.get("NO_COLOR") is not None or not sys.stdout.isatty()


def peindre(texte: str, couleur: str) -> str:
    return texte if _sans_couleur() else f"{couleur}{texte}{NORMAL}"


async def jouer(profil: str, journal: Path) -> list[dict]:
    """Lance un serveur au profil donné et joue tout le scénario."""
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "mcp_server.server"],
        env={**os.environ, "SORABEL_PROFILE": profil,
             "GATEWAY_JOURNAL": str(journal)},
        cwd=str(RACINE),
    )
    resultats: list[dict] = []
    async with stdio_client(params) as (lecture, ecriture):
        async with ClientSession(lecture, ecriture) as session:
            await session.initialize()
            catalogue = await session.list_tools()
            resultats.append({"_catalogue": [t.name for t in catalogue.tools]})
            for tool, arguments, _ in SCENARIO:
                reponse = await session.call_tool(tool, arguments)
                texte = next((c.text for c in reponse.content
                              if getattr(c, "text", None)), "{}")
                resultats.append(json.loads(texte))
    return resultats


def resumer(enveloppe: dict) -> str:
    statut = enveloppe.get("status", "?")
    payload = enveloppe.get("payload") or {}
    code = payload.get("code", "")
    detail = ""
    if statut == "ok":
        if "sources" in payload:
            detail = f"{len(payload['sources'])} source(s)"
        elif "rows" in payload:
            detail = f"{len(payload['rows'])} ligne(s)"
        elif "schema" in payload:
            detail = f"{len(payload['schema'])} caractères de schéma"
    return f"{statut:14}{code:20}{detail}"


async def principal(journal: Path) -> int:
    if journal.exists():
        journal.unlink()

    print(f"Journal de la session : {journal}")
    print("Matrice : governance/matrice.yaml, la MEME pour les deux processus\n")

    par_profil = {}
    for profil in PROFILS:
        print(f"  lancement du serveur, profil {profil}...", flush=True)
        par_profil[profil] = await jouer(profil, journal)

    print("\n" + "=" * 96)
    print("CATALOGUE ANNONCE PAR tools/list")
    print("=" * 96)
    for profil in PROFILS:
        outils = par_profil[profil][0]["_catalogue"]
        print(f"  {profil:11} {len(outils)} tools : {', '.join(sorted(outils))}")
    manquants = (set(par_profil["commercial"][0]["_catalogue"])
                 - set(par_profil["support"][0]["_catalogue"]))
    print(f"  {peindre('difference', JAUNE)} : {', '.join(sorted(manquants)) or 'aucune'}")

    print("\n" + "=" * 96)
    print("LE MEME APPEL, LES DEUX PROFILS")
    print("=" * 96)
    for i, (tool, arguments, pourquoi) in enumerate(SCENARIO, start=1):
        argument = next(iter(arguments.values()), "")
        print(f"\n{i}. {tool}({str(argument)[:58]!r})")
        print(f"   {peindre(pourquoi, GRIS)}")
        for profil in PROFILS:
            enveloppe = par_profil[profil][i]
            statut = enveloppe.get("status", "?")
            print(f"     {profil:11} "
                  + peindre(resumer(enveloppe), COULEUR.get(statut, "")))
            if statut != "ok":
                print(f"       {peindre(enveloppe.get('message', '')[:82], GRIS)}")

    print("\n" + "=" * 96)
    print("LE JOURNAL, PARTAGE PAR LES DEUX PROCESSUS")
    print("=" * 96)
    entrees = [json.loads(ligne) for ligne
               in journal.read_text(encoding="utf-8").splitlines() if ligne.strip()]
    print(f"  {len(entrees)} entrees pour {len(SCENARIO) * len(PROFILS)} appels\n")
    for e in entrees:
        couleur = COULEUR.get(e["status"], "")
        print(f"  {e['timestamp'][11:19]}  {e['profile']:11} {e['tool']:16} "
              + peindre(f"{e['status']:14}{e.get('code', ''):18}", couleur)
              + f"{e['duree_ms']:8.0f} ms")

    autorises = sum(1 for e in entrees if e["status"] != "refused")
    refuses = len(entrees) - autorises
    print(f"\n  {autorises} appel(s) autorise(s), {refuses} refuse(s), "
          "tous journalises. C'est E5.")
    if len(entrees) != len(SCENARIO) * len(PROFILS):
        print(peindre("  ATTENTION : le compte ne tombe pas juste.", ROUGE))
        return 1
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--journal", default=str(RACINE / "logs" / "demo.jsonl"),
                    help="chemin du journal de la session")
    ns = ap.parse_args()
    return asyncio.run(principal(Path(ns.journal)))


if __name__ == "__main__":
    raise SystemExit(main())

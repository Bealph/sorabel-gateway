#!/usr/bin/env python3
"""Contrôle que `eval/cas_mcp.jsonl` dit encore la vérité.

POURQUOI CE SCRIPT EXISTE
Ce fichier de cas est l'**oracle** des quatre tests d'acceptation MCP, ceux
qu'on joue en direct devant l'évaluateur. Il a été écrit pendant la revue du
2026-09-02, précisément pour combler l'absence d'oracle, puis le dépôt amont a
été rapatrié et la matrice a changé.

Le 2026-09-03, il était périmé sur **cinq axes** à la fois :

- les droits : il attendait `search_docs` refusé au support, alors que le
  cadrage DSI le lui accorde. Cinq cas concernés ;
- un profil `dev` qui n'existe pas au contrat. Trois cas ;
- deux statuts hors contrat, `out_of_corpus` et `not_found` ;
- des noms d'arguments périmés, `q` pour `query`, `ref` pour `reference` ;
- des clés de journal en français, `horodatage`, `decision`, `latence_ms`.

C'est la troisième occurrence du même mode de défaillance, après les
énumérations de la base et `GUIDE_ACCES.md` : **ce qui est recopié dérive**. Un
oracle faux est plus dangereux qu'un oracle absent, parce qu'il fait échouer un
serveur juste, ou pire, réussir un serveur faux.

CE QUE FAIT CE SCRIPT
Il confronte chaque cas aux **sources qui font foi** : `governance/matrice.yaml`
pour les droits, le catalogue MCP pour les signatures, et le contrat
d'intégration pour les statuts et les clés de journal. Il ne juge pas ce qu'un
appel *rend* : cela reste le travail des tests. Il juge si l'attente est
**formulable**, c'est-à-dire cohérente avec ce que le système peut produire.

Usage : python eval/verifier_cas_mcp.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from common.matrice import droits  # noqa: E402
from mcp_server.catalogue import CATALOGUE  # noqa: E402
from mcp_server.journal import CHAMPS_CONTRAT  # noqa: E402

CAS = RACINE / "eval" / "cas_mcp.jsonl"

#: Les cinq statuts du contrat d'intégration, et rien d'autre.
STATUTS = frozenset({"ok", "refused", "clarification", "hors_corpus", "error"})

#: Profils du contrat, plus le pseudo-profil `tous` du cas qui porte sur le
#: journal lui-même.
PROFILS = frozenset({"support", "commercial"})

#: Tools qui ne sont pas au catalogue mais que des cas nomment légitimement :
#: un nom inexistant pour éprouver le deny-by-default, une composition, et le
#: joker du cas qui porte sur le journal.
HORS_CATALOGUE = frozenset({"tool_inexistant", "*", "search_docs+get_document"})

#: Vocabulaire périmé, celui d'avant le rapatriement de l'amont. Interdit
#: partout, y compris dans les motifs quand il y désigne une attente.
PERIMES = (
    (r'"status": "(out_of_corpus|not_found)"', "statut hors contrat"),
    (r'"(horodatage|latence_ms|request_id|decision)"', "clé de journal périmée"),
    (r'"profil": "dev"', "profil dev, qui n'existe pas au contrat"),
    (r'"(q|ref)": ', "nom d'argument périmé : query, reference"),
)

#: Nombre maximal de cas autorisés à porter `limite_connue`. Voir le
#: contrôle 10 bis : le plafond est le seul garde-fou qu'un script
#: puisse réellement opposer à l'accumulation des échecs tolérés.
PLAFOND_LIMITES = 2

SIGNATURES = {o.nom: set((o.schema().get("properties") or {})) for o in CATALOGUE}


def charger() -> list[dict]:
    return [json.loads(ligne) for ligne
            in CAS.read_text(encoding="utf-8").splitlines() if ligne.strip()]


def controler(cas: list[dict], brut: str) -> list[str]:
    echecs: list[str] = []

    def ko(quoi: str) -> None:
        echecs.append(quoi)

    # 1. Vocabulaire périmé, sur le texte brut : le plus large des filets.
    for motif, quoi in PERIMES:
        for m in re.finditer(motif, brut):
            ligne = brut[:m.start()].count("\n") + 1
            ko(f"ligne {ligne} : {m.group(0)!r} -- {quoi}")

    # 2. Identité des cas.
    ids = [c["id"] for c in cas]
    if len(ids) != len(set(ids)):
        ko(f"identifiants en double : {sorted({i for i in ids if ids.count(i) > 1})}")

    for c in cas:
        i = c["id"]
        profil, tool = c["profil"], c["tool"]
        attendu = c.get("attendu") or {}

        # 3. Le profil existe.
        if profil not in PROFILS and profil != "tous":
            ko(f"{i} : profil inconnu {profil!r}")
            continue

        # 4. Le tool existe.
        if tool not in SIGNATURES and tool not in HORS_CATALOGUE:
            ko(f"{i} : tool inconnu {tool!r}")
            continue

        # 5. Le statut attendu est l'un des cinq du contrat.
        statut = attendu.get("status")
        if statut is not None and statut not in STATUTS:
            ko(f"{i} : statut {statut!r} hors contrat, attendus {sorted(STATUTS)}")

        # 6. LE CONTROLE QUI AURAIT ATTRAPE LA DERIVE.
        #    L'attente de droit doit s'accorder avec la matrice, dans les DEUX
        #    sens. Un cas qui attend un refus de tool sur un tool accordé est
        #    faux ; un cas qui attend autre chose qu'un refus sur un tool non
        #    accordé l'est tout autant, et c'est le sens qui manquait.
        if profil in PROFILS and tool in SIGNATURES:
            accorde = tool in droits(profil).tools
            refus_de_tool = (statut == "refused"
                             and attendu.get("code") == "UNAUTHORIZED_TOOL")
            if refus_de_tool and accorde:
                ko(f"{i} : attend UNAUTHORIZED_TOOL, or la matrice accorde "
                   f"{tool!r} au profil {profil!r}")
            if accorde is False and not refus_de_tool:
                ko(f"{i} : la matrice refuse {tool!r} au profil {profil!r}, "
                   f"l'attente devrait etre refused/UNAUTHORIZED_TOOL, "
                   f"pas {statut!r}")

        # 7. Les noms d'arguments sont ceux de la signature du tool.
        if tool in SIGNATURES:
            inconnus = set(c.get("args") or {}) - SIGNATURES[tool]
            if inconnus:
                ko(f"{i} : argument(s) hors signature de {tool} : "
                   f"{sorted(inconnus)}, attendus {sorted(SIGNATURES[tool])}")

        # 8. Les champs de journal attendus existent réellement au journal.
        champs = attendu.get("champs_obligatoires")
        if champs and set(champs) - set(CHAMPS_CONTRAT):
            ko(f"{i} : champs de journal inconnus : "
               f"{sorted(set(champs) - set(CHAMPS_CONTRAT))}")

        # 9. Un motif vide laisserait un cas sans raison d'être.
        if len(c.get("motif", "")) < 40:
            ko(f"{i} : motif absent ou trop court pour justifier le cas")

        # 10. `limite_connue` déclare qu'un cas échoue aujourd'hui SANS que
        #     l'attente soit alignée sur le comportement observé. C'est la
        #     bonne façon de consigner une faiblesse, et la mauvaise façon
        #     serait d'en faire un fourre-tout : on exige donc qu'elle nomme
        #     une décision du projet et une cause, sans quoi elle deviendrait
        #     un moyen de faire disparaître un échec du rapport.
        limite = c.get("limite_connue")
        if limite is not None:
            if not re.fullmatch(r"D\d+", str(limite.get("decision_projet", ""))):
                ko(f"{i} : limite_connue sans decision de projet nommee (ex. D48)")
            if len(limite.get("cause", "")) < 40:
                ko(f"{i} : limite_connue sans cause etayee")
            if not limite.get("constat"):
                ko(f"{i} : limite_connue sans constat de ce qui echoue")

    # 10 bis. LE PLAFOND, et c'est le seul garde-fou réellement opposable.
    #     Éprouvé le 2026-09-03 : un `limite_connue` bien formé mais creux
    #     franchit les contrôles ci-dessus, parce qu'un script ne juge pas la
    #     sincérité d'une prose. Il peut en revanche compter. Un oracle qui
    #     accumule les limites tolérées cesse d'être un oracle, et l'accumulation
    #     se ferait un cas à la fois, sans que rien ne sonne. Relever ce plafond
    #     doit rester un geste délibéré, visible en revue de code.
    limites = [c["id"] for c in cas if c.get("limite_connue")]
    if len(limites) > PLAFOND_LIMITES:
        ko(f"{len(limites)} cas portent limite_connue ({', '.join(limites)}), "
           f"plafond fixe a {PLAFOND_LIMITES}. Corriger la cause, ou relever le "
           f"plafond sciemment.")

    # 11. La couverture : chaque tool du catalogue est éprouvé au moins une fois,
    #     et chacune des exigences que ces cas portent l'est aussi.
    joues = {c["tool"] for c in cas}
    for nom in SIGNATURES:
        if nom not in joues:
            ko(f"tool {nom!r} du catalogue : aucun cas ne l'eprouve")
    for exigence in ("E1", "E3", "E4", "E5"):
        if not any(c["exigence"] == exigence for c in cas):
            ko(f"exigence {exigence} : aucun cas ne la porte")

    return echecs


def main() -> int:
    if not CAS.exists():
        print(f"ERREUR : {CAS} absent.", file=sys.stderr)
        return 2
    brut = CAS.read_text(encoding="utf-8")
    cas = charger()
    echecs = controler(cas, brut)

    for e in echecs:
        print(f"  ECHEC {e}", file=sys.stderr)
    if echecs:
        print(f"\n{len(echecs)} incoherence(s) entre {CAS.name} et la matrice.",
              file=sys.stderr)
        return 1

    par_profil = {p: sum(1 for c in cas if c["profil"] == p)
                  for p in sorted({c["profil"] for c in cas})}
    refus = sum(1 for c in cas if (c.get("attendu") or {}).get("status") == "refused")
    print(f"{len(cas)} cas coherents avec la matrice et le contrat.")
    print(f"  profils : {par_profil}")
    print(f"  {refus} refus attendus, {len(cas) - refus} appels attendus autorises")
    print(f"  {len(SIGNATURES)} tools du catalogue, tous eprouves")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

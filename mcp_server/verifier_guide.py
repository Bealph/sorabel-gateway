#!/usr/bin/env python3
"""Vérifie le mini guide d'accès, et régénère ses tableaux de faits.

POURQUOI CE SCRIPT EXISTE
`mcp_server/GUIDE_ACCES.md` est un **livrable**, lu par un intégrateur externe.
Le 2026-09-03 il annonçait encore trois profils dont un `dev` qui n'existe pas,
donnait `search_docs` comme interdit au support alors qu'il lui est accessible,
donnait `get_schema` comme accessible alors qu'il ne l'est pas, écrivait
`SORABEL_PROFIL` au lieu de `SORABEL_PROFILE`, et décrivait des charges utiles
avec des clés qui n'existent nulle part dans le code.

La revue de conception avait prédit exactement cela : « rien ne compare les
trois vues à la source ». Le constat n'avait pas été fermé, et la dérive est
arrivée. Un guide d'accès faux est pire qu'un guide absent : l'intégrateur lui
fait confiance.

CE QUE FAIT CE SCRIPT
Il **génère** les tableaux de faits du guide, entre balises, depuis les deux
seules sources qui font foi : `governance/matrice.yaml` pour les droits, et le
serveur lui-même pour la forme des charges utiles. Et il contrôle les
affirmations textuelles qu'on ne peut pas générer, comme le nom de la variable
d'environnement.

Usage : python mcp_server/verifier_guide.py
        python mcp_server/verifier_guide.py --verifier   controle seul
        python mcp_server/verifier_guide.py --sans-appels  n'appelle aucun tool
"""
from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from common.matrice import catalogue, droits  # noqa: E402
from mcp_server.catalogue import CATALOGUE  # noqa: E402

GUIDE = RACINE / "mcp_server" / "GUIDE_ACCES.md"

#: Les cinq statuts du contrat d'intégration, et rien d'autre.
STATUTS = ("ok", "refused", "clarification", "hors_corpus", "error")

#: Affirmations textuelles à contrôler : (motif interdit, ce qu'il faut écrire).
#: Elles ne se génèrent pas, mais elles se vérifient.
INTERDITS = (
    (r"SORABEL_PROFIL\b(?!E)", "SORABEL_PROFILE"),
    (r"\bprofil `dev`|\| `dev` \||profil dev\b", "le profil dev n'existe pas au contrat"),
)

DEBUT = "<!-- GENERE-DEBUT {} -->"
FIN = "<!-- GENERE-FIN {} -->"


def bloc(nom: str, lignes: list[str]) -> str:
    return "\n".join([DEBUT.format(nom), *lignes, FIN.format(nom)])


def remplacer(texte: str, nom: str, contenu: str) -> str:
    motif = re.compile(
        re.escape(DEBUT.format(nom)) + r".*?" + re.escape(FIN.format(nom)), re.S)
    if not motif.search(texte):
        raise SystemExit(f"balises {nom!r} absentes de {GUIDE.name}. "
                         "Les poser autour du tableau a generer.")
    return motif.sub(lambda _: contenu, texte)


# --- Les tableaux générés -----------------------------------------------------

def table_tools() -> list[str]:
    """Qui peut appeler quoi. Source : `governance/matrice.yaml`."""
    profils = ["support", "commercial"]
    droits_par_profil = {p: droits(p) for p in profils}
    L = ["| Tool | " + " | ".join(f"`{p}`" for p in profils) + " |",
         "| --- | " + " | ".join([":---:"] * len(profils)) + " |"]
    for outil in CATALOGUE:
        cases = ["oui" if outil.nom in droits_par_profil[p].tools else "**non**"
                 for p in profils]
        L.append(f"| `{outil.nom}` | " + " | ".join(cases) + " |")
    L += ["",
          "Un appel à un tool absent de votre colonne est refusé **avant toute "
          "logique métier**, avec le code `UNAUTHORIZED_TOOL`. Ce n'est pas une "
          "panne, c'est le comportement attendu. Le catalogue annoncé par "
          "`tools/list` est lui aussi borné à votre profil : on ne vous annonce "
          "pas ce que vous ne pouvez pas appeler."]
    return L


def table_ressources() -> list[str]:
    """Collections et tables accessibles. Source : la matrice."""
    L = ["| Ressource | `support` | `commercial` |", "| --- | :---: | :---: |"]
    sup, com = droits("support"), droits("commercial")
    for coll in sorted(sup.collections | com.collections):
        L.append(f"| collection `{coll}` | "
                 f"{'oui' if coll in sup.collections else '**non**'} | "
                 f"{'oui' if coll in com.collections else 'oui'} |")
    for table in sorted(sup.tables | com.tables):
        L.append(f"| table `{table}` | "
                 f"{'oui' if table in sup.tables else '**non**'} | "
                 f"{'oui' if table in com.tables else 'oui'} |")
    for colonne in sorted(sup.colonnes_interdites | com.colonnes_interdites):
        L.append(f"| colonne `{colonne}` | "
                 f"{'**retirée**' if colonne in sup.colonnes_interdites else 'visible'} | "
                 f"{'**retirée**' if colonne in com.colonnes_interdites else 'visible'} |")
    L += ["",
          "Une **table** absente est un refus, pas un filtrage : `ventes` n'est "
          "pas accessible au `support`, pas même par une jointure. Une **colonne** "
          "retirée l'est dans toute la requête, y compris dans un tri, un filtre "
          "ou une sous-requête, et pas seulement dans les colonnes affichées."]
    return L


#: Appels représentatifs, un par tool, pour relever la forme réelle des charges
#: utiles. Le profil est celui qui a le droit d'appeler le tool.
APPELS = (
    ("answer_question", "support",
     {"question": "quelle est la procedure de retour d'un produit defectueux ?"}),
    ("search_docs", "support", {"query": "REF-8842"}),
    ("get_document", "support", {"doc_id": "REF-8842-v2.1"}),
    ("list_sources", "support", {"doc_type": "fiche_technique"}),
    ("ask_database", "commercial", {"question": "combien de commandes en avril ?"}),
    ("get_schema", "commercial", {}),
    ("check_stock", "support", {"reference": "REF-8842"}),
    ("order_status", "support", {"order_id": "CMD-2025-0004"}),
)


def _forme(valeur, profondeur: int = 0) -> str:
    """Décrit la FORME d'une valeur, jamais son contenu.

    Le guide doit dire quelles clés existent, pas ce que la base contient : une
    charge utile recopiée deviendrait une fuite et une source de dérive.
    """
    if isinstance(valeur, dict):
        if profondeur >= 1:
            return "{" + ", ".join(f"`{k}`" for k in valeur) + "}"
        return ", ".join(f"`{k}`" + (f" {_forme(v, profondeur + 1)}"
                                     if isinstance(v, (dict, list)) and v else "")
                         for k, v in valeur.items())
    if isinstance(valeur, list):
        return "[" + (_forme(valeur[0], profondeur + 1) if valeur else "") + "]"
    return ""


def table_payloads(sans_appels: bool) -> list[str]:
    """La forme réelle de chaque charge utile, relevée en appelant le serveur."""
    L = ["| Tool | `status` | Clés de `payload` en cas de succès |",
         "| --- | --- | --- |"]
    if sans_appels:
        L.append("| *(relevé non joué : `--sans-appels`)* | | |")
        return L

    from mcp_server.server import Gateway

    passerelles = {p: Gateway(droits(p)) for p in ("support", "commercial")}
    for nom, profil, arguments in APPELS:
        statut, payload, _ = passerelles[profil].appeler(nom, arguments)
        L.append(f"| `{nom}` | `{statut}` | {_forme(payload) or '*(vide)*'} |")
    L += ["",
          "Relevé en appelant réellement le serveur : ce tableau ne peut pas "
          "diverger du code sans que le contrôle tombe. Seules les **clés** y "
          "figurent, jamais les valeurs."]
    return L


def table_statuts() -> list[str]:
    L = ["| `status` | Ce qu'il signifie | Conduite à tenir |",
         "| --- | --- | --- |",
         "| `ok` | réponse valide | l'exploiter |",
         "| `refused` | droit refusé, écriture refusée, ou colonne hors périmètre "
         "| afficher le refus, ne pas reformuler pour contourner |",
         "| `clarification` | la question est ambiguë | redemander la précision |",
         "| `hors_corpus` | la documentation ne couvre pas la question "
         "| le dire, ne rien inventer |",
         "| `error` | panne technique du serveur | aucune conclusion métier |",
         "",
         "**Ces cinq statuts sont les seuls.** Un code plus précis peut "
         "accompagner un refus dans `payload.code`, par exemple "
         "`UNAUTHORIZED_TOOL`, `FORBIDDEN_COLUMN`, `READ_ONLY_VIOLATION` ou "
         "`OUT_OF_SCHEMA`. Il ne remplace jamais le `status` : un client "
         "aiguille sur `status`, et lit `code` pour affiner."]
    return L


# --- Contrôles textuels -------------------------------------------------------

def controler(texte: str) -> list[str]:
    echecs = []
    for motif, attendu in INTERDITS:
        for m in re.finditer(motif, texte):
            ligne = texte[:m.start()].count("\n") + 1
            echecs.append(f"ligne {ligne} : {m.group(0)!r} -- attendu : {attendu}")

    nommes = set(re.findall(r"`(support|commercial|dev)`", texte))
    inconnus = nommes - {"support", "commercial"}
    if inconnus:
        echecs.append(f"profils inconnus cites : {sorted(inconnus)}")

    for outil in catalogue():
        if f"`{outil}`" not in texte:
            echecs.append(f"tool {outil} du catalogue jamais cite dans le guide")
    return echecs


def main() -> int:
    if not GUIDE.exists():
        print(f"ERREUR : {GUIDE} absent.", file=sys.stderr)
        return 2
    texte = GUIDE.read_text(encoding="utf-8")
    sans_appels = "--sans-appels" in sys.argv

    neuf = texte
    blocs = [("tools", table_tools()),
             ("ressources", table_ressources()),
             ("statuts", table_statuts())]
    if not sans_appels:
        # En `--sans-appels`, on ne RELEVE pas les charges utiles, donc on ne
        # les compare pas non plus : substituer un texte de remplacement puis
        # conclure a une derive ferait crier au loup pour rien, et une alerte
        # qui se declenche a tort finit par etre ignoree.
        blocs.append(("payloads", table_payloads(sans_appels=False)))
    for nom, lignes in blocs:
        neuf = remplacer(neuf, nom, bloc(nom, lignes))
    neuf = re.sub(r"(> Tableaux de faits générés le )\d{4}-\d{2}-\d{2}",
                  lambda m: m.group(1) + date.today().isoformat(), neuf)

    echecs = controler(neuf)
    for e in echecs:
        print(f"  ECHEC {e}", file=sys.stderr)
    if echecs:
        print(f"\n{len(echecs)} affirmation(s) fausse(s), rien n'a ete ecrit.",
              file=sys.stderr)
        return 1

    if "--verifier" in sys.argv:
        sans_date = lambda t: re.sub(r"générés le \d{4}-\d{2}-\d{2}", "generes le DATE", t)  # noqa: E731
        if sans_date(neuf) == sans_date(texte):
            print("guide a jour, aucune affirmation fausse.")
            return 0
        print("GUIDE PERIME : relancer python mcp_server/verifier_guide.py",
              file=sys.stderr)
        return 1

    GUIDE.write_text(neuf, encoding="utf-8", newline="\n")
    print(f"{GUIDE.relative_to(RACINE)} regenere, aucune affirmation fausse.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

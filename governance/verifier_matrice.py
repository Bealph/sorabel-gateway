#!/usr/bin/env python3
"""Verifie la matrice d'acces, et regenere sa vue lisible.

POURQUOI CE SCRIPT EXISTE
La matrice etait ecrite en clair a trois endroits : le chantier 03, le catalogue
05, et le mini guide d'acces. Trois copies manuelles de la meme information, et
le fichier que le dossier designe comme source de verite depuis D21 n'existait
meme pas. C'est le mode de defaillance qui a deja frappe deux fois sur les
enumerations de la base : ce qui est recopie diverge.

Desormais : governance/matrice.yaml est la source, cette vue en est une sortie,
et les CONTROLES ci-dessous refusent une matrice incoherente.

Ce sont les controles qui justifient ce script, pas la generation du tableau.
Pour trois profils et huit tools, un tableau ecrit a la main suffirait ; un
invariant non verifie, non.

Usage : python governance/verifier_matrice.py
        python governance/verifier_matrice.py --verifier   controle seul, n'ecrit rien
"""
from __future__ import annotations

import re
import sqlite3
import sys
from datetime import date
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
SOURCE = RACINE / "governance" / "matrice.yaml"
VUE = RACINE / "governance" / "matrice_lisible.md"
BASE = RACINE / "data" / "sorabel.db"


def charger(chemin: Path) -> dict:
    """Lit le YAML. Utilise pyyaml s'il est la, sinon un lecteur du sous-ensemble
    restreint que ce fichier emploie : dictionnaires imbriques, listes de
    scalaires, commentaires. Le repli existe pour que le controle tourne AVANT
    le lot 0, qui installera les dependances."""
    texte = chemin.read_text(encoding="utf-8")
    try:
        import yaml  # noqa: PLC0415
        return yaml.safe_load(texte)
    except ImportError:
        pass

    racine: dict = {}
    # Chaque entree de pile : (indentation, conteneur, parent, cle). Le conteneur
    # d'une cle sans valeur est indetermine tant qu'aucun enfant n'est lu : c'est
    # le PREMIER enfant qui dit si c'est un dictionnaire ou une liste.
    pile: list[list] = [[-1, racine, None, None]]

    def materialiser(entree: list, en_liste: bool) -> object:
        _, conteneur, parent, cle = entree
        attendu = list if en_liste else dict
        if isinstance(conteneur, attendu):
            return conteneur
        neuf_conteneur = [] if en_liste else {}
        if parent is not None and cle is not None:
            parent[cle] = neuf_conteneur
        entree[1] = neuf_conteneur
        return neuf_conteneur

    for brut in texte.splitlines():
        ligne = brut.split(" #")[0].rstrip() if " #" in brut else brut.rstrip()
        if not ligne.strip() or ligne.lstrip().startswith("#"):
            continue
        indent = len(ligne) - len(ligne.lstrip())
        contenu = ligne.strip()
        while len(pile) > 1 and pile[-1][0] >= indent:
            pile.pop()
        entree = pile[-1]

        if contenu.startswith("- "):
            liste = materialiser(entree, en_liste=True)
            valeur = contenu[2:].strip()
            if ":" in valeur:
                cle, _, reste = valeur.partition(":")
                obj = {cle.strip(): reste.strip()}
                liste.append(obj)                      # type: ignore[union-attr]
                pile.append([indent + 2, obj, None, None])
            else:
                liste.append(valeur)                   # type: ignore[union-attr]
            continue

        dico = materialiser(entree, en_liste=False)
        cle, _, reste = contenu.partition(":")
        cle, reste = cle.strip(), reste.strip()
        if reste == "[]":
            dico[cle] = []                             # type: ignore[index]
        elif reste:
            dico[cle] = int(reste) if reste.isdigit() else reste   # type: ignore[index]
        else:
            dico[cle] = {}                             # type: ignore[index]
            pile.append([indent, dico[cle], dico, cle])   # type: ignore[index]
    return racine


def normaliser(d: dict) -> dict:
    """Le lecteur de repli cree un dict vide la ou une liste etait attendue."""
    for cle in ("catalogue", "collections", "profils"):
        d.setdefault(cle, {})
    return d


class Controle:
    def __init__(self) -> None:
        self.echecs: list[str] = []
        self.avertissements: list[str] = []
        self.faits: list[str] = []

    def exige(self, condition: bool, message: str) -> None:
        (self.faits if condition else self.echecs).append(message)

    def signale(self, message: str) -> None:
        self.avertissements.append(message)


def controler(m: dict) -> Controle:
    c = Controle()
    tools = set(m["catalogue"].get("rag", []) or []) | set(m["catalogue"].get("sql", []) or [])
    collections = set(m["collections"] or {})
    sensibles = set(m.get("colonnes_sensibles") or [])
    profils = m["profils"] or {}

    c.exige(len(tools) == 8, f"le catalogue compte {len(tools)} tools, 8 attendus")

    # catalogue ferme
    for nom, p in profils.items():
        inconnus = set(p.get("tools") or []) - tools
        c.exige(not inconnus, f"{nom} : aucun tool hors catalogue"
                              + (f" (trouves : {sorted(inconnus)})" if inconnus else ""))
        inconnues = set(p.get("collections") or []) - collections
        c.exige(not inconnues, f"{nom} : aucune collection inconnue"
                               + (f" (trouvees : {sorted(inconnues)})" if inconnues else ""))

    # E5 : le support interdit les trois colonnes sensibles
    sup = profils.get("support", {})
    interdites = set(sup.get("colonnes_interdites") or [])
    manquantes = sensibles - interdites
    c.exige(not manquantes,
            "E5 : le support interdit les 3 colonnes sensibles"
            + (f" -- MANQUE {sorted(manquantes)}" if manquantes else ""))

    # E4 / D18 : les briques RAG n'appartiennent qu'au profil dev
    briques = {"search_docs", "get_document", "list_sources"}
    for nom, p in profils.items():
        a_des_briques = briques & set(p.get("tools") or [])
        if nom == "dev":
            c.exige(a_des_briques == briques, "dev : possede les 3 briques RAG")
        else:
            c.exige(not a_des_briques,
                    f"{nom} : aucune brique RAG"
                    + (f" -- POSSEDE {sorted(a_des_briques)}" if a_des_briques else ""))

    # P7 : notes interdites au support
    c.exige("notes" not in set(sup.get("collections") or []),
            "P7 : la collection notes n'est pas accessible au support")

    # coherence avec le schema reel
    if BASE.exists():
        cx = sqlite3.connect(f"file:{BASE}?mode=ro", uri=True)
        reelles = {t[0] for t in cx.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
        colonnes = set()
        for t in reelles:
            for col in cx.execute(f"PRAGMA table_info({t})"):
                colonnes.add(f"{t}.{col[1]}")
        cx.close()
        for nom, p in profils.items():
            fantomes = set(p.get("tables") or []) - reelles
            c.exige(not fantomes, f"{nom} : toutes les tables existent"
                                  + (f" -- INCONNUES {sorted(fantomes)}" if fantomes else ""))
            fantomes = set(p.get("colonnes_interdites") or []) - colonnes
            c.exige(not fantomes, f"{nom} : toutes les colonnes interdites existent"
                                  + (f" -- INCONNUES {sorted(fantomes)}" if fantomes else ""))
        fantomes = sensibles - colonnes
        c.exige(not fantomes, "les colonnes sensibles existent dans la base"
                              + (f" -- INCONNUES {sorted(fantomes)}" if fantomes else ""))
    else:
        c.signale("base absente, controles de schema non joues. "
                  "data/ n'est pas versionne, c'est attendu sur un depot fraichement clone.")
    return c


def vue(m: dict) -> str:
    tools_rag = m["catalogue"].get("rag", []) or []
    tools_sql = m["catalogue"].get("sql", []) or []
    profils = m["profils"] or {}
    noms = list(profils)
    sensibles = m.get("colonnes_sensibles") or []

    L = [f"<!-- GENERE par governance/verifier_matrice.py depuis matrice.yaml. "
         f"Ne pas editer a la main. -->",
         "", "# Matrice d'acces, vue lisible", "",
         f"> Vue **générée** le {date.today().isoformat()} depuis `governance/matrice.yaml`,",
         "> qui est la source de vérité (D21). À titre informatif : en cas de divergence,",
         "> c'est le fichier YAML qui fait foi, jamais ce document.", "",
         "## Quel profil peut appeler quel tool", "",
         "| Tool | Famille | " + " | ".join(noms) + " |",
         "| --- | --- | " + " | ".join([":---:"] * len(noms)) + " |"]
    for famille, liste in (("RAG", tools_rag), ("SQL", tools_sql)):
        for t in liste:
            cases = ["oui" if t in (profils[n].get("tools") or []) else "**non**" for n in noms]
            L.append(f"| `{t}` | {famille} | " + " | ".join(cases) + " |")

    L += ["", "## Quel profil accède à quelle collection documentaire", "",
          "| Collection | `doc_type` | " + " | ".join(noms) + " |",
          "| --- | --- | " + " | ".join([":---:"] * len(noms)) + " |"]
    for coll, dt in (m["collections"] or {}).items():
        cases = ["oui" if coll in (profils[n].get("collections") or []) else "**non**" for n in noms]
        L.append(f"| `{coll}` | `{dt}` | " + " | ".join(cases) + " |")

    L += ["", "## Colonnes SQL retirées, par profil", "",
          "Les colonnes ci-dessous sont **sensibles au sens d'E5**. Une colonne retirée",
          "n'apparaît pas dans le schéma montré au modèle, et le contrôle de périmètre",
          "la rejette après génération.", "",
          "| Colonne sensible | " + " | ".join(noms) + " |",
          "| --- | " + " | ".join([":---:"] * len(noms)) + " |"]
    for col in sensibles:
        cases = ["**retirée**" if col in (profils[n].get("colonnes_interdites") or [])
                 else "visible" for n in noms]
        L.append(f"| `{col}` | " + " | ".join(cases) + " |")

    L += ["", "## Tables accessibles", "",
          "Aucune table n'est interdite à aucun profil : la restriction porte sur les",
          "**colonnes**, jamais sur les tables.", "",
          "| Profil | Tables | Rôle |", "| --- | --- | --- |"]
    for n in noms:
        p = profils[n]
        L.append(f"| `{n}` | {len(p.get('tables') or [])} sur 5 | {p.get('description', '')} |")

    L += ["", "## Invariants contrôlés", "",
          "Ces règles ne sont pas des commentaires : le script échoue si l'une tombe.", ""]
    for inv in (m.get("invariants") or []):
        if isinstance(inv, dict):
            L.append(f"- **{inv.get('id', '?')}** : {inv.get('enonce', '')}")
    L.append("")
    return "\n".join(L)


def main() -> int:
    if not SOURCE.exists():
        print(f"ERREUR : {SOURCE} est absent.", file=sys.stderr)
        return 2
    m = normaliser(charger(SOURCE))
    c = controler(m)

    for f in c.faits:
        print(f"  ok    {f}")
    for a in c.avertissements:
        print(f"  note  {a}")
    for e in c.echecs:
        print(f"  ECHEC {e}", file=sys.stderr)

    if c.echecs:
        print(f"\n{len(c.echecs)} controle(s) en echec, rien n'a ete ecrit.", file=sys.stderr)
        return 1

    neuf = vue(m)
    if "--verifier" in sys.argv:
        ancien = VUE.read_text(encoding="utf-8") if VUE.exists() else ""
        sans_date = lambda t: re.sub(r"le \d{4}-\d{2}-\d{2}", "le DATE", t)
        if sans_date(ancien) == sans_date(neuf):
            print(f"\n{len(c.faits)} controles passes, vue a jour.")
            return 0
        print("\nVUE PERIMEE : relancer python governance/verifier_matrice.py", file=sys.stderr)
        return 1

    VUE.write_text(neuf, encoding="utf-8", newline="\n")
    print(f"\n{len(c.faits)} controles passes. {VUE.relative_to(RACINE)} regeneree.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

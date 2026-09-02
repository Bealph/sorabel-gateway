#!/usr/bin/env python3
"""Verifie la matrice d'acces, et regenere sa vue lisible.

POURQUOI CE SCRIPT EXISTE
La matrice etait ecrite en clair a trois endroits : le chantier 03, le catalogue
05, et le mini guide d'acces. Trois copies manuelles de la meme information, et
le fichier que le dossier designe comme source de verite depuis D21 n'existait
meme pas. C'est le mode de defaillance qui a deja frappe sur les enumerations de
la base : ce qui est recopie diverge.

CE QUE LA REVUE DU 2026-09-02 A CORRIGE ICI
La premiere version controlait la matrice CONTRE ELLE-MEME. Le controle E5
verifiait que colonnes_sensibles etait inclus dans les colonnes interdites au
support : les deux listes vivant dans le meme fichier, en retirer une colonne
des deux laissait 19 controles sur 19 au vert. Un invariant qui se verifie
contre une donnee du meme fichier ne verifie rien, il s'annule avec elle.

Desormais les invariants sont ancres EN DUR ci-dessous, hors de la donnee qu'ils
controlent, et la classification des colonnes doit etre EXHAUSTIVE : une colonne
ajoutee a la base fait echouer le controle au lieu de devenir visible en silence.

Usage : python governance/verifier_matrice.py
        python governance/verifier_matrice.py --verifier    controle seul, n'ecrit rien
        python governance/verifier_matrice.py --sans-base   admet l'absence de data/
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
CORPUS = RACINE / "data" / "corpus"

# --- ANCRES ------------------------------------------------------------------
# Ecrites ici, et pas dans le YAML, precisement pour qu'une edition de la matrice
# ne puisse pas les emporter avec elle. Les modifier est un acte deliberE, qui
# passe par une relecture de code.

TOOLS_ATTENDUS = {
    "answer_question", "search_docs", "get_document", "list_sources",
    "ask_database", "get_schema", "check_stock", "order_status",
}                                                          # D17, catalogue ferme
PROFILS_ATTENDUS = {"support", "commercial", "dev"}        # P7, pas de 4e profil
SENSIBLES_E5 = {                                           # litteral de E5
    "produits.prix_achat_ht", "produits.marge_pct", "ventes.marge_ht",
}
BRIQUES_RAG = {"search_docs", "get_document", "list_sources"}   # D18, dev seul


def charger(chemin: Path) -> dict:
    """Lit le YAML. Utilise pyyaml s'il est la, sinon un lecteur du sous-ensemble
    restreint que ce fichier emploie : dictionnaires imbriques, listes de
    scalaires, listes de dictionnaires, commentaires. Le repli existe pour que le
    controle tourne AVANT le lot 0, qui installera les dependances."""
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
                # indent + 1, et non + 2 : les cles filles d'un item de liste sont
                # a indent + 2, et une entree posee a indent + 2 se faisait depiler
                # par sa propre fille, qui ecrasait alors la liste par un dict.
                # C'est le bug qui a vide la section des invariants de la vue.
                pile.append([indent + 1, obj, None, None])
            else:
                liste.append(valeur)                   # type: ignore[union-attr]
            continue

        dico = materialiser(entree, en_liste=False)
        cle, _, reste = contenu.partition(":")
        cle, reste = cle.strip(), reste.strip()
        if reste.startswith("[") and reste.endswith("]"):
            corps = reste[1:-1].strip()
            dico[cle] = [x.strip() for x in corps.split(",")] if corps else []   # type: ignore[index]
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
        self.faits: list[str] = []

    def exige(self, condition: bool, message: str) -> None:
        (self.faits if condition else self.echecs).append(message)

    def compare(self, obtenu: set, attendu: set, quoi: str) -> None:
        """Egalite stricte, et le message NOMME le fautif. Un controle qui dit
        seulement 'echec' oblige a relire tout le fichier."""
        trop, manque = sorted(obtenu - attendu), sorted(attendu - obtenu)
        detail = ""
        if trop:
            detail += f" -- EN TROP {trop}"
        if manque:
            detail += f" -- MANQUE {manque}"
        self.exige(not trop and not manque, quoi + detail)


def colonnes_reelles() -> tuple[set[str], set[str]]:
    """(tables, colonnes qualifiees) de la base metier, en lecture seule."""
    cx = sqlite3.connect(f"file:{BASE}?mode=ro", uri=True)
    tables = {t[0] for t in cx.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
    colonnes = {f"{t}.{c[1]}" for t in tables for c in cx.execute(f"PRAGMA table_info({t})")}
    cx.close()
    return tables, colonnes


def doc_types_du_corpus() -> dict[str, set[str]]:
    """Les doc_type declares dans le corpus, par dossier. Ne lit que ce qui est
    lisible sans dependance : la balise meta des HTML, l'en-tete des Markdown.
    Les PDF sont hors de portee ici, et c'est dit dans le rapport."""
    trouves: dict[str, set[str]] = {}
    motifs = (re.compile(r'name="type"\s+content="([^"]+)"'),
              re.compile(r'^type\s*:\s*(\S+)', re.M))
    for dossier in sorted(p for p in CORPUS.iterdir() if p.is_dir()):
        vus: set[str] = set()
        for f in dossier.iterdir():
            if f.suffix.lower() not in (".html", ".htm", ".md"):
                continue
            t = f.read_text(encoding="utf-8", errors="replace")[:2000]
            for m in motifs:
                trouve = m.search(t)
                if trouve:
                    vus.add(trouve.group(1).strip())
                    break
        if vus:
            trouves[dossier.name] = vus
    return trouves


def controler(m: dict, sans_base: bool) -> Controle:
    c = Controle()
    tools = set(m["catalogue"].get("rag", []) or []) | set(m["catalogue"].get("sql", []) or [])
    collections = m["collections"] or {}
    profils = m["profils"] or {}
    sensibles = set(m.get("colonnes_sensibles") or [])
    restreintes = set(m.get("colonnes_restreintes") or [])
    publiques = set(m.get("colonnes_publiques") or [])

    # --- Ancrage : la matrice est comparee a des constantes du script ---------
    c.compare(tools, TOOLS_ATTENDUS, "catalogue : exactement les 8 tools de D17")
    c.compare(set(profils), PROFILS_ATTENDUS, "profils : exactement les 3 de P7")
    c.compare(sensibles, SENSIBLES_E5, "colonnes_sensibles : exactement les 3 d'E5")

    # --- Catalogue ferme et collections connues ------------------------------
    for nom, p in profils.items():
        c.compare(set(p.get("tools") or []) - TOOLS_ATTENDUS, set(),
                  f"{nom} : aucun tool hors catalogue")
        c.compare(set(p.get("collections") or []) - set(collections), set(),
                  f"{nom} : aucune collection inconnue")

    # --- E5 : le support interdit tout ce qui ne doit pas sortir --------------
    sup = profils.get("support", {})
    interdites = set(sup.get("colonnes_interdites") or [])
    c.compare((SENSIBLES_E5 | restreintes) - interdites, set(),
              "E5 : le support interdit les colonnes sensibles et restreintes")

    # --- Le lexique de refus couvre chaque colonne retiree --------------------
    lexique = m.get("lexique_refus") or {}
    c.compare(SENSIBLES_E5 | restreintes, set(lexique),
              "lexique de refus : une entree par colonne retiree")
    vides = {col for col, termes in lexique.items() if not termes}
    c.compare(vides, set(), "lexique de refus : aucune entree vide")

    # --- E4 / D18 : les briques RAG n'appartiennent qu'au profil dev ----------
    for nom in PROFILS_ATTENDUS:
        p = profils.get(nom, {})
        possede = BRIQUES_RAG & set(p.get("tools") or [])
        if nom == "dev":
            c.compare(possede, BRIQUES_RAG, "dev : possede les 3 briques RAG")
        else:
            c.compare(possede, set(), f"{nom} : aucune brique RAG")

    # --- P7 : notes interdites au support ------------------------------------
    c.exige("notes" not in set(sup.get("collections") or []),
            "P7 : la collection notes n'est pas accessible au support")

    # --- Coherence avec le schema reel, et classification EXHAUSTIVE ----------
    if not BASE.exists():
        if sans_base:
            c.exige(True, "base absente, controles de schema volontairement sautes (--sans-base)")
        else:
            c.exige(False, f"base absente : {BASE.relative_to(RACINE)}. "
                           "7 controles ne peuvent pas etre joues. "
                           "Relancer avec --sans-base pour l'admettre explicitement")
    else:
        tables, colonnes = colonnes_reelles()
        for nom, p in profils.items():
            c.compare(set(p.get("tables") or []) - tables, set(),
                      f"{nom} : toutes les tables existent")
            c.compare(set(p.get("colonnes_interdites") or []) - colonnes, set(),
                      f"{nom} : toutes les colonnes interdites existent")
        # C'est LE controle qui transforme la liste noire en deny-by-default :
        # toute colonne de la base doit etre classee, dans un sens ou dans l'autre.
        c.compare(sensibles | restreintes | publiques, colonnes,
                  f"classification exhaustive des {len(colonnes)} colonnes de la base")
        chevauche = (sensibles & publiques) | (restreintes & publiques) | (sensibles & restreintes)
        c.compare(chevauche, set(), "aucune colonne classee deux fois")

    # --- Les doc_type declares existent-ils dans le corpus ? -----------------
    if not CORPUS.exists():
        if not sans_base:
            c.exige(False, f"corpus absent : {CORPUS.relative_to(RACINE)}. "
                           "Relancer avec --sans-base pour l'admettre explicitement")
        else:
            c.exige(True, "corpus absent, controle des doc_type saute (--sans-base)")
    else:
        c.compare({p.name for p in CORPUS.iterdir() if p.is_dir()}, set(collections),
                  "les dossiers du corpus sont exactement les collections declarees")
        trouves = doc_types_du_corpus()
        for coll, vus in sorted(trouves.items()):
            attendu = collections.get(coll)
            c.compare(vus, {attendu} if attendu else set(),
                      f"{coll} : doc_type du corpus conforme a la matrice")
        non_couvertes = set(collections) - set(trouves)
        if non_couvertes:
            c.exige(True, f"doc_type non lisible sans dependance pour {sorted(non_couvertes)} "
                          "(PDF), a controler par le loader du lot 1")
    return c


def vue(m: dict) -> str:
    tools_rag = m["catalogue"].get("rag", []) or []
    tools_sql = m["catalogue"].get("sql", []) or []
    profils = m["profils"] or {}
    noms = list(profils)
    sensibles = list(m.get("colonnes_sensibles") or [])
    restreintes = list(m.get("colonnes_restreintes") or [])

    L = ["<!-- GENERE par governance/verifier_matrice.py depuis matrice.yaml. "
         "Ne pas editer a la main. -->",
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
          "Une colonne retirée n'apparaît pas dans le schéma montré au modèle, et le",
          "contrôle de périmètre la rejette après génération. Le périmètre porte sur",
          "**toute occurrence** de la colonne, y compris dans un `WHERE`, un `ORDER BY`,",
          "un `GROUP BY` ou un `HAVING` : un tri sur une colonne retirée la divulgue",
          "sans jamais l'afficher.", "",
          "| Colonne | Classe | " + " | ".join(noms) + " |",
          "| --- | --- | " + " | ".join([":---:"] * len(noms)) + " |"]
    for col, classe in ([(c, "sensible (E5)") for c in sensibles]
                        + [(c, "restreinte") for c in restreintes]):
        cases = ["**retirée**" if col in (profils[n].get("colonnes_interdites") or [])
                 else "visible" for n in noms]
        L.append(f"| `{col}` | {classe} | " + " | ".join(cases) + " |")

    publiques = m.get("colonnes_publiques") or []
    L += ["", f"Les {len(publiques)} autres colonnes de la base sont classées **publiques** : "
              "elles peuvent",
          "sortir pour n'importe quel profil. La classification est exhaustive, et le",
          "contrôle échoue sur toute colonne de la base qui n'est classée nulle part.", ""]

    L += ["## Tables accessibles", "",
          "Aucune table n'est interdite à aucun profil : la restriction porte sur les",
          "**colonnes**, jamais sur les tables.", "",
          "| Profil | Tables | Rôle |", "| --- | --- | --- |"]
    for n in noms:
        p = profils[n]
        L.append(f"| `{n}` | {len(p.get('tables') or [])} sur 5 | {p.get('description', '')} |")

    L += ["", "## Invariants contrôlés", "",
          "Ces règles ne sont pas des commentaires : le script échoue si l'une tombe.",
          "Les quatre premières se contrôlent contre des **ancres écrites en dur** dans",
          "le script, hors de ce fichier : un invariant qui se vérifie contre une donnée",
          "du fichier qu'il contrôle s'annule avec elle.", ""]
    for inv in (m.get("invariants") or []):
        if isinstance(inv, dict):
            L.append(f"- **{inv.get('id', '?')}** : {inv.get('enonce', '')}")
    L.append("")
    return "\n".join(L)


def main() -> int:
    if not SOURCE.exists():
        print(f"ERREUR : {SOURCE} est absent.", file=sys.stderr)
        return 2
    sans_base = "--sans-base" in sys.argv
    m = normaliser(charger(SOURCE))
    c = controler(m, sans_base)

    for f in c.faits:
        print(f"  ok    {f}")
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

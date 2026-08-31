#!/usr/bin/env python3
"""Releve les faits du jeu de donnees et regenere la section GENEREE de analyse_donnees.md.

POURQUOI CE SCRIPT EXISTE
Les valeurs relevees dans la base et le corpus ont d'abord ete recopiees a la main
dans les documents de conception. Deux consequences constatees le 2026-08-31 :
  - six litteraux d'enumeration avaient perdu leurs accents ("Cablage" au lieu de
    "Cablage" accentue). Une requete sur ces valeurs renvoie zero ligne, sans
    erreur, en franchissant toutes les gardes : le pire mode de defaillance ;
  - la meme enumeration recopiee a trois endroits avait diverge (deux entrepots
    a un endroit, trois a un autre, dans le meme fichier).
La regle qui en decoule : un releve ne se recopie pas, il se genere.

CE QUE LE SCRIPT NE FAIT PAS
Il ne touche a aucune decision de conception. Il ne reecrit que le bloc delimite
par les marqueurs DEBUT/FIN ci-dessous dans docs/analyse_donnees.md. Tout ce qui
est hors de ces marqueurs est ecrit a la main et preserve.

Usage : python docs/releve_donnees.py            regenere le bloc
        python docs/releve_donnees.py --verifier  sort en erreur si le bloc est
                                                  perime, sans rien ecrire
"""
from __future__ import annotations

import io
import os
import re
import sqlite3
import sys
import zlib
from collections import Counter
from datetime import date
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
BASE = RACINE / "data" / "sorabel.db"
CORPUS = RACINE / "data" / "corpus"
CIBLE = RACINE / "docs" / "analyse_donnees.md"

DEBUT = "<!-- RELEVE:DEBUT -- genere par docs/releve_donnees.py, ne pas editer a la main -->"
FIN = "<!-- RELEVE:FIN -->"

# Colonnes sensibles : ce n'est PAS un releve, c'est l'exigence E5 du brief.
# Elles figurent ici pour etre annotees dans la sortie, pas pour etre decouvertes.
SENSIBLES = {"produits.prix_achat_ht", "produits.marge_pct", "ventes.marge_ht"}

# Au-dela de ce nombre de valeurs distinctes, une colonne n'est pas une enumeration.
SEUIL_ENUM = 15


def tables(cx: sqlite3.Connection) -> list[str]:
    q = "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    return [r[0] for r in cx.execute(q)]


def releve_sql(cx: sqlite3.Connection) -> dict:
    out = {"tables": [], "enums": [], "fk": [], "plages": []}
    for t in tables(cx):
        cols = list(cx.execute(f"PRAGMA table_info({t})"))
        n = cx.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        noms = []
        for c in cols:
            nom = c[1]
            marque = " (SENSIBLE, E5)" if f"{t}.{nom}" in SENSIBLES else ""
            noms.append(f"`{nom}`{marque}")
        out["tables"].append((t, n, ", ".join(noms)))

        for c in cols:
            nom, typ = c[1], (c[2] or "").upper()
            if "TEXT" not in typ:
                continue
            d = cx.execute(f"SELECT COUNT(DISTINCT {nom}) FROM {t}").fetchone()[0]
            if 1 < d <= SEUIL_ENUM:
                vals = [r[0] for r in cx.execute(
                    f"SELECT DISTINCT {nom} FROM {t} WHERE {nom} IS NOT NULL ORDER BY 1")]
                out["enums"].append((f"{t}.{nom}", d, vals))
            elif nom.startswith("date") or nom.endswith("_date"):
                mn, mx = cx.execute(f"SELECT MIN({nom}), MAX({nom}) FROM {t}").fetchone()
                out["plages"].append((f"{t}.{nom}", mn, mx))

        for f in cx.execute(f"PRAGMA foreign_key_list({t})"):
            out["fk"].append((f"{t}.{f[3]}", f"{f[2]}.{f[4]}"))
    return out


def texte_pdf(chemin: Path) -> str:
    brut = chemin.read_bytes()
    morceaux = []
    for m in re.finditer(rb"stream\r?\n(.*?)endstream", brut, re.S):
        bloc = m.group(1)
        try:
            bloc = zlib.decompress(bloc)
        except Exception:
            pass
        morceaux.append(bloc)
    return b"\n".join(morceaux).decode("latin-1")


def sections_pdf(chemin: Path) -> int:
    lignes = re.findall(r"\(([^()]*)\)\s*Tj", texte_pdf(chemin))
    return sum(1 for l in lignes if re.match(r"^\s*\d+\.\s+\S", l))


def releve_corpus() -> dict:
    out = {}
    regles = {
        "fiches": (".pdf", r"-v[\d.]+\.pdf$", lambda p: 1),
        "notices": (".pdf", r"-v[\d.]+\.pdf$", sections_pdf),
        "sav": (".html", r"-v[\d.]+\.html$", lambda p: p.read_text(encoding="utf-8", errors="ignore").count("<h2>")),
        "notes": (".md", r"$^", lambda p: 1),
    }
    for coll, (ext, suff, compte) in regles.items():
        d = CORPUS / coll
        if not d.is_dir():
            continue
        fichiers = sorted(p for p in d.iterdir() if p.suffix == ext)
        groupes = {re.sub(suff, "", p.name) for p in fichiers}
        par_doc = Counter(compte(p) for p in fichiers)
        chunks = sum(k * v for k, v in par_doc.items())
        out[coll] = {
            "fichiers": len(fichiers),
            "groupes": len(groupes),
            "sections": dict(sorted(par_doc.items())),
            "chunks": chunks,
        }
    return out


def templatage() -> list[str]:
    """Combien de corps de texte DISTINCTS chaque collection contient-elle ?

    Un corpus ou 80 documents partagent le meme corps ne permet pas de mesurer
    la pertinence : toute question sur ce contenu a 80 bonnes reponses. C'est
    une propriete du jeu qui borne la mesure E6, il faut la relever.
    """
    import hashlib
    out = []
    for coll, ext in (("fiches", ".pdf"), ("notices", ".pdf"),
                      ("sav", ".html"), ("notes", ".md")):
        d = CORPUS / coll
        if not d.is_dir():
            continue
        sigs: dict[str, int] = {}
        gabs: dict[str, int] = {}
        for f in sorted(p for p in d.iterdir() if p.suffix == ext):
            if ext == ".pdf":
                lignes = re.findall(r"\(([^()]*)\)\s*Tj", texte_pdf(f))
                corps = [l for l in lignes
                         if not re.search(r"R.f.rence produit|FICHE |NOTICE |Version", l)]
                t = "|".join(corps)
            else:
                t = f.read_text(encoding="utf-8", errors="ignore")
                t = re.sub(r"<title>.*?</title>|<h1>.*?</h1>|<meta[^>]*>|^---.*?^---",
                           "", t, flags=re.S | re.M)
            brut = re.sub(r"REF-\d{4}|\d{4}-\d{2}-\d{2}", "", t)
            # variante ou l'on neutralise aussi les VALEURS : ce qui reste est le gabarit
            gab = re.sub(r"[\d.,]+\s*(?:V|A|W|kA|mm|EUR|%)?", "", brut)
            for cle, d in (("brut", sigs), ("gabarit", gabs)):
                v = brut if cle == "brut" else gab
                h = hashlib.md5(v.encode("utf-8", "ignore")).hexdigest()
                d[h] = d.get(h, 0) + 1
        tot = sum(sigs.values())
        if tot:
            out.append((coll, tot, len(sigs), len(gabs), max(gabs.values())))
    return out


def pieges(cx: sqlite3.Connection) -> list[str]:
    """Anomalies du jeu qui illustrent des decisions, sans les fonder."""
    p = []
    n = cx.execute("SELECT COUNT(*) FROM (SELECT nom FROM produits GROUP BY nom HAVING COUNT(*)>1)").fetchone()[0]
    tot = cx.execute("SELECT COUNT(*) FROM produits").fetchone()[0]
    if n:
        p.append(f"{n} libelles de produits sur {tot} designent plusieurs references : "
                 f"un libelle n'est pas une cle (illustre D27).")
    # La numerotation repart a chaque annee : grouper par prefixe, sinon les trous
    # d'une annee sont combles par les numeros d'une autre et rien n'est detecte.
    par_annee: dict[str, set[int]] = {}
    for (i,) in cx.execute("SELECT id FROM commandes WHERE id LIKE 'CMD-%'"):
        bouts = i.split("-")
        if len(bouts) == 3 and bouts[2].isdigit():
            par_annee.setdefault(bouts[1], set()).add(int(bouts[2]))
    total_trous, detail = 0, []
    for an, nums in sorted(par_annee.items()):
        manquants = sorted(set(range(min(nums), max(nums) + 1)) - nums)
        if manquants:
            total_trous += len(manquants)
            detail.append(f"{an} : {len(manquants)} manquants, dont CMD-{an}-{manquants[0]:04d}")
    if total_trous:
        p.append(f"{total_trous} numeros de commande manquent dans des suites par ailleurs continues "
                 f"({' ; '.join(detail)}) : un identifiant bien forme peut ne designer aucune ligne "
                 f"(illustre D26).")
    return p


def rendu() -> str:
    cx = sqlite3.connect(f"file:{BASE}?mode=ro", uri=True)
    sql, corp, anomalies = releve_sql(cx), releve_corpus(), pieges(cx)
    cx.close()
    tmpl = templatage()

    L = [DEBUT, "",
         f"> Bloc **généré** le {date.today().isoformat()} par `docs/releve_donnees.py`.",
         "> Il décrit **ce jeu de données**, pas la conception. Un autre corpus produirait",
         "> d'autres valeurs sans qu'aucune décision ne change. Ne pas éditer à la main :",
         "> relancer le script.", "",
         "### Base SQL", "",
         "| Table | Lignes | Colonnes |", "| --- | ---: | --- |"]
    for t, n, cols in sql["tables"]:
        L.append(f"| `{t}` | {n} | {cols} |")

    L += ["", "### Clés étrangères", "", "| Depuis | Vers |", "| --- | --- |"]
    for a, b in sql["fk"]:
        L.append(f"| `{a}` | `{b}` |")

    L += ["", "### Énumérations", "",
          "Colonnes textuelles à faible cardinalité. Ce sont les littéraux à fournir au",
          "modèle de génération SQL (décision D9). **Les accents en font partie.**", "",
          "| Colonne | Valeurs distinctes | Valeurs |", "| --- | ---: | --- |"]
    for col, n, vals in sql["enums"]:
        L.append(f"| `{col}` | {n} | " + ", ".join(f"`{v}`" for v in vals) + " |")

    if sql["plages"]:
        L += ["", "### Plages de dates", "", "| Colonne | De | À |", "| --- | --- | --- |"]
        for col, mn, mx in sql["plages"]:
            L.append(f"| `{col}` | {mn} | {mx} |")

    L += ["", "### Corpus documentaire", "",
          "| Collection | Fichiers | Groupes de versions | Sections par document | Chunks |",
          "| --- | ---: | ---: | --- | ---: |"]
    tf = tg = tc = 0
    for coll, d in corp.items():
        sec = ", ".join(f"{k} ({v} doc)" for k, v in d["sections"].items())
        L.append(f"| `{coll}` | {d['fichiers']} | {d['groupes']} | {sec} | {d['chunks']} |")
        tf += d["fichiers"]; tg += d["groupes"]; tc += d["chunks"]
    L.append(f"| **total** | **{tf}** | **{tg}** | | **{tc}** |")

    if tmpl:
        L += ["", "### Diversité réelle du contenu", "",
              "Une collection dont tous les documents partagent un seul corps ne permet",
              "pas de mesurer la pertinence : une question sur ce contenu y a autant de",
              "bonnes réponses qu'il y a de documents. Cela borne ce que E6 peut établir.",
              "", 
              "| Collection | Documents | Textes distincts | Gabarits distincts | Plus grand gabarit |",
              "| --- | ---: | ---: | ---: | ---: |"]
        for coll, tot, n, ng, gros in tmpl:
            L.append(f"| `{coll}` | {tot} | {n} | {ng} | {gros} |")
        L += ["",
              "« Textes distincts » compte les corps différents une fois références et",
              "dates neutralisées. « Gabarits » neutralise en plus les valeurs chiffrées :",
              "l'écart entre les deux colonnes dit si la variation est de fond ou seulement",
              "numérique."]

    if anomalies:
        L += ["", "### Anomalies du jeu", "",
              "Elles **illustrent** des décisions, elles ne les fondent pas : les règles",
              "correspondantes tiennent sur un jeu qui n'aurait aucune de ces anomalies.", ""]
        L += [f"- {a}" for a in anomalies]

    L += ["", FIN]
    return "\n".join(L)


def main() -> int:
    if not BASE.exists():
        print(f"ERREUR : base absente ({BASE}). Le jeu de donnees n'est pas versionne.", file=sys.stderr)
        return 2
    neuf = rendu()
    src = CIBLE.read_text(encoding="utf-8") if CIBLE.exists() else ""
    if DEBUT in src and FIN in src:
        a, b = src.index(DEBUT), src.index(FIN) + len(FIN)
        sortie, ancien = src[:a] + neuf + src[b:], src[a:b]
    else:
        sortie, ancien = src.rstrip() + "\n\n---\n\n## Relevé du jeu de données\n\n" + neuf + "\n", ""

    if "--verifier" in sys.argv:
        if ancien.strip() == neuf.strip():
            print("releve a jour")
            return 0
        print("RELEVE PERIME : relancer python docs/releve_donnees.py", file=sys.stderr)
        return 1

    CIBLE.write_text(sortie, encoding="utf-8", newline="\n")
    print(f"{CIBLE.relative_to(RACINE)} : bloc de releve regenere")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

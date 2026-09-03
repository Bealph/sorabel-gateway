#!/usr/bin/env python3
"""Mesure le routage conversationnel sur les fixtures d'évaluation.

    uv run python eval/mesure_routage.py

POURQUOI CE SCRIPT EXISTE
Le routage est la seule pièce du produit dont la qualité ne se voit pas : une
réponse mal routée ressemble à une réponse. Sans mesure, on ne saurait pas que
« quelle est la marge sur la REF-8842 ? » part en documentaire, donc que le
refus de colonne sensible ne se produit jamais et qu'E5 devient invisible.

LA REFERENCE, ET SA LIMITE
Elle vient du fichier de fixture : `questions_rag.jsonl` est par construction
documentaire, `questions_sql.jsonl` par construction base. C'est légitime pour
ces deux fichiers, alors que fabriquer des étiquettes à la main l'était moins :
un premier jeu de 20 questions annotées mécaniquement s'est révélé faux sur au
moins cinq d'entre elles, « quel est le stock total de la REF-8842 ? » étant
étiquetée base alors que le tool figé de stock y répond aussi bien.

Les 8 questions **hors corpus** de la fixture RAG sont comptées à part. Elles
sont documentaires parce qu'elles figurent dans ce fichier, mais plusieurs sont
sémantiquement des questions de gestion (« quel est le chiffre d'affaires de
Sorabel en 2025 ? »). Les router en base n'est pas une faute : aucune brique
n'a la réponse et les deux chemins s'abstiennent.
"""
from __future__ import annotations

import json
import sys
import unicodedata
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from client.routeur import Routeur  # noqa: E402

#: Les questions dont le routage conditionne une démonstration d'exigence. Un
#: échec ici pèse plus que trois points d'agrégat : c'est une exigence qui
#: cesse d'être visible dans la conversation.
CRITIQUES = (
    ("quelle est la marge sur la REF-8842 ?", "BASE", "E5, refus de colonne"),
    ("les references dont la marge depasse 40 %", "BASE", "E5, predicat"),
    ("donne-moi les adresses mail des clients de Lille", "BASE",
     "E5, colonne restreinte"),
    ("supprime les commandes de test", "BASE", "E3, ecriture"),
    ("mets a jour le prix de la REF-8842 a 89,90", "BASE", "E3, ecriture"),
    ("quel est le prix d'achat du projecteur LED 100 W ?", "BASE", "E5, colonne"),
    ("quelle est la procedure de retour d'un produit defectueux ?", "DOCUMENT",
     "E1, reponse documentaire"),
    ("la REF-8842 est-elle disponible a Lyon ?", "BASE", "tool fige de stock"),
    ("ou en est la commande CMD-2025-0004 ?", "BASE", "tool fige de commande"),
)


def sansaccent(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", t.lower())
                   if unicodedata.category(c) != "Mn")


def lire(nom: str) -> list[dict]:
    chemin = RACINE / "eval" / nom
    return [json.loads(ligne) for ligne in chemin.read_text(encoding="utf-8").splitlines()
            if ligne.strip()]


def enonce(q: dict) -> str:
    return q.get("question") or q.get("query") or ""


def cote(etiquette: str) -> str:
    """DOCUMENT contre le reste.

    Les trois étiquettes STOCK, COMMANDE et BASE mènent toutes à la couche SQL :
    pour juger le routage entre les deux BRIQUES, elles comptent ensemble.
    """
    return "DOCUMENT" if etiquette == "DOCUMENT" else "BASE"


def main() -> int:
    routeur = Routeur()
    rag, sql = lire("questions_rag.jsonl"), lire("questions_sql.jsonl")
    hors = {sansaccent(enonce(q)) for q in rag
            if "hors" in str(q.get("categorie") or q.get("type") or "").lower()}

    cas = ([(enonce(q), "DOCUMENT") for q in rag]
           + [(enonce(q), "BASE") for q in sql])
    print(f"{len(cas)} questions : {len(rag)} documentaires dont {len(hors)} "
          f"hors corpus, {len(sql)} base")

    resultats = [(q, attendu, routeur.router(q)) for q, attendu in cas]

    def compter(garder) -> tuple[int, int, int, int, int, int]:
        jeu = [(q, a, r) for q, a, r in resultats if garder(q)]
        justes = sum(cote(r.etiquette) == a for _, a, r in jeu)
        doc = [(a, r) for _, a, r in jeu if a == "DOCUMENT"]
        bas = [(a, r) for _, a, r in jeu if a == "BASE"]
        return (justes, len(jeu),
                sum(cote(r.etiquette) == a for a, r in doc), len(doc),
                sum(cote(r.etiquette) == a for a, r in bas), len(bas))

    print()
    print(f"  {'jeu':26}{'juste':>10}{'documentaire':>15}{'base':>10}")
    print("  " + "-" * 61)
    for titre, garder in (("tout le jeu", lambda q: True),
                          ("sans les hors corpus",
                           lambda q: sansaccent(q) not in hors)):
        j, n, jd, nd, jb, nb = compter(garder)
        print(f"  {titre:26}{j:>6}/{n:<3}{jd:>9}/{nd:<5}{jb:>6}/{nb}")

    duree = sum(r.duree_ms for _, _, r in resultats) / len(resultats)
    print(f"\n  {duree:.0f} ms par question en moyenne")

    par = {}
    for _, _, r in resultats:
        par[r.par] = par.get(r.par, 0) + 1
    print("  mecanisme qui a tranche :")
    for mecanisme, combien in sorted(par.items(), key=lambda x: -x[1]):
        print(f"    {combien:>3}  {mecanisme}")

    print("\n  erreurs, hors questions hors corpus :")
    erreurs = [(q, a, r) for q, a, r in resultats
               if cote(r.etiquette) != a and sansaccent(q) not in hors]
    for q, a, r in erreurs:
        print(f"    attendu {a:9} obtenu {r.etiquette:9} par {r.par:28} {q[:46]}")
    if not erreurs:
        print("    aucune")

    print("\n  LES QUESTIONS DE DEMONSTRATION DES EXIGENCES :")
    manques = 0
    for q, attendu, quoi in CRITIQUES:
        r = routeur.router(q)
        ok = cote(r.etiquette) == attendu
        manques += not ok
        print(f"    {'OK ' if ok else 'ECHEC'} {quoi:26}-> {r.etiquette:9} "
              f"par {r.par}")
    if manques:
        print(f"\n  {manques} question(s) de demonstration mal routee(s) : une "
              "exigence cesse d'etre visible dans la conversation.",
              file=sys.stderr)
        return 1
    print("\n  les 9 questions de demonstration partent au bon endroit.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

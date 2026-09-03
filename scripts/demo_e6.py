"""Écran 5 : la preuve chiffrée du gain de la recherche avancée (E6).

Cet écran est **statique**, et c'est voulu. Le rapport qu'il affiche est
`eval/rapport_gain.md`, **généré** par `python -m retrieval.rapport` depuis les
fixtures d'évaluation. Le recalculer à chaque affichage rejouerait 30 questions
sur quatre configurations, soit plusieurs minutes, pour un résultat identique.

Ce qui compte pour E6 n'est pas qu'une page sache mesurer, c'est que la mesure
soit **reproductible et datée**. La page affiche donc l'artefact, et dit avec
quelle commande le refaire.
"""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from scripts.page import configurer  # noqa: E402

configurer("Sorabel, mesure E6")

RAPPORT = RACINE / "eval" / "rapport_gain.md"
PROTOCOLE = RACINE / "docs" / "mesure_e6.md"

st.title("E6 · le gain de la recherche avancée, mesuré")
st.caption("« La recherche hybride surpasse la dense simple, preuve chiffrée. » "
           "C'est le seul critère de performance du brief qui exige un nombre.")

if not RAPPORT.exists():
    st.error(
        f"`{RAPPORT.relative_to(RACINE)}` absent. Le produire avec "
        "`uv run python -m retrieval.rapport`.")
    st.stop()

g, d = st.columns([3, 1])
with d:
    st.info(
        "**Rapport généré, jamais écrit à la main.**\n\n"
        "```\nuv run python -m retrieval.rapport\n```\n"
        "Source : `eval/questions_rag.jsonl` et `eval/attendus_rag.jsonl`, "
        "fixtures officielles non modifiées.\n\n"
        f"Protocole écrit **avant** l'implémentation : "
        f"`{PROTOCOLE.relative_to(RACINE)}`.", icon="📐")
    st.warning(
        "**Ce que la mesure ne prouve pas**, et le rapport le dit lui-même : "
        "sur 8 à 9 questions notables, une bascule vaut 12 points, les "
        "intervalles de Wilson se recouvrent et McNemar donne p = 0,5. "
        "Le gain est net sur le classement, la puissance statistique ne l'est "
        "pas. Le dire vaut mieux que de le laisser découvrir.", icon="⚠️")
    with st.expander("Pourquoi le socle vaut 8 questions et non 14"):
        st.markdown(
            "Le corpus est massivement **template** : les 80 notices partagent "
            "un seul corps de texte, les 90 procédures SAV aussi. Le seul "
            "signal qui les distingue est le **titre**, recopié dans chaque "
            "chunk. Sans ce report, le moteur citerait une notice au hasard "
            "parmi 80, avec des métadonnées parfaitement formées : E1 "
            "formellement satisfaite, citation fausse, et rien ne le "
            "signalerait.\n\n"
            "Une question de la fixture, RAG-19, est de plus **mal étiquetée** : "
            "elle est hors corpus en réalité. Tout est dans "
            "`docs/mesure_e6.md`, sections 2 et 7.")

with g:
    texte = RAPPORT.read_text(encoding="utf-8")
    # La première ligne est un avertissement de génération destiné au dépôt,
    # pas au lecteur de l'interface : la vignette de droite le dit mieux.
    st.markdown("\n".join(texte.splitlines()[1:]))

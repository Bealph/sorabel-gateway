"""Démonstration visuelle de la brique RAG.

    uv sync --extra vector --extra demo
    uv run streamlit run scripts/demo_rag.py

**Ce que cette page est, et n'est pas.** C'est une démonstration du chantier 1 :
elle appelle directement la couche `retrieval`, sans passer par MCP, puisque le
serveur est le chantier 3. L'interface livrable, elle, parlera à **deux
processus serveurs distincts**, un par profil (chantier 8, D39).

Conséquence sur la conception de cette page, et c'est délibéré : **il n'y a pas
de sélecteur de profil.** Un sélecteur ferait croire que le profil est une
préférence d'affichage. Le profil est une propriété du serveur, fixée à son
lancement (D28). La page joue donc la même question dans **deux services
instanciés séparément**, et montre les deux issues côte à côte.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.matrice import droits  # noqa: E402
from retrieval.depot import Depot  # noqa: E402
from retrieval.recherche import CONFIGS  # noqa: E402
from retrieval.service import ServiceRag, seuil_pour  # noqa: E402

st.set_page_config(page_title="Sorabel Data Gateway, demo RAG", layout="wide")

COULEUR = {"ok": "🟢", "hors_corpus": "🟡", "refused": "🔴"}


@st.cache_resource
def service(profil: str, config: str) -> ServiceRag:
    """Un service par (profil, configuration). Le cache évite de recharger les
    modèles à chaque interaction : ils coûtent une dizaine de secondes."""
    return ServiceRag(droits(profil), CONFIGS[config], depot=Depot())


@st.cache_data
def manifeste() -> dict:
    return Depot().manifeste


def afficher_reponse(colonne, titre: str, sous_titre: str, resultat: tuple) -> None:
    statut, payload, message = resultat
    with colonne:
        st.markdown(f"**{titre}**")
        st.caption(sous_titre)
        st.markdown(f"{COULEUR.get(statut, '⚪')} `status = {statut}`")
        if statut == "ok":
            st.text_area("Réponse", payload.get("answer", ""), height=260,
                         key=f"rep-{titre}", label_visibility="collapsed")
            st.markdown(f"**{len(payload.get('sources', []))} source(s) citée(s)**")
            for s in payload.get("sources", []):
                st.markdown(f"- {s['titre']}  \n  `{s['reference']}` · {s['date']}")
        else:
            st.info(message or "Aucun message.")
            st.caption("Aucune réponse n'est produite. L'abstention est un statut, "
                       "pas une réponse vide : un client ne peut pas les confondre.")


# ---------------------------------------------------------------- barre latérale
m = manifeste()
st.sidebar.title("Index")
st.sidebar.metric("Chunks indexés", m["chunks"])
st.sidebar.metric("Documents", m["documents"])
st.sidebar.metric("Groupes de versions", m["groupes_de_versions"])
st.sidebar.caption(f"Modèle : `{m['modele']}`, {m['dimension']} dimensions")
st.sidebar.caption(f"Généré le {m['genere_le']}")
st.sidebar.divider()
st.sidebar.caption(
    "Démonstration du chantier 1. Elle appelle la couche `retrieval` "
    "directement : le serveur MCP est le chantier 3."
)

st.title("Sorabel Data Gateway")
st.caption("Recherche documentaire gouvernée : ce que le profil change, "
           "et ce que la recherche avancée apporte.")

onglet_e6, onglet_gouv, onglet_mesure = st.tabs(
    ["Dense contre hybride (E6)", "Deux profils (E4, E5)", "La mesure (E6)"]
)

# ------------------------------------------------------- onglet 1 : E6 en direct
with onglet_e6:
    st.markdown(
        "La **même question**, jouée dans les deux configurations comparées par "
        "le protocole. À gauche la baseline que le brief nomme « recherche dense "
        "initiale », à droite la recherche hybride complète."
    )
    exemples = [
        "REF-8836",
        "quelle est la procédure de retour d'un produit défectueux sous garantie ?",
        "quel disjoncteur pour du triphasé ?",
        "quelle est la politique de télétravail chez Sorabel ?",
    ]
    choix = st.selectbox("Exemples du jeu d'évaluation", exemples, key="ex-e6")
    question = st.text_input("Question", choix, key="q-e6")

    if st.button("Comparer", key="btn-e6", type="primary"):
        with st.spinner("Recherche..."):
            gauche, droite = st.columns(2)
            afficher_reponse(
                gauche, "A · dense seul",
                f"seuil {seuil_pour(CONFIGS['A'])} sur le cosinus",
                service("support", "A").answer_question(question))
            afficher_reponse(
                droite, "D · hybride + reranking + court-circuit",
                f"seuil {seuil_pour(CONFIGS['D'])} sur le score du reranker",
                service("support", "D").answer_question(question))
        st.caption(
            "Les deux seuils diffèrent parce que les deux échelles diffèrent : "
            "cosinus borné dans [0, 1] d'un côté, logits non bornés du "
            "cross-encoder de l'autre. Un seul seuil pour les deux ne voudrait "
            "rien dire."
        )

# ------------------------------------------ onglet 2 : la gouvernance en direct
with onglet_gouv:
    st.markdown(
        "La **même question**, adressée à deux services instanciés sur deux "
        "profils. C'est l'écran qui démontre E4 et E5 : sans lui, une interface "
        "montre un moteur de recherche, pas une gateway gouvernée."
    )
    st.caption(
        "Il n'y a volontairement **pas de sélecteur de profil** : le profil est "
        "une propriété du serveur, fixée à son lancement, pas une préférence "
        "d'affichage. La page joue deux services, elle ne bascule pas un réglage."
    )
    exemples_g = [
        "quelle est notre politique tarifaire sur les remises ?",
        "que dit le compte rendu de la dernière réunion achats ?",
        "quelle est la procédure de retour d'un produit défectueux sous garantie ?",
    ]
    choix_g = st.selectbox("Exemples", exemples_g, key="ex-g")
    question_g = st.text_input("Question", choix_g, key="q-g")

    if st.button("Jouer sur les deux profils", key="btn-g", type="primary"):
        with st.spinner("Recherche..."):
            gauche, droite = st.columns(2)
            for colonne, profil in ((gauche, "support"), (droite, "commercial")):
                d = droits(profil)
                afficher_reponse(
                    colonne, f"profil `{profil}`",
                    f"{len(d.doc_types)} collections : {', '.join(sorted(d.collections))}",
                    service(profil, "D").answer_question(question_g))
        st.caption(
            "Le filtrage s'applique **avant** la recherche, pas après : le "
            "passage interdit n'est pas lu, et la profondeur de recherche est "
            "remplie de candidats autorisés."
        )

    st.divider()
    st.markdown("**Ce que chaque profil voit du corpus**")
    lignes = []
    for profil in ("support", "commercial"):
        d = droits(profil)
        inventaire = service(profil, "D").list_sources()[1]["sources"]
        lignes.append({
            "profil": profil,
            "collections": ", ".join(sorted(d.collections)),
            "documents visibles": len(inventaire),
            "tools autorisés": len(d.tools),
        })
    st.dataframe(lignes, width="stretch", hide_index=True)

# ------------------------------------------------------- onglet 3 : la mesure
with onglet_mesure:
    rapport = Path(__file__).resolve().parent.parent / "eval" / "rapport_gain.md"
    if rapport.exists():
        st.markdown(rapport.read_text(encoding="utf-8"))
    else:
        st.warning("Rapport absent. Lancer `uv run python -m retrieval.rapport`.")

    st.divider()
    st.markdown("**Le jeu d'évaluation**")
    chemin = Path(__file__).resolve().parent.parent / "eval" / "questions_rag.jsonl"
    questions = [json.loads(ligne) for ligne in
                 chemin.read_text(encoding="utf-8").splitlines() if ligne.strip()]
    st.dataframe(questions, width="stretch", hide_index=True)

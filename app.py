"""Sorabel Data Gateway : l'interface du produit, point d'entrée déployé.

    uv run streamlit run app.py

C'est le livrable que le brief nomme « un lien vers une interface graphique du
produit fonctionnel », et le seul qui exige un artefact **déployé**. C'est aussi
celui que l'évaluateur ouvrira en premier, avant le dossier et avant les
journaux.

**Le piège, énoncé au chantier 8.** Une interface qui montre une réponse
documentaire et un résultat SQL montre un chatbot. Elle ne démontre ni E4 ni E5,
c'est-à-dire pas la gouvernance, qui est le sujet du projet. Le produit de
Sorabel n'est pas la recherche, ce sont les **droits sur la recherche**.

Les pages ne sont pas dupliquées ici : `st.navigation` monte les scripts de
`scripts/` tels quels, et chacun reste lançable seul pendant le développement.
"""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

RACINE = Path(__file__).resolve().parent
sys.path.insert(0, str(RACINE))

st.set_page_config(page_title="Sorabel Data Gateway", layout="wide",
                   page_icon="🔌")

PAGES = RACINE / "scripts"


def accueil() -> None:
    st.title("Sorabel Data Gateway")
    st.markdown(
        "Un serveur **MCP** unique et gouverné, consommé par tous les outils "
        "internes de Sorabel. Il expose trois briques derrière un seul point "
        "d'accès : une recherche documentaire qui cite ses sources, un "
        "Text-to-SQL en lecture seule, et une matrice de droits qui décide, "
        "pour chaque appel, ce que l'appelant a le droit de voir.")

    st.info(
        "**Ce que cette interface cherche à prouver.** Montrer une réponse et "
        "un tableau de résultats montrerait un chatbot. Ce qui distingue ce "
        "produit, c'est que **le même appel donne deux issues selon le profil**, "
        "et que les deux sont journalisées. C'est l'objet de la page "
        "« Serveur MCP », et c'est par là qu'il faut commencer.", icon="🎯")

    st.warning(
        "**Cette interface n'est pas le client du produit, elle tient sa "
        "place.** Le cadrage DSI nomme trois consommateurs de la gateway : le "
        "**bot Slack du support**, l'**IDE des développeurs** et le **poste "
        "des commerciaux**. Chacun est un programme distinct, qui lance son "
        "propre processus serveur avec son profil. "
        "L'application Slack en particulier n'est **pas** un client MCP "
        "direct : c'est un service à héberger, qui accuse réception sous les "
        "3 secondes qu'impose Slack, puis publie la réponse dans un second "
        "message (D34). Elle n'est pas construite, et c'est un manque assumé, "
        "inscrit au reste à faire sous les items A1 et A2. "
        "Ce que cette interface démontre est la **gateway et sa gouvernance**, "
        "qui ne changent pas d'un client à l'autre : c'est précisément "
        "l'intérêt d'un point d'accès unique.", icon="💬")

    st.subheader("Les six exigences, et où chacune se voit")
    st.dataframe([
        {"Exigence": "E1 · citer ses sources, ne jamais inventer",
         "Où la voir": "RAG", "Ce qui la rend visible":
         "les sources sous chaque réponse, et une abstention affichée en clair "
         "quand le corpus ne couvre pas"},
        {"Exigence": "E2 · trouver par référence exacte ET en langage naturel",
         "Où la voir": "RAG", "Ce qui la rend visible":
         "REF-8842 par court-circuit, et une question en langage naturel, les "
         "deux aboutissent"},
        {"Exigence": "E3 · SQL en lecture seule, requête toujours renvoyée",
         "Où la voir": "Text-to-SQL", "Ce qui la rend visible":
         "le SQL affiché à côté du résultat, jamais replié, et une demande "
         "d'écriture refusée"},
        {"Exigence": "E4 · un serveur, des droits par profil",
         "Où la voir": "Serveur MCP", "Ce qui la rend visible":
         "les deux catalogues négociés, 7 tools contre 8, et un appel refusé "
         "avant toute logique métier"},
        {"Exigence": "E5 · tout appel journalisé, rien de sensible au support",
         "Où la voir": "Serveur MCP", "Ce qui la rend visible":
         "le même appel joué sur les deux profils, et le journal partagé qui "
         "porte les deux décisions à la suite"},
        {"Exigence": "E6 · le gain de la recherche avancée, chiffré",
         "Où la voir": "Mesure E6", "Ce qui la rend visible":
         "le tableau d'ablation sur quatre configurations, avec ses "
         "intervalles et ce qu'il ne prouve pas"},
    ], width="stretch", hide_index=True)

    g, d = st.columns(2)
    with g:
        st.subheader("Trois choses à savoir avant de cliquer")
        st.markdown(
            "1. **Le profil n'est pas un réglage d'affichage.** Il est fixé au "
            "lancement du serveur et immuable pour la vie du processus. "
            "L'interface parle donc à **deux serveurs**, un par profil : "
            "choisir un profil, c'est choisir à qui l'on s'adresse. Il n'y a "
            "volontairement aucun sélecteur.\n"
            "2. **Le premier chargement est lent.** Les modèles d'embedding, "
            "de reranking et de génération SQL se chargent à la demande. "
            "Comptez une trentaine de secondes, puis tout devient rapide.\n"
            "3. **La génération SQL tourne en local**, sur un petit modèle "
            "retenu délibérément (D48). Il réussit 17 des 24 questions de "
            "l'évaluation, et cette limite est assumée et documentée plutôt "
            "que masquée.")
    with d:
        st.subheader("Ce que ce produit n'est pas")
        st.markdown(
            "- **Pas d'authentification.** L'interface n'identifie personne. "
            "Elle démontre une matrice de droits, pas une gestion d'identité, "
            "et le dossier dit précisément pourquoi les deux ne se confondent "
            "pas : un fournisseur d'identité dit *qui*, la matrice dit *quoi*.\n"
            "- **Pas de sélecteur de profil**, voir ci-contre.\n"
            "- **Pas de refus « joli ».** Un refus s'affiche avec son code et "
            "sa cause, parce que c'est ce qu'un intégrateur doit voir.\n"
            "- **Aucune écriture n'est possible**, sur aucun chemin. La base "
            "est ouverte en lecture seule et toute requête est analysée avant "
            "exécution.")

    st.divider()
    st.caption(
        "Dossier de conception, matrice d'accès et journaux : voir le dépôt. "
        "La matrice fait foi dans `governance/matrice.yaml`, et un script "
        "vérifie que ni le guide d'accès, ni l'oracle de gouvernance, ni la "
        "vue lisible n'en divergent.")


navigation = st.navigation({
    "Le produit": [
        st.Page(accueil, title="Accueil", icon="🏠", default=True),
        st.Page(str(PAGES / "demo_chat.py"), title="Assistant", icon="💬",
                url_path="assistant"),
    ],
    "Sous le capot": [
        st.Page(str(PAGES / "demo_mcp.py"), title="Serveur MCP", icon="🔐",
                url_path="mcp"),
        st.Page(str(PAGES / "demo_rag.py"), title="Recherche documentaire",
                icon="📚", url_path="rag"),
        st.Page(str(PAGES / "demo_sql.py"), title="Text-to-SQL", icon="🗃️",
                url_path="sql"),
    ],
    "La preuve chiffrée": [
        st.Page(str(PAGES / "demo_e6.py"), title="Mesure E6", icon="📈",
                url_path="e6"),
    ],
})
navigation.run()

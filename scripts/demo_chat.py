"""Assistant Sorabel : l'interface conversationnelle, sur les deux profils.

    uv run streamlit run scripts/demo_chat.py

**Ce que cette page est.** Un champ, une question, une réponse. L'utilisateur
ignore qu'il existe huit tools et n'en choisit aucun : le routage décide. C'est
l'inverse des écrans techniques, qui **exposent** la mécanique ; celui-ci la
**cache**, et ne garde visible que ce qui sert à comprendre la réponse.

CHOISIR UN PROFIL N'EST PAS SE DONNER UN DROIT, ET LA NUANCE EST TOUT
Le défaut corrigé pendant la conception était de faire du profil un
**paramètre d'appel de tool** : n'importe quel appelant se déclarait alors
`commercial`, et E4 devenait décorative. Ici, rien de tel. **Deux processus
serveur** tournent, chacun lancé avec son profil, immuable pour sa vie entière
(D28). Le sélecteur choisit **auquel des deux on parle**, exactement comme
l'écran MCP le fait déjà. Aucun tool ne reçoit de profil, et aucune variable
d'environnement n'est modifiée en cours de route.

Cela s'écarte néanmoins de D40, qui écartait tout sélecteur de l'interface
livrable. L'écart est assumé, demandé par le pilote pour pouvoir éprouver les
deux profils, et borné : il sélectionne un interlocuteur, jamais une
permission.

**Le fil est commun aux deux profils**, et chaque réponse porte la marque de
celui qui l'a produite. C'est ce qui rend la comparaison lisible : poser la
même question aux deux, et lire les deux issues à la suite.
"""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from scripts.page import configurer  # noqa: E402

configurer("Assistant Sorabel")

from client.conversation import Conversation  # noqa: E402
from client.routeur import Routeur  # noqa: E402
from common.matrice import droits  # noqa: E402
from scripts.client_persistant import ClientPersistant  # noqa: E402

PROFILS = ("support", "commercial")
JOURNAL = RACINE / "logs" / "demo_mcp.jsonl"
TRACE = RACINE / "logs" / "conversation.jsonl"

PASTILLE = {"ok": "🟢", "refused": "🔴", "clarification": "🟡",
            "hors_corpus": "🟡", "error": "⚫"}
LECTURE_TITRE = {"refused": "Demande refusée",
                 "clarification": "Précision nécessaire",
                 "hors_corpus": "Hors documentation",
                 "error": "Panne technique"}

#: Questions d'amorce, avec ce qui se produit REELLEMENT sur chaque profil,
#: relevé le 2026-09-03 en jouant les deux. Une légende qui promettrait mieux
#: que ce que la page rend serait le pire des défauts sur un écran de
#: démonstration : l'évaluateur clique, et la promesse tombe devant lui.
#:
#: « Combien de ventes en avril ? » a été RETIREE de cette liste. Le support y
#: répond `ok`, parce que la table `ventes` lui est cachée et que le modèle
#: substitue `commandes` sans le dire, tandis que le commercial échoue sur une
#: colonne mal devinée. Le bouton donnerait donc à croire que le support a plus
#: d'accès que le commercial, ce qui est l'inverse de la vérité. Le phénomène
#: reste consigné, c'est le cas MCP-18.
EXEMPLES = [
    ("Où en est la négociation avec le fournisseur Fixor ?",
     "E5 · le support s'abstient, le commercial obtient la réponse et ses "
     "sources. C'est la comparaison la plus nette."),
    ("Quelle est la procédure de retour d'un produit défectueux ?",
     "E1 · même réponse pour les deux, avec ses sources citées"),
    ("Combien de commandes en avril ?",
     "E3 · un résultat, et la requête qui l'a produit"),
    ("Quelle est la marge sur la REF-8842 ?",
     "E5 · refusée au support par la matrice, en une milliseconde. Le "
     "commercial y a droit, mais le générateur local échoue à écrire la "
     "requête : deux refus, deux causes, deux codes."),
    ("Supprime les commandes de test",
     "E3 · refusée pour les deux. Sur le profil commercial, le modèle produit "
     "un vrai DELETE que la couche AST arrête."),
]


@st.cache_resource
def sessions() -> dict[str, tuple[ClientPersistant, Conversation]]:
    """Une session MCP et une conversation PAR PROFIL, gardées ouvertes.

    L'encodeur est partagé : deux routeurs indépendants chargeraient le modèle
    d'embeddings deux fois, pour un vocabulaire qui ne diffère que par les
    tables du profil.
    """
    from common.embeddings import Encodeur

    encodeur = Encodeur()
    out = {}
    for profil in PROFILS:
        client = ClientPersistant(profil, JOURNAL)
        routeur = Routeur(encodeur=encodeur, profil=profil)
        out[profil] = (client, Conversation(client, routeur, trace=TRACE,
                                            profil=profil))
    return out


TOUT = sessions()
fil: list = st.session_state.setdefault("fil", [])

# ------------------------------------------------------------ barre latérale
st.sidebar.title("Assistant Sorabel")
actif = st.sidebar.radio(
    "À qui vous adressez-vous ?", PROFILS,
    format_func=lambda p: f"{p} · {len(TOUT[p][0].outils)} tools",
    help="Ce n'est pas un réglage de droits : c'est le choix du serveur auquel "
         "la question est envoyée. Les deux tournent en permanence.")
st.sidebar.caption(f"client réel de ce profil : {droits(actif).client}")

for profil in PROFILS:
    client = TOUT[profil][0]
    if client.erreur:
        st.sidebar.error(f"`{profil}` : {client.erreur}")

st.sidebar.info(
    "**Deux processus serveur, un par profil.** Chacun a reçu son profil au "
    "lancement, et ne peut plus en changer (D28). Le sélecteur ci-dessus "
    "choisit l'interlocuteur, il ne modifie aucun droit : aucun tool ne prend "
    "de profil en paramètre, et c'est précisément le défaut que la conception "
    "a corrigé.", icon="🔒")

st.sidebar.divider()
st.sidebar.subheader("Comment la question est aiguillée")
st.sidebar.markdown(
    "Vous ne choisissez pas de tool, le **routage** le fait. Il combine un "
    "vocabulaire **déclaré**, relevé dans le schéma de la base et dans le "
    "lexique de refus de la matrice, puis une **similarité d'embeddings** "
    "quand aucun terme ne tranche.\n\n"
    "Mesuré sur les 54 questions des fixtures : **47 justes**, 44 sur 46 hors "
    "questions hors corpus, et **9 sur 9** sur celles qui démontrent une "
    "exigence. Rejouable par `uv run python eval/mesure_routage.py`.")
with st.sidebar.expander("Ce qui avait été essayé d'abord, et qui a échoué"):
    st.markdown(
        "Confier le routage au modèle local retenu par D48. **Quatre montages "
        "mesurés, tous au niveau du hasard**, dont l'un répondait "
        "« documentaire » à 100 % des questions. C'est un modèle de *code* de "
        "0,5 milliard de paramètres : la classification en français libre est "
        "hors de sa portée, et la conclusion vient de la mesure.")

if st.sidebar.button("Effacer le fil"):
    st.session_state["fil"] = []
    st.rerun()

# ------------------------------------------------------------------- en-tête
st.title("Posez votre question")
st.caption(f"Vous parlez au serveur **{actif}**. Documentation technique, "
           "procédures SAV, stocks, commandes : l'assistant choisit lui-même "
           "où chercher.")

if not fil:
    st.markdown("**Quelques questions pour commencer :**")
    for question, quoi in EXEMPLES:
        colonne, legende = st.columns([2, 3])
        if colonne.button(question, key=f"ex-{question[:20]}", width="stretch"):
            st.session_state["amorce"] = (question, actif)
            st.rerun()
        legende.caption(quoi)
    st.info(
        "Le premier échange ouvre deux sessions serveur et charge les modèles "
        "à la demande : comptez une trentaine de secondes. Une question sur la "
        "base passe ensuite par un modèle de génération SQL local, environ "
        "quinze secondes.", icon="⏳")


# ------------------------------------------------------------------ affichage
def afficher(tour) -> None:  # noqa: ANN001
    with st.chat_message("user"):
        st.write(tour.question)
        st.caption(f"posée au profil `{tour.profil}`")

    with st.chat_message("assistant"):
        st.markdown(f"{PASTILLE.get(tour.statut, '⚪')} **`{tour.profil}`**")
        if tour.statut == "ok":
            st.write(tour.texte)
        elif tour.refuse:
            st.error(f"**{LECTURE_TITRE[tour.statut]}.** {tour.texte}")
        else:
            st.warning(f"**{LECTURE_TITRE.get(tour.statut, '')}.** {tour.texte}")

        # E1 porte sur la restitution : les sources restent visibles.
        if tour.sources:
            st.markdown("**Sources**")
            for s in tour.sources:
                st.markdown(f"- {s.get('titre', '?')} · "
                            f"`{s.get('reference', '?')}` · {s.get('date', '?')}")

        # E3 oblige la gateway à RENVOYER la requête, pas la page à l'afficher.
        # Repliée quand tout va bien ; VISIBLE sur un refus, car un refus sans
        # sa requête n'est pas auditable, et c'est là que le SQL compte le plus.
        if tour.sql:
            if tour.statut == "ok":
                with st.expander("Voir la requête exécutée"):
                    st.code(tour.sql, language="sql")
            else:
                st.markdown("**Requête refusée**")
                st.code(tour.sql, language="sql")

        lignes = tour.payload.get("rows")
        colonnes = tour.payload.get("columns") or []
        if lignes and not (len(lignes) == 1 and len(colonnes) == 1):
            st.dataframe([dict(zip(colonnes, r)) for r in lignes],
                         width="stretch", hide_index=True)

        r = tour.routage
        if r:
            detail = f"`{r.tool}` · aiguillé par {r.par}"
            if r.indice:
                detail += f" « {r.indice} »"
            if r.similarites:
                detail += " · " + ", ".join(
                    f"{k} {v:.3f}" for k, v in sorted(r.similarites.items(),
                                                      key=lambda x: -x[1]))
            if tour.code:
                detail += f" · code `{tour.code}`"
            detail += f" · {tour.duree_ms / 1000:.1f} s"
            st.caption(detail)


for tour in fil:
    afficher(tour)

# Rejouer la MEME question sur l'autre serveur : c'est la comparaison que la
# gouvernance demande, obtenue sans ressaisir la question, donc sans risque
# qu'elle diffère d'une virgule.
if fil:
    dernier = fil[-1]
    autre = next(p for p in PROFILS if p != dernier.profil)
    if st.button(f"Rejouer cette question sur le profil « {autre} »"):
        st.session_state["amorce"] = (dernier.question, autre)
        st.rerun()

# ------------------------------------------------------------------- saisie
saisie = st.chat_input(f"Votre question au profil {actif}")
amorce = st.session_state.pop("amorce", None)
question, cible = (saisie, actif) if saisie else (amorce or (None, actif))

if question:
    with st.spinner(f"Recherche en cours sur le profil {cible}..."):
        fil.append(TOUT[cible][1].repondre(question))
    st.rerun()

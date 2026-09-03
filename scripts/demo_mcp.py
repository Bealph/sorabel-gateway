"""Démonstration visuelle du serveur MCP : gouvernance et journal.

    uv sync --extra vector --extra demo
    uv run streamlit run scripts/demo_mcp.py

**Ce que cette page montre.** Les deux autres démonstrations appellent les
couches internes ; celle-ci parle au **vrai serveur, par le vrai protocole**, en
stdio. Deux processus tournent en arrière-plan, un par profil, et chaque bouton
est un appel MCP réel.

C'est la seule des trois pages qui montre le **produit** plutôt que ses briques :
le catalogue négocié à l'ouverture, l'enveloppe telle qu'un client la reçoit, et
le journal que les deux processus partagent.

**Il n'y a pas de sélecteur de profil au sens d'un réglage.** Le profil est fixé
au lancement du serveur (D28) et immuable pour la vie du processus. La page
entretient **deux sessions distinctes**, et choisir un profil, c'est choisir à
quel serveur on parle.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import streamlit as st

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from scripts.page import configurer  # noqa: E402

from scripts.client_persistant import ClientPersistant  # noqa: E402

configurer("Sorabel, demo serveur MCP")

JOURNAL = RACINE / "logs" / "demo_mcp.jsonl"
PROFILS = ("support", "commercial")
PASTILLE = {"ok": "🟢", "refused": "🔴", "clarification": "🟡",
            "hors_corpus": "🟡", "error": "⚫"}

#: Le scénario de la session de démonstration. Les deux profils reçoivent
#: exactement les mêmes appels : c'est la seule façon de montrer que la
#: différence vient de la matrice et de rien d'autre.
SCENARIO = (
    ("answer_question",
     {"question": "quelle est la procedure de retour d'un produit defectueux ?"},
     "E1 · une réponse documentaire avec ses sources"),
    ("answer_question",
     {"question": "ou en est la negociation avec le fournisseur Fixor ?"},
     "E5 · la réponse vit dans les notes internes, fermées au support"),
    ("get_schema", {},
     "E4 · le tool n'est pas au catalogue du support"),
    ("ask_database", {"question": "quelle est la marge sur la REF-8842 ?"},
     "E5 · la colonne est retirée au support, refus en moins d'une milliseconde"),
    ("check_stock", {"reference": "REF-8842"},
     "un tool figé, accessible aux deux, déterministe"),
)


# --------------------------------------------------------------- ressources
@st.cache_resource
def client(profil: str) -> ClientPersistant:
    """Une session MCP ouverte par profil, gardée pour toute la session.

    Sans persistance, chaque clic relancerait un processus serveur et
    rechargerait ses modèles. Un client MCP durable ne fait pas cela, un IDE non
    plus : il ouvre une session et la garde.
    """
    return ClientPersistant(profil, JOURNAL)


@st.cache_data
def cas_gouvernance() -> list[dict]:
    chemin = RACINE / "eval" / "cas_mcp.jsonl"
    return [json.loads(ligne) for ligne
            in chemin.read_text(encoding="utf-8").splitlines() if ligne.strip()]


def lire_journal() -> list[dict]:
    if not JOURNAL.exists():
        return []
    return [json.loads(ligne) for ligne
            in JOURNAL.read_text(encoding="utf-8").splitlines() if ligne.strip()]


# ------------------------------------------------------------------ affichage
def enveloppe(colonne, titre: str, sous_titre: str, reponse: dict,
              duree: float | None = None) -> None:
    statut = reponse.get("status", "?")
    payload = reponse.get("payload") or {}
    with colonne:
        st.markdown(f"**{titre}**")
        st.caption(sous_titre)
        entete = f"{PASTILLE.get(statut, '⚪')} `status = {statut}`"
        if payload.get("code"):
            entete += f" · `code = {payload['code']}`"
        if duree is not None:
            entete += f" · {duree * 1000:.0f} ms" if duree < 1 else f" · {duree:.1f} s"
        st.markdown(entete)
        if reponse.get("message"):
            st.info(reponse["message"])
        with st.expander("L'enveloppe brute, telle que le client la reçoit"):
            st.json(reponse, expanded=False)


def tableau_journal(entrees: list[dict]) -> None:
    if not entrees:
        st.info("Journal vide. Jouer un appel pour l'alimenter.")
        return
    st.dataframe([
        {
            "heure": e["timestamp"][11:23],
            "profil": e["profile"],
            "tool": e["tool"],
            "status": f"{PASTILLE.get(e['status'], '')} {e['status']}",
            "code": e.get("code", ""),
            "durée": f"{e['duree_ms']:.0f} ms",
            "arguments": json.dumps(e.get("arguments", {}), ensure_ascii=False)[:70],
        }
        for e in entrees
    ], width="stretch", hide_index=True)
    refuses = sum(1 for e in entrees if e["status"] == "refused")
    g, d, t = st.columns(3)
    g.metric("Appels journalisés", len(entrees))
    d.metric("Refusés", refuses)
    t.metric("Autorisés", len(entrees) - refuses)
    st.caption(
        "**Une ligne par appel, autorisé comme refusé.** C'est E5, et c'est vrai "
        "par construction : tous les appels traversent un point de passage unique "
        "qui journalise avant de rendre l'enveloppe. Il n'y a pas de second "
        "chemin, donc pas de chemin qui aurait oublié le journal."
    )


# ------------------------------------------------------------ barre latérale
st.sidebar.title("Les deux serveurs")
st.sidebar.caption(
    "Deux processus `python -m mcp_server.server`, un par profil, lancés au "
    "premier chargement de la page. Ils lisent la **même** matrice et écrivent "
    "dans le **même** journal."
)
for profil in PROFILS:
    c = client(profil)
    if c.erreur:
        st.sidebar.error(f"`{profil}` : {c.erreur}")
    else:
        st.sidebar.success(f"`{profil}` · {len(c.outils)} tools · session ouverte")
st.sidebar.divider()
st.sidebar.caption(f"Journal : `{JOURNAL.relative_to(RACINE)}`")
if st.sidebar.button("Vider le journal"):
    JOURNAL.unlink(missing_ok=True)
    st.rerun()

st.title("Le serveur MCP, en fonctionnement")
st.caption("Deux processus, une matrice, un journal. Chaque bouton de cette page "
           "est un appel MCP réel, en stdio.")

onglets = st.tabs([
    "Le catalogue négocié",
    "Un appel, de bout en bout",
    "La session de démonstration",
    "Le journal (E5)",
    "Les 22 cas de gouvernance",
])

# --------------------------------------------- onglet 1 : le catalogue
with onglets[0]:
    st.markdown(
        "À l'ouverture d'une session, le client demande `tools/list`. Le serveur "
        "répond avec **le catalogue borné au profil** : on n'annonce pas ce que "
        "l'appelant ne peut pas appeler."
    )
    g, d = st.columns(2)
    for colonne, profil in zip((g, d), PROFILS):
        c = client(profil)
        with colonne:
            st.markdown(f"### `{profil}` · {len(c.outils)} tools")
            st.dataframe([
                {"tool": o.nom,
                 "paramètres": ", ".join((o.schema.get("properties") or {})) or "—",
                 "obligatoires": ", ".join(o.schema.get("required") or []) or "aucun"}
                for o in c.outils
            ], width="stretch", hide_index=True)

    manquants = ({o.nom for o in client("commercial").outils}
                 - {o.nom for o in client("support").outils})
    st.warning(f"Différence de catalogue : **{', '.join(sorted(manquants)) or 'aucune'}**",
               icon="🔎")
    st.info(
        "**Aucun paramètre n'est obligatoire, et c'est délibéré.** Le contrôle du "
        "droit d'appeler doit précéder toute validation de schéma : un client sans "
        "droit sur un tool doit recevoir un refus de **matrice**, pas une erreur "
        "de protocole. La suite d'acceptance le vérifie en appelant chaque tool "
        "interdit avec un objet d'arguments vide.\n\n"
        "**Aucun tool ne prend le profil en paramètre.** Un paramètre est rempli "
        "par l'appelant : le bot support n'aurait qu'à se déclarer `commercial`.",
        icon="🔒")

    with st.expander("La définition complète d'un tool, telle que le protocole la transporte"):
        choix = st.selectbox("Tool", [o.nom for o in client("commercial").outils],
                             key="t1")
        outil = next(o for o in client("commercial").outils if o.nom == choix)
        st.json({"name": outil.nom, "description": outil.description,
                 "inputSchema": outil.schema}, expanded=True)

# --------------------------------------------- onglet 2 : un appel
with onglets[1]:
    st.markdown(
        "Un appel réel, et tout ce qu'il produit : l'enveloppe rendue au client, "
        "et la ligne de journal écrite côté serveur."
    )
    g, d = st.columns([1, 2])
    with g:
        profil_2 = st.radio("À quel serveur parle-t-on ?", PROFILS, key="p2",
                            help="Ce n'est pas un réglage d'affichage : c'est le "
                                 "choix du processus auquel on s'adresse.")
        outils_2 = [o.nom for o in client(profil_2).outils]
        # On propose AUSSI les tools hors catalogue : c'est le refus qu'on veut voir.
        tous = sorted({o.nom for p in PROFILS for o in client(p).outils})
        tool_2 = st.selectbox("Tool", tous, key="t2",
                              help="Un tool absent du catalogue de ce profil est "
                                   "appelable, et sera refusé.")
        if tool_2 not in outils_2:
            st.caption(f"⚠️ hors catalogue de `{profil_2}` : refus attendu")
        defauts = {
            "answer_question": '{"question": "quelle est la procedure de retour ?"}',
            "search_docs": '{"query": "REF-8842"}',
            "get_document": '{"doc_id": "REF-8842-v2.1"}',
            "list_sources": '{"doc_type": "fiche_technique"}',
            "ask_database": '{"question": "combien de commandes en avril ?"}',
            "get_schema": "{}",
            "check_stock": '{"reference": "REF-8842"}',
            "order_status": '{"order_id": "CMD-2026-0042"}',
        }
        args_2 = st.text_area("Arguments (JSON)", defauts.get(tool_2, "{}"),
                              height=110, key="a2")
        lancer = st.button("Appeler", type="primary", key="b2")
    with d:
        if lancer:
            try:
                arguments = json.loads(args_2 or "{}")
            except json.JSONDecodeError as e:
                st.error(f"Arguments illisibles : {e}")
            else:
                avant = len(lire_journal())
                with st.spinner("Appel MCP en cours..."):
                    debut = time.time()
                    reponse = client(profil_2).appeler(tool_2, arguments)
                    duree = time.time() - debut
                enveloppe(st.container(), f"`{tool_2}` sur `{profil_2}`",
                          "appel MCP réel, transport stdio", reponse, duree)
                nouvelles = lire_journal()[avant:]
                st.markdown("**La ligne de journal que cet appel a écrite**")
                if nouvelles:
                    st.json(nouvelles[-1], expanded=True)
                else:
                    st.error("Aucune ligne de journal : ce serait un angle mort d'audit.")

# --------------------------------------------- onglet 3 : la session
with onglets[2]:
    st.markdown(
        "La **même séquence d'appels**, jouée sur les deux profils. C'est l'écran "
        "qui démontre E4 et E5 : la différence ne peut venir que de la matrice, "
        "puisque tout le reste est identique."
    )
    if st.button("Jouer la session complète", type="primary", key="b3"):
        JOURNAL.unlink(missing_ok=True)
        resultats: dict[str, list] = {p: [] for p in PROFILS}
        barre = st.progress(0.0, text="Session en cours...")
        total = len(SCENARIO) * len(PROFILS)
        fait = 0
        for profil in PROFILS:
            for tool, arguments, _ in SCENARIO:
                debut = time.time()
                resultats[profil].append(
                    (client(profil).appeler(tool, arguments), time.time() - debut))
                fait += 1
                barre.progress(fait / total, text=f"{profil} · {tool}")
        barre.empty()

        for i, (tool, arguments, pourquoi) in enumerate(SCENARIO):
            st.divider()
            argument = next(iter(arguments.values()), "")
            st.markdown(f"**{i + 1}. `{tool}`** · {str(argument)[:70]}")
            st.caption(pourquoi)
            g, d = st.columns(2)
            for colonne, profil in zip((g, d), PROFILS):
                reponse, duree = resultats[profil][i]
                enveloppe(colonne, f"`{profil}`", "", reponse, duree)

        st.divider()
        st.markdown("### Le journal partagé par les deux processus")
        tableau_journal(lire_journal())

# --------------------------------------------- onglet 4 : le journal
with onglets[3]:
    st.markdown(
        "Le journal est un fichier **JSONL en ajout**, une ligne complète par "
        "appel. Un arrêt brutal peut perdre la dernière ligne, jamais corrompre "
        "les précédentes, et il se lit sans outil, ce qui compte le jour où on "
        "l'ouvre devant quelqu'un."
    )
    entrees = lire_journal()
    filtres = st.columns(3)
    profils_vus = sorted({e["profile"] for e in entrees}) or list(PROFILS)
    statuts_vus = sorted({e["status"] for e in entrees}) or ["ok"]
    f_profil = filtres[0].multiselect("Profil", profils_vus, profils_vus)
    f_statut = filtres[1].multiselect("Statut", statuts_vus, statuts_vus)
    f_tool = filtres[2].multiselect("Tool", sorted({e["tool"] for e in entrees}),
                                    sorted({e["tool"] for e in entrees}))
    tableau_journal([e for e in entrees
                     if e["profile"] in f_profil and e["status"] in f_statut
                     and e["tool"] in f_tool])

    with st.expander("Ce qui entre au journal, et ce qui n'y entre pas"):
        st.markdown(
            "- **Y entre** : l'horodatage, le profil, le tool, les arguments, le "
            "statut, le message, le code, la durée, les ressources touchées et le "
            "SQL généré. Le SQL y figure même quand l'appel est refusé : un refus "
            "sans sa requête n'est pas auditable.\n"
            "- **N'y entre pas** : aucune ligne de résultat. Les **ressources "
            "touchées** suffisent à un audit E5 pour compter les accès tentés à "
            "une colonne sensible, sans recopier la donnée elle-même."
        )
        if entrees:
            st.json(entrees[-1], expanded=True)

# --------------------------------------------- onglet 5 : les cas
with onglets[4]:
    cas = cas_gouvernance()
    st.markdown(
        f"Les **{len(cas)} cas de gouvernance** de `eval/cas_mcp.jsonl` : profil × "
        "tool × attendu, avec les attentes de journal. Ils ont été écrits pendant "
        "la revue de conception, quand les quatre tests d'acceptation MCP "
        "n'avaient **aucun oracle**."
    )
    st.dataframe([
        {"id": c["id"], "exigence": c["exigence"], "profil": c["profil"],
         "tool": c["tool"],
         "attendu": f"{c['attendu'].get('status', '')} {c['attendu'].get('code', '')}".strip(),
         "motif": c["motif"][:90]}
        for c in cas
    ], width="stretch", hide_index=True)

    st.warning(
        "**Ce fichier était faux jusqu'au 2026-09-03**, et sur cinq axes : il "
        "attendait `search_docs` refusé au support alors que le cadrage le lui "
        "accorde, nommait un profil `dev` qui n'existe pas, employait deux "
        "statuts hors contrat, des noms d'arguments périmés et des clés de "
        "journal en français. Il avait été écrit **avant** le rapatriement du "
        "dépôt amont et jamais réaligné. Un oracle faux est plus dangereux "
        "qu'un oracle absent : il fait échouer un serveur juste, ou pire, "
        "réussir un serveur faux.\n\n"
        "Il est désormais tenu par `eval/verifier_cas_mcp.py`, qui le confronte "
        "à la matrice, au catalogue et au contrat. Contrôle éprouvé par huit "
        "mutations, dont la dérive historique elle-même : **8 sur 8 attrapées**.",
        icon="⚠️")

    st.divider()
    jouables = [c for c in cas if c["profil"] in PROFILS and "+" not in c["tool"]
                and c["tool"] != "*"]
    st.markdown(f"**Rejouer les {len(jouables)} cas directement jouables**")
    st.caption(
        "Les autres portent sur une composition de deux tools, ou sur le journal "
        "lui-même, et se jouent dans la suite d'acceptance. Les appels à "
        "`ask_database` passent par le modèle local : compter une quinzaine de "
        "secondes chacun."
    )
    if st.button("Rejouer", type="primary", key="b5"):
        lignes = []
        barre = st.progress(0.0)
        for i, c in enumerate(jouables, start=1):
            barre.progress((i - 1) / len(jouables), text=f"{c['id']} · {c['tool']}")
            reponse = client(c["profil"]).appeler(c["tool"], c.get("args") or {})
            payload = reponse.get("payload") or {}
            obtenu, code = reponse.get("status", "?"), payload.get("code", "")
            attendu = c["attendu"].get("status", "")
            # Un cas peut fixer un code exact, ou admettre plusieurs codes quand
            # la COUCHE qui prononce le refus dépend de la qualité du modèle.
            admis = c["attendu"].get("codes_admis") or (
                [c["attendu"]["code"]] if "code" in c["attendu"] else [])
            juste = obtenu == attendu and (not admis or code in admis)
            limite = c.get("limite_connue")
            lignes.append({
                "id": c["id"], "exigence": c["exigence"], "profil": c["profil"],
                "tool": c["tool"], "attendu": attendu,
                "code attendu": " ou ".join(admis) or "—",
                "obtenu": obtenu, "code obtenu": code or "—",
                "verdict": "✅" if juste else ("⚠️" if limite else "❌"),
                "limite connue": limite["decision_projet"] if limite else "",
            })
        barre.empty()
        justes = [x for x in lignes if x["verdict"] == "✅"]
        connus = [x for x in lignes if x["verdict"] == "⚠️"]
        inattendus = [x for x in lignes if x["verdict"] == "❌"]
        (st.success if not inattendus else st.error)(
            f"{len(justes)} sur {len(lignes)} conformes à l'oracle · "
            f"{len(connus)} limite(s) connue(s) · {len(inattendus)} écart(s) "
            "inattendu(s)")
        st.dataframe(lignes, width="stretch", hide_index=True)

        for x in connus:
            c = next(k for k in cas if k["id"] == x["id"])
            lim = c["limite_connue"]
            st.warning(
                f"**{x['id']} · limite connue, {lim['decision_projet']}.** "
                f"{lim['constat'].capitalize()}. {lim['cause'].capitalize()}.\n\n"
                "**L'attente reste `ok` alors que le système échoue, et c'est "
                "délibéré.** La gouvernance est juste : `marge_pct` figure bien "
                "dans le schéma rendu au commercial, vérifié le 2026-09-03. Ce "
                "qui manque est la capacité du générateur retenu par D48, "
                "mesurée à 17/24. Aligner l'oracle sur le comportement observé "
                "transformerait une limite de modèle en comportement attendu, "
                "et la ferait disparaître du rapport. C'est précisément ce "
                "qu'un oracle sert à empêcher.", icon="⚠️")
        st.caption(
            "**Deux cas rendent `ok` là où l'on attendrait un refus, et c'est "
            "voulu.** MCP-12 et MCP-18 documentent un angle mort réel : la "
            "couche 0 cache la colonne `marge_pct` et la table `ventes`, donc le "
            "modèle ne peut pas les nommer. Au lieu d'échouer, il **substitue** "
            "une ressource visible et rend une réponse plausible qui ne répond "
            "pas à la question. Aucune donnée sensible ne sort, mais aucune "
            "couche ne vérifie le *sens*. C'est le troisième motif de D41, et "
            "l'oracle le dit au lieu de le masquer.")

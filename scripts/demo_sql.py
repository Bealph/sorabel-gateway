"""Démonstration visuelle du chantier Text-to-SQL.

    uv sync --extra vector --extra demo
    uv run streamlit run scripts/demo_sql.py

**Ce que cette page montre, et pourquoi elle existe.** Le Text-to-SQL est le
chantier le plus riche en mécanique et le moins visuel des trois : une question
entre, un tableau sort, et tout ce qui se joue entre les deux est invisible.
Cette page rend chaque étage visible, et surtout **elle montre où une question
s'arrête**. Un refus sans son étage n'apprend rien ; un refus qui nomme sa
couche explique le système entier.

**Ce qu'elle n'est pas.** Elle n'est pas un client MCP. Elle appelle directement
`ServiceSql.tracer()`, qui rend le prompt envoyé au modèle, sa sortie brute et
les ressources extraites de l'arbre syntaxique. Un client MCP, lui, ne reçoit
que l'enveloppe `{status, payload, message}` : la page affiche les deux côte à
côte, précisément pour qu'on voie ce qui NE sort pas.

**Le contournement du pré-filtre est une capacité de cette page, jamais du
serveur.** Un interrupteur qui désactive une garde, exposé côté serveur ou passé
dans un appel de tool, serait le défaut corrigé sur `profil` : n'importe quel
appelant s'en servirait. Ici c'est un argument d'un appel direct, absent de toute
signature de tool et de toute variable d'environnement.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.config import CONFIG  # noqa: E402
from common.matrice import droits, lexique_refus  # noqa: E402
from sql.gardes import LIMITE  # noqa: E402
from sql.generateur import GenerateurLocal  # noqa: E402
from sql.schema import introspecter  # noqa: E402
from sql.service import ServiceSql, Trace  # noqa: E402

st.set_page_config(page_title="Sorabel, demo Text-to-SQL", layout="wide")

PASTILLE = {"ok": "🟢", "refused": "🔴", "clarification": "🟡", "error": "⚫"}
RACINE = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------- ressources
@st.cache_resource
def generateur() -> GenerateurLocal:
    """Un seul générateur pour toute la session, préchauffé dès le lancement.

    Mesuré sur ce poste : le premier appel coûte jusqu'à 677 secondes, contre
    12 à 20 ensuite. Ce n'est pas la génération, c'est le chargement du modèle
    sur un processeur bridé. Sans préchauffage annoncé, la page paraît cassée.
    """
    g = GenerateurLocal()
    g.prechauffer()
    return g


@st.cache_resource
def service(profil: str) -> ServiceSql:
    return ServiceSql(droits(profil), generateur())


@st.cache_data
def jeu_eval() -> list[dict]:
    questions = {q["id"]: q for q in _jsonl("questions_sql.jsonl")}
    for a in _jsonl("attendus_sql.jsonl"):
        questions.get(a["id"], {}).update({f"attendu_{k}": v for k, v in a.items()
                                           if k not in ("id",)})
    return list(questions.values())


def _jsonl(nom: str) -> list[dict]:
    chemin = RACINE / "eval" / nom
    return [json.loads(ligne) for ligne
            in chemin.read_text(encoding="utf-8").splitlines() if ligne.strip()]


# ------------------------------------------------------------------ affichage
def bandeau_modele() -> None:
    g = generateur()
    if g.pret:
        st.success(f"Modèle `{g.nom}` chargé. Comptez 12 à 20 s par question.",
                   icon="✅")
        return
    st.warning(
        f"**Modèle `{g.nom}` en cours de chargement**, en tâche de fond. "
        "Sur ce poste, le processeur descend à 801 MHz sur 2304 sous charge : "
        "le premier chargement a été mesuré jusqu'à **677 secondes**. La page "
        "n'est pas figée. Les tools figés et tous les refus fonctionnent déjà, "
        "eux, sans modèle.", icon="⏳")
    if st.button("Rafraîchir l'état du chargement"):
        st.rerun()


def pile(trace: Trace) -> None:
    """La pile de gardes, étage par étage, avec celui qui a tranché."""
    st.markdown("**La pile de gardes, étage par étage**")
    lignes = []
    for e in trace.etapes:
        lignes.append({
            "étage": e.nom,
            "issue": "🛑 a bloqué" if e.bloque else "✅ passé",
            "durée": f"{e.duree * 1000:.1f} ms" if e.duree < 1 else f"{e.duree:.2f} s",
            "ce qu'il a vu": e.detail,
        })
    st.dataframe(lignes, width="stretch", hide_index=True)
    if trace.bloque_par:
        st.error(f"Arrêtée par **{trace.bloque_par}** · code `{trace.code}`", icon="🛑")
    st.caption(
        "Le pré-filtre coûte moins d'une milliseconde et le reste coûte tout : "
        "c'est pourquoi il court-circuite la démonstration, et pourquoi "
        "l'onglet « Défense en profondeur » permet de le désactiver."
    )


def detail_technique(trace: Trace) -> None:
    """Tout ce que le tool ne montre pas, et que la page montre."""
    g1, g2 = st.columns(2)

    with g1:
        st.markdown("**Couche 0 · le schéma réellement envoyé au modèle**")
        st.caption(
            "Introspecté puis intersecté avec la matrice. Les énumérations sont "
            "relevées dans la base, accents compris : `'Cablage'` sans accent "
            "rendrait zéro ligne en franchissant toutes les gardes, sans erreur."
        )
        st.code(trace.prompt_schema or "(non atteint)", language="sql")
        if trace.jointures:
            st.caption("Chemins de jointure transmis, les seuls du périmètre :")
            st.code("\n".join(trace.jointures), language="text")

    with g2:
        st.markdown("**La sortie brute du modèle, avant analyse**")
        st.caption(
            "La sortie est structurée en trois cas : `SQL:`, `CLARIFY:` ou "
            "`HORS_SCHEMA:`. Un générateur qui ne saurait rendre que du SQL "
            "serait contraint d'inventer une requête pour une question hors "
            "schéma. Une sortie hors format devient un refus, jamais une "
            "requête devinée."
        )
        if trace.generation:
            st.code(trace.generation.brut or "(le générateur n'a pas été appelé)",
                    language="text")
            st.markdown(f"Cas retenu : `{trace.generation.cas}`")
        else:
            st.info("Le générateur n'a pas été atteint : un étage antérieur a tranché.")

        if trace.verdict is not None and getattr(trace.verdict, "ok", False):
            st.markdown("**Couche 3 · ce que l'AST a vu**")
            st.caption(
                "Toute occurrence d'une colonne, pas seulement les projections : "
                "`ORDER BY marge_pct` divulgue le classement sans afficher la "
                "colonne."
            )
            st.json(trace.verdict.ressources, expanded=True)


def sql_et_resultat(trace: Trace) -> None:
    genere = trace.generation.sql if trace.generation else ""
    reecrit = getattr(trace.verdict, "sql", "") if trace.verdict is not None else ""
    if genere:
        st.markdown("**Couche 5 · le SQL, toujours renvoyé avec le résultat (E3)**")
        st.code(genere, language="sql")
        if reecrit and reecrit != genere:
            st.caption(f"Réécrit par la couche 4, qui plafonne à {LIMITE} lignes :")
            st.code(reecrit, language="sql")
        elif reecrit:
            st.caption("Inchangé par la couche 4 : un agrégat scalaire rend une "
                       "seule ligne, y injecter un `LIMIT` n'aurait pas de sens.")

    if trace.resultat is not None and trace.statut == "ok":
        st.markdown(f"**Résultat · {len(trace.resultat.lignes)} ligne(s)**")
        if trace.resultat.lignes:
            st.dataframe(
                [dict(zip(trace.resultat.colonnes, ligne))
                 for ligne in trace.resultat.lignes],
                width="stretch", hide_index=True)
        if trace.resultat.tronque:
            st.warning(f"Résultat **tronqué** à {LIMITE} lignes. Une troncature "
                       "muette serait un résultat faux : elle est signalée.", icon="✂️")


def enveloppe_du_tool(trace: Trace) -> None:
    """Ce qu'un vrai client MCP recevrait, et rien de plus."""
    statut, payload, message = trace.enveloppe()
    st.markdown("**Ce qu'un client MCP reçoit, lui**")
    st.caption(
        "La page voit tout ce qui précède parce qu'elle appelle le service en "
        "direct. Un client MCP ne reçoit que cette enveloppe : ni le prompt, ni "
        "le schéma, ni la sortie brute du modèle."
    )
    st.json({"status": statut, "payload": payload, "message": message}, expanded=True)


def rendre_trace(trace: Trace) -> None:
    entete = f"{PASTILLE.get(trace.statut, '⚪')} `status = {trace.statut}`"
    if trace.code:
        entete += f" · `code = {trace.code}`"
    entete += f" · {trace.duree:.1f} s"
    st.markdown(entete)
    if trace.message:
        st.info(trace.message)
    pile(trace)
    sql_et_resultat(trace)
    with st.expander("Les éléments techniques que le tool ne montre pas", expanded=True):
        detail_technique(trace)
    with st.expander("L'enveloppe du contrat d'intégration"):
        enveloppe_du_tool(trace)


# ------------------------------------------------------------ barre latérale
st.sidebar.title("Périmètre par profil")
schema_complet = introspecter()
total_colonnes = sum(len(t.colonnes) for t in schema_complet.values())
for profil in ("support", "commercial"):
    d = droits(profil)
    svc = ServiceSql(d)
    colonnes = sum(len(t.colonnes) for t in svc.schema.values())
    st.sidebar.markdown(f"**`{profil}`**")
    st.sidebar.caption(
        f"{len(svc.schema)} tables sur {len(schema_complet)}, "
        f"{colonnes} colonnes sur {total_colonnes}"
    )
    retirees = sorted(d.colonnes_interdites)
    if retirees:
        st.sidebar.caption("retirées : " + ", ".join(f"`{c}`" for c in retirees))
    else:
        st.sidebar.caption("aucune colonne retirée")
st.sidebar.divider()
st.sidebar.caption(f"Base : `{CONFIG.base_sql.name}` · plafond `LIMIT {LIMITE}` · "
                   "délai d'exécution 5 s")
st.sidebar.caption("Démonstration du chantier 2. Elle appelle `ServiceSql` en "
                   "direct : le serveur MCP est le chantier 3.")

st.title("Text-to-SQL gouverné")
st.caption("Une question en langage naturel, six couches de gardes, et la "
           "requête toujours renvoyée avec le résultat.")
bandeau_modele()

onglets = st.tabs([
    "Une question, la pile entière",
    "Deux profils (E5)",
    "Défense en profondeur",
    "Les tools figés",
    "Le jeu d'évaluation",
])

# ------------------------------------------- onglet 1 : la pile entière
with onglets[0]:
    exemples = [
        "combien de commandes en avril ?",
        "quelles références sont sous leur seuil de réapprovisionnement à LYON ?",
        "supprime les commandes de test",
        "quelle est la météo à Lille demain ?",
        "quel est le meilleur client ?",
    ]
    profil = st.radio("Profil du serveur", ("commercial", "support"),
                      horizontal=True, key="p1",
                      help="Ce n'est pas un réglage d'affichage : chaque profil "
                           "est un service instancié séparément, comme le "
                           "serveur l'est à son lancement.")
    choix = st.selectbox("Exemples", exemples, key="ex1")
    question = st.text_input("Question", choix, key="q1")
    if st.button("Jouer", type="primary", key="b1"):
        with st.spinner("Traitement..."):
            rendre_trace(service(profil).tracer(question))

# ------------------------------------------- onglet 2 : deux profils
with onglets[1]:
    st.markdown(
        "La **même question**, adressée à deux services instanciés sur deux "
        "profils. C'est l'écran qui démontre E5 : les colonnes sensibles ne "
        "sortent jamais pour le `support`, quelle que soit la formulation."
    )
    exemples_2 = [
        "quelle est la marge sur la REF-8842 ?",
        "quel est le prix d'achat du projecteur LED 100 W ?",
        "combien de commandes en avril ?",
        "donne-moi les adresses mail des clients de Lille",
    ]
    choix_2 = st.selectbox("Exemples", exemples_2, key="ex2")
    question_2 = st.text_input("Question", choix_2, key="q2")
    if st.button("Jouer sur les deux profils", type="primary", key="b2"):
        with st.spinner("Traitement..."):
            traces = {p: service(p).tracer(question_2)
                      for p in ("support", "commercial")}
        for colonne, profil_2 in zip(st.columns(2), ("support", "commercial")):
            with colonne:
                st.markdown(f"### profil `{profil_2}`")
                rendre_trace(traces[profil_2])

# ------------------------------------------- onglet 3 : defense en profondeur
with onglets[2]:
    st.markdown(
        "Le pré-filtre lexical de la couche 0 bis refuse en **moins d'une "
        "milliseconde**, avant toute génération. C'est excellent pour E5, et "
        "c'est un problème pour une démonstration : on ne voit jamais les "
        "couches suivantes travailler."
    )
    st.info(
        "**Ce contournement est une capacité de cette page, jamais du serveur.** "
        "Un interrupteur qui désactive une garde, exposé côté serveur ou passé "
        "dans un appel de tool, serait le défaut que ce dossier a corrigé sur "
        "`profil` : n'importe quel appelant s'en servirait. Ici c'est un "
        "argument d'un appel direct à `ServiceSql.tracer()`, absent de toute "
        "signature de tool. La page peut le faire parce qu'elle **n'est pas** "
        "un client MCP.", icon="🔒")

    with st.expander("Le lexique de refus, tel qu'il est déclaré dans la matrice"):
        st.caption(
            "Il n'a **aucune valeur de sécurité** : une liste de mots se "
            "contourne par une paraphrase. Il rend le refus explicite et "
            "imputable, donc journalisable et démontrable. La sécurité, elle, "
            "reste portée par les couches qui raisonnent sur l'AST."
        )
        st.json(lexique_refus(), expanded=True)

    st.markdown(
        "**Ce que l'expérience montre réellement, mesuré le 2026-09-03.** "
        "J'attendais que la couche 3 attrape la même demande sur l'arbre "
        "syntaxique. Elle ne le fait pas, et pour une bonne raison : la couche 0 "
        "a retiré la colonne du schéma, donc **le modèle ne peut pas la nommer**. "
        "Trois issues sont possibles quand le pré-filtre est désactivé, et la "
        "troisième est la plus instructive."
    )
    st.dataframe([
        {"issue": "le modèle se récuse",
         "statut": "refused · OUT_OF_SCHEMA",
         "ce que cela dit": "la couche 0 a suffi, le modèle dit qu'il ne peut pas répondre"},
        {"issue": "le modèle invente le nom de la colonne retirée",
         "statut": "refused · FORBIDDEN_COLUMN",
         "ce que cela dit": "la couche 3 le rattrape sur l'AST, voir le banc d'essai ci-dessous"},
        {"issue": "le modèle SUBSTITUE une colonne visible",
         "statut": "ok",
         "ce que cela dit": "rien ne fuit, mais la réponse porte sur autre chose que la question"},
    ], width="stretch", hide_index=True)
    st.warning(
        "**La troisième issue est le vrai motif du pré-filtre.** Mesuré : "
        "« classement des produits par marge », pré-filtre désactivé, produit "
        "`SELECT nom FROM produits ORDER BY prix_vente_ht DESC` et un statut "
        "`ok`. E5 tient, aucune donnée sensible ne sort. Mais l'utilisateur "
        "reçoit un classement par **prix** en croyant lire un classement par "
        "**marge**, et rien ne le lui signale. Le pré-filtre ne sert donc pas "
        "qu'à l'imputabilité : il évite une réponse silencieusement hors sujet.",
        icon="⚠️")

    exemples_3 = [
        "classement des produits par marge",
        "quelle est la marge sur la REF-8842 ?",
        "quel est le prix d'achat du projecteur LED 100 W ?",
    ]
    choix_3 = st.selectbox("Exemples", exemples_3, key="ex3")
    question_3 = st.text_input("Question", choix_3, key="q3")
    st.caption("Profil `support` : la question nomme une ressource retirée.")
    if st.button("Jouer les deux fois", type="primary", key="b3"):
        with st.spinner("Traitement..."):
            avec = service("support").tracer(question_3)
            sans = service("support").tracer(question_3, prefiltre=False)
        g, d = st.columns(2)
        with g:
            st.markdown("### Pré-filtre **actif**")
            st.caption("Le fonctionnement normal du serveur.")
            rendre_trace(avec)
        with d:
            st.markdown("### Pré-filtre **désactivé**")
            st.caption("Ce que la question devient sans lui.")
            rendre_trace(sans)
        if sans.statut == "ok":
            st.error(
                f"Sans le pré-filtre, la question reçoit un `ok` en "
                f"{sans.duree:.1f} s. Regardez le SQL : il ne touche aucune "
                "colonne interdite, donc aucune garde n'avait de raison de le "
                "refuser. La réponse est néanmoins hors sujet.", icon="⚠️")
        else:
            st.success(
                f"Les deux issues sont un refus : {avec.duree * 1000:.1f} ms "
                f"avec le pré-filtre, {sans.duree:.1f} s sans. La différence de "
                f"coût est ce que le pré-filtre économise, et `{sans.code}` "
                "nomme l'étage qui a tranché à sa place.", icon="🛡️")

    st.divider()
    st.markdown("**Banc d'essai de la couche 3, sans modèle**")
    st.caption(
        "Le modèle ne peut pas nommer une colonne retirée, donc il est difficile "
        "de lui faire produire le SQL que la couche 3 refuserait. On le soumet "
        "donc directement : c'est le garde qu'on éprouve ici, pas la génération. "
        "Chaque requête ci-dessous ne **projette** aucune colonne sensible."
    )
    attaques = {
        "tri sur une colonne retirée":
            "SELECT ref, nom FROM produits ORDER BY marge_pct DESC",
        "agrégat filtré sur une colonne retirée":
            "SELECT categorie FROM produits GROUP BY categorie HAVING AVG(marge_pct) > 45",
        "dichotomie sur un prédicat":
            "SELECT ref FROM produits WHERE ref = 'REF-8842' AND marge_pct >= 47.3",
        "colonne retirée derrière un alias de résultat":
            "SELECT ref, marge_pct AS m FROM produits ORDER BY m DESC",
        "colonne retirée dans une sous-requête":
            "SELECT ref FROM produits WHERE ref IN (SELECT ref FROM produits WHERE marge_pct > 40)",
        "exfiltration par base attachée":
            "ATTACH DATABASE 'exfil.db' AS atk",
    }
    from sql.gardes import valider as _valider  # noqa: PLC0415

    svc_sup = service("support")
    st.dataframe([
        {
            "attaque": nom,
            "SQL soumis": sql,
            "issue": (lambda v: "🛑 " + v.code if not v.ok else "❌ PASSE")(
                _valider(sql, svc_sup.droits, svc_sup.schema)),
        }
        for nom, sql in attaques.items()
    ], width="stretch", hide_index=True)
    st.caption(
        "La dichotomie est celle qui compte : en quelques appels de ce genre, "
        "la marge exacte de `REF-8842` se reconstitue seuil par seuil, sans que "
        "la colonne apparaisse une seule fois dans un résultat. C'est pourquoi "
        "le périmètre porte sur **toute occurrence** d'une colonne et non sur "
        "les seules projections."
    )

# ------------------------------------------- onglet 4 : les tools figes
with onglets[3]:
    st.markdown(
        "`check_stock` et `order_status` sont des **requêtes paramétrées**, "
        "jamais générées. Ils ne passent par aucune analyse syntaxique, "
        "puisqu'il n'y a rien à analyser : leur garantie E5 tient à leur "
        "requête, écrite une fois et relue. Ils fonctionnent **sans modèle**."
    )
    g, d = st.columns(2)
    with g:
        ref = st.text_input("check_stock · référence", "REF-8842", key="cs")
        if st.button("Appeler check_stock", key="b4a"):
            statut, payload, message = service("support").check_stock(ref)
            st.markdown(f"{PASTILLE.get(statut, '⚪')} `status = {statut}`")
            if message:
                st.info(message)
            st.json({"status": statut, "payload": payload, "message": message})
    with d:
        cmd = st.text_input("order_status · identifiant", "CMD-2026-0042", key="os")
        st.caption("`CMD-2026-0042` est bien formé mais absent : la numérotation "
                   "des commandes comporte des trous. `CMD-42` est mal formé. "
                   "Les deux se répondent différemment.")
        if st.button("Appeler order_status", key="b4b"):
            statut, payload, message = service("support").order_status(cmd)
            st.markdown(f"{PASTILLE.get(statut, '⚪')} `status = {statut}`")
            if message:
                st.info(message)
            st.json({"status": statut, "payload": payload, "message": message})

# ------------------------------------------- onglet 5 : le jeu d'evaluation
with onglets[4]:
    st.markdown(
        "Les 24 questions de `eval/questions_sql.jsonl`, avec l'attendu de "
        "`eval/attendus_sql.jsonl`. Mesure du 2026-09-02 avec le modèle retenu : "
        "**17 statuts justes sur 24**, dont **8 sur 8 sur les questions de "
        "sécurité**. Les huit échecs sont des échecs de qualité de génération, "
        "jamais de gouvernance."
    )
    st.dataframe(jeu_eval(), width="stretch", hide_index=True)
    st.divider()
    st.markdown("**Rejouer une question du jeu**")
    jeu = jeu_eval()
    etiquettes = [f"{q['id']} · [{q['type']}] {q['question'][:56]}" for q in jeu]
    choisie = st.selectbox("Question", etiquettes, key="ex5")
    q = jeu[etiquettes.index(choisie)]
    st.caption(f"Profil imposé par le jeu : `{q['profil']}` · "
               f"attendu : `{q.get('attendu_status', '?')}`"
               + (f" · code `{q['attendu_code']}`" if q.get("attendu_code") else ""))
    if q.get("attendu_sql_reference"):
        st.caption("SQL de référence de l'oracle :")
        st.code(q["attendu_sql_reference"], language="sql")
    if st.button("Rejouer cette question", type="primary", key="b5"):
        debut = time.time()
        with st.spinner("Traitement..."):
            trace = service(q["profil"]).tracer(q["question"])
        attendu = q.get("attendu_status", "")
        correspond = {"out_of_schema": "refused", "clarify": "clarification",
                      "not_found": "ok"}.get(attendu, attendu)
        if trace.statut == correspond:
            st.success(f"Statut conforme à l'oracle : `{trace.statut}` "
                       f"en {time.time() - debut:.1f} s", icon="✅")
        else:
            st.error(f"Attendu `{correspond}`, obtenu `{trace.statut}`", icon="❌")
        rendre_trace(trace)

"""Rendu d'une réponse de la gateway dans un message Slack. C'est l'item A2.

POURQUOI CET ITEM EXISTE SEPAREMENT
Le chantier 7 l'avait laissé ouvert en une phrase qui dit tout : « E1 exige des
sources citées ; un message Slack mal conçu peut les rendre illisibles. » Un
mur de texte où titre, référence et date se noient ne satisfait pas E1 dans son
intention, même s'il contient formellement les trois champs.

TROIS REGLES, ET AUCUNE N'EST DECORATIVE

1. **Les sources sont une liste, pas une phrase.** Titre en gras, référence en
   code, date en clair. Un agent du SAV doit pouvoir dire au client « c'est
   dans la fiche REF-8842 du 12 mars » sans relire trois fois.

2. **Un refus s'affiche comme un refus**, avec son code. Slack rend le texte
   sur fond ordinaire : sans marque explicite, un refus de colonne sensible
   ressemble à une réponse. C'est exactement ce que D40 interdisait pour
   l'interface, et cela vaut ici.

3. **Le SQL n'est pas affiché par défaut.** E3 oblige la gateway à le
   *renvoyer*, ce qu'elle fait, journal compris ; l'afficher est un choix de
   restitution. Un agent du SAV ne lit pas de SQL. Il apparaît donc sur un
   refus, où il est la seule chose qui rende la décision auditable.

Le format est celui des **Block Kit** de Slack, une liste de blocs JSON. On
n'emploie que `section`, `context` et `divider`, disponibles partout et rendus
correctement sur mobile.
"""
from __future__ import annotations

#: Ce qu'un statut hors `ok` signifie, pour quelqu'un qui n'a pas lu le contrat
#: d'intégration de la DSI.
LECTURE = {
    "refused": ":no_entry: *Demande refusée*",
    "clarification": ":question: *Précision nécessaire*",
    "hors_corpus": ":grey_question: *Hors documentation*",
    "error": ":warning: *Panne technique*",
}

#: Slack tronque les blocs de texte au-delà de 3000 caractères, en silence. On
#: coupe donc nous-mêmes, en le disant.
MAX_TEXTE = 2800


def _texte(contenu: str) -> dict:
    if len(contenu) > MAX_TEXTE:
        contenu = contenu[:MAX_TEXTE] + "\n_… réponse tronquée._"
    return {"type": "section", "text": {"type": "mrkdwn", "text": contenu}}


def _contexte(contenu: str) -> dict:
    return {"type": "context",
            "elements": [{"type": "mrkdwn", "text": contenu}]}


def sources_en_blocs(sources: list[dict]) -> list[dict]:
    """Les sources, en liste lisible. Titre, référence, date : E1 mot pour mot."""
    if not sources:
        return []
    lignes = []
    for s in sources:
        titre = s.get("titre") or "sans titre"
        reference = s.get("reference") or "?"
        date = s.get("date") or "date inconnue"
        lignes.append(f"• *{titre}* — `{reference}` — {date}")
    return [{"type": "divider"},
            _texte("*Sources*\n" + "\n".join(lignes))]


def repondre(question: str, enveloppe: dict, tool: str = "",
             demandeur: str = "") -> list[dict]:
    """L'enveloppe de la gateway, rendue en blocs Slack.

    `demandeur` est l'identifiant Slack de la personne, uniquement pour la
    mention d'accusé. Il n'entre dans **aucune** décision d'autorisation : la
    gateway ne le voit jamais (D28, D34).
    """
    statut = enveloppe.get("status", "error")
    payload = enveloppe.get("payload") or {}
    message = enveloppe.get("message") or ""

    blocs: list[dict] = [_contexte(f"> {question}")]

    if statut == "ok":
        corps = payload.get("answer") or _resumer_lignes(payload) or "Réponse reçue."
        blocs.append(_texte(corps))
        blocs += sources_en_blocs(payload.get("sources") or [])
    else:
        entete = LECTURE.get(statut, "*Réponse indisponible*")
        blocs.append(_texte(f"{entete}\n{message}"))
        # Regle 3 : le SQL apparait sur un refus, car c'est la qu'il rend la
        # decision auditable. Un refus sans sa requete ne s'explique pas.
        if payload.get("sql"):
            blocs.append(_texte("*Requête refusée*\n```" + payload["sql"] + "```"))

    pied = []
    if tool:
        pied.append(f"`{tool}`")
    if payload.get("code"):
        pied.append(f"code `{payload['code']}`")
    if pied:
        blocs.append(_contexte(" · ".join(pied)))
    return blocs


def _resumer_lignes(payload: dict) -> str:
    """Un résumé par GABARIT, jamais par reformulation.

    Même règle que la conversation web : reformuler une donnée juste ouvrirait
    une occasion d'inventer là où il n'y en avait aucune.
    """
    if "rows" not in payload:
        return ""
    lignes = payload.get("rows") or []
    colonnes = payload.get("columns") or []
    if payload.get("trouve") is False:
        return "Aucune donnée pour cet identifiant."
    if not lignes:
        return "Aucun résultat."
    if len(lignes) == 1 and len(colonnes) == 1:
        return f"*{lignes[0][0]}*"
    entete = " | ".join(str(c) for c in colonnes)
    corps = "\n".join(" | ".join(str(v) for v in ligne) for ligne in lignes[:15])
    reste = "" if len(lignes) <= 15 else f"\n_… {len(lignes) - 15} ligne(s) de plus._"
    return f"```{entete}\n{corps}```{reste}"


def accuse(question: str) -> list[dict]:
    """L'accusé de réception, publié SOUS LES TROIS SECONDES de Slack.

    Ce n'est pas une politesse : Slack coupe la connexion au-delà de son budget,
    et notre chaîne (recherche hybride, reranking, génération SQL) le dépasse
    largement. Le message est donc envoyé en deux temps, et l'utilisateur doit
    savoir qu'on cherche (D34).
    """
    return [_contexte(f"> {question}"),
            _texte(":hourglass_flowing_sand: Je cherche, la réponse arrive.")]

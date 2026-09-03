"""Le catalogue des huit tools : nom, description, schéma d'entrée.

**Tous les paramètres sont facultatifs, et c'est délibéré.** Le contrôle du droit
d'appeler doit s'exécuter AVANT toute validation d'argument : un client sans
droit sur un tool doit recevoir un refus de matrice, pas une erreur de schéma.
La suite d'acceptance le vérifie en appelant chaque tool interdit avec un objet
d'arguments **vide**. Un paramètre obligatoire ferait échouer la requête au
niveau du protocole, et le refus attendu n'aurait jamais lieu.

L'argument manquant est ensuite traité par le tool lui-même, qui répond
`refused` avec un message explicite. Le refus reste donc net, il arrive
simplement au bon endroit.

**Aucun tool ne prend le profil en paramètre** (D28). Un paramètre est rempli par
l'appelant : le bot support n'aurait qu'à se déclarer `commercial`.
"""
from __future__ import annotations

from dataclasses import dataclass, field


def _texte(description: str) -> dict:
    return {"type": "string", "description": description}


@dataclass(frozen=True)
class Outil:
    nom: str
    resume: str            # première ligne, celle que le client affiche
    description: str
    proprietes: dict = field(default_factory=dict)

    def schema(self) -> dict:
        # `required` reste VIDE : voir l'en-tête du module.
        return {"type": "object", "properties": self.proprietes, "required": []}


CATALOGUE: tuple[Outil, ...] = (
    Outil(
        "answer_question",
        "Répond à une question documentaire, sources citées, ou s'abstient.",
        "Recherche hybride sur le corpus autorisé au profil, puis réponse ancrée "
        "sur les passages retenus. Toute réponse cite ses sources (titre, "
        "référence, date). Si le corpus ne couvre pas la question, le statut est "
        "`hors_corpus` et aucune réponse n'est produite : l'outil n'invente jamais.",
        {"question": _texte("La question, en langage naturel.")},
    ),
    Outil(
        "search_docs",
        "Cherche des passages dans le corpus, sans rien rédiger.",
        "Brique de recherche : rend des passages classés avec leur score et leurs "
        "métadonnées, sans génération. Une référence exacte comme `REF-8842` "
        "passe par un filtre déterministe et remonte en tête. Utiliser "
        "`answer_question` pour obtenir une réponse rédigée et sourcée.",
        {"query": _texte("Les termes cherchés, ou une référence `REF-XXXX`."),
         "k": {"type": "integer", "description": "Nombre de passages, 5 par défaut."}},
    ),
    Outil(
        "get_document",
        "Rend un document complet, par son identifiant.",
        "Prend un `doc_id` tel que `search_docs` le renvoie. Un identifiant hors "
        "du périmètre du profil est indistinguable d'un identifiant inexistant : "
        "on ne renseigne pas un appelant sur ce qu'il n'a pas le droit de voir.",
        {"doc_id": _texte("Identifiant rendu par `search_docs`.")},
    ),
    Outil(
        "list_sources",
        "Inventaire du corpus accessible au profil.",
        "Rend un enregistrement par document : identifiant, titre, référence, "
        "version, date, type. Un `doc_type` hors périmètre est refusé "
        "explicitement, et non filtré en silence.",
        {"doc_type": _texte("Filtre facultatif : fiche_technique, notice, "
                            "procedure_sav ou note_interne.")},
    ),
    Outil(
        "ask_database",
        "Répond à une question métier en SQL lecture seule, requête renvoyée.",
        "Traduit la question en une requête SQL, la fait passer par la pile de "
        "gardes, l'exécute en lecture seule et renvoie **toujours** la requête "
        "avec le résultat. Toute écriture est refusée. Les colonnes hors "
        "périmètre du profil sont refusées, y compris dans un tri ou un filtre. "
        "Une question hors schéma reçoit un refus, jamais une requête inventée.",
        {"question": _texte("La question métier, en langage naturel.")},
    ),
    Outil(
        "get_schema",
        "Rend le schéma des tables accessibles au profil. Aucune donnée.",
        "Schéma commenté, borné au périmètre du profil, avec les valeurs "
        "d'énumération réelles et les chemins de jointure. Aide à formuler une "
        "question pour `ask_database`. Ne renvoie aucune ligne de la base.",
        {},
    ),
    Outil(
        "check_stock",
        "Stock d'une référence, par entrepôt. Requête figée.",
        "Requête paramétrée, jamais générée : le résultat est déterministe. Une "
        "référence mal formée est refusée ; une référence bien formée mais "
        "inconnue rend un résultat vide que le message explicite.",
        {"reference": _texte("Référence produit, format `REF-NNNN`.")},
    ),
    Outil(
        "order_status",
        "Statut d'une commande. Requête figée.",
        "Requête paramétrée, jamais générée. Un identifiant mal formé est "
        "refusé ; un identifiant bien formé mais absent rend un résultat vide "
        "que le message explicite. La numérotation des commandes comporte des "
        "trous, les deux cas se distinguent.",
        {"order_id": _texte("Identifiant de commande, format `CMD-AAAA-NNNN`.")},
    ),
)

PAR_NOM = {o.nom: o for o in CATALOGUE}

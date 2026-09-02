"""Les quatre tools documentaires, indépendamment de MCP.

Ce module ne connaît ni le protocole ni l'enveloppe : il rend des dictionnaires.
Le serveur les emballe. Cette séparation rend la logique testable sans lancer un
processus, et elle évite que le contrat de transport contamine la recherche.

**La réponse est EXTRACTIVE, sans modèle de génération.** C'est un choix, et il
faut l'assumer : E1 exige que l'outil « ne invente jamais ». Une réponse composée
par un modèle demande de faire confiance à une consigne d'ancrage ; une réponse
extraite des passages retenus ne peut pas inventer **par construction**. Sur une
gateway gouvernée, cette garantie vaut mieux qu'une prose plus fluide. Une couche
générative pourrait s'ajouter au-dessus, sans rien changer aux sources ni au
mécanisme d'abstention.
"""
from __future__ import annotations

from common.matrice import Droits

from .depot import Depot, Passage
from .recherche import Chercheur, Config, Resultat

#: Seuils d'abstention, calibrés le 2026-09-02 sur `eval/questions_rag.jsonl`,
#: en traitant RAG-19 comme hors corpus, ce que l'annotation impose.
#:
#: **Il y a DEUX seuils parce qu'il y a deux échelles.** La branche dense score
#: en cosinus, dans [0, 1] ; la branche avancée score avec les logits du
#: cross-encoder, non bornés. Un seul seuil pour les deux ne voudrait rien dire.
#:
#: | branche | plafond hors corpus | plancher couvertes notables | marge |
#: | --- | ---: | ---: | ---: |
#: | dense | 0,8519 | 0,8534 | **0,0015** |
#: | avancée, reranker | -2,39 | -0,98 | **1,41** |
#:
#: Le reranker sépare presque mille fois mieux. C'est son apport RÉEL, et il
#: n'apparaît pas dans le Recall@k : sur le classement, l'hybride plafonnait
#: déjà. Sur la DÉCISION D'ABSTENTION, il change tout.
#:
#: Prix assumé du seuil avancé : deux questions `couverte` sur treize reçoivent
#: une abstention à tort, RAG-13 et RAG-16. Ce sont précisément les deux dont la
#: réponse est une constante du corpus, dupliquée à l'identique dans 80
#: documents. Abaisser le seuil pour les récupérer ferait répondre deux
#: questions hors corpus : sacrifier E1 pour gagner du rappel est exactement ce
#: que le protocole de mesure interdit.
SEUIL_DENSE = 0.853
SEUIL_AVANCE = -1.7


def seuil_pour(config: Config) -> float:
    """Le seuil qui correspond à l'échelle de scores de cette configuration."""
    return SEUIL_AVANCE if config.rerank else SEUIL_DENSE


def source(p: Passage) -> dict:
    """Le triplet qu'E1 exige de toute réponse documentaire."""
    m = p.metadonnees
    return {
        "titre": str(m.get("titre", "")),
        "reference": str(m.get("reference", "")),
        "date": str(m.get("date", "")),
    }


def _sources_dedoublonnees(passages: list[Passage]) -> list[dict]:
    """Un document cité une seule fois, même s'il fournit plusieurs passages."""
    vues: dict[str, dict] = {}
    for p in passages:
        vues.setdefault(p.doc_id, source(p))
    return list(vues.values())


def composer(passages: list[Passage]) -> str:
    """La réponse : les passages retenus, dans l'ordre, chacun attribué.

    Chaque bloc porte le document dont il vient. Un lecteur peut donc vérifier
    l'attribution passage par passage, et pas seulement en bas de réponse.
    """
    blocs = []
    for p in passages:
        m = p.metadonnees
        section = str(m.get("section") or "").strip()
        # Le texte indexé est `en-tête [+ titre de section] + corps`. On retire
        # exactement ce qu'on a ajouté à l'ingestion, sinon la section
        # s'afficherait deux fois : une fois venue du chunk, une fois d'ici.
        corps = p.texte.split("\n", 2 if section else 1)[-1].strip()
        tete = f"{m.get('titre')} ({m.get('reference')}, v{m.get('version')}, {m.get('date')})"
        blocs.append(f"{tete}\n{section + chr(10) if section else ''}{corps}")
    return "\n\n".join(blocs)


class ServiceRag:
    """Les quatre tools. Une instance par processus, modèles paresseux."""

    def __init__(self, droits: Droits, config: Config, seuil: float | None = None,
                 depot: Depot | None = None) -> None:
        self.droits = droits
        self.depot = depot or Depot()
        self.chercheur = Chercheur(self.depot)
        # Le seuil vit dans la config de recherche : c'est un étage de
        # l'entonnoir, pas un réglage d'affichage. Il est choisi selon l'échelle
        # de scores de la configuration, jamais fixé une fois pour toutes.
        self.config = Config(**{**config.__dict__,
                                "seuil": seuil if seuil is not None else seuil_pour(config)})

    @property
    def doc_types(self) -> set[str]:
        return set(self.droits.doc_types)

    # --- answer_question : le tool de haut niveau (E1) ----------------------

    def answer_question(self, question: str) -> tuple[str, dict, str]:
        """Rend (status, payload, message). L'abstention est un statut, pas une
        réponse vide : un client ne doit jamais pouvoir la confondre."""
        if not question or not question.strip():
            return "refused", {}, "La question est vide."

        r: Resultat = self.chercheur.chercher(question, self.doc_types, self.config)
        if r.abstention or not r.passages:
            return ("hors_corpus", {},
                    "Cette question n'est pas couverte par la documentation Sorabel "
                    "accessible a ce profil. Aucune reponse n'est inventee.")

        # Règle dure de D7 : pas de sources, pas de réponse. Si le dédoublonnage
        # ne laissait rien, on s'abstient plutôt que de rendre une prose nue.
        sources = _sources_dedoublonnees(r.passages)
        if not sources:
            return "hors_corpus", {}, "Aucune source citable pour cette question."

        return "ok", {"answer": composer(r.passages), "sources": sources}, ""

    # --- Les trois briques --------------------------------------------------

    def search_docs(self, query: str, k: int | None = None) -> tuple[str, dict, str]:
        """Passages classés, aucune génération. Le seuil ne s'applique PAS ici :
        une brique de recherche rend ce qu'elle trouve, et c'est l'appelant qui
        décide. C'est answer_question qui porte la garantie d'abstention."""
        if not query or not query.strip():
            return "refused", {}, "La requete est vide."

        config = Config(**{**self.config.__dict__, "seuil": None,
                           "k": k or self.config.k})
        r = self.chercheur.chercher(query, self.doc_types, config)
        hits = [
            {
                "doc_id": p.doc_id,
                "score": round(float(p.score), 4),
                "text": p.texte,
                "metadata": {
                    "reference": str(p.metadonnees.get("reference", "")),
                    "doc_type": str(p.metadonnees.get("doc_type", "")),
                    "version": str(p.metadonnees.get("version", "")),
                    "date": str(p.metadonnees.get("date", "")),
                    "titre": str(p.metadonnees.get("titre", "")),
                    "section": str(p.metadonnees.get("section", "")),
                },
            }
            for p in r.passages
        ]
        if not hits:
            return "hors_corpus", {"hits": []}, "Aucun passage ne correspond a cette requete."
        return "ok", {"hits": hits, "voie": r.voie}, ""

    def get_document(self, doc_id: str) -> tuple[str, dict, str]:
        """Un document complet. Un identifiant hors périmètre est indistinguable
        d'un identifiant inexistant, et c'est voulu : on ne renseigne pas un
        appelant sur l'existence de ce qu'il n'a pas le droit de voir."""
        if not doc_id or not doc_id.strip():
            return "refused", {}, "Le doc_id est vide."
        trouve = self.depot.document(doc_id.strip(), self.doc_types)
        if trouve is None:
            return ("hors_corpus", {},
                    f"Aucun document {doc_id!r} dans le perimetre de ce profil.")
        texte, meta = trouve
        return "ok", {"text": texte, "metadata": meta}, ""

    def list_sources(self, doc_type: str | None = None) -> tuple[str, dict, str]:
        """Inventaire du corpus autorisé. Un `doc_type` hors périmètre est refusé
        explicitement, et non filtré en silence : le client doit savoir que sa
        demande a été rejetée, pas croire que la collection est vide."""
        vises = self.doc_types
        if doc_type:
            if doc_type not in vises:
                return ("refused", {},
                        f"La collection {doc_type!r} n'est pas accessible a ce profil.")
            vises = {doc_type}
        return "ok", {"sources": self.depot.documents(vises)}, ""

"""L'entonnoir de recherche, et les quatre configurations de l'ablation E6.

Les étages, dans l'ordre :

1. **Filtre de profil** (E4), avant toute recherche, sur les deux branches.
2. **Court-circuit sur référence exacte** (E2), un filtre par métadonnée.
3. **Les deux moteurs en parallèle**, lexical et dense.
4. **Fusion RRF**, sur les rangs et non sur les scores.
5. **Reranking** par cross-encoder.
6. **Arbitrage de version** : un chunk par groupe, la version courante.
7. **Seuil d'abstention** (E1).

Les drapeaux de `Config` donnent les quatre configurations que le protocole E6
demande de mesurer. Ce n'est pas de la souplesse gratuite : sans elles, le gain
global reste un chiffre qu'on ne peut imputer à aucune brique.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from common.embeddings import Encodeur

from .depot import Depot, Passage

#: Motif d'une référence produit. Tiret obligatoire, casse indifférente.
MOTIF_REF = re.compile(r"REF-\d{4}", re.IGNORECASE)

#: Ordre de préférence quand une référence porte plusieurs types de document et
#: que la question n'en nomme aucun. Une question qui dit « fiche » ou « notice »
#: prime sur cet ordre.
PREFERENCE_TYPE = ("fiche_technique", "notice", "procedure_sav", "note_interne")

#: Mots par lesquels une question désigne explicitement un type de document.
INDICES_TYPE = {
    "fiche_technique": ("fiche", "fiche technique", "caracteristique", "caractéristique"),
    "notice": ("notice", "installation", "installer", "montage"),
    "procedure_sav": ("procedure", "procédure", "sav", "garantie", "retour", "echange", "échange"),
    "note_interne": ("note interne", "note", "compte rendu"),
}

#: Constante de la fusion RRF. 60 est la valeur d'usage : elle amortit les
#: premiers rangs sans écraser la queue de liste.
K_RRF = 60


@dataclass(frozen=True)
class Config:
    """Une configuration de recherche. `A` est la baseline, `D` le système complet."""

    lexical: bool = True
    court_circuit: bool = True
    rerank: bool = True
    n: int = 50      # profondeur de chaque moteur
    m: int = 20      # candidats soumis au reranking
    k: int = 5       # passages retenus
    seuil: float | None = None   # None = pas d'abstention, pour la mesure brute


#: Les quatre configurations de l'ablation. Voir docs/mesure_e6.md.
CONFIGS = {
    "A": Config(lexical=False, court_circuit=False, rerank=False),
    "B": Config(lexical=True, court_circuit=False, rerank=False),
    "C": Config(lexical=True, court_circuit=False, rerank=True),
    "D": Config(lexical=True, court_circuit=True, rerank=True),
}


@dataclass
class Resultat:
    """Ce que rend l'entonnoir, avec de quoi expliquer ce qui s'est passé."""

    passages: list[Passage] = field(default_factory=list)
    voie: str = "hybride"        # "reference" si le court-circuit a joué
    score_max: float = 0.0
    abstention: bool = False


def type_demande(question: str) -> str | None:
    """Le type de document que la question nomme, s'il y en a un."""
    q = question.lower()
    for doc_type, indices in INDICES_TYPE.items():
        if any(indice in q for indice in indices):
            return doc_type
    return None


def fusion_rrf(*listes: list[Passage]) -> list[Passage]:
    """Fusionne des listes classées par leurs RANGS, pas par leurs scores.

    Le problème que cela résout : un score BM25 de 12,4 et un cosinus de 0,81 ne
    se somment pas. RRF ignore les valeurs et ne regarde que la position. Un
    chunk 3e partout bat un chunk 1er ici et 40e ailleurs.

    Un chunk absent d'une liste n'y marque rien : c'est le terme nul, et non un
    rang de pénalité arbitraire.
    """
    cumul: dict[str, float] = {}
    vus: dict[str, Passage] = {}
    for liste in listes:
        for rang, p in enumerate(liste, start=1):
            cumul[p.chunk_id] = cumul.get(p.chunk_id, 0.0) + 1.0 / (K_RRF + rang)
            vus.setdefault(p.chunk_id, p)
    ordonnes = sorted(cumul.items(), key=lambda kv: kv[1], reverse=True)
    return [
        Passage(chunk_id=i, texte=vus[i].texte, score=s, metadonnees=vus[i].metadonnees)
        for i, s in ordonnes
    ]


def arbitrer_versions(passages: list[Passage]) -> list[Passage]:
    """Un seul passage par groupe de versions : la version courante.

    Sans cet étage, le cross-encoder, qui ignore les dates, peut classer une
    v1.0 devant une v2.1. La réponse citerait alors honnêtement, format E1
    respecté, un document périmé. C'est exactement ce que le brief reproche à
    l'existant. Mesuré sur l'index réel : « quel disjoncteur pour du triphasé ? »
    rendait REF-1024 deux fois dans les trois premiers résultats.
    """
    garde: dict[str, Passage] = {}
    for p in passages:
        courant = garde.get(p.version_group)
        if courant is None:
            garde[p.version_group] = p
            continue
        # À groupe égal, la version courante gagne. À défaut, le meilleur rang,
        # c'est-à-dire le premier rencontré, la liste étant déjà classée.
        if p.metadonnees.get("is_latest") and not courant.metadonnees.get("is_latest"):
            garde[p.version_group] = p
    return [p for p in passages if garde.get(p.version_group) is p]


class Chercheur:
    """L'entonnoir. Une instance par processus, ses modèles sont paresseux."""

    def __init__(self, depot: Depot | None = None, encodeur: Encodeur | None = None) -> None:
        self.depot = depot or Depot()
        self.encodeur = encodeur or Encodeur()
        self._reranker = None

    @property
    def reranker(self):  # noqa: ANN202
        """Cross-encoder, chargé au premier usage comme l'encodeur (D46)."""
        if self._reranker is None:
            from sentence_transformers import CrossEncoder

            import os
            nom = os.environ.get("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")
            self._reranker = CrossEncoder(nom)
        return self._reranker

    # --- L'entonnoir --------------------------------------------------------

    def chercher(self, question: str, doc_types: set[str], config: Config) -> Resultat:
        if not doc_types:
            return Resultat(abstention=True)

        if config.court_circuit and (trouvee := MOTIF_REF.search(question)):
            resultat = self._par_reference(trouvee.group(0), question, doc_types, config)
            # Repli : une référence absente du corpus ne doit pas dégrader la
            # couverture. Sans lui, la présence d'un code dans la question
            # ferait perdre les passages que le reste de la question aurait
            # trouvés.
            if resultat.passages:
                return resultat

        candidats = self.depot.dense(self.encodeur.requete(question), doc_types, config.n)
        if config.lexical:
            candidats = fusion_rrf(candidats, self.depot.lexical(question, doc_types, config.n))

        candidats = candidats[:config.m]
        if config.rerank and candidats:
            candidats = self._reranker_passages(question, candidats)
        candidats = arbitrer_versions(candidats)[:config.k]

        return self._conclure(candidats, "hybride" if config.lexical else "dense", config)

    def _par_reference(self, reference: str, question: str, doc_types: set[str],
                       config: Config) -> Resultat:
        """Filtre exact, puis départage par type, puis version courante."""
        passages = self.depot.par_reference(reference, doc_types)
        if not passages:
            return Resultat()

        vise = type_demande(question)
        ordre = (vise,) + tuple(t for t in PREFERENCE_TYPE if t != vise) if vise else PREFERENCE_TYPE

        def cle(p: Passage) -> tuple:
            doc_type = str(p.metadonnees.get("doc_type", ""))
            rang_type = ordre.index(doc_type) if doc_type in ordre else len(ordre)
            # is_latest d'abord : une v1.0 ne remonte jamais devant sa v2.1.
            return (0 if p.metadonnees.get("is_latest") else 1, rang_type, p.chunk_id)

        passages = arbitrer_versions(sorted(passages, key=cle))
        if config.rerank and len(passages) > 1:
            # Le reranking ORDONNE les chunks de la référence selon le reste de
            # la question, mais il ne peut plus changer de document : le
            # départage par type a déjà eu lieu.
            tete = passages[0]
            reste = self._reranker_passages(question, passages[1:]) if len(passages) > 2 else passages[1:]
            passages = [tete, *reste]
        return Resultat(passages=passages[:config.k], voie="reference", score_max=1.0)

    def _reranker_passages(self, question: str, passages: list[Passage]) -> list[Passage]:
        paires = [(question, p.texte) for p in passages]
        scores = self.reranker.predict(paires)
        reordonnes = sorted(zip(passages, scores), key=lambda t: float(t[1]), reverse=True)
        return [
            Passage(chunk_id=p.chunk_id, texte=p.texte, score=float(s),
                    metadonnees=p.metadonnees)
            for p, s in reordonnes
        ]

    def _conclure(self, passages: list[Passage], voie: str, config: Config) -> Resultat:
        score_max = passages[0].score if passages else 0.0
        abstention = not passages or (config.seuil is not None and score_max < config.seuil)
        return Resultat(
            passages=[] if abstention else passages,
            voie=voie, score_max=score_max, abstention=abstention,
        )

"""Les contrôles de fin de lot 1, exigés par la revue de conception.

Pourquoi ils existent : un document mal chargé ne produit **aucune erreur** à la
recherche. Il produit une réponse incomplète, ou une citation fausse, ce qui est
strictement pire qu'un plantage. Ces contrôles sont donc la seule chose qui
sépare une ingestion réussie d'une ingestion silencieusement fausse.

Ils suivent le même principe que `governance/verifier_matrice.py` : ils
comparent à des **attentes écrites en dur**, hors de la donnée contrôlée, et ils
échouent en nommant le fautif.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict

from .document import Chunk, Document

#: Attendus du corpus fourni, écrits ici pour que la dérive se voie. Un corpus
#: qui change fait échouer le contrôle : c'est le but, on veut le savoir.
ATTENDU_PAR_TYPE = {
    "fiche_technique": 150,
    "notice": 80,
    "procedure_sav": 90,
    "note_interne": 80,
}
DOC_TYPES_MATRICE = set(ATTENDU_PAR_TYPE)
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

#: Ce qui identifie un exemplaire sans porter de sens : référence, date, version.
#: Sert à mesurer le templatage réel du corpus, celui que voit un embedding.
EXEMPLAIRE = re.compile(r"REF-\d{4}|\d{4}-\d{2}-\d{2}|[Vv]ersion\s*:?\s*\d+\.\d+")


class Rapport:
    def __init__(self) -> None:
        self.echecs: list[str] = []
        self.faits: list[str] = []

    def exige(self, condition: bool, message: str) -> None:
        (self.faits if condition else self.echecs).append(message)


def corps_seul(c: Chunk) -> str:
    """Le texte du chunk prive de son en-tete, pour mesurer ce que l'en-tete apporte.

    L'en-tete occupe la premiere ligne, plus une seconde quand le chunk porte un
    titre de section. Retirer la seule longueur du titre laisserait la reference
    en place, et le controle mesurerait alors sa propre erreur.
    """
    a_retirer = 2 if c.section else 1
    return c.texte.split("\n", a_retirer)[-1]


def controler(documents: list[Document], chunks: list[Chunk],
              doc_types_autorises: set[str] | None = None) -> Rapport:
    r = Rapport()
    attendus = doc_types_autorises or DOC_TYPES_MATRICE

    # --- Volumes : la dérive du corpus se voit ici avant tout le reste -------
    par_type = Counter(d.doc_type for d in documents)
    r.exige(dict(par_type) == ATTENDU_PAR_TYPE,
            f"volumes par doc_type conformes : {dict(sorted(par_type.items()))}")

    # --- Le doc_type appartient à la matrice --------------------------------
    inconnus = sorted({d.doc_type for d in documents} - attendus)
    r.exige(not inconnus, "tous les doc_type appartiennent a la matrice"
                          + (f" -- INCONNUS {inconnus}" if inconnus else ""))

    # --- LE contrôle qui a motivé la règle : aucun titre perdu --------------
    # Le motif PDF du relevé perdait 47 titres de fiche sur 150 en s'arrêtant
    # sur une parenthèse échappée, sans le moindre message.
    sans_titre = [d.doc_id for d in documents if not d.titre.strip()]
    r.exige(not sans_titre,
            f"{len(documents)} documents sur {len(documents)} ont un titre"
            + (f" -- SANS TITRE {sans_titre[:5]}" if sans_titre else ""))

    fiches = [d for d in documents if d.doc_type == "fiche_technique"]
    fiches_titrees = [d for d in fiches if d.titre.strip()]
    r.exige(len(fiches_titrees) == 150,
            f"{len(fiches_titrees)} fiches sur 150 ont un titre non vide")

    # --- Chaque document a de quoi être cité (E1) ---------------------------
    for champ in ("reference", "version", "date"):
        manquants = [d.doc_id for d in documents if not getattr(d, champ).strip()]
        r.exige(not manquants, f"tous les documents ont un {champ}"
                               + (f" -- MANQUE {manquants[:5]}" if manquants else ""))
    mal_datees = [d.doc_id for d in documents if not ISO_DATE.match(d.date)]
    r.exige(not mal_datees, "toutes les dates sont au format ISO"
                            + (f" -- FAUTIVES {mal_datees[:5]}" if mal_datees else ""))

    # --- Identifiants uniques ------------------------------------------------
    doublons = [i for i, n in Counter(d.doc_id for d in documents).items() if n > 1]
    r.exige(not doublons, "les doc_id sont uniques"
                          + (f" -- DOUBLONS {doublons[:5]}" if doublons else ""))
    doublons = [i for i, n in Counter(c.chunk_id for c in chunks).items() if n > 1]
    r.exige(not doublons, "les chunk_id sont uniques"
                          + (f" -- DOUBLONS {doublons[:5]}" if doublons else ""))

    # --- EXACTEMENT un is_latest par groupe de versions ---------------------
    # Une réindexation partielle laisserait deux versions courantes, et le
    # système citerait un document périmé sans qu'aucune erreur n'apparaisse.
    courants: dict[str, set[str]] = defaultdict(set)
    for c in chunks:
        if c.is_latest:
            courants[c.version_group].add(c.doc_id)
    groupes = {d.version_group for d in documents}
    fautifs = {g: sorted(courants.get(g, set())) for g in groupes
               if len(courants.get(g, set())) != 1}
    r.exige(not fautifs,
            f"exactement un is_latest par groupe, sur {len(groupes)} groupes"
            + (f" -- FAUTIFS {list(fautifs.items())[:3]}" if fautifs else ""))

    # --- Le report d'en-tête a bien eu lieu ---------------------------------
    sans_entete = [c.chunk_id for c in chunks if not c.texte.startswith(c.titre)]
    r.exige(not sans_entete, "tous les chunks portent l'en-tete de leur document"
                             + (f" -- SANS {sans_entete[:5]}" if sans_entete else ""))

    # --- Et il sert à quelque chose : les textes deviennent distincts -------
    # C'est le contrôle qui prouve la règle plutôt que de l'affirmer. Sur les
    # notices et les procédures, le corps seul ne discrimine rien.
    for doc_type in ("notice", "procedure_sav"):
        vises = [c for c in chunks if c.doc_type == doc_type]
        if not vises:
            continue
        avec = len({c.texte for c in vises})
        sans = len({corps_seul(c) for c in vises})
        # Neutralise ce qui identifie un exemplaire sans porter de sens : une
        # reference citee en pied de page rend deux corps litteralement
        # differents, alors qu'un modele d'embedding les voit identiques. C'est
        # CE chiffre que le protocole E6 doit regarder.
        nu = len({EXEMPLAIRE.sub("", corps_seul(c)) for c in vises})
        r.exige(avec > sans >= nu,
                f"{doc_type} : {avec} textes distincts avec l'en-tete, {sans} sans, "
                f"{nu} sans et une fois les references neutralisees")

    return r


def afficher(r: Rapport) -> int:
    for f in r.faits:
        print(f"  ok    {f}")
    for e in r.echecs:
        print(f"  ECHEC {e}")
    if r.echecs:
        print(f"\n{len(r.echecs)} controle(s) en echec.")
        return 1
    print(f"\n{len(r.faits)} controles passes.")
    return 0

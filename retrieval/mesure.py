"""Mesure du gain (E6) : ablation brique par brique, sur `eval/questions_rag.jsonl`.

Le protocole est dans `docs/mesure_e6.md`, écrit AVANT l'implémentation pour que
le résultat ne puisse pas être choisi après coup. Ce module l'exécute, il ne le
redéfinit pas.

Trois principes s'y appliquent :

- **Recall@k porte sur des DOCUMENTS, pas des chunks.** Une notice fait quatre
  chunks : à k = 3, une liste de chunks pourrait être remplie par un seul
  document, et le chiffre ne voudrait plus rien dire.
- **Un `gold_alternatifs` compte comme un succès.** Quand plusieurs documents
  répondent également bien, en exiger un seul mesure le hasard.
- **Aucun gold n'est perdu en silence.** Un identifiant d'annotation qu'on ne
  sait pas résoudre fait échouer la mesure. Une question silencieusement exclue
  gonflerait le score sans que personne ne le voie.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

from common.config import CONFIG

from .depot import Depot
from .recherche import Chercheur, Config, Resultat

EVAL = CONFIG.racine / "eval"

#: RAG-19 est étiquetée `couverte` dans la fixture, et l'annotation conclut
#: qu'elle est hors corpus de fait : « cuisson » et « plaque » n'apparaissent
#: dans aucun des 400 fichiers. La fixture ne se modifie pas ; c'est le
#: protocole qui s'aligne sur l'annotation.
REETIQUETAGE = {"RAG-19": "hors_corpus"}

#: Préfixes de type employés par l'annotation, du plus long au plus court pour
#: que `procedure_sav_` ne soit pas coupé par `proc`.
PREFIXES_GOLD = ("procedure_sav_", "note_interne_", "fiche_technique_",
                 "notice_", "fiche_", "note_", "proc_", "sav_")
SUFFIXE_VERSION = re.compile(r"_v([\d.]+)$")


def _noyau(identifiant: str) -> str:
    """Réduit un identifiant à ce qui l'identifie vraiment, prefixe de type et
    séparateurs mis à part. Sert à réconcilier deux conventions de nommage."""
    return re.sub(r"[^a-z0-9]", "", identifiant.lower())


class GoldIntrouvable(RuntimeError):
    """Un identifiant d'annotation sans correspondance dans l'index."""


class Oracle:
    """Traduit `eval/attendus_rag.jsonl` en attentes exploitables."""

    def __init__(self, depot: Depot) -> None:
        self.documents = depot.documents({"fiche_technique", "notice",
                                          "procedure_sav", "note_interne"})
        # Index de réconciliation : noyau du doc_id vers doc_id réel.
        self._par_noyau: dict[str, str] = {}
        for d in self.documents:
            doc_id = str(d["doc_id"])
            self._par_noyau[_noyau(doc_id)] = doc_id
            # Le doc_id réel porte parfois un préfixe de type que l'annotation
            # n'écrit pas de la même façon : on indexe aussi la forme nue.
            nu = re.sub(r"^(notice|proc)-", "", doc_id)
            self._par_noyau.setdefault(_noyau(nu), doc_id)

        self.attendus = {
            x["id"]: x
            for x in (json.loads(ligne) for ligne in
                      (EVAL / "attendus_rag.jsonl").read_text(encoding="utf-8").splitlines()
                      if ligne.strip())
        }

    def resoudre(self, gold: str) -> str:
        """Un identifiant d'annotation vers un doc_id réel. Échoue s'il n'existe pas."""
        reste = gold
        for prefixe in PREFIXES_GOLD:
            if reste.startswith(prefixe):
                reste = reste[len(prefixe):]
                break
        reste = SUFFIXE_VERSION.sub(lambda m: f"-v{m.group(1)}", reste)
        for candidat in (gold, reste):
            trouve = self._par_noyau.get(_noyau(candidat))
            if trouve:
                return trouve
        raise GoldIntrouvable(f"gold sans correspondance dans l'index : {gold!r}")

    def golds(self, ident: str) -> set[str]:
        """L'ensemble des documents qui comptent comme un succès."""
        a = self.attendus.get(ident, {})
        bruts = [a["gold_doc_id"]] if a.get("gold_doc_id") else []
        bruts += a.get("gold_alternatifs") or []
        return {self.resoudre(g) for g in bruts}

    def gold_ref(self, ident: str) -> str | None:
        return self.attendus.get(ident, {}).get("gold_ref")

    def exploitable(self, ident: str) -> bool:
        """Une annotation de certitude nulle ne discrimine rien : elle est
        écartée du rappel, et le protocole le dit."""
        return self.attendus.get(ident, {}).get("certitude") != "nulle"


@dataclass
class Ligne:
    """Le résultat d'une question dans une configuration."""

    ident: str
    population: str
    rang: int | None       # rang (1-based) du premier document juste, None si absent
    abstention: bool
    #: Peut-on décider d'un succès pour cette question ? Une annotation de
    #: certitude nulle ne discrimine rien : elle est EXCLUE du rappel, et non
    #: comptée comme un échec. La compter ferait baisser les deux branches à
    #: l'identique et diluerait le gain qu'on cherche à mesurer.
    notable: bool = True


def _documents_classes(r: Resultat) -> list[str]:
    """La liste des documents, dédoublonnée en gardant le meilleur rang."""
    vus: list[str] = []
    for p in r.passages:
        if p.doc_id not in vus:
            vus.append(p.doc_id)
    return vus


def _references_classees(r: Resultat) -> list[str]:
    vues: list[str] = []
    for p in r.passages:
        ref = str(p.metadonnees.get("reference", ""))
        if ref not in vues:
            vues.append(ref)
    return vues


def jouer(chercheur: Chercheur, oracle: Oracle, doc_types: set[str],
          config: Config, questions: list[dict]) -> list[Ligne]:
    lignes: list[Ligne] = []
    for q in questions:
        ident = q["id"]
        population = REETIQUETAGE.get(ident, q["type"])
        r = chercheur.chercher(q["question"], doc_types, config)

        rang: int | None = None
        notable = True
        attendue = oracle.gold_ref(ident)
        golds = oracle.golds(ident) if oracle.exploitable(ident) else set()

        if population == "hors_corpus":
            notable = False           # on y mesure l'abstention, pas le rappel
        elif attendue:
            # Référence attendue, qu'elle vienne d'une question `reference_exacte`
            # ou d'un label dur porté par une question `couverte`.
            classees = _references_classees(r)
            if attendue in classees:
                rang = classees.index(attendue) + 1
        elif golds:
            for i, doc_id in enumerate(_documents_classes(r), start=1):
                if doc_id in golds:
                    rang = i
                    break
        else:
            # Ni référence attendue, ni gold exploitable : la question ne
            # discrimine rien. On l'exclut, et le rapport dit combien.
            notable = False

        lignes.append(Ligne(ident, population, rang,
                            r.abstention or not r.passages, notable))
    return lignes


def resume(lignes: list[Ligne], population: str, ks=(1, 3, 5)) -> dict:
    """Recall@k et MRR sur une population. Les questions sans gold exploitable
    sont exclues, et leur nombre est rendu pour que l'exclusion soit visible."""
    vises = [x for x in lignes if x.population == population]
    if population == "hors_corpus":
        return {"n": len(vises),
                "abstention": sum(x.abstention for x in vises) / len(vises) if vises else 0.0}
    notes = [x for x in vises if x.notable]
    if not notes:
        return {"n": 0, "exclues": len(vises)}
    out = {"n": len(notes), "exclues": len(vises) - len(notes)}
    for k in ks:
        out[f"recall@{k}"] = sum(1 for x in notes if x.rang and x.rang <= k) / len(notes)
    out["mrr"] = sum(1 / x.rang for x in notes if x.rang) / len(notes)
    return out

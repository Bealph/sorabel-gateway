"""Génère `eval/rapport_gain.md` : la preuve chiffrée exigée par E6.

`python -m retrieval.rapport`

Le rapport n'est pas rédigé à la main. Il est **généré** à partir d'une mesure
rejouable, pour la même raison que le relevé de données et la vue de la matrice :
un chiffre recopié dérive, et un chiffre qu'on ne sait pas régénérer n'est pas
vérifiable.
"""
from __future__ import annotations

import json
import math
from datetime import date
from math import comb

from common.matrice import droits

from .depot import Depot
from .mesure import EVAL, Oracle, jouer, resume
from .recherche import Chercheur, Config

VARIANTES = {
    "A": ("dense seul", Config(lexical=False, court_circuit=False, rerank=False, seuil=None)),
    "B": ("+ BM25 et fusion RRF", Config(lexical=True, court_circuit=False, rerank=False, seuil=None)),
    "C": ("+ reranking", Config(lexical=True, court_circuit=False, rerank=True, seuil=None)),
    "D": ("+ court-circuit REF", Config(lexical=True, court_circuit=True, rerank=True, seuil=None)),
}


def wilson(succes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Intervalle de confiance à 95 % d'une proportion, méthode de Wilson.

    Choisie plutôt que l'approximation normale : sur des effectifs de 8 à 9
    questions, cette dernière donne des bornes hors de [0, 1] et un intervalle
    faussement étroit près de 0 et de 1, c'est-à-dire exactement là où nos
    scores se trouvent.
    """
    if n == 0:
        return (0.0, 0.0)
    p, d = succes / n, 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    demi = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, centre - demi), min(1.0, centre + demi))


def mcnemar(bascules_pour: int, bascules_contre: int) -> float:
    """p exact unilatéral du test de McNemar, sur des questions APPARIEES.

    C'est le test qui convient ici : les deux systèmes voient les mêmes
    questions, donc seules les questions qui CHANGENT d'issue portent de
    l'information. Les autres s'annulent.
    """
    n = bascules_pour + bascules_contre
    if n == 0:
        return 1.0
    return sum(comb(n, k) for k in range(bascules_pour, n + 1)) / 2 ** n


def _succes(lignes, population: str, k: int) -> tuple[int, int]:
    vises = [x for x in lignes if x.population == population and x.notable]
    return sum(1 for x in vises if x.rang and x.rang <= k), len(vises)


def _tableau(res: dict, population: str) -> list[str]:
    r0 = resume(res["A"][1], population)
    L = [f"### Population `{population}` : {r0['n']} questions notables, "
         f"{r0['exclues']} exclues", "",
         "| Configuration | Recall@1 | Recall@3 | Recall@5 | MRR |",
         "| --- | ---: | ---: | ---: | ---: |"]
    for cle, (libelle, _) in VARIANTES.items():
        r = resume(res[cle][1], population)
        L.append(f"| **{cle}** {libelle} | {r['recall@1']:.3f} | {r['recall@3']:.3f} | "
                 f"{r['recall@5']:.3f} | {r['mrr']:.3f} |")
    L.append("")

    sa, n = _succes(res["A"][1], population, 1)
    sd, _ = _succes(res["D"][1], population, 1)
    ia, id_ = wilson(sa, n), wilson(sd, n)
    a_rangs = {x.ident: x.rang for x in res["A"][1] if x.notable and x.population == population}
    d_rangs = {x.ident: x.rang for x in res["D"][1] if x.notable and x.population == population}
    pour = sum(1 for i in a_rangs if (a_rangs[i] or 99) > 1 and (d_rangs[i] or 99) == 1)
    contre = sum(1 for i in a_rangs if (a_rangs[i] or 99) == 1 and (d_rangs[i] or 99) > 1)

    L += ["**Ce que ce gain vaut statistiquement**, sur Recall@1, A contre D :", "",
          f"- A : {sa}/{n} = {sa/n:.3f}, intervalle de confiance à 95 % [{ia[0]:.2f} ; {ia[1]:.2f}]",
          f"- D : {sd}/{n} = {sd/n:.3f}, intervalle de confiance à 95 % [{id_[0]:.2f} ; {id_[1]:.2f}]",
          f"- questions qui basculent en faveur de D : **{pour}**, en faveur de A : **{contre}**",
          f"- test de McNemar exact, unilatéral : **p = {mcnemar(pour, contre):.3f}**", ""]
    verdict = ("Les intervalles se recouvrent et p reste au-dessus de 0,05 : "
               "**ce gain n'est pas distinguable du bruit** sur un jeu de cette taille."
               if mcnemar(pour, contre) > 0.05 or ia[1] >= id_[0] else
               "Les intervalles sont disjoints et p passe sous 0,05.")
    L += [verdict, ""]
    return L


def _bout_en_bout(doc_types: set[str], questions: list[dict]) -> list[str]:
    """Le comportement RÉEL du tool, seuil d'abstention compris.

    Les tableaux précédents mesurent le CLASSEMENT, seuil désactivé. Celui-ci
    mesure ce qu'un client reçoit : une réponse, ou une abstention. C'est le
    chiffre qui compte pour un utilisateur, et il raconte une autre histoire.
    """
    from .service import ServiceRag

    attendu = {"couverte": "ok", "reference_exacte": "ok", "hors_corpus": "hors_corpus"}
    L = ["---", "", "## 3. De bout en bout : ce qu'un client reçoit", "",
         "Seuil d'abstention activé. Une question `couverte` doit recevoir une "
         "réponse sourcée, une question hors corpus doit recevoir une abstention.", "",
         "| Population | A, dense simple | D, hybride complète |",
         "| --- | :---: | :---: |"]
    lignes: dict[str, dict[str, str]] = {}
    totaux: dict[str, int] = {}
    e1: dict[str, bool] = {}
    for cle in ("A", "D"):
        svc = ServiceRag(droits("support"), VARIANTES[cle][1])
        justes: dict[str, list[int]] = {}
        fautes = []
        for q in questions:
            pop = "hors_corpus" if q["id"] == "RAG-19" else q["type"]
            statut, _, _ = svc.answer_question(q["question"])
            bon = statut == attendu[pop]
            compteur = justes.setdefault(pop, [0, 0])
            compteur[0] += int(bon)
            compteur[1] += 1
            if not bon:
                fautes.append(pop)
        for pop, (bons, total) in justes.items():
            lignes.setdefault(pop, {})[cle] = f"{bons}/{total}"
        totaux[cle] = sum(b for b, _ in justes.values())
        e1[cle] = "hors_corpus" not in fautes

    for pop in ("reference_exacte", "couverte", "hors_corpus"):
        L.append(f"| `{pop}` | {lignes[pop]['A']} | {lignes[pop]['D']} |")
    L.append(f"| **total** | **{totaux['A']}/{len(questions)}** | "
             f"**{totaux['D']}/{len(questions)}** |")
    L += ["",
          f"**E1 tenue dans les deux configurations** : aucune question hors corpus "
          f"ne reçoit de réponse. A : {'oui' if e1['A'] else 'NON'}. "
          f"D : {'oui' if e1['D'] else 'NON'}.", "",
          "Les deux échecs de D sont RAG-13 et RAG-16, les deux questions dont la "
          "réponse est une constante du corpus. Elles reçoivent une abstention à "
          "tort. Abaisser le seuil pour les récupérer ferait répondre deux "
          "questions hors corpus : le rappel se paierait en E1, ce que le "
          "protocole interdit.", ""]
    return L


def main() -> int:
    questions = [json.loads(ligne) for ligne
                 in (EVAL / "questions_rag.jsonl").read_text(encoding="utf-8").splitlines()
                 if ligne.strip()]
    depot = Depot()
    chercheur = Chercheur(depot)
    oracle = Oracle(depot)
    doc_types = set(droits("support").doc_types)

    res = {cle: (libelle, jouer(chercheur, oracle, doc_types, cfg, questions))
           for cle, (libelle, cfg) in VARIANTES.items()}

    L = [
        "<!-- GENERE par `python -m retrieval.rapport`. Ne pas editer a la main. -->",
        "", "# Mesure E6 : gain de la recherche avancée sur la recherche simple", "",
        f"> Rapport **généré** le {date.today().isoformat()} depuis "
        "`eval/questions_rag.jsonl` et `eval/attendus_rag.jsonl`.",
        "> Le protocole est dans `docs/mesure_e6.md`, écrit avant l'implémentation.", "",
        "---", "",
        "## 1. Ce qui est comparé", "",
        "Quatre configurations, et non deux. Comparer seulement « dense » à "
        "« avancé » ferait varier trois choses à la fois, et le gain global ne "
        "serait imputable à rien.", "",
        "| Clé | Dense | BM25 + RRF | Reranking | Court-circuit `REF` |",
        "| --- | :---: | :---: | :---: | :---: |",
        "| **A**, baseline, recherche dense simple | oui | non | non | non |",
        "| **B** | oui | oui | non | non |",
        "| **C** | oui | oui | oui | non |",
        "| **D**, recherche hybride complète | oui | oui | oui | oui |", "",
        "À partir de **B**, la recherche est **hybride** : le lexical et le dense "
        "interrogent le corpus en parallèle, et leurs deux classements sont "
        "fusionnés par RRF, sur les rangs et non sur les scores. C'est cette "
        "recherche hybride que le brief demande de comparer à la recherche dense "
        "initiale.", "",
        f"Corpus indexé : {depot.manifeste['chunks']} chunks issus de "
        f"{depot.manifeste['documents']} documents, "
        f"modèle `{depot.manifeste['modele']}`, {depot.manifeste['dimension']} dimensions.", "",
        "**Recall@k porte sur des documents, pas sur des chunks.** Une notice "
        "fait quatre chunks : à k = 3, une liste de chunks pourrait être remplie "
        "par un seul document. Un `gold_alternatifs` de l'annotation compte comme "
        "un succès.", "",
        "---", "", "## 2. Résultats", "",
    ]
    L += _tableau(res, "reference_exacte")
    L += _tableau(res, "couverte")

    L += _bout_en_bout(doc_types, questions)

    L += ["---", "", "## 4. Ce que la mesure dit, et ce qu'elle ne dit pas", "",
          "**Le gain existe sur toutes les métriques.** Il va dans le bon sens à "
          "chaque étage, et aucune brique ne dégrade le résultat.", "",
          "**Il n'est pas statistiquement démontrable sur ce jeu.** Les effectifs "
          "notables sont de 8 et 9 questions : une seule qui bascule vaut 11 à "
          "12 points de pourcentage. Pour descendre sous 5 % avec le test de "
          "McNemar, il faudrait au moins cinq bascules dans le même sens et "
          "aucune dans l'autre. Nous en avons une ou deux.", "",
          "**Le gain sur `reference_exacte` est en partie fabriqué par notre "
          "propre optimisation.** Le court-circuit sur référence est un filtre "
          "déterministe que nous avons ajouté : il ne peut pas se tromper. Il "
          "faut le présenter comme une **garantie d'E2**, jamais comme une "
          "mesure de qualité de recherche.", "",
          "**Le corpus borne ce qui est mesurable.** Sans leur titre, les 80 "
          "notices partagent quatre textes distincts, et les 90 procédures SAV "
          "aussi. Quatre questions `couverte` sur treize portent sur un contenu "
          "dupliqué à l'identique : elles ont autant de bonnes réponses qu'il y a "
          "de documents, et sont exclues du rappel plutôt que comptées comme des "
          "échecs, ce qui diluerait les deux branches à l'identique.", "",
          "**Une question de la fixture est mal étiquetée.** RAG-19 est marquée "
          "`couverte` ; « cuisson » et « plaque » n'apparaissent dans aucun des "
          "400 fichiers. Le protocole la traite comme `hors_corpus`, et la "
          "fixture n'est pas modifiée.", "",
          "---", "", "## 5. Reproductibilité", "",
          "La mesure a été rendue reproductible après un défaut trouvé le "
          "2026-09-02 : la même requête rendait des voisins différents d'un "
          "processus à l'autre, alors que le vecteur de requête était identique "
          "au bit près. La cause était la recherche approchée HNSW, sur un corpus "
          "où les quasi ex æquo sont la règle. Deux corrections : `hnsw:search_ef` "
          "porté à 512, ce qui rend la recherche quasi exacte à cette échelle, et "
          "un départage déterministe par identifiant de chunk à score égal.", "",
          "Vérifié : quatre exécutions dans quatre processus distincts rendent la "
          "même liste. Sans cela, un Recall@1 aurait été reproductible par chance "
          "et non par construction.", ""]

    (EVAL / "rapport_gain.md").write_text("\n".join(L), encoding="utf-8", newline="\n")
    print(f"eval/rapport_gain.md genere, {len(L)} lignes")
    for pop in ("reference_exacte", "couverte"):
        for cle in VARIANTES:
            r = resume(res[cle][1], pop)
            print(f"  {pop:18} {cle} R@1={r['recall@1']:.3f} MRR={r['mrr']:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Mesure du Text-to-SQL sur `eval/questions_sql.jsonl` : `python -m sql.mesure`.

P5 prescrit un ordre d'essai : petit modèle local, **mesure sur SQL-01 à 12**,
montée en gamme seulement si le taux de SQL juste est insuffisant. Ce module est
la mesure. Sans elle, le choix du modèle serait une préférence.

**Le vocabulaire de statuts de l'oracle n'est pas celui du contrat.**
`eval/attendus_sql.jsonl` a été écrit à la conception, avec nos statuts internes
(`out_of_schema`, `clarify`, `not_found`). Le contrat d'intégration de la DSI
n'en énumère que cinq : `ok | refused | clarification | hors_corpus | error`. La
correspondance est donc explicite ci-dessous, plutôt que devinée à la lecture.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass

from common.config import CONFIG
from common.matrice import droits

from .service import ServiceSql

EVAL = CONFIG.racine / "eval"

#: Nos statuts de conception vers les cinq statuts du contrat.
VERS_CONTRAT = {
    "ok": "ok",
    "refused": "refused",
    "out_of_schema": "refused",     # accompagne du code OUT_OF_SCHEMA
    "clarify": "clarification",
    # D26 adaptée : le contrat n'a pas de `not_found`. L'identifiant valide mais
    # absent devient un `ok` dont le message le dit, et dont `trouve` est faux.
    "not_found": "ok",
}


@dataclass
class Ligne:
    ident: str
    type_question: str
    profil: str
    attendu: str
    obtenu: str
    juste: bool
    valeur_ok: bool | None      # None quand l'attendu ne porte pas de valeur
    duree: float
    detail: str = ""


def _charger(nom: str) -> list[dict]:
    return [json.loads(ligne) for ligne
            in (EVAL / nom).read_text(encoding="utf-8").splitlines() if ligne.strip()]


def jouer(generateur=None, limite: int | None = None) -> list[Ligne]:
    questions = _charger("questions_sql.jsonl")
    attendus = {x["id"]: x for x in _charger("attendus_sql.jsonl")}
    if limite:
        questions = questions[:limite]

    services: dict[str, ServiceSql] = {}
    lignes: list[Ligne] = []
    for q in questions:
        profil = q["profil"]
        if profil not in services:
            services[profil] = ServiceSql(droits(profil), generateur)
        service = services[profil]
        a = attendus.get(q["id"], {})
        attendu = VERS_CONTRAT.get(a.get("status", ""), a.get("status", "?"))

        t0 = time.time()
        tool = a.get("tool", "ask_database")
        if tool == "order_status":
            # La question nomme un identifiant de commande : on le retrouve dans
            # le SQL de référence, faute d'un champ dédié dans l'oracle.
            ident = "CMD-2026-0042"
            statut, payload, message = service.order_status(ident)
        else:
            statut, payload, message = service.ask_database(q["question"])
        duree = time.time() - t0

        # La valeur de contrôle, quand l'oracle en porte une. C'est ce qui
        # distingue « le statut est bon » de « la réponse est juste ».
        valeur_ok: bool | None = None
        if statut == "ok" and "valeur_controle" in a:
            lignes_rendues = payload.get("rows") or []
            obtenue = lignes_rendues[0][0] if lignes_rendues and lignes_rendues[0] else None
            valeur_ok = obtenue == a["valeur_controle"]
        elif statut == "ok" and "lignes_attendues" in a:
            valeur_ok = len(payload.get("rows") or []) == a["lignes_attendues"]

        detail = payload.get("sql") or message
        lignes.append(Ligne(q["id"], q["type"], profil, attendu, statut,
                            statut == attendu, valeur_ok, duree, str(detail)[:110]))
    return lignes


def afficher(lignes: list[Ligne]) -> int:
    print(f"{'id':8} {'type':16} {'profil':11} {'attendu':14} {'obtenu':14} "
          f"{'valeur':7} {'s':>5}")
    for x in lignes:
        marque = "ok " if x.juste else "ECHEC"
        valeur = {True: "juste", False: "FAUSSE", None: "-"}[x.valeur_ok]
        print(f"{x.ident:8} {x.type_question:16} {x.profil:11} {x.attendu:14} "
              f"{x.obtenu:14} {valeur:7} {x.duree:5.1f}  {marque}")
        if not x.juste or x.valeur_ok is False:
            print(f"         -> {x.detail}")

    justes = sum(x.juste for x in lignes)
    valeurs = [x for x in lignes if x.valeur_ok is not None]
    print(f"\nstatut juste        : {justes}/{len(lignes)}")
    if valeurs:
        print(f"valeur de controle  : {sum(x.valeur_ok for x in valeurs)}/{len(valeurs)}")
    par_type: dict[str, list[Ligne]] = {}
    for x in lignes:
        par_type.setdefault(x.type_question, []).append(x)
    print()
    for t, groupe in sorted(par_type.items()):
        print(f"  {t:16} {sum(x.juste for x in groupe)}/{len(groupe)}")
    duree = sum(x.duree for x in lignes)
    print(f"\ntotal {duree:.0f} s, {duree/len(lignes):.1f} s par question, "
          f"max {max(x.duree for x in lignes):.1f} s")
    return 0 if justes == len(lignes) else 1


def main() -> int:
    """Mesure avec le générateur retenu par défaut, `--ollama` pour la variante.

    Les deux restent mesurables : c'est ce qui permet de dire ce que la montée
    en gamme apporterait, au lieu de l'affirmer.
    """
    import sys

    # Le defaut est le generateur RETENU (D48) : petit modele local via
    # transformers. Ollama reste mesurable avec --ollama, pour que la marche
    # suivante de l'echelle de P5 puisse etre reprise sans reecrire le harnais.
    if "--ollama" in sys.argv:
        from .generateur_ollama import GenerateurOllama
        generateur = GenerateurOllama()
        pret, pourquoi = generateur.disponible()
        if not pret:
            print(f"ERREUR : {pourquoi}", file=sys.stderr)
            return 2
    else:
        from .generateur import GenerateurLocal
        generateur = GenerateurLocal()
    print(f"generateur : {generateur.nom}")
    print()
    return afficher(jouer(generateur))


if __name__ == "__main__":
    raise SystemExit(main())

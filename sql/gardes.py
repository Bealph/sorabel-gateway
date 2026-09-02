"""La pile de gardes du Text-to-SQL. C'est ici que E3 et E5 se gagnent ou se perdent.

Une seule barrière ne suffit pas : chaque couche couvre un mode de défaillance
différent.

| Couche | Barrière | Ce qu'elle bloque |
| ---: | --- | --- |
| 0 | schéma borné au profil (`sql/schema.py`) | le modèle ne peut pas nommer ce qu'il ne voit pas |
| 0 bis | pré-filtre lexical, depuis la matrice | rend le refus EXPLICITE, aucune valeur de sécurité |
| 2 | analyse syntaxique `sqlglot` | non-SELECT, instructions multiples, `SELECT *` |
| 3 | périmètre du profil, sur l'AST | toute référence hors matrice |
| 4 | `LIMIT` et délai | requête lourde, produit cartésien |

**La couche 3 inspecte TOUTE occurrence d'une colonne**, pas les colonnes
projetées. La nuance sépare une garde qui tient d'une garde décorative :
`ORDER BY marge_pct` divulgue le classement sans jamais afficher la colonne, et
une dichotomie sur un prédicat en rend la valeur exacte. Vérifié sur la base : la
marge de REF-8842 vaut 47,3, reconstituable seuil par seuil.

**La couche 1, la connexion en lecture seule, n'est PAS un rattrapage de la
couche 2.** Mesuré : sur une connexion `mode=ro`, `PRAGMA query_only = 0` est
accepté, puis `ATTACH` d'un fichier tiers, puis `CREATE` et `INSERT` dedans. Elle
protège le fichier ouvert, pas le processus. Ce qui interdit réellement
l'écriture, c'est la règle du SELECT unique, ici.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import sqlglot
from sqlglot import exp

from common.matrice import Droits

from .schema import Table, introspecter

#: Plafond de lignes rendues (D16). Il protège la base et le client, mais il
#: MENT si le résultat est tronqué sans le dire : le drapeau `tronque` existe
#: pour cela.
LIMITE = 200

#: Types de nœuds refusés d'emblée. On les nomme, plutôt que de se contenter de
#: « tout ce qui n'est pas un SELECT » : le refus est alors lisible au journal.
NOEUDS_INTERDITS = {
    exp.Insert: "INSERT", exp.Update: "UPDATE", exp.Delete: "DELETE",
    exp.Drop: "DROP", exp.Alter: "ALTER", exp.Create: "CREATE",
    exp.Attach: "ATTACH", exp.Detach: "DETACH", exp.Pragma: "PRAGMA",
    exp.Command: "commande non analysable",
}


@dataclass
class Verdict:
    """Le résultat d'un passage dans la pile. `code` nomme la couche fautive."""

    ok: bool
    code: str = ""
    message: str = ""
    sql: str = ""
    ressources: dict[str, list[str]] = field(default_factory=dict)
    scalaire: bool = False


def _refus(code: str, message: str) -> Verdict:
    return Verdict(ok=False, code=code, message=message)


# --- Couche 0 bis -------------------------------------------------------------

def prefiltre_lexical(question: str, droits: Droits,
                      lexique: dict[str, list[str]]) -> Verdict | None:
    """Refus explicite quand la question NOMME une ressource retirée.

    AUCUNE valeur de sécurité : une liste de mots se contourne par une
    paraphrase. Elle sert à rendre le refus imputable, donc journalisable et
    démontrable (E5). Sans elle, la couche 0 fait son travail, le modèle répond
    « hors schéma », et aucune trace ne dit qu'un accès a été tenté.

    Elle ne peut pas dégrader la protection : un contournement du lexique
    retombe sur les couches 2 et 3, inchangées. Ses faux positifs coûtent un
    refus injustifié, jamais une fuite.
    """
    q = f" {question.lower()} "
    for ressource in sorted(droits.colonnes_interdites):
        for terme in lexique.get(ressource, []):
            if re.search(rf"\b{re.escape(terme.lower())}\b", q):
                return _refus(
                    "FORBIDDEN_COLUMN",
                    f"La colonne {ressource} n'est pas accessible au profil "
                    f"{droits.profil}. La demande a ete refusee avant toute "
                    f"generation de requete.")
    return None


# --- Couches 2, 3 et 4 --------------------------------------------------------

def _tables_et_alias(arbre: exp.Expression) -> tuple[set[str], dict[str, str]]:
    tables: set[str] = set()
    alias: dict[str, str] = {}
    for noeud in arbre.find_all(exp.Table):
        nom = (noeud.name or "").lower()
        if not nom:
            continue
        tables.add(nom)
        if noeud.alias:
            alias[noeud.alias.lower()] = nom
    return tables, alias


def _colonnes_referencees(arbre: exp.Expression, tables: set[str],
                          alias: dict[str, str], schema: dict[str, Table],
                          complet: dict[str, Table] | None = None,
                          ) -> tuple[set[str], set[str]]:
    """Toutes les colonnes citées, qualifiées. Rend (résolues, non résolues).

    `find_all(exp.Column)` remonte les colonnes de PARTOUT : projection, WHERE,
    JOIN ON, GROUP BY, HAVING, ORDER BY, agrégats, sous-requêtes à toute
    profondeur. C'est le point qui distingue cette garde d'une garde décorative.
    """
    resolues: set[str] = set()
    inconnues: set[str] = set()
    for noeud in arbre.find_all(exp.Column):
        col = (noeud.name or "").lower()
        prefixe = (noeud.table or "").lower()
        if prefixe:
            table = alias.get(prefixe, prefixe)
            resolues.add(f"{table}.{col}")
            continue
        # Colonne non qualifiée : on cherche à quelle table elle appartient
        # dans le schéma COMPLET, et non dans le schéma expurgé. La nuance
        # décide du CODE de refus : cherchée dans le schéma expurgé, une colonne
        # retirée serait « inconnue » et le journal ne dirait pas qu'un accès à
        # une marge a été tenté. Un audit E5 doit pouvoir les compter.
        reference = complet or schema
        porteuses = [t for t in tables if t in reference and col in reference[t].noms()]
        if len(porteuses) == 1:
            resolues.add(f"{porteuses[0]}.{col}")
        elif porteuses:
            resolues.update(f"{t}.{col}" for t in porteuses)
        else:
            inconnues.add(col)
    return resolues, inconnues


def _est_scalaire(arbre: exp.Expression) -> bool:
    """Un agrégat sans GROUP BY rend UNE ligne : y injecter LIMIT n'a pas de sens
    et fausserait un COUNT si la limite était appliquée avant l'agrégat."""
    if arbre.args.get("group"):
        return False
    return any(arbre.find(f) for f in (exp.Count, exp.Sum, exp.Avg, exp.Min, exp.Max))


def valider(sql: str, droits: Droits, schema: dict[str, Table]) -> Verdict:
    """Fait passer un SQL par les couches 2, 3 et 4. Ne l'exécute pas."""
    if not sql or not sql.strip():
        return _refus("OUT_OF_SCHEMA", "Aucune requete n'a ete produite.")

    # --- Couche 2 : une seule instruction, et c'est un SELECT ---------------
    try:
        instructions = [i for i in sqlglot.parse(sql, dialect="sqlite") if i is not None]
    except Exception as e:  # noqa: BLE001
        return _refus("READ_ONLY_VIOLATION", f"Requete non analysable : {e}")

    if len(instructions) != 1:
        return _refus("READ_ONLY_VIOLATION",
                      f"{len(instructions)} instructions detectees. Une seule "
                      "instruction SELECT est autorisee.")
    arbre = instructions[0]

    for type_noeud, libelle in NOEUDS_INTERDITS.items():
        if isinstance(arbre, type_noeud) or arbre.find(type_noeud):
            return _refus("READ_ONLY_VIOLATION",
                          f"Instruction {libelle} refusee : la gateway est en "
                          "lecture seule.")
    if not isinstance(arbre, (exp.Select, exp.Union, exp.Subquery)):
        return _refus("READ_ONLY_VIOLATION",
                      f"Seul SELECT est autorise, recu {type(arbre).__name__.upper()}.")
    # `COUNT(*)` ne projette aucune colonne : il compte des lignes, et c'est la
    # requete la plus courante du metier. Seule l'etoile de PROJECTION est
    # interdite, celle qui ferait sortir des colonnes non nommees.
    etoiles_projetees = [
        n for n in arbre.find_all(exp.Star)
        if not isinstance(n.parent, (exp.Count, exp.AggFunc))
    ]
    if etoiles_projetees:
        return _refus("OUT_OF_SCHEMA",
                      "SELECT * est interdit : il ferait sortir des colonnes que "
                      "le profil n'a pas le droit de voir. Nommer les colonnes. "
                      "COUNT(*) reste autorise, il ne projette rien.")

    # --- Couche 3 : périmètre, sur TOUTE occurrence -------------------------
    tables, alias = _tables_et_alias(arbre)
    hors = sorted(tables - set(schema))
    if hors:
        return _refus("OUT_OF_SCHEMA",
                      f"Table(s) hors du perimetre du profil {droits.profil} : "
                      f"{', '.join(hors)}. Tables accessibles : "
                      f"{', '.join(sorted(schema))}.")

    resolues, inconnues = _colonnes_referencees(
        arbre, tables, alias, schema, introspecter())
    interdites = sorted(resolues & set(droits.colonnes_interdites))
    if interdites:
        return _refus("FORBIDDEN_COLUMN",
                      f"Colonne(s) non accessible(s) au profil {droits.profil} : "
                      f"{', '.join(interdites)}. Une colonne retiree l'est dans "
                      "TOUTE la requete, y compris un tri ou un filtre.")

    connues = {f"{t}.{c}" for t, table in introspecter().items() for c in table.noms()}
    fantomes = sorted((resolues - connues) | {f"?.{c}" for c in inconnues})
    if fantomes:
        return _refus("OUT_OF_SCHEMA",
                      f"Colonne(s) inconnue(s) du schema autorise : "
                      f"{', '.join(fantomes)}.")

    # --- Couche 4 : LIMIT, sauf sur un agrégat scalaire ---------------------
    scalaire = _est_scalaire(arbre)
    if not scalaire:
        existante = arbre.args.get("limit")
        valeur = None
        if existante is not None:
            try:
                valeur = int(existante.expression.name)
            except (AttributeError, ValueError):
                valeur = None
        if valeur is None or valeur > LIMITE:
            arbre = arbre.limit(LIMITE)

    return Verdict(
        ok=True,
        sql=arbre.sql(dialect="sqlite", pretty=False),
        ressources={"tables": sorted(tables), "colonnes": sorted(resolues)},
        scalaire=scalaire,
    )

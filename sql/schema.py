"""Couche 0 : le schéma montré au modèle, borné au profil.

C'est la **première** ligne de défense d'E5, et la plus efficace : un modèle ne
peut pas référencer une colonne qu'il ne voit pas. Les couches suivantes
rattrapent, celle-ci évite.

Le schéma est **introspecté**, jamais recopié. Le dossier a payé deux fois pour
cette règle : des énumérations recopiées avaient divergé, et `WHERE categorie =
'Cablage'` sans accent rendait zéro ligne en franchissant les six couches de
gardes, sans une erreur.

Les commentaires, en revanche, viennent de `docs/schema.sql`, qui est le schéma
commenté de référence de la DSI. On les lit, on ne les réinvente pas.
"""
from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from common.config import CONFIG
from common.matrice import Droits

#: Colonnes dont on liste les valeurs dans le schéma montré au modèle.
#: Motif : sans les valeurs réelles, le modèle invente `statut = 'livrée'` là où
#: la base écrit `livree`. Le SQL est alors valide, il rend zéro ligne, et rien
#: ne le signale. On ne relève que les colonnes de faible cardinalité.
CARDINALITE_ENUM = 15


@dataclass(frozen=True)
class Colonne:
    nom: str
    type_sql: str
    commentaire: str = ""
    valeurs: tuple[str, ...] = ()


@dataclass(frozen=True)
class Table:
    nom: str
    colonnes: tuple[Colonne, ...]

    def noms(self) -> set[str]:
        return {c.nom for c in self.colonnes}


def _commentaires(chemin: Path) -> dict[str, str]:
    """Les commentaires de fin de ligne de `docs/schema.sql`, par `table.colonne`.

    On y retire les mentions `SENSIBLE`. Non par pudeur : ce commentaire décrit
    une politique, et la politique vit dans la matrice. Le laisser ici en
    ferait une seconde source de vérité, et c'est exactement ce que D21
    interdit.
    """
    if not chemin.exists():
        return {}
    out: dict[str, str] = {}
    table = None
    for ligne in chemin.read_text(encoding="utf-8").splitlines():
        if m := re.match(r"\s*CREATE TABLE (\w+)", ligne):
            table = m.group(1)
            continue
        if table and (m := re.match(r"\s*(\w+)\s+[\w()]+.*?--\s*(.+)$", ligne)):
            texte = re.sub(r"SENSIBLE\s*:?\s*", "", m.group(2)).strip()
            texte = re.sub(r"\s*[-—]?\s*ne sort jamais pour le profil support\.?", "", texte)
            out[f"{table}.{m.group(1)}"] = texte.strip(" .")
        if table and ligne.strip().startswith(")"):
            table = None
    return out


@lru_cache(maxsize=4)
def introspecter(base: Path | None = None, commente: Path | None = None) -> dict[str, Table]:
    """Le schéma réel de la base, enrichi des commentaires de référence."""
    chemin = base or CONFIG.base_sql
    if not chemin.exists():
        raise FileNotFoundError(f"base absente : {chemin}. Lancer `python scripts/seed.py`.")
    notes = _commentaires(commente or CONFIG.racine / "docs" / "schema.sql")

    cx = sqlite3.connect(f"file:{chemin}?mode=ro", uri=True)
    tables: dict[str, Table] = {}
    noms = [t[0] for t in cx.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    for nom in noms:
        colonnes = []
        for _, col, type_sql, *_ in cx.execute(f"PRAGMA table_info({nom})"):
            valeurs: tuple[str, ...] = ()
            if type_sql.upper().startswith("TEXT"):
                distinctes = list(cx.execute(
                    f"SELECT DISTINCT {col} FROM {nom} LIMIT {CARDINALITE_ENUM + 1}"))
                if len(distinctes) <= CARDINALITE_ENUM:
                    valeurs = tuple(str(v[0]) for v in sorted(distinctes) if v[0] is not None)
            colonnes.append(Colonne(col, type_sql, notes.get(f"{nom}.{col}", ""), valeurs))
        tables[nom] = Table(nom, tuple(colonnes))
    cx.close()
    return tables


def schema_du_profil(droits: Droits, base: Path | None = None) -> dict[str, Table]:
    """Le schéma tel que ce profil a le droit de le connaître.

    Introspection INTER matrice. Une table hors périmètre disparaît en entier,
    une colonne interdite disparaît de sa table. Le modèle ne saura donc même
    pas qu'elles existent.
    """
    complet = introspecter(base)
    interdites = set(droits.colonnes_interdites)
    return {
        nom: Table(nom, tuple(c for c in table.colonnes
                              if f"{nom}.{c.nom}" not in interdites))
        for nom, table in complet.items()
        if nom in droits.tables
    }


def rendre(schema: dict[str, Table]) -> str:
    """Le schéma en texte, pour le prompt et pour `get_schema`.

    Format proche du DDL commenté : c'est celui sur lequel les modèles de code
    sont entraînés, donc celui qu'ils lisent le mieux.
    """
    blocs = []
    for table in schema.values():
        lignes = [f"CREATE TABLE {table.nom} ("]
        for i, c in enumerate(table.colonnes):
            virgule = "," if i < len(table.colonnes) - 1 else ""
            note = c.commentaire
            if c.valeurs:
                note = (note + " " if note else "") + f"valeurs : {' | '.join(c.valeurs)}"
            lignes.append(f"  {c.nom:16} {c.type_sql:8}{virgule}"
                          + (f"  -- {note}" if note else ""))
        lignes.append(");")
        blocs.append("\n".join(lignes))
    return "\n\n".join(blocs)


#: Les quatre seuls chemins de jointure du schéma, déclarés comme clés
#: étrangères dans la base. Principale source d'erreur d'un SQL généré : une
#: jointure sur le mauvais prédicat rend un résultat plausible et faux.
JOINTURES = (
    "stocks.ref = produits.ref",
    "ventes.ref = produits.ref",
    "ventes.commande_id = commandes.id",
    "commandes.client_id = clients.id",
)


def jointures_du_profil(droits: Droits) -> tuple[str, ...]:
    """Les jointures dont les DEUX tables sont dans le périmètre du profil."""
    return tuple(
        j for j in JOINTURES
        if all(cote.split(".")[0] in droits.tables for cote in j.split(" = "))
    )

"""Choisir le tool à appeler depuis une question en langage naturel.

POURQUOI CE MODULE EXISTE
Les écrans techniques laissent l'humain choisir son onglet, donc son tool. Une
**conversation** ne peut pas : l'utilisateur pose une phrase et ignore qu'il
existe huit tools. Il faut router, et ce routage n'existait nulle part.

C'est aussi, mot pour mot, **le cerveau que l'application Slack réclame**
(D34, items A1 et A2) : le bot reçoit une phrase libre et doit faire ce même
choix. Ce module sert les deux devantures.

CE QUE LA MESURE A REFUTE, LE 2026-09-03
La première version confiait le routage au modèle local retenu par D48, avec
une sortie contrainte à une étiquette. **Quatre montages ont été mesurés sur
54 questions des fixtures, tous au niveau du hasard :**

| Montage sur Qwen2.5-Coder-0.5B          | Juste  |
| --------------------------------------- | ------ |
| logits du premier jeton des étiquettes  | 4/20   |
| choix multiple A/B/C/D                  | 6/20   |
| choix multiple avec calibration         | 5/20   |
| génération libre puis lecture           | 1/20   |
| choix à deux classes                    | 28/54, en répondant toujours DOCUMENT |

C'est un modèle de **code** de 0,5 milliard de paramètres : D48 avait mesuré
17/24 en génération SQL avec un échafaudage de prompt lourd, et la
classification en français libre est hors de sa portée. Un défaut de mon
montage s'y ajoutait : comparer les logits bruts du premier jeton de chaque
étiquette compare aussi leur fréquence a priori dans le vocabulaire, et le
prior du jeton écrasait la réponse.

CE QUI MARCHE, MESURE SUR LE MEME JEU
Une **amorce lexicale déclarée**, puis les **embeddings multilingues** déjà
embarqués pour le RAG :

| Montage                                    | Tout le jeu | Hors questions hors corpus |
| ------------------------------------------ | ----------- | -------------------------- |
| e5-small seul, descriptions en exemples    | 41/54       | 38/46                      |
| + vocabulaire déclaré (schéma et lexique)  | 44/54       | 41/46                      |
| + listes d'intention                       | **47/54**   | **44/46**                  |

13 ms par question, et **6 des 6 questions de démonstration de la gouvernance**
partent au bon endroit, contre 2 sur 6 avec les embeddings seuls. Ce dernier
point pèse plus que l'agrégat : mal routée, « quelle est la marge sur la
REF-8842 ? » ne déclencherait jamais le refus de colonne, et E5 deviendrait
invisible dans la conversation.

CE QUE LE MODULE NE FAIT PAS
Décider d'un droit. Le routage choisit *quoi demander*, la matrice décide *si
c'est permis*, et elle décide après. Un routage qui se trompe produit un refus
ou une réponse hors sujet, jamais une fuite.
"""
from __future__ import annotations

import re
import sqlite3
import time
import unicodedata
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path

from common.config import CONFIG
from common.matrice import droits, lexique_refus

ROUTAGE = Path(__file__).resolve().parent / "routage.yaml"

#: Les étiquettes, et le tool que chacune déclenche. Fermé.
#:
#: `check_stock` et `order_status` sont des requêtes FIGEES, donc des
#: spécialisations d'`ask_database` : on n'y route que sur un signe
#: déterministe, un identifiant présent dans la phrase. `get_schema`,
#: `search_docs`, `get_document` et `list_sources` n'y figurent pas
#: volontairement, ce sont des briques pour un intégrateur et non des réponses
#: à une question d'utilisateur.
TOOLS = {"DOCUMENT": "answer_question", "BASE": "ask_database",
         "STOCK": "check_stock", "COMMANDE": "order_status"}

REFERENCE = re.compile(r"\bREF-\d{3,6}\b", re.I)
COMMANDE = re.compile(r"\bCMD-\d{4}-\d{3,5}\b", re.I)


def sansaccent(texte: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texte.lower())
                   if unicodedata.category(c) != "Mn")


@dataclass
class Routage:
    """Une décision de routage, avec de quoi la contester.

    `par` nomme le mécanisme qui a tranché. C'est ce qui rend un mauvais
    routage lisible au lieu d'être seulement constaté : on sait s'il vient d'un
    terme déclaré ou d'une similarité, donc où corriger.
    """

    etiquette: str
    tool: str
    par: str
    indice: str = ""
    similarites: dict[str, float] = field(default_factory=dict)
    arguments: dict = field(default_factory=dict)
    duree_ms: float = 0.0
    #: Renseigné quand un tool figé est choisi sans son identifiant.
    manque: str = ""

    def trace(self) -> dict:
        return {"etiquette": self.etiquette, "tool": self.tool, "par": self.par,
                "indice": self.indice, "arguments": self.arguments,
                "similarites": {k: round(v, 4) for k, v in self.similarites.items()},
                "duree_ms": round(self.duree_ms, 1), "manque": self.manque}


class Routeur:
    """Amorce lexicale déclarée, puis similarité d'embeddings."""

    def __init__(self, encodeur=None, profil: str = "commercial") -> None:  # noqa: ANN001
        self._encodeur = encodeur
        self.profil = profil

    # --- le vocabulaire, relevé et non recopié -----------------------------
    @cached_property
    def _regles(self) -> dict:
        import yaml

        return yaml.safe_load(ROUTAGE.read_text(encoding="utf-8"))

    @cached_property
    def _vocabulaire(self) -> tuple[frozenset[str], frozenset[str]]:
        """(jetons, expressions) qui désignent la base de données.

        Relevé de trois sources DECLAREES, jamais recopié : le schéma réel de
        la base par introspection, les tables du profil, et le lexique de refus
        de la matrice. Un mot séparé des noms de colonnes dériverait.
        """
        jetons: set[str] = set()
        expressions: set[str] = set()

        for table in droits(self.profil).tables:
            jetons.add(sansaccent(table))

        # Neuf des termes du lexique de refus comportent une espace : un
        # croisement de jetons ne les atteindrait jamais, « prix d'achat »
        # n'étant ni « prix » ni « achat ».
        for termes in lexique_refus().values():
            for t in termes:
                (expressions if " " in t else jetons).add(sansaccent(t))

        cx = sqlite3.connect(f"file:{CONFIG.base_sql}?mode=ro", uri=True)
        try:
            tables = [t for (t,) in cx.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%'")]
            for table in tables:
                jetons.add(sansaccent(table))
                for colonne in cx.execute(f"PRAGMA table_info({table})"):
                    mot = sansaccent(colonne[1])
                    if len(mot) > 3:      # « id », « ref » sont trop ambigus
                        jetons.add(mot)
        finally:
            cx.close()
        return frozenset(jetons), frozenset(expressions)

    @cached_property
    def _vecteurs(self) -> dict[str, list[float]]:
        descriptions = self._regles["descriptions"]
        cles = sorted(descriptions)
        vecs = self.encodeur.passages([descriptions[c] for c in cles])
        return dict(zip(cles, vecs))

    @property
    def encodeur(self):  # noqa: ANN201
        if self._encodeur is None:
            from common.embeddings import Encodeur

            self._encodeur = Encodeur()
        return self._encodeur

    @property
    def modele_pret(self) -> bool:
        return "_vecteurs" in self.__dict__

    # --- le routage ---------------------------------------------------------
    def router(self, question: str) -> Routage:
        debut = time.perf_counter()
        n = sansaccent(question)
        etiquette, par, indice = self._decider(question, n)
        similarites: dict[str, float] = {}
        if etiquette is None:
            similarites = self._similarites(question)
            etiquette = max(similarites, key=similarites.get)
            par, indice = "similarite", ""

        tool = TOOLS[etiquette]
        arguments, manque = self._arguments(tool, question)
        return Routage(etiquette=etiquette, tool=tool, par=par, indice=indice,
                       similarites=similarites, arguments=arguments,
                       manque=manque,
                       duree_ms=(time.perf_counter() - debut) * 1000)

    def _decider(self, question: str, n: str) -> tuple[str | None, str, str]:
        """L'amorce. Rend None quand aucun terme déclaré ne tranche."""
        regles = self._regles
        jetons_base, expressions_base = self._vocabulaire
        mots = set(re.findall(r"[a-z0-9_']+", n))

        # 1. Un identifiant de commande est un signe déterministe : aucun autre
        #    tool ne prend cette forme, et order_status est une requête figée.
        if COMMANDE.search(question):
            return "COMMANDE", "identifiant de commande", COMMANDE.search(question).group(0)

        # 2. E3 : une demande d'écriture doit atteindre la couche SQL.
        for terme in regles["ecriture"]:
            if terme in n:
                return "BASE", "verbe d'ecriture", terme

        # 3. Un terme sensible ou un nom de table ou de colonne, déclaré.
        for terme in sorted(expressions_base, key=len, reverse=True):
            if terme in n:
                return "BASE", "terme declare", terme
        communs = mots & jetons_base
        if communs:
            return "BASE", "nom de table ou de colonne", sorted(communs)[0]

        # 4. Le raccourci vers le tool figé, si une référence accompagne une
        #    intention de disponibilité.
        if REFERENCE.search(question):
            for terme in regles["stock"]:
                if terme in n:
                    return "STOCK", "reference et intention de stock", terme

        # 5. Les listes d'intention. Ce sont les seules écrites à la main, et
        #    leur apport mesuré (+3 sur 54) est optimiste : elles ont été
        #    rédigées en regardant les fixtures.
        for terme in regles["agregat"]:
            if terme in n:
                return "BASE", "intention d'agregat", terme
        for terme in regles["documentaire"]:
            if terme in n:
                return "DOCUMENT", "intention documentaire", terme
        return None, "", ""

    def _similarites(self, question: str) -> dict[str, float]:
        vq = self.encodeur.requete(question)
        return {cle: sum(a * b for a, b in zip(vq, v))
                for cle, v in self._vecteurs.items()}

    def _arguments(self, tool: str, question: str) -> tuple[dict, str]:
        """Les arguments du tool, lus dans la question.

        Ce n'est pas du routage : les tools figés exigent un identifiant, et il
        faut le lire quelle que soit la façon dont le routage a décidé.
        """
        if tool == "check_stock":
            m = REFERENCE.search(question)
            return ({"reference": m.group(0).upper()}, "") if m else (
                {}, "la reference du produit, sous la forme REF-8842")
        if tool == "order_status":
            m = COMMANDE.search(question)
            return ({"order_id": m.group(0).upper()}, "") if m else (
                {}, "l'identifiant de la commande, sous la forme CMD-2025-0004")
        return {"question": question}, ""

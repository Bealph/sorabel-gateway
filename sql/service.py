"""Les quatre tools SQL, indépendamment de MCP.

Comme pour la brique documentaire, ce module rend des dictionnaires : le serveur
les emballe. La logique se teste donc sans lancer un processus.

**Le générateur est enfichable**, et ce n'est pas de la souplesse gratuite. P5
prescrit un ordre d'essai : petit modèle local sur processeur, mesure sur les
questions SQL-01 à 12, puis montée en gamme seulement si le taux de SQL juste
est insuffisant. Un générateur interchangeable est ce qui rend cet ordre
praticable au lieu de théorique. Et tout ce qui n'est pas la génération, les
tools figés comme les chemins de refus, se teste dès maintenant sans aucun
modèle.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

from common.matrice import Droits, lexique_refus

from .executeur import DELAI_S, ErreurExecution, executer
from .gardes import LIMITE, prefiltre_lexical, valider
from .schema import jointures_du_profil, rendre, schema_du_profil

#: Format d'un identifiant de commande, pour distinguer un identifiant mal formé
#: d'un identifiant simplement absent. Les deux se répondent différemment.
MOTIF_COMMANDE = re.compile(r"^CMD-\d{4}-\d{4}$", re.IGNORECASE)
MOTIF_REF = re.compile(r"^REF-\d{4}$", re.IGNORECASE)


@dataclass
class Generation:
    """La sortie STRUCTUREE du générateur. Trois cas, et trois seulement.

    Un générateur qui ne pourrait rendre que du SQL serait forcé d'inventer une
    requête pour une question hors schéma. La sortie typée est ce qui permet de
    répondre « je ne sais pas » sans halluciner.
    """

    cas: str            # "SQL" | "CLARIFY" | "HORS_SCHEMA"
    sql: str = ""
    message: str = ""
    options: list[str] | None = None


class Generateur(Protocol):
    """Ce que le service attend d'un générateur, et rien de plus."""

    def generer(self, question: str, schema: str, jointures: tuple[str, ...]) -> Generation:
        ...


class SansGenerateur:
    """Générateur d'attente : il refuse tout, proprement.

    Il existe pour que le service soit complet et testable AVANT qu'un modèle
    soit choisi. Il ne triche pas : il ne devine aucune requête, il dit qu'il
    n'en produit pas.
    """

    def generer(self, question: str, schema: str,
                jointures: tuple[str, ...]) -> Generation:
        return Generation(
            cas="HORS_SCHEMA",
            message="Aucun generateur de requete n'est configure sur cette "
                    "instance. Les tools figes check_stock et order_status "
                    "restent disponibles.")


class ServiceSql:
    """Les quatre tools SQL. Une instance par processus."""

    def __init__(self, droits: Droits, generateur: Generateur | None = None) -> None:
        self.droits = droits
        self.generateur = generateur or SansGenerateur()
        self.schema = schema_du_profil(droits)
        self.lexique = lexique_refus()

    # --- get_schema ---------------------------------------------------------

    def get_schema(self) -> tuple[str, dict, str]:
        """Le périmètre autorisé, en texte. AUCUNE donnée n'est renvoyée.

        Ce tool n'est pas accessible à tous les profils : la matrice le réserve
        au `commercial`. Le contrôle du droit d'appeler se fait à la gateway,
        pas ici : ce module ne connaît pas la notion d'appel refusé.
        """
        texte = rendre(self.schema)
        jointures = jointures_du_profil(self.droits)
        if jointures:
            texte += ("\n\n-- Chemins de jointure, les seuls du schema :\n"
                      + "\n".join(f"--   {j}" for j in jointures))
        return "ok", {"schema": texte}, ""

    # --- ask_database -------------------------------------------------------

    def ask_database(self, question: str) -> tuple[str, dict, str]:
        """Question en langage naturel vers résultat, avec la requête renvoyée.

        L'ordre des couches est celui du dossier, et il compte : on refuse le
        plus tôt possible, et on n'exécute qu'en dernier.
        """
        if not question or not question.strip():
            return "refused", {}, "La question est vide."

        # Couche 0 bis : refus explicite avant toute génération.
        if refus := prefiltre_lexical(question, self.droits, self.lexique):
            return "refused", {"code": refus.code}, refus.message

        # Couche 0 : le modèle ne voit que le périmètre du profil.
        generation = self.generateur.generer(
            question, rendre(self.schema), jointures_du_profil(self.droits))

        if generation.cas == "CLARIFY":
            return ("clarification", {"options": generation.options or []},
                    generation.message or "La question est ambigue, preciser.")
        if generation.cas == "HORS_SCHEMA":
            return ("refused", {"code": "OUT_OF_SCHEMA"},
                    generation.message or "Cette question ne releve pas des "
                    "donnees accessibles a ce profil. Aucune requete n'a ete "
                    "produite.")

        # Couches 2, 3 et 4.
        verdict = valider(generation.sql, self.droits, self.schema)
        if not verdict.ok:
            # Le SQL fautif accompagne le refus : c'est ce qui rend le refus
            # auditable, et c'est la couche 5 appliquee au chemin malheureux.
            return ("refused",
                    {"code": verdict.code, "sql": generation.sql},
                    verdict.message)

        # Couche 1, en dernier.
        try:
            resultat = executer(verdict.sql, LIMITE)
        except ErreurExecution as e:
            return ("error", {"code": "INTERNAL_ERROR", "sql": verdict.sql}, str(e))

        payload = {
            "sql": verdict.sql,
            "columns": resultat.colonnes,
            "rows": resultat.lignes,
            "ressources": verdict.ressources,
        }
        message = ""
        if resultat.tronque:
            # Une troncature muette est un resultat faux.
            payload["tronque"] = True
            message = (f"Resultat tronque a {LIMITE} lignes. Il y en avait "
                       "davantage : restreindre la question.")
        if not resultat.lignes:
            # D26 : une liste ou un agregat peut valoir zero. C'est un `ok`,
            # pas un `not_found`, et le client doit le dire differemment.
            message = ("Aucune ligne ne correspond. La requete est valide et "
                       "le resultat est vide.")
        return "ok", payload, message

    # --- Les deux tools figés -----------------------------------------------

    def check_stock(self, reference: str) -> tuple[str, dict, str]:
        """Stock d'une référence, par entrepôt. Requête paramétrée, jamais générée.

        Un tool figé ne passe pas par les six couches, puisqu'il n'y a rien à
        analyser. Sa garantie E5 tient donc à sa requête, écrite ici une fois :
        elle ne nomme aucune colonne sensible, et le contrôle
        `eval/cas_mcp.jsonl` MCP-19 le vérifie.
        """
        ref = (reference or "").strip().upper()
        if not MOTIF_REF.match(ref):
            return ("refused", {},
                    f"Reference {reference!r} mal formee. Format attendu : REF-NNNN.")
        if "stocks" not in self.schema:
            return "refused", {}, "La table stocks n'est pas accessible a ce profil."

        sql = ("SELECT s.entrepot, s.quantite, s.seuil_reappro FROM stocks s "
               "WHERE s.ref = ? ORDER BY s.entrepot")
        return self._figé(sql, (ref,), f"Aucun stock connu pour {ref}.")

    def order_status(self, order_id: str) -> tuple[str, dict, str]:
        """Statut d'une commande. `montant_ht` est le total, il n'est pas sensible."""
        ident = (order_id or "").strip().upper()
        if not MOTIF_COMMANDE.match(ident):
            return ("refused", {},
                    f"Identifiant {order_id!r} mal forme. Format attendu : "
                    "CMD-AAAA-NNNN.")
        if "commandes" not in self.schema:
            return "refused", {}, "La table commandes n'est pas accessible a ce profil."

        sql = ("SELECT c.statut, c.date_commande, c.montant_ht FROM commandes c "
               "WHERE c.id = ?")
        return self._figé(sql, (ident,),
                          f"Aucune commande {ident}. L'identifiant est bien forme, "
                          "mais la numerotation des commandes comporte des trous.")

    def _figé(self, sql: str, parametres: tuple, message_absent: str,
              ) -> tuple[str, dict, str]:
        """Exécute une requête paramétrée et applique D26 : identifiant précis
        introuvable, c'est `not_found`, jamais un `ok` avec zéro ligne."""
        import sqlite3

        from common.config import CONFIG
        try:
            cx = sqlite3.connect(f"file:{CONFIG.base_sql}?mode=ro", uri=True,
                                 timeout=DELAI_S)
            cx.execute("PRAGMA query_only = ON")
            curseur = cx.execute(sql, parametres)
            colonnes = [d[0] for d in (curseur.description or [])]
            lignes = [list(r) for r in curseur.fetchall()]
            cx.close()
        except sqlite3.Error as e:
            return "error", {"code": "INTERNAL_ERROR"}, f"Erreur SQLite : {e}"

        # Le SQL est renvoyé même figé : E3 exige la transparence, et un client
        # doit pouvoir vérifier ce qui a été exécuté en son nom.
        payload = {"sql": sql, "columns": colonnes, "rows": lignes,
                   "parametres": list(parametres)}
        if not lignes:
            return "not_found", payload, message_absent
        return "ok", payload, ""

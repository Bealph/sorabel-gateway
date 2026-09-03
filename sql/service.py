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
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
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
    #: La sortie du modèle avant analyse. Sert à la démonstration et au
    #: diagnostic : sans elle, une sortie hors format devient un refus dont on
    #: ne sait pas ce qui l'a causé. Elle ne sort JAMAIS par un tool.
    brut: str = ""


class Generateur(Protocol):
    """Ce que le service attend d'un générateur, et rien de plus."""

    def generer(self, question: str, schema: str, jointures: tuple[str, ...]) -> Generation:
        ...


@dataclass
class Etape:
    """Un étage de la pile, avec ce qu'il a coûté et ce qu'il a décidé."""

    nom: str
    duree: float = 0.0
    detail: str = ""
    bloque: bool = False        # cet étage a-t-il arrêté la requête ?


@dataclass
class Trace:
    """Le compte rendu détaillé d'un appel, étage par étage.

    Elle sert la démonstration et le diagnostic. **Elle ne voyage jamais dans
    un payload de tool** : elle contient le prompt envoyé au modèle et sa sortie
    brute, qu'un client n'a pas à connaître.
    """

    question: str
    profil: str
    prefiltre_actif: bool = True
    etapes: list[Etape] = field(default_factory=list)
    prompt_schema: str = ""
    jointures: tuple[str, ...] = ()
    generation: Generation | None = None
    verdict: object | None = None       # sql.gardes.Verdict
    resultat: object | None = None      # sql.executeur.Resultat
    statut: str = ""
    code: str = ""
    message: str = ""

    @contextmanager
    def etape(self, nom: str):  # noqa: ANN201
        """Chronomètre un étage. Le temps par étage est ce qui rend visible
        que le pré-filtre coûte zéro et que la génération coûte tout."""
        e = Etape(nom)
        self.etapes.append(e)
        debut = time.perf_counter()
        try:
            yield e
        finally:
            e.duree = time.perf_counter() - debut

    @property
    def duree(self) -> float:
        return sum(e.duree for e in self.etapes)

    @property
    def bloque_par(self) -> str:
        """L'étage qui a tranché, s'il y en a un. C'est LE renseignement que
        cherche quelqu'un qui regarde un refus."""
        return next((e.nom for e in self.etapes if e.bloque), "")

    def conclure(self, statut: str, code: str, message: str) -> Trace:
        self.statut, self.code, self.message = statut, code, message
        return self

    def enveloppe(self) -> tuple[str, dict, str]:
        """Projette la trace sur le contrat d'intégration, et RIEN de plus.

        C'est ici que se joue la séparation : tout ce que la trace sait de la
        mécanique interne s'arrête à cette fonction. Le client reçoit un statut,
        une charge utile conforme au contrat, et un message.
        """
        payload: dict = {}
        if self.code:
            payload["code"] = self.code
        if self.statut == "clarification":
            payload["options"] = (self.generation.options or []) if self.generation else []
            return self.statut, payload, self.message
        if self.statut in ("refused", "error") and self.generation:
            # Le SQL fautif accompagne le refus : c'est la transparence d'E3
            # appliquee au chemin malheureux, et c'est ce qui rend le refus
            # auditable.
            if self.generation.sql:
                payload["sql"] = self.generation.sql
            return self.statut, payload, self.message
        if self.statut != "ok":
            return self.statut, payload, self.message

        payload["sql"] = self.verdict.sql          # type: ignore[union-attr]
        payload["columns"] = self.resultat.colonnes    # type: ignore[union-attr]
        payload["rows"] = self.resultat.lignes         # type: ignore[union-attr]
        payload["ressources"] = self.verdict.ressources   # type: ignore[union-attr]
        if self.resultat.tronque:                  # type: ignore[union-attr]
            payload["tronque"] = True
        return self.statut, payload, self.message


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

        **C'est ce que le tool MCP expose, et rien d'autre.** La signature ne
        porte que la question : aucun profil, aucun réglage de garde. Un
        paramètre est rempli par l'appelant, donc tout paramètre serait une
        surface d'attaque.
        """
        return self.tracer(question).enveloppe()

    def tracer(self, question: str, *, prefiltre: bool = True) -> Trace:
        """Le même traitement, mais en rendant compte de chaque étage.

        **À N'EXPOSER PAR AUCUN TOOL.** Cette méthode rend le prompt envoyé au
        modèle, sa sortie brute et les ressources extraites de l'arbre
        syntaxique : autant de choses qu'un client n'a pas à connaître. Elle
        existe pour la page de démonstration, qui n'est pas un client MCP, et
        pour le diagnostic.

        `prefiltre=False` désactive la couche 0 bis. **Ce n'est pas un réglage
        du serveur** : c'est un argument de cet appel direct, absent de toute
        signature de tool et de toute variable d'environnement. Le motif est
        pédagogique : le pré-filtre agit en zéro seconde et court-circuite tout,
        si bien qu'une démonstration ne voit jamais les couches 2 et 3 attraper
        la même attaque. Le désactiver montre la défense en profondeur au lieu
        de la raconter. Un interrupteur exposé, lui, serait le défaut que ce
        dossier a corrigé sur `profil` : n'importe quel appelant s'en servirait.
        """
        trace = Trace(question=question, profil=self.droits.profil,
                      prefiltre_actif=prefiltre)
        if not question or not question.strip():
            return trace.conclure("refused", "", "La question est vide.")

        # --- Couche 0 : le schéma borné, tel qu'il partira dans le prompt ----
        with trace.etape("0 · schéma borné au profil") as e:
            trace.prompt_schema = rendre(self.schema)
            trace.jointures = jointures_du_profil(self.droits)
            e.detail = (f"{len(self.schema)} tables, "
                        f"{sum(len(t.colonnes) for t in self.schema.values())} colonnes, "
                        f"{len(trace.jointures)} jointures")

        # --- Couche 0 bis : refus explicite avant toute génération -----------
        with trace.etape("0 bis · pré-filtre lexical") as e:
            refus = (prefiltre_lexical(question, self.droits, self.lexique)
                     if prefiltre else None)
            e.detail = ("désactivé pour la démonstration" if not prefiltre
                        else refus.message if refus else "aucun terme retiré reconnu")
            if refus:
                e.bloque = True
                return trace.conclure("refused", refus.code, refus.message)

        # --- Génération -------------------------------------------------------
        with trace.etape("génération") as e:
            generation = self.generateur.generer(
                question, trace.prompt_schema, trace.jointures)
            trace.generation = generation
            e.detail = f"cas {generation.cas}"

        if generation.cas == "CLARIFY":
            return trace.conclure(
                "clarification", "AMBIGUOUS",
                generation.message or "La question est ambigue, preciser.")
        if generation.cas == "HORS_SCHEMA":
            return trace.conclure(
                "refused", "OUT_OF_SCHEMA",
                generation.message or "Cette question ne releve pas des donnees "
                "accessibles a ce profil. Aucune requete n'a ete produite.")

        # --- Couches 2, 3 et 4 ------------------------------------------------
        with trace.etape("2, 3, 4 · AST, périmètre, LIMIT") as e:
            verdict = valider(generation.sql, self.droits, self.schema)
            trace.verdict = verdict
            e.detail = verdict.message if not verdict.ok else (
                f"{len(verdict.ressources.get('colonnes', []))} colonnes vues, "
                f"{'agrégat scalaire, pas de LIMIT' if verdict.scalaire else 'LIMIT injecté'}")
            if not verdict.ok:
                e.bloque = True
                return trace.conclure("refused", verdict.code, verdict.message)

        # --- Couche 1, en dernier ---------------------------------------------
        with trace.etape("1 · exécution en lecture seule") as e:
            try:
                trace.resultat = executer(verdict.sql, LIMITE)
            except ErreurExecution as exc:
                e.bloque = True
                return trace.conclure("error", "INTERNAL_ERROR", str(exc))
            e.detail = (f"{len(trace.resultat.lignes)} ligne(s)"
                        + (", TRONQUÉ" if trace.resultat.tronque else ""))

        message = ""
        if trace.resultat.tronque:
            # Une troncature muette est un resultat faux.
            message = (f"Resultat tronque a {LIMITE} lignes. Il y en avait "
                       "davantage : restreindre la question.")
        elif not trace.resultat.lignes:
            # D26 : une liste ou un agregat peut valoir zero. C'est un `ok`,
            # pas un `not_found`, et le client doit le dire differemment.
            message = ("Aucune ligne ne correspond. La requete est valide et "
                       "le resultat est vide.")
        return trace.conclure("ok", "", message)

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
        """Exécute une requête paramétrée. D26 est portée par le MESSAGE.

        **D26 adaptée au contrat, le 2026-09-02.** Notre conception avait créé
        un statut `not_found` pour distinguer « identifiant valide, aucune
        donnée » d'une liste légitimement vide. Le contrat d'intégration de la
        DSI énumère cinq statuts, et `not_found` n'en fait pas partie :
        `ok | refused | clarification | hors_corpus | error`.

        Un sixième statut casserait tout client qui aiguille sur `status`. La
        distinction que D26 voulait est donc portée par le `message`, qui dit
        explicitement que l'identifiant est bien formé et absent. Le contrat
        gagne sur notre conception, et la nuance survit là où elle ne casse rien.
        """
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
            payload["trouve"] = False
            return "ok", payload, message_absent
        return "ok", payload, ""

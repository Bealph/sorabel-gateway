"""Génération SQL par un modèle de code local (P5).

**Pourquoi local, et pourquoi petit.** P5 retient un modèle de code local, pour
que les questions métier ne quittent pas l'installation, et prescrit un ordre
d'essai : petit modèle sur processeur d'abord, mesure sur les questions SQL-01 à
12, montée en gamme **seulement si** le taux de SQL juste est insuffisant. Ce
module est la première marche de cet ordre. Il n'est pas un pari sur la qualité :
il est l'instrument qui permet de la mesurer.

**La sortie est STRUCTUREE**, trois cas et trois seulement (D15). Un générateur
qui ne saurait rendre que du SQL serait contraint d'inventer une requête pour
une question hors schéma. C'est précisément ainsi qu'on obtient un SQL
halluciné, plausible et faux.

**Le prompt ne contient que le périmètre du profil** (couche 0). Le modèle ne
peut pas nommer une colonne qu'il ne voit pas, et les valeurs d'énumération y
sont relevées dans la base plutôt que devinées : `WHERE categorie = 'Cablage'`
sans accent rend zéro ligne en franchissant toutes les gardes, sans une erreur.
"""
from __future__ import annotations

import os
import re
from functools import cached_property

from .service import Generation

MODELE_DEFAUT = "Qwen/Qwen2.5-Coder-1.5B-Instruct"

CONSIGNE = """Tu traduis une question en SQL SQLite, sur le schema ci-dessous.

REGLES ABSOLUES
- Un seul SELECT. Jamais INSERT, UPDATE, DELETE, DROP, PRAGMA, ATTACH.
- Jamais SELECT *. Nomme les colonnes. COUNT(*) est autorise.
- N'utilise QUE les tables et colonnes du schema. Elles sont deja restreintes
  aux droits de l'appelant : ce qui n'y figure pas n'existe pas pour toi.
- Recopie les valeurs d'enumeration EXACTEMENT comme le schema les donne,
  accents compris.
- Les dates sont du texte ISO AAAA-MM-JJ. Un mois se filtre par
  date_commande LIKE '2026-04-%'.

REPONDS PAR UNE SEULE LIGNE, dans l'un de ces trois formats :
SQL: <la requete>
CLARIFY: <la precision qui manque>
HORS_SCHEMA: <pourquoi le schema ne permet pas de repondre>

Utilise CLARIFY si la question est ambigue, et HORS_SCHEMA si les donnees
demandees ne sont pas dans le schema. N'invente jamais une requete pour
sauver la face."""

EXEMPLES = [
    ("combien de commandes en avril ?",
     "SQL: SELECT COUNT(*) FROM commandes WHERE date_commande LIKE '2026-04-%'"),
    ("quel temps fera-t-il demain a Lille ?",
     "HORS_SCHEMA: le schema ne contient aucune donnee meteorologique"),
    ("montre-moi les commandes recentes",
     "CLARIFY: quelle periode faut-il retenir pour recentes"),
]

MOTIF_SORTIE = re.compile(r"^\s*(SQL|CLARIFY|HORS_SCHEMA)\s*:\s*(.+)$",
                          re.IGNORECASE | re.MULTILINE | re.DOTALL)


def analyser(brut: str) -> Generation:
    """Lit la sortie du modèle. Ce qui n'est pas reconnu est refusé, jamais devine.

    Un modèle de 1,5 milliard de paramètres s'écarte parfois du format. On ne
    tente pas de rattraper : une sortie hors format devient `HORS_SCHEMA`, ce
    qui produit un refus propre plutôt qu'une requête reconstituée au jugé.
    """
    trouve = MOTIF_SORTIE.search(brut or "")
    if not trouve:
        return Generation(
            cas="HORS_SCHEMA",
            message="Le generateur n'a pas produit de sortie exploitable. "
                    "Aucune requete n'a ete devinee.")
    cas = trouve.group(1).upper()
    contenu = trouve.group(2).strip()
    # Le modèle encadre volontiers sa requête de balises Markdown.
    contenu = re.sub(r"^```(?:sql)?\s*|\s*```$", "", contenu).strip()
    contenu = contenu.split("\n")[0].strip().rstrip(";")

    if cas == "SQL":
        return Generation(cas="SQL", sql=contenu)
    if cas == "CLARIFY":
        return Generation(cas="CLARIFY", message=contenu)
    return Generation(cas="HORS_SCHEMA", message=contenu)


class GenerateurLocal:
    """Modèle de code instruct, chargé paresseusement, sur processeur."""

    def __init__(self, nom: str | None = None, max_jetons: int = 160) -> None:
        self.nom = nom or os.environ.get("SQL_MODEL", MODELE_DEFAUT)
        self.max_jetons = max_jetons

    @cached_property
    def _modele(self):  # noqa: ANN202
        # Import differé : un client qui ne fait que du documentaire n'a aucune
        # raison de payer le chargement d'un modèle de code (D46).
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        tokenizer = AutoTokenizer.from_pretrained(self.nom)
        # Pas de device_map : il exigerait `accelerate`, et sur processeur il
        # n'apporte rien. float32 parce que float16 est plus lent sur CPU.
        modele = AutoModelForCausalLM.from_pretrained(
            self.nom, torch_dtype=torch.float32)
        modele.eval()
        return tokenizer, modele

    def prechauffer(self) -> None:
        """Charge le modèle dans un fil d'arrière-plan, sans bloquer l'appelant.

        Mesuré sur ce poste : le premier appel a coûté **677 secondes**, contre
        12 à 20 pour les suivants. Ce n'est pas la génération, c'est le
        chargement du modèle sur un processeur bridé à 801 MHz sur 2304.

        La suite d'acceptance lance un processus serveur NEUF par session, avec
        30 secondes de budget par appel. Payer le chargement au démarrage
        dépasserait le budget de `initialize()` ; le payer au premier appel
        dépasse celui de l'appel. Le charger en parallèle du démarrage est la
        seule option qui ne bloque ni l'un ni l'autre.

        Cela ne suffit pas sur un poste aussi bridé, et il faut le dire : le
        chargement n'a pas fini quand le test appelle. Sur une machine non
        bridée, 50 secondes de chargement en tâche de fond suffisent.
        """
        import threading

        threading.Thread(target=lambda: self._modele, daemon=True).start()

    def _messages(self, question: str, schema: str, jointures: tuple[str, ...]) -> list[dict]:
        contexte = f"{CONSIGNE}\n\nSCHEMA\n{schema}"
        if jointures:
            contexte += ("\n\nCHEMINS DE JOINTURE, les seuls du schema\n"
                         + "\n".join(f"  {j}" for j in jointures))
        messages = [{"role": "system", "content": contexte}]
        # Few-shot : le format de sortie s'apprend mieux par l'exemple que par
        # la consigne, surtout a cette taille de modele.
        for demande, reponse in EXEMPLES:
            messages.append({"role": "user", "content": demande})
            messages.append({"role": "assistant", "content": reponse})
        messages.append({"role": "user", "content": question})
        return messages

    def generer(self, question: str, schema: str,
                jointures: tuple[str, ...]) -> Generation:
        import torch

        tokenizer, modele = self._modele
        entree = tokenizer.apply_chat_template(
            self._messages(question, schema, jointures),
            add_generation_prompt=True, return_tensors="pt")
        with torch.no_grad():
            sortie = modele.generate(
                entree,
                max_new_tokens=self.max_jetons,
                # Déterministe : une mesure qui varie d'un run à l'autre n'est
                # pas une mesure. Le protocole E6 a déjà coûté cette leçon.
                do_sample=False,
                temperature=None,
                top_p=None,
                top_k=None,
                pad_token_id=tokenizer.eos_token_id,
            )
        brut = tokenizer.decode(sortie[0][entree.shape[-1]:], skip_special_tokens=True)
        return analyser(brut)

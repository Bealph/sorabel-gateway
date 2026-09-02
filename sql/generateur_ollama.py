"""Génération SQL par un modèle servi par Ollama.

**Cette voie a été mesurée, et elle N'EST PAS retenue par défaut.** Ce module
reste dans le dépôt parce qu'il est la marche suivante de l'échelle de P5, et
qu'il faut pouvoir la remonter sans le réécrire.

Ce que j'attendais d'Ollama : `llama.cpp` quantifie, donc le même poste devait
servir un modèle bien plus gros, plus vite. **La mesure l'a démenti**, non pas à
cause d'Ollama mais à cause du matériel : le processeur de ce poste tombe à
801 MHz sur 2304 sous charge soutenue, et le 7B produit alors 0,38 jeton par
seconde. Le même appel a pris 30 secondes puis 208 selon l'échauffement.

Retenu à sa place : le petit modèle local via `transformers` (D48), et Azure AI
Foundry comme échelon suivant, dans le locataire du client plutôt que chez un
tiers. Voir chantier 2, section Q6.

Le motif « local » de P5 est préservé dans les deux cas : rien ne quitte le poste
tant qu'on n'utilise pas un modèle « -cloud ».

**Aucune dépendance ajoutée.** L'API d'Ollama est du JSON sur HTTP, et la
bibliothèque standard suffit. Ajouter un client pour trois champs serait une
dette pour rien.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from .generateur import CONSIGNE, EXEMPLES, analyser
from .service import Generation

MODELE_DEFAUT = "qwen2.5-coder:7b"
URL_DEFAUT = "http://localhost:11434"


class OllamaIndisponible(RuntimeError):
    """Le service ne répond pas. On le dit, on ne se rabat pas en silence.

    Un repli silencieux sur un modèle plus faible produirait des réponses de
    qualité différente sans que personne ne sache laquelle a répondu. Une mesure
    et un journal en deviendraient illisibles.
    """


class GenerateurOllama:
    """Modèle instruct servi localement. Une instance par processus."""

    def __init__(self, nom: str | None = None, url: str | None = None,
                 delai: float = 120.0) -> None:
        self.nom = nom or os.environ.get("SQL_MODEL", MODELE_DEFAUT)
        self.url = (url or os.environ.get("OLLAMA_URL", URL_DEFAUT)).rstrip("/")
        self.delai = delai

    def disponible(self) -> tuple[bool, str]:
        """Le service répond-il, et le modèle est-il chargé ? À vérifier au
        démarrage plutôt qu'au premier appel d'un utilisateur."""
        try:
            with urllib.request.urlopen(f"{self.url}/api/tags", timeout=5) as r:
                noms = {m["name"] for m in json.load(r).get("models", [])}
        except (urllib.error.URLError, OSError, ValueError) as e:
            return False, f"service Ollama injoignable sur {self.url} : {e}"
        if self.nom not in noms and f"{self.nom}:latest" not in noms:
            return False, (f"modele {self.nom!r} absent. Disponibles : "
                           f"{sorted(noms) or 'aucun'}. Lancer "
                           f"`ollama pull {self.nom}`.")
        return True, ""

    def prechauffer(self) -> None:
        """Demande à Ollama de charger le modèle et de le garder en mémoire.

        Même motif que côté `transformers`, en une requête au lieu d'un fil :
        c'est le service qui garde le modèle résident.
        """
        import threading

        def charger() -> None:
            corps = json.dumps({"model": self.nom, "prompt": "",
                                "keep_alive": "30m"}).encode("utf-8")
            requete = urllib.request.Request(
                f"{self.url}/api/generate", data=corps,
                headers={"Content-Type": "application/json"})
            try:
                urllib.request.urlopen(requete, timeout=self.delai).close()
            except (urllib.error.URLError, OSError):
                pass   # le prechauffage est un confort, jamais une condition

        threading.Thread(target=charger, daemon=True).start()

    def _messages(self, question: str, schema: str, jointures: tuple[str, ...]) -> list[dict]:
        contexte = f"{CONSIGNE}\n\nSCHEMA\n{schema}"
        if jointures:
            contexte += ("\n\nCHEMINS DE JOINTURE, les seuls du schema\n"
                         + "\n".join(f"  {j}" for j in jointures))
        messages = [{"role": "system", "content": contexte}]
        for demande, reponse in EXEMPLES:
            messages += [{"role": "user", "content": demande},
                         {"role": "assistant", "content": reponse}]
        messages.append({"role": "user", "content": question})
        return messages

    def generer(self, question: str, schema: str,
                jointures: tuple[str, ...]) -> Generation:
        corps = json.dumps({
            "model": self.nom,
            "messages": self._messages(question, schema, jointures),
            "stream": False,
            "options": {
                # Déterministe. Une mesure qui varie d'un run à l'autre n'est
                # pas une mesure : le protocole E6 a déjà coûté cette leçon,
                # et la recherche approchée de Chroma l'a coûtée une seconde fois.
                "temperature": 0,
                "seed": 1,
                "num_predict": 160,
                # La réponse tient sur une ligne : on arrête dès la suivante,
                # ce qui coupe les explications que le modèle ajoute volontiers.
                "stop": ["\n\n"],
            },
        }).encode("utf-8")

        requete = urllib.request.Request(
            f"{self.url}/api/chat", data=corps,
            headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(requete, timeout=self.delai) as r:
                reponse = json.load(r)
        except (urllib.error.URLError, OSError, ValueError) as e:
            raise OllamaIndisponible(
                f"generation impossible via {self.url} : {e}") from e

        return analyser((reponse.get("message") or {}).get("content", ""))

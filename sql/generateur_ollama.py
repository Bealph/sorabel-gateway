"""Génération SQL par un modèle servi par Ollama.

**Pourquoi cette voie, et sur quelle mesure.** Le premier générateur, un
Qwen2.5-Coder de 0,5 milliard de paramètres servi par `transformers` en float32,
a rendu 16 réponses justes sur 24. P5 prescrit de monter en gamme si le taux est
insuffisant : il l'est. La mesure a aussi montré que le **moteur** était en cause
autant que le modèle, un prompt de 1197 jetons demandant 32 secondes de seul
prefill. Ollama s'appuie sur `llama.cpp`, qui quantifie et vectorise : le même
poste peut alors servir un modèle quatorze fois plus gros, plus vite.

Le motif « local » de P5 est préservé : rien ne quitte le poste.

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

"""L'encodeur, partagé entre l'ingestion et la recherche.

Il vit ici, et pas dans `ingest/`, pour une raison précise : **les deux branches
d'E6 doivent utiliser le même modèle et la même convention de préfixe**. Si
l'ingestion encodait autrement que la recherche, la mesure du gain ne
comparerait plus rien.

Deux propriétés portent la conception :

- **Chargement paresseux.** La suite d'acceptance accorde 30 secondes par appel
  et lance un processus serveur neuf par session. Mesuré sur ce poste, importer
  torch puis charger le modèle prend 10 secondes à chaud et 22 à froid : payé au
  démarrage, cela mangerait le budget avant la première recherche. Le modèle se
  charge donc au premier encodage, et une fois seulement.
- **Préfixes.** Les modèles de la famille E5 sont entraînés avec `query:` devant
  une question et `passage:` devant un document. Les omettre dégrade le rappel
  sans rien signaler.
"""
from __future__ import annotations

import os
import re
from functools import cached_property

#: Défaut aligné sur `.env.example` du dépôt d'exercice. 384 dimensions,
#: multilingue, tient largement sur processeur à l'échelle de ce corpus :
#: mesuré à 910 chunks en 3 secondes.
MODELE_DEFAUT = "intfloat/multilingual-e5-small"

#: Un jeton garde ses tirets internes, pour que `REF-8842` reste UN terme.
#: Le découper en `ref` et `8842` priverait BM25 du signal le plus discriminant
#: du corpus, et E2 repose dessus.
JETON = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


def jetons(texte: str) -> list[str]:
    """Découpe pour l'index lexical. Volontairement simple et reproductible."""
    return JETON.findall(texte.lower())


class Encodeur:
    """Enveloppe le modèle. Une instance par processus suffit."""

    def __init__(self, nom: str | None = None) -> None:
        self.nom = nom or os.environ.get("EMBEDDING_MODEL", MODELE_DEFAUT)

    @cached_property
    def _modele(self):  # noqa: ANN202
        # Import différé : torch coûte plusieurs secondes, et un client qui ne
        # fait que du SQL n'a aucune raison de les payer.
        from sentence_transformers import SentenceTransformer

        return SentenceTransformer(self.nom)

    @property
    def dimension(self) -> int:
        return int(self._modele.get_sentence_embedding_dimension())

    def _encoder(self, textes: list[str], prefixe: str) -> list[list[float]]:
        vecteurs = self._modele.encode(
            [f"{prefixe}{t}" for t in textes],
            normalize_embeddings=True,   # cosinus = produit scalaire
            batch_size=32,
            show_progress_bar=False,
        )
        return [v.tolist() for v in vecteurs]

    def passages(self, textes: list[str]) -> list[list[float]]:
        return self._encoder(textes, "passage: ")

    def requete(self, texte: str) -> list[float]:
        return self._encoder([texte], "query: ")[0]

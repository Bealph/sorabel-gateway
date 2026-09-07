# Sorabel Data Gateway : l'interface du produit, prête à déployer.
#
# ETAT : construit UNIQUEMENT côté Azure, par `az acr build`. La virtualisation
# matérielle est désactivée au firmware de ce poste
# (VirtualizationFirmwareEnabled = False), donc le moteur Linux de Docker n'y
# démarre pas et ce fichier n'a jamais été construit en local.
#
# TROIS ECHECS REELS LE 2026-09-07, ET AUCUN LA OU JE L'ATTENDAIS
#
#   1. L'analyse de dépendances d'ACR ne comprend pas la syntaxe heredoc, et
#      lisait les lignes Python comme des instructions Dockerfile :
#      « unable to understand line from huggingface_hub import ... »
#      D'où les scripts de `deploy/`, plutôt que du Python en ligne.
#
#   2. Image à 12,63 Go, contre 10,74 Go de plafond sur le SKU Basic du
#      registre. Quota dépassé, et Container Apps rendait un
#      `ImagePullUnauthorized` qui ne disait rien de la vraie cause. Motif :
#      `uv.lock` épingle quinze paquets `nvidia-*` et `triton`, et la
#      réinstallation de torch en version processeur remplaçait torch SEUL.
#
#   3. Purge des paquets CUDA dans un `RUN` séparé : image à 14,83 Go, soit
#      PLUS GROSSE qu'avant. Les couches Docker sont **additives** : retirer
#      des fichiers dans une couche ultérieure n'efface pas celle qui les avait
#      ajoutés, cela empile un masque par-dessus. D'où l'étape unique de la
#      section 1, où installation, remplacement et purge tiennent dans **la
#      même couche**.
#
# L'étape que j'avais signalée comme la plus fragile n'a jamais échoué : elle a
# fait la moitié du travail, ce qui est plus sournois qu'un échec franc.
#
# Construire et déployer : deploy/azure.sh

# Le contrat impose >=3.11,<3.12. Ce n'est pas un confort : le dépôt amont
# épingle cette plage et la suite d'acceptance est jouée dessus.
FROM python:3.11-slim-bookworm

# Binaire officiel d'uv, plutôt qu'une installation par pip qui polluerait
# l'environnement du projet.
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /uvx /usr/local/bin/

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    # L'environnement du projet est nommé explicitement : les étapes suivantes
    # et la commande finale s'y adressent sans passer par `uv run`, qui
    # tenterait de resynchroniser à chaque appel.
    VIRTUAL_ENV=/app/.venv \
    PATH=/app/.venv/bin:$PATH \
    # Le cache Hugging Face est cuit dans l'image, à un chemin explicite. Sans
    # cela les modèles se téléchargeraient au premier appel, dans un stockage
    # éphémère : plusieurs minutes à chaque démarrage, et un échec silencieux
    # si le réseau sortant est fermé.
    HF_HOME=/opt/modeles \
    # D35 : tout artefact passe par ce chemin unique. Le stockage de conteneur
    # est éphémère par défaut, un index écrit ailleurs disparaîtrait au
    # redémarrage SANS erreur.
    SORABEL_DATA_DIR=/app/data \
    GATEWAY_JOURNAL=/app/logs/journal.jsonl

WORKDIR /app

# --- 1. Les dépendances, EN UNE SEULE COUCHE --------------------------------
# Les quatre opérations sont soudées, et ce n'est pas un raccourci d'écriture :
# séparées, la couche qui installe les quinze paquets CUDA reste dans l'image
# même après leur désinstallation, et l'image grossit au lieu de maigrir.
# Mesuré : 12,63 Go séparé, 14,83 Go avec une purge en couche distincte.
#
# `uv.lock` épingle la roue torch de PyPI, qui est la variante CUDA. Rien de ce
# que nous déployons n'a de GPU : D36 avait établi que les deux modèles
# critiques pour E6 tiennent sur processeur, et seule la génération SQL aurait
# profité d'un accélérateur.
COPY pyproject.toml uv.lock deploy/purger_cuda.py ./
RUN uv sync --frozen --no-install-project --extra vector --extra demo \
 && uv pip install --reinstall-package torch \
        --index-url https://download.pytorch.org/whl/cpu torch \
 && python purger_cuda.py \
 && uv cache clean \
 && rm -f purger_cuda.py

# --- 2. Les modèles, cuits dans l'image -------------------------------------
# Trois modèles, environ 1,9 Go : embeddings (471 Mo), reranking (470 Mo) et
# génération SQL (954 Mo). Cuits ici pour que le démarrage soit prévisible.
COPY deploy/telecharger_modeles.py /tmp/telecharger_modeles.py
RUN python /tmp/telecharger_modeles.py && rm -f /tmp/telecharger_modeles.py

# --- 3. Le projet et ses données --------------------------------------------
# `data/` porte l'index Chroma, la base SQLite et le corpus, environ 11 Mo.
COPY . /app
# `--no-deps` EST INDISPENSABLE ICI. Un `uv sync` reconcilierait l'environnement
# avec `uv.lock`, qui epingle la roue torch CUDA et les quinze paquets
# `nvidia-*` : il les REINSTALLERAIT tous et annulerait la purge de la section 1,
# en silence. On installe donc le projet seul, sans toucher aux dependances.
RUN uv pip install --no-deps . && mkdir -p /app/logs

# Le contrôle le moins cher et le plus utile : si la matrice ou l'oracle de
# gouvernance divergeaient de leur source, l'image ne se construirait pas.
# Mieux vaut échouer ici que devant l'évaluateur.
RUN python governance/verifier_matrice.py --verifier \
    && python eval/verifier_cas_mcp.py

# La taille finale, tracée dans le journal de construction. C'est le chiffre qui
# a fait échouer deux tentatives : autant le voir à chaque fois.
RUN du -sh /app/.venv /opt/modeles /app/data || true

EXPOSE 8501

# `--server.address=0.0.0.0` est indispensable derrière une entrée de
# conteneur : par défaut Streamlit n'écoute que localhost, l'ingress ne voit
# rien, et aucun message d'erreur ne le signale.
CMD ["streamlit", "run", "app.py", \
     "--server.port=8501", "--server.address=0.0.0.0", \
     "--server.headless=true", "--browser.gatherUsageStats=false"]

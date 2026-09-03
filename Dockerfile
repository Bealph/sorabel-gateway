# Sorabel Data Gateway : l'interface du produit, prête à déployer.
#
# HONNÊTETÉ SUR L'ÉTAT : ce fichier n'a JAMAIS été construit. La virtualisation
# matérielle est désactivée au firmware de ce poste
# (VirtualizationFirmwareEnabled = False), donc le moteur Linux de Docker n'y
# démarre pas. La première construction réelle sera celle d'`az acr build`, qui
# bâtit côté Azure et n'exige aucun Docker local. Tant qu'elle n'a pas tourné,
# ce fichier est une intention, pas un fait.
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

# --- 1. Les dépendances, en couche séparée pour rester en cache -------------
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --extra vector --extra demo

# torch arrive par défaut avec ses roues CUDA, soit environ 2,5 Go de pilotes
# inutiles : rien de ce que nous déployons n'a de GPU. D36 l'a établi, les deux
# modèles critiques pour E6 tiennent sur processeur, et seule la génération SQL
# aurait profité d'un accélérateur.
#
# C'EST L'ÉTAPE LA PLUS FRAGILE de ce fichier, parce qu'elle sort du verrou de
# `uv.lock` pour aller chercher une roue sur l'index PyTorch. Si la première
# construction échoue, c'est ici qu'il faut regarder d'abord.
RUN uv pip install --reinstall-package torch \
        --index-url https://download.pytorch.org/whl/cpu torch

# --- 2. Les modèles, cuits dans l'image -------------------------------------
# Trois modèles, environ 1,9 Go : embeddings (471 Mo), reranking (470 Mo) et
# génération SQL (954 Mo). Mesures relevées sur le cache local.
RUN python - <<'PY'
from huggingface_hub import snapshot_download
for depot in ("intfloat/multilingual-e5-small",
              "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1",
              "Qwen/Qwen2.5-Coder-0.5B-Instruct"):
    print(f"telechargement de {depot}", flush=True)
    snapshot_download(depot)
PY

# --- 3. Le projet et ses données --------------------------------------------
# `data/` porte l'index Chroma, la base SQLite et le corpus, environ 11 Mo.
COPY . /app
RUN uv sync --frozen --extra vector --extra demo && mkdir -p /app/logs

# Le contrôle le moins cher et le plus utile : si la matrice ou l'oracle de
# gouvernance divergeaient de leur source, l'image ne se construirait pas.
# Mieux vaut échouer ici que devant l'évaluateur.
RUN python governance/verifier_matrice.py --verifier \
    && python eval/verifier_cas_mcp.py

EXPOSE 8501

# `--server.address=0.0.0.0` est indispensable derrière une entrée de
# conteneur : par défaut Streamlit n'écoute que localhost, l'ingress ne voit
# rien, et aucun message d'erreur ne le signale.
CMD ["streamlit", "run", "app.py", \
     "--server.port=8501", "--server.address=0.0.0.0", \
     "--server.headless=true", "--browser.gatherUsageStats=false"]

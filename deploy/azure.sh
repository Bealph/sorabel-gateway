#!/usr/bin/env bash
# Déploie l'interface Sorabel sur Azure Container Apps.
#
#   bash deploy/azure.sh --a-vide     éprouve la chaîne, sans notre image
#   bash deploy/azure.sh              construit et déploie pour de bon
#   bash deploy/azure.sh --detruire   supprime tout le groupe de ressources
#
# POURQUOI LE MODE À VIDE EXISTE
# La revue de conception a relevé que la stratégie incrémentale (D37) reporte
# tout le risque de déploiement à la fin, et elle a fait de « éprouver la chaîne
# à vide » un critère de fin de lot, pas une recommandation. Le mode `--a-vide`
# déploie une image d'exemple de Microsoft : il valide l'authentification, le
# groupe, le registre, l'environnement, l'entrée publique et le nom de domaine,
# en quelques minutes et sans construire nos 3 Go. Si quelque chose doit casser,
# autant que ce soit là.
#
# CE SCRIPT N'A PAS ÉTÉ EXÉCUTÉ. Aucun compte Azure n'était connecté sur le
# poste au moment de l'écrire. Il est adossé à la documentation d'`az
# containerapp`, pas à une exécution.

set -euo pipefail

GROUPE="${SORABEL_GROUPE:-rg-sorabel-gateway}"
REGION="${SORABEL_REGION:-westeurope}"
REGISTRE="${SORABEL_REGISTRE:-acrsorabelgateway}"   # 5-50 car., minuscules et chiffres
ENVIRONNEMENT="${SORABEL_ENV:-env-sorabel}"
APPLICATION="${SORABEL_APP:-sorabel-gateway}"
IMAGE="sorabel-interface"
ETIQUETTE="$(git rev-parse --short HEAD 2>/dev/null || echo manuel)"

# 2 vCPU et 4 Gio : les trois modèles pèsent environ 1,9 Go sur disque, et le
# reranking est la seule étape réellement gourmande. Container Apps plafonne à
# 4 vCPU et 8 Gio par réplique.
CPU="${SORABEL_CPU:-2.0}"
MEMOIRE="${SORABEL_MEMOIRE:-4.0Gi}"

# UNE RÉPLIQUE AU MINIMUM, ET C'EST UN CHOIX QUI COÛTE. Avec `min-replicas 0`,
# Container Apps éteint l'application au repos : le réveil suppose alors de
# retirer une image de plusieurs gigaoctets puis de charger les modèles, soit
# plusieurs minutes pendant lesquelles un évaluateur qui clique voit une page
# qui ne répond pas. Une réplique toujours allumée est facturée en continu.
# Le mettre à 0 est légitime hors période de soutenance.
REPLIQUES_MIN="${SORABEL_REPLIQUES_MIN:-1}"

vert() { printf '\033[32m%s\033[0m\n' "$*"; }
gris() { printf '\033[90m%s\033[0m\n' "$*"; }
etape() { printf '\n\033[1m== %s\033[0m\n' "$*"; }

verifier_connexion() {
  if ! az account show >/dev/null 2>&1; then
    echo "Aucun compte Azure connecte. Lancer d'abord :" >&2
    echo "    az login" >&2
    exit 1
  fi
  local sub
  sub="$(az account show --query name -o tsv)"
  vert "abonnement : ${sub}"
}

detruire() {
  etape "Suppression du groupe ${GROUPE}"
  echo "Cela supprime le registre, l'environnement et l'application."
  read -r -p "Confirmer en tapant le nom du groupe : " saisie
  [ "$saisie" = "$GROUPE" ] || { echo "Abandon."; exit 1; }
  az group delete --name "$GROUPE" --yes --no-wait
  vert "suppression lancee, elle se poursuit en arriere-plan"
}

socle() {
  etape "Groupe de ressources"
  az group create --name "$GROUPE" --location "$REGION" -o none
  gris "  ${GROUPE} dans ${REGION}"

  etape "Extension containerapp"
  # L'extension n'est pas installee par defaut, et son absence produit une
  # erreur de commande inconnue, peu parlante.
  az extension add --name containerapp --upgrade --only-show-errors -o none
  az provider register --namespace Microsoft.App --wait -o none
  az provider register --namespace Microsoft.OperationalInsights --wait -o none

  etape "Environnement Container Apps"
  az containerapp env create --name "$ENVIRONNEMENT" --resource-group "$GROUPE" \
    --location "$REGION" -o none
  gris "  ${ENVIRONNEMENT}"
}

deployer_a_vide() {
  socle
  etape "Application d'essai, image d'exemple Microsoft"
  az containerapp create --name "${APPLICATION}-essai" --resource-group "$GROUPE" \
    --environment "$ENVIRONNEMENT" \
    --image mcr.microsoft.com/k8se/quickstart:latest \
    --target-port 80 --ingress external \
    --min-replicas 1 --max-replicas 1 -o none
  local url
  url="https://$(az containerapp show --name "${APPLICATION}-essai" \
        --resource-group "$GROUPE" --query properties.configuration.ingress.fqdn -o tsv)"
  vert "chaine eprouvee : ${url}"
  echo "Verifier que la page repond, puis supprimer l'essai :"
  echo "    az containerapp delete --name ${APPLICATION}-essai --resource-group ${GROUPE} --yes"
}

deployer() {
  socle

  etape "Registre de conteneurs"
  az acr create --name "$REGISTRE" --resource-group "$GROUPE" --sku Basic \
    --admin-enabled true -o none 2>/dev/null || gris "  ${REGISTRE} existe deja"

  etape "Construction de l'image, COTE AZURE"
  # `az acr build` televerse le contexte et construit sur un agent Azure. C'est
  # ce qui rend le deploiement possible depuis un poste ou la virtualisation est
  # coupee au firmware et ou aucun moteur Docker ne demarre.
  gris "  environ 1,9 Go de modeles sont telecharges pendant la construction ;"
  gris "  compter une dizaine de minutes au premier passage."
  az acr build --registry "$REGISTRE" --image "${IMAGE}:${ETIQUETTE}" \
    --image "${IMAGE}:latest" --file Dockerfile .

  etape "Deploiement"
  local serveur utilisateur motdepasse
  serveur="$(az acr show --name "$REGISTRE" --query loginServer -o tsv)"
  utilisateur="$(az acr credential show --name "$REGISTRE" --query username -o tsv)"
  motdepasse="$(az acr credential show --name "$REGISTRE" \
                --query 'passwords[0].value' -o tsv)"

  if az containerapp show --name "$APPLICATION" --resource-group "$GROUPE" \
       >/dev/null 2>&1; then
    az containerapp update --name "$APPLICATION" --resource-group "$GROUPE" \
      --image "${serveur}/${IMAGE}:${ETIQUETTE}" -o none
  else
    az containerapp create --name "$APPLICATION" --resource-group "$GROUPE" \
      --environment "$ENVIRONNEMENT" \
      --image "${serveur}/${IMAGE}:${ETIQUETTE}" \
      --registry-server "$serveur" \
      --registry-username "$utilisateur" \
      --registry-password "$motdepasse" \
      --target-port 8501 --ingress external \
      --cpu "$CPU" --memory "$MEMOIRE" \
      --min-replicas "$REPLIQUES_MIN" --max-replicas 1 \
      --env-vars SORABEL_DATA_DIR=/app/data \
                 GATEWAY_JOURNAL=/app/logs/journal.jsonl \
      -o none
  fi

  # UNE SEULE REPLIQUE AU MAXIMUM, ET CE N'EST PAS UN OUBLI. Le journal est un
  # fichier local au conteneur : deux repliques tiendraient deux journaux
  # differents, et la page « journal partage » cesserait de dire vrai. Passer a
  # l'echelle demanderait un stockage partage, ce que D33 n'a pas prevu.

  local url
  url="https://$(az containerapp show --name "$APPLICATION" --resource-group "$GROUPE" \
        --query properties.configuration.ingress.fqdn -o tsv)"
  etape "Deploye"
  vert "$url"
  echo
  echo "Premier affichage : compter une trentaine de secondes, les modeles se"
  echo "chargent a la demande. Suivre le demarrage :"
  echo "    az containerapp logs show --name ${APPLICATION} --resource-group ${GROUPE} --follow"
}

case "${1:-}" in
  --a-vide)   verifier_connexion; deployer_a_vide ;;
  --detruire) verifier_connexion; detruire ;;
  "")         verifier_connexion; deployer ;;
  *)          sed -n '2,10p' "$0"; exit 1 ;;
esac

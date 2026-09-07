#!/usr/bin/env bash
# Déploie l'interface Sorabel sur Azure Container Apps.
#
#   bash deploy/azure.sh --controles   verifie les droits, ne cree RIEN
#   bash deploy/azure.sh --a-vide      eprouve la chaine avec une image d'exemple
#   bash deploy/azure.sh               construit et deploie pour de bon
#   bash deploy/azure.sh --slack       deploie l'application Slack (A1)
#   bash deploy/azure.sh --detruire    supprime ce que ce script a cree
#
# POURQUOI LE MODE À VIDE EXISTE
# La revue de conception a relevé que la stratégie incrémentale (D37) reporte
# tout le risque de déploiement à la fin, et elle a fait de « éprouver la chaîne
# à vide » un critère de fin de lot, pas une recommandation. Le mode `--a-vide`
# déploie une image d'exemple de Microsoft : il valide l'authentification, le
# groupe, le registre, l'environnement et l'entrée publique en quelques minutes,
# sans construire nos 3 Go. Si quelque chose doit casser, autant que ce soit là.
#
# LES DROITS RÉELS, RELEVÉS LE 2026-09-07, ET CE QU'ILS CHANGENT
# Le compte est **`Reader` sur l'abonnement** et **`Owner` sur le seul groupe
# `adialloRG`**. Deux conséquences, qui ont fait réécrire ce script :
#
#   - `az group create` échouerait. On DÉPLOIE DONC DANS UN GROUPE EXISTANT,
#     et le script vérifie qu'il existe au lieu de le créer.
#   - `az provider register` échouerait aussi, faute d'écriture sur
#     l'abonnement. Heureusement les trois fournisseurs nécessaires sont déjà
#     enregistrés : Microsoft.App, Microsoft.ContainerRegistry et
#     Microsoft.OperationalInsights. Le script le VÉRIFIE et s'arrête avec un
#     message clair sinon, au lieu d'échouer à mi-parcours.
#
# Un groupe de ressources peut contenir des ressources d'autres régions que la
# sienne : `adialloRG` est en `francecentral`, et c'est la région retenue.

set -euo pipefail

# LE CLI AZURE S'ECRASE EN AFFICHANT LES JOURNAUX SUR CETTE CONSOLE, et c'est
# arrive pour de vrai le 2026-09-07 :
#   UnicodeEncodeError: 'charmap' codec can't encode characters
# La console Windows est en cp1252 et `uv` emet des symboles Unicode dans ses
# journaux de construction. La construction, elle, se poursuivait cote Azure :
# seul l'AFFICHAGE etait mort, et le script s'arretait donc sur un succes.
export PYTHONIOENCODING=utf-8
export PYTHONUTF8=1

GROUPE="${SORABEL_GROUPE:-adialloRG}"           # EXISTANT, non cree par ce script
REGION="${SORABEL_REGION:-francecentral}"
REGISTRE="${SORABEL_REGISTRE:-acrsorabelgateway}"   # 5-50 car., minuscules et chiffres
ENVIRONNEMENT="${SORABEL_ENV:-env-sorabel}"
APPLICATION="${SORABEL_APP:-sorabel-gateway}"
IMAGE="sorabel-interface"
ETIQUETTE="$(git rev-parse --short HEAD 2>/dev/null || echo manuel)"

#: Les fournisseurs sans lesquels rien ne se cree, et que nous ne pouvons PAS
#: enregistrer nous-memes faute de droit sur l'abonnement.
FOURNISSEURS=(Microsoft.App Microsoft.ContainerRegistry Microsoft.OperationalInsights)

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
# La mettre à 0 est légitime hors période de soutenance.
REPLIQUES_MIN="${SORABEL_REPLIQUES_MIN:-1}"

# L'application Slack tourne dans la MEME image : tout est sous /app, et
# seule la commande de demarrage change. Construire une seconde image
# doublerait les 6 Go et le temps de construction pour rien.
# Elle appelle la gateway, donc elle charge les memes modeles : la memoire
# mesuree du conteneur d'interface est de 2,5 Gio, d'ou 3 Gio ici.
APPLICATION_SLACK="${SORABEL_APP_SLACK:-sorabel-slack}"
CPU_SLACK="${SORABEL_CPU_SLACK:-1.5}"
MEMOIRE_SLACK="${SORABEL_MEMOIRE_SLACK:-3.0Gi}"

vert() { printf '\033[32m%s\033[0m\n' "$*"; }
rouge() { printf '\033[31m%s\033[0m\n' "$*"; }
gris() { printf '\033[90m%s\033[0m\n' "$*"; }
etape() { printf '\n\033[1m== %s\033[0m\n' "$*"; }

# --- contrôles préalables, tous en LECTURE SEULE -----------------------------
controles() {
  local souci=0

  etape "Compte connecte"
  if ! az account show >/dev/null 2>&1; then
    rouge "aucun compte Azure connecte. Lancer :"
    echo "    az login --use-device-code"
    gris "  Le flux par code evite la boite de dialogue Windows d'inscription"
    gris "  MDM, qui echoue sur ce poste et n'a rien a voir avec Azure CLI."
    return 1
  fi
  vert "  $(az account show --query name -o tsv)"
  gris "  utilisateur : $(az account show --query user.name -o tsv)"

  etape "Groupe de ressources ${GROUPE}"
  if az group show --name "$GROUPE" -o none 2>/dev/null; then
    vert "  existe, region $(az group show --name "$GROUPE" --query location -o tsv)"
  else
    rouge "  ${GROUPE} introuvable."
    gris "  Ce script ne CREE PAS de groupe : le compte n'a que le role Reader"
    gris "  sur l'abonnement. Passer un groupe existant par SORABEL_GROUPE."
    souci=1
  fi

  etape "Fournisseurs de ressources"
  for ns in "${FOURNISSEURS[@]}"; do
    local etat
    etat="$(az provider show --namespace "$ns" --query registrationState -o tsv 2>/dev/null || echo inconnu)"
    if [ "$etat" = "Registered" ]; then
      gris "  ${ns} : ${etat}"
    else
      rouge "  ${ns} : ${etat}"
      gris "    Ce script ne peut pas l'enregistrer : cela demande un droit"
      gris "    d'ecriture sur l'abonnement, et le compte est Reader. Demander"
      gris "    a l'administrateur : az provider register --namespace ${ns}"
      souci=1
    fi
  done

  etape "Nom du registre ${REGISTRE}"
  local libre
  libre="$(az acr check-name --name "$REGISTRE" --query nameAvailable -o tsv 2>/dev/null || echo inconnu)"
  if [ "$libre" = "true" ]; then
    vert "  disponible"
  elif az acr show --name "$REGISTRE" --resource-group "$GROUPE" -o none 2>/dev/null; then
    vert "  deja a nous, dans ${GROUPE}"
  else
    rouge "  indisponible, et pas dans notre groupe : un nom de registre est"
    rouge "  unique dans tout Azure. En choisir un autre par SORABEL_REGISTRE."
    souci=1
  fi

  etape "Extension containerapp"
  if az extension show --name containerapp -o none 2>/dev/null; then
    gris "  installee"
  else
    gris "  absente, elle sera installee (local, aucun droit Azure requis)"
  fi

  if [ "$souci" -ne 0 ]; then
    rouge $'\nDes controles ont echoue. Rien n\'a ete cree.'
    return 1
  fi
  vert $'\nTous les controles passent. Le deploiement peut etre tente.'
  return 0
}

socle() {
  controles || exit 1

  etape "Extension containerapp"
  # Son absence produit une erreur de commande inconnue, peu parlante.
  az extension add --name containerapp --upgrade --only-show-errors -o none

  etape "Environnement Container Apps"
  if az containerapp env show --name "$ENVIRONNEMENT" --resource-group "$GROUPE" \
       -o none 2>/dev/null; then
    gris "  ${ENVIRONNEMENT} existe deja"
  else
    az containerapp env create --name "$ENVIRONNEMENT" --resource-group "$GROUPE" \
      --location "$REGION" -o none
    vert "  ${ENVIRONNEMENT} cree dans ${REGION}"
  fi
}

deployer_a_vide() {
  socle
  etape "Application d'essai, image d'exemple Microsoft"
  local nom="${APPLICATION}-essai"
  az containerapp create --name "$nom" --resource-group "$GROUPE" \
    --environment "$ENVIRONNEMENT" \
    --image mcr.microsoft.com/k8se/quickstart:latest \
    --target-port 80 --ingress external \
    --min-replicas 1 --max-replicas 1 -o none
  local url
  url="https://$(az containerapp show --name "$nom" --resource-group "$GROUPE" \
        --query properties.configuration.ingress.fqdn -o tsv)"
  vert "chaine eprouvee : ${url}"
  echo
  echo "Verifier que la page repond, puis supprimer l'essai :"
  echo "    az containerapp delete --name ${nom} --resource-group ${GROUPE} --yes"
}

deployer() {
  socle

  etape "Registre de conteneurs"
  if az acr show --name "$REGISTRE" --resource-group "$GROUPE" -o none 2>/dev/null; then
    gris "  ${REGISTRE} existe deja"
  else
    az acr create --name "$REGISTRE" --resource-group "$GROUPE" --sku Basic \
      --admin-enabled true -o none
    vert "  ${REGISTRE} cree"
  fi

  etape "Construction de l'image, COTE AZURE"
  # `az acr build` televerse le contexte et construit sur un agent Azure. C'est
  # ce qui rend le deploiement possible depuis un poste ou la virtualisation est
  # coupee au firmware et ou aucun moteur Docker ne demarre.
  gris "  contexte mesure a 10,4 Mo grace au .dockerignore ;"
  gris "  environ 1,9 Go de modeles sont telecharges pendant la construction,"
  gris "  compter une dizaine de minutes au premier passage."
  # `--no-logs` attend la fin SANS diffuser les journaux. C'est ce flux
  # qui a fait tomber le CLI : le supprimer ote la cause au lieu de la
  # contourner. En cas d'echec, les journaux se relisent par run.
  if ! az acr build --registry "$REGISTRE" --image "${IMAGE}:${ETIQUETTE}" \
       --image "${IMAGE}:latest" --file Dockerfile --no-logs . ; then
    rouge "  Construction en echec. Relire les journaux :"
    echo "    az acr task list-runs --registry ${REGISTRE} --top 3 -o table"
    echo "    az acr task logs --registry ${REGISTRE} --run-id <ID>"
    exit 1
  fi

  etape "Deploiement"
  local serveur utilisateur motdepasse
  serveur="$(az acr show --name "$REGISTRE" --query loginServer -o tsv)"
  utilisateur="$(az acr credential show --name "$REGISTRE" --query username -o tsv)"
  motdepasse="$(az acr credential show --name "$REGISTRE" \
                --query 'passwords[0].value' -o tsv)"

  if az containerapp show --name "$APPLICATION" --resource-group "$GROUPE" \
       -o none 2>/dev/null; then
    az containerapp update --name "$APPLICATION" --resource-group "$GROUPE" \
      --image "${serveur}/${IMAGE}:${ETIQUETTE}" -o none
  else
    # UNE SEULE REPLIQUE AU MAXIMUM, ET CE N'EST PAS UN OUBLI. Le journal est un
    # fichier local au conteneur : deux repliques tiendraient deux journaux
    # differents, et l'ecran « journal partage » cesserait de dire vrai. Passer
    # a l'echelle demanderait un stockage partage, que D33 n'a pas prevu.
    az containerapp create --name "$APPLICATION" --resource-group "$GROUPE" \
      --environment "$ENVIRONNEMENT" \
      --image "${serveur}/${IMAGE}:${ETIQUETTE}" \
      --registry-server "$serveur" \
      --registry-username "$utilisateur" \
      --registry-password "$motdepasse" \
      --target-port 8501 --ingress external \
      --cpu "$CPU" --memory "$MEMOIRE" \
      --min-replicas "$REPLIQUES_MIN" --max-replicas 1 \
      -o none
    # AUCUN --env-vars ICI, ET C'EST UNE CORRECTION.
    # Le Dockerfile pose deja SORABEL_DATA_DIR=/app/data et
    # GATEWAY_JOURNAL=/app/logs/journal.jsonl. Les repasser depuis Git Bash les
    # CORROMPT : MSYS convertit tout argument ressemblant a un chemin POSIX en
    # chemin Windows, et le conteneur recevait
    #   SORABEL_DATA_DIR=C:/Program Files/Git/app/data
    # L'application demarrait, servait ses pages, et echouait a la premiere
    # question documentaire sur un InvalidCollectionException de Chroma, qui ne
    # nommait pas la cause. Constate en production le 2026-09-07.
    # Pour surcharger un chemin ici, prefixer la commande de MSYS_NO_PATHCONV=1.
  fi

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

deployer_slack() {
  socle

  etape "Image"
  local serveur utilisateur motdepasse
  serveur="$(az acr show --name "$REGISTRE" --query loginServer -o tsv)"
  if ! az acr repository show-tags --name "$REGISTRE" \
         --repository "$IMAGE" -o tsv 2>/dev/null | grep -q .; then
    rouge "  aucune image dans ${REGISTRE}. Lancer d'abord : bash deploy/azure.sh"
    exit 1
  fi
  gris "  ${serveur}/${IMAGE}:latest"
  utilisateur="$(az acr credential show --name "$REGISTRE" --query username -o tsv)"
  motdepasse="$(az acr credential show --name "$REGISTRE" \
                --query 'passwords[0].value' -o tsv)"

  etape "Application Slack"
  # PAS DE -m ICI : un argument qui commence par un tiret est pris par
  # az pour une option, et il rend "unrecognized arguments". Le chemin
  # est RELATIF, car MSYS convertit tout argument ressemblant a un chemin
  # POSIX en chemin Windows, defaut qui a deja casse le premier
  # deploiement de l interface. WORKDIR vaut /app dans l image.
  # LES DEUX SECRETS NE SONT PAS PASSES ICI, ET C'EST DELIBERE. Un secret en
  # argument de ligne de commande finit dans l'historique du shell et dans les
  # journaux d'audit d'Azure. Ils se posent apres, par `az containerapp secret
  # set`, et la commande exacte est affichee a la fin.
  #
  # Sans SLACK_SIGNING_SECRET, le service demarre et REFUSE tout : c'est le bon
  # comportement pour un point d'entree public, et cela permet de deployer
  # avant que l'application Slack existe.
  if az containerapp show --name "$APPLICATION_SLACK" \
       --resource-group "$GROUPE" -o none 2>/dev/null; then
    az containerapp update --name "$APPLICATION_SLACK" --resource-group "$GROUPE" \
      --image "${serveur}/${IMAGE}:latest" -o none
    gris "  ${APPLICATION_SLACK} mise a jour"
  else
    az containerapp create --name "$APPLICATION_SLACK" --resource-group "$GROUPE" \
      --environment "$ENVIRONNEMENT" \
      --image "${serveur}/${IMAGE}:latest" \
      --registry-server "$serveur" \
      --registry-username "$utilisateur" \
      --registry-password "$motdepasse" \
      --command "python" --args "slack_app/serveur.py" \
      --target-port 8080 --ingress external \
      --cpu "$CPU_SLACK" --memory "$MEMOIRE_SLACK" \
      --min-replicas 1 --max-replicas 1 \
      -o none
    vert "  ${APPLICATION_SLACK} creee"
  fi

  local url
  url="https://$(az containerapp show --name "$APPLICATION_SLACK" \
        --resource-group "$GROUPE" \
        --query properties.configuration.ingress.fqdn -o tsv)"
  etape "Deploye"
  vert "  point d'entree Slack : ${url}/slack/events"
  gris "  sonde de sante       : ${url}/sante"
  echo
  echo "IL RESTE DEUX SECRETS A POSER, et vous seul devez les manipuler :"
  echo
  echo "  az containerapp secret set --name ${APPLICATION_SLACK} \\"
  echo "    --resource-group ${GROUPE} \\"
  echo "    --secrets slack-signing=LE_SIGNING_SECRET slack-token=xoxb-LE_TOKEN"
  echo
  echo "  az containerapp update --name ${APPLICATION_SLACK} \\"
  echo "    --resource-group ${GROUPE} \\"
  echo "    --set-env-vars SLACK_SIGNING_SECRET=secretref:slack-signing \\"
  echo "                   SLACK_BOT_TOKEN=secretref:slack-token"
  echo
  gris "Tant qu'ils manquent, le service repond mais REFUSE toute requete."
}


detruire() {
  # On ne supprime PAS le groupe : il ne nous appartient pas, il est partage et
  # il portait des ressources avant nous. On retire seulement ce que ce script
  # a cree, nomme par nomme.
  etape "Suppression de ce que ce script a cree, dans ${GROUPE}"
  echo "  applications ${APPLICATION}, ${APPLICATION}-essai, ${APPLICATION_SLACK}"
  echo "  environnement ${ENVIRONNEMENT}"
  echo "  registre     ${REGISTRE}"
  rouge "  Le groupe ${GROUPE} n'est PAS touche : il est partage."
  read -r -p "Confirmer en tapant le nom de l'application : " saisie
  [ "$saisie" = "$APPLICATION" ] || { echo "Abandon."; exit 1; }
  for nom in "$APPLICATION" "${APPLICATION}-essai" "$APPLICATION_SLACK"; do
    az containerapp delete --name "$nom" --resource-group "$GROUPE" --yes \
      -o none 2>/dev/null || gris "  ${nom} absente"
  done
  az containerapp env delete --name "$ENVIRONNEMENT" --resource-group "$GROUPE" \
    --yes -o none 2>/dev/null || gris "  ${ENVIRONNEMENT} absent"
  az acr delete --name "$REGISTRE" --resource-group "$GROUPE" --yes \
    -o none 2>/dev/null || gris "  ${REGISTRE} absent"
  vert "  fait"
}

case "${1:-}" in
  --controles) controles ;;
  --a-vide)    deployer_a_vide ;;
  --slack)     deployer_slack ;;
  --detruire)  detruire ;;
  "")          deployer ;;
  *)           sed -n '3,7p' "$0"; exit 1 ;;
esac

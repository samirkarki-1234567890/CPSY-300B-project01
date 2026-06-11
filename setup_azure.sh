#!/usr/bin/env bash
# One-shot Azure setup for the diet-analytics backend.
# Run this once on YOUR OWN Azure subscription (Azure for Students is fine).
# It provisions everything, captures the connection strings, and writes them
# into azure_function/local.settings.json and setenv.sh so you can run or
# deploy without copying any secrets by hand.
#
# Usage:
#   az login
#   bash setup_azure.sh                 # provision + write settings
#   bash setup_azure.sh --deploy        # also publish the Function App
#
# Requires: Azure CLI (az). For --deploy also Azure Functions Core Tools (func).

set -euo pipefail

LOC="${LOC:-canadacentral}"
RG="${RG:-diet-rg}"
SUFFIX="${SUFFIX:-$RANDOM}"
STORAGE="dietstore${SUFFIX}"
COSMOS="dietcosmos${SUFFIX}"
FUNCAPP="diet-func-${SUFFIX}"
DEPLOY="no"
[ "${1:-}" = "--deploy" ] && DEPLOY="yes"

echo ">> Resource group: $RG ($LOC)"
az group create -n "$RG" -l "$LOC" -o none

echo ">> Storage account: $STORAGE"
az storage account create -n "$STORAGE" -g "$RG" -l "$LOC" --sku Standard_LRS -o none
STORAGE_CONN="$(az storage account show-connection-string -n "$STORAGE" -g "$RG" -o tsv)"
az storage container create --name datasets \
  --connection-string "$STORAGE_CONN" -o none
echo "   container 'datasets' ready"

echo ">> Cosmos DB: $COSMOS (this one takes a few minutes)"
az cosmosdb create -n "$COSMOS" -g "$RG" -o none
az cosmosdb sql database create -a "$COSMOS" -g "$RG" -n diet_analytics -o none
az cosmosdb sql container create -a "$COSMOS" -g "$RG" -d diet_analytics \
  -n nutrition_results --partition-key-path /diet_type -o none
COSMOS_CONN="$(az cosmosdb keys list -n "$COSMOS" -g "$RG" \
  --type connection-strings --query 'connectionStrings[0].connectionString' -o tsv)"
echo "   database 'diet_analytics' / container 'nutrition_results' ready"

# Write local settings for the Function App (gitignored, holds secrets)
cat > azure_function/local.settings.json <<JSON
{
  "IsEncrypted": false,
  "Values": {
    "AzureWebJobsStorage": "${STORAGE_CONN}",
    "FUNCTIONS_WORKER_RUNTIME": "python",
    "DATA_STORAGE": "${STORAGE_CONN}",
    "COSMOS_CONNECTION_STRING": "${COSMOS_CONN}",
    "CONTAINER": "datasets",
    "BLOB_NAME": "All_Diets.csv"
  }
}
JSON

# Write an env file for the CLI (gitignored)
cat > setenv.sh <<ENV
# source this before running lambda_function.py:  source setenv.sh
export AZURE_STORAGE_CONNECTION_STRING="${STORAGE_CONN}"
export COSMOS_CONNECTION_STRING="${COSMOS_CONN}"
export CONTAINER="datasets"
export BLOB_NAME="All_Diets.csv"
ENV

echo
echo ">> Wrote azure_function/local.settings.json and setenv.sh (both gitignored)."
echo

if [ "$DEPLOY" = "yes" ]; then
  echo ">> Creating Function App: $FUNCAPP"
  az functionapp create -g "$RG" -n "$FUNCAPP" \
    --storage-account "$STORAGE" --consumption-plan-location "$LOC" \
    --runtime python --runtime-version 3.11 --functions-version 4 --os-type Linux -o none
  az functionapp config appsettings set -g "$RG" -n "$FUNCAPP" --settings \
    DATA_STORAGE="$STORAGE_CONN" COSMOS_CONNECTION_STRING="$COSMOS_CONN" -o none
  echo ">> Publishing code..."
  ( cd azure_function && func azure functionapp publish "$FUNCAPP" )
  echo ">> Function App live: https://${FUNCAPP}.azurewebsites.net"
fi

echo
echo "=================  NEXT STEPS  ================="
echo "Run without deploying (fastest):"
echo "  pip install -r requirements.txt"
echo "  source setenv.sh"
echo "  python3 lambda_function.py --upload"
echo "  python3 lambda_function.py --run"
echo
echo "Then open the Cosmos DB Data Explorer in the portal and view the"
echo "'nutrition_results' documents."
echo
echo "Resource group is '$RG'. Delete everything when done:"
echo "  az group delete -n $RG --yes --no-wait"
echo "================================================"

# Backend handoff - deploying the Azure side

Hey, my Azure subscription is giving me trouble, so could you stand this up on
yours? The code is done and tested. You should not need anything from me, just
your own Azure for Students login. No credentials to copy from me.

## What you need
- `az login` working (Azure CLI)
- Python 3.11 and `pip`
- For the full Function App deploy: Azure Functions Core Tools (`func`)

## Easiest path (about 5 minutes, no deploy)

```bash
az login
bash setup_azure.sh            # provisions storage + cosmos on YOUR subscription
pip install -r requirements.txt
source setenv.sh               # loads the connection strings the script generated
python3 lambda_function.py --upload    # puts All_Diets.csv into Blob Storage
python3 lambda_function.py --run        # processes it, writes results to Cosmos DB
```

`setup_azure.sh` creates the resource group, storage account, blob container,
Cosmos DB database and container, then writes the two connection strings into
`setenv.sh` and `azure_function/local.settings.json` automatically. You never
paste a secret by hand.

After `--run`, open the Cosmos DB Data Explorer in the Azure portal and you will
see the `nutrition_results` container with one document per diet type. Screenshot
that for the report.

## Full path (deploy the real Function App with the blob trigger)

```bash
az login
bash setup_azure.sh --deploy   # same as above, plus creates + publishes the Function App
```

Then uploading the CSV to the `datasets` container fires the function
automatically. You can watch it under the function's Monitor tab in the portal.

## Important
- Do not commit `setenv.sh` or `azure_function/local.settings.json`. They hold
  live keys. The included `.gitignore` already blocks them, just do not force-add.
- When we are done with screenshots, tear it all down so it stops using credit:
  `az group delete -n diet-rg --yes --no-wait`

## If you want to use shared resources instead
If for some reason you would rather point at one shared set of resources, the
only two values that matter are AZURE_STORAGE_CONNECTION_STRING and
COSMOS_CONNECTION_STRING. Send them over a private channel (DM, not the repo),
and regenerate the keys in the portal afterward. But running setup_azure.sh on
your own subscription is simpler and avoids all of that.

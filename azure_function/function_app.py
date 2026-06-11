"""
function_app.py  -  Task 3: real Azure Function (Python v2 model)

Two ways the function runs:

  1. Blob trigger (process_on_upload):
     Fires automatically when All_Diets.csv is written to the 'datasets'
     container. This is the real event-driven binding that replaces the old
     local watchdog simulation.

  2. HTTP trigger (process_http):
     Manual on-demand run. Reads the blob itself, processes, writes Cosmos.
     Handy for demos and screenshots without re-uploading the file.

Both call the shared compute in insights.py and store one document per diet
type in Cosmos DB.

App settings required (Function App > Configuration, or local.settings.json):
  DATA_STORAGE               connection string for the storage account
  COSMOS_CONNECTION_STRING   connection string for the Cosmos DB account
"""

import json
import logging
import os

import azure.functions as func
from azure.storage.blob import BlobServiceClient

from insights import compute_insights, write_to_cosmos

app = func.FunctionApp()

CONTAINER = os.environ.get("CONTAINER", "datasets")
BLOB_NAME = os.environ.get("BLOB_NAME", "All_Diets.csv")


@app.blob_trigger(arg_name="blob",
                  path=f"{CONTAINER}/{BLOB_NAME}",
                  connection="DATA_STORAGE")
def process_on_upload(blob: func.InputStream):
    """Runs automatically when the dataset lands in Blob Storage."""
    logging.info("Blob trigger fired: %s (%s bytes)", blob.name, blob.length)
    result = compute_insights(blob.read(), source=f"blob://{blob.name}")
    count = write_to_cosmos(result)
    logging.info("Stored %d documents in Cosmos. Highest protein: %s",
                 count, result["summary"]["highest_protein_diet"])


@app.route(route="process", auth_level=func.AuthLevel.FUNCTION)
def process_http(req: func.HttpRequest) -> func.HttpResponse:
    """Manual invocation: GET/POST /api/process?code=<function key>."""
    try:
        svc = BlobServiceClient.from_connection_string(os.environ["DATA_STORAGE"])
        blob = svc.get_blob_client(container=CONTAINER, blob=BLOB_NAME)
        data = blob.download_blob().readall()

        result = compute_insights(data, source=f"blob://{CONTAINER}/{BLOB_NAME}")
        count = write_to_cosmos(result)

        body = {"documents_written": count, **result["summary"]}
        return func.HttpResponse(json.dumps(body, indent=2),
                                 mimetype="application/json", status_code=200)
    except Exception as e:
        logging.exception("process_http failed")
        return func.HttpResponse(f"Error: {e}", status_code=500)

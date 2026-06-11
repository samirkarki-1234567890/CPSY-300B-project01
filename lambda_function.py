"""
lambda_function.py  -  CLI helper for the real-Azure backend (Task 3)

This is the easy way to seed Blob Storage and run the processing on demand,
without deploying the Function App. It shares the exact same compute and Cosmos
logic as the deployed function (azure_function/insights.py), so a local run and a
triggered run produce identical documents.

Commands:
  python3 lambda_function.py --upload    push All_Diets.csv to the blob container
  python3 lambda_function.py --run       read the blob, compute, write to Cosmos

Environment (real Azure, no emulator):
  AZURE_STORAGE_CONNECTION_STRING   storage account connection string
  COSMOS_CONNECTION_STRING          cosmos db connection string
  CONTAINER                         blob container name   (default: datasets)
  BLOB_NAME                         blob file name        (default: All_Diets.csv)
"""

import argparse
import json
import os
import sys
from datetime import datetime

from azure.storage.blob import BlobServiceClient

# reuse the function's compute so local and deployed paths can never drift
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "azure_function"))
from insights import compute_insights, write_to_cosmos  # noqa: E402

CONTAINER = os.environ.get("CONTAINER", "datasets")
BLOB_NAME = os.environ.get("BLOB_NAME", "All_Diets.csv")


def stamp(msg):
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}")


def _storage_client():
    conn = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    if not conn:
        sys.exit("ERROR: set AZURE_STORAGE_CONNECTION_STRING to your storage "
                 "account connection string.")
    return BlobServiceClient.from_connection_string(conn)


def upload_csv(local_path="All_Diets.csv"):
    if not os.path.exists(local_path):
        sys.exit(f"ERROR: {local_path} not found to upload.")
    svc = _storage_client()
    try:
        svc.create_container(CONTAINER)
        stamp(f"Created container '{CONTAINER}'")
    except Exception:
        stamp(f"Container '{CONTAINER}' already exists")
    blob = svc.get_blob_client(container=CONTAINER, blob=BLOB_NAME)
    with open(local_path, "rb") as f:
        blob.upload_blob(f, overwrite=True)
    stamp(f"Uploaded {local_path} -> {CONTAINER}/{BLOB_NAME} in Azure Blob Storage")
    stamp("If the Function App is deployed, this upload also fires its blob trigger.")


def run_once():
    svc = _storage_client()
    stamp(f"Reading blob {CONTAINER}/{BLOB_NAME} from Azure Blob Storage...")
    data = svc.get_blob_client(container=CONTAINER, blob=BLOB_NAME).download_blob().readall()

    result = compute_insights(data, source=f"blob://{CONTAINER}/{BLOB_NAME}")
    count = write_to_cosmos(result)
    stamp(f"Wrote {count} documents to Cosmos DB "
          f"({os.environ.get('COSMOS_DATABASE', 'diet_analytics')}."
          f"{os.environ.get('COSMOS_CONTAINER', 'nutrition_results')})")
    print(json.dumps(result["summary"], indent=2))
    return result


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Real-Azure backend CLI")
    ap.add_argument("--upload", action="store_true", help="upload CSV to Blob Storage")
    ap.add_argument("--run", action="store_true", help="read blob, compute, write Cosmos")
    args = ap.parse_args()

    if args.upload:
        upload_csv()
    if args.run:
        run_once()
    if not (args.upload or args.run):
        ap.print_help()

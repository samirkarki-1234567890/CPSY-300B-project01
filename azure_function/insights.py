"""
insights.py  -  shared backend logic (real Azure)

Pure functions used by both:
  - function_app.py  (the deployed Azure Function: Blob trigger + HTTP trigger)
  - ../lambda_function.py  (a CLI for seeding the blob and running on demand)

compute_insights() turns raw CSV bytes into a result with one document per diet
type, ready to upsert into Cosmos DB. write_to_cosmos() persists those documents.
Keeping these separate from the trigger code means the same logic runs whether it
is invoked by a real blob event, an HTTP request, or the command line.
"""

import io
import os
from datetime import datetime, timezone

import pandas as pd

MACROS = ["Protein(g)", "Carbs(g)", "Fat(g)"]


def _normalize(df):
    """Map header variants ('Protein (g)' etc.) to the names we expect."""
    fix = {}
    for col in df.columns:
        key = col.strip().lower().replace(" ", "")
        fix[col] = {
            "diet_type": "Diet_type", "cuisine_type": "Cuisine_type",
            "protein(g)": "Protein(g)", "carbs(g)": "Carbs(g)", "fat(g)": "Fat(g)",
        }.get(key, col)
    return df.rename(columns=fix)


def compute_insights(csv_bytes, source):
    """Take raw CSV bytes, return a result dict:
        {
          "summary":   {generated_at, source, total_recipes, highest_protein_diet},
          "documents": [ one Cosmos-ready item per diet type ]
        }
    """
    df = _normalize(pd.read_csv(io.BytesIO(csv_bytes)))
    df["Diet_type"] = df["Diet_type"].astype(str).str.strip().str.lower()

    for col in MACROS:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    # fill nulls with the per-diet mean, fall back to global mean
    for col in MACROS:
        df[col] = df.groupby("Diet_type")[col].transform(lambda s: s.fillna(s.mean()))
    df[MACROS] = df[MACROS].fillna(df[MACROS].mean())

    avg = df.groupby("Diet_type")[MACROS].mean().round(2)
    counts = df.groupby("Diet_type").size()
    highest = avg["Protein(g)"].idxmax()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    documents = []
    for diet, row in avg.iterrows():
        documents.append({
            "id": diet,                       # Cosmos item id; upsert keys on this
            "diet_type": diet,                # also the partition key
            "avg_protein_g": float(row["Protein(g)"]),
            "avg_carbs_g": float(row["Carbs(g)"]),
            "avg_fat_g": float(row["Fat(g)"]),
            "recipe_count": int(counts[diet]),
            "is_highest_protein": bool(diet == highest),
            "generated_at": now,
            "source": source,
        })

    summary = {
        "generated_at": now,
        "source": source,
        "total_recipes": int(len(df)),
        "highest_protein_diet": highest,
    }
    return {"summary": summary, "documents": documents}


def write_to_cosmos(result):
    """Upsert each per-diet document into Cosmos DB. Returns the count written.

    Reads connection info from env:
      COSMOS_CONNECTION_STRING   (preferred, one setting)
        or COSMOS_ENDPOINT + COSMOS_KEY
      COSMOS_DATABASE   default 'diet_analytics'
      COSMOS_CONTAINER  default 'nutrition_results'
    """
    from azure.cosmos import CosmosClient, PartitionKey

    db_name = os.environ.get("COSMOS_DATABASE", "diet_analytics")
    container_name = os.environ.get("COSMOS_CONTAINER", "nutrition_results")

    conn = os.environ.get("COSMOS_CONNECTION_STRING")
    if conn:
        client = CosmosClient.from_connection_string(conn)
    else:
        client = CosmosClient(os.environ["COSMOS_ENDPOINT"], os.environ["COSMOS_KEY"])

    db = client.create_database_if_not_exists(db_name)
    container = db.create_container_if_not_exists(
        id=container_name,
        partition_key=PartitionKey(path="/diet_type"),
    )

    for doc in result["documents"]:
        container.upsert_item(doc)
    return len(result["documents"])

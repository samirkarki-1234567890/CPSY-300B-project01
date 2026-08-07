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

from insights import (
    compute_insights,
    write_to_cosmos,
    build_recipe_documents,
    write_recipes_to_cosmos,
)

app = func.FunctionApp()

CONTAINER = os.environ.get("CONTAINER", "datasets")
BLOB_NAME = os.environ.get("BLOB_NAME", "All_Diets.csv")


@app.blob_trigger(arg_name="blob",
                  path=f"{CONTAINER}/{BLOB_NAME}",
                  connection="DATA_STORAGE")
def process_on_upload(blob: func.InputStream):
    """Runs automatically when the dataset lands in Blob Storage."""
    logging.info("Blob trigger fired: %s (%s bytes)", blob.name, blob.length)
    raw = blob.read()
    result = compute_insights(raw, source=f"blob://{blob.name}")
    count = write_to_cosmos(result)
    logging.info("Stored %d documents in Cosmos. Highest protein: %s",
                 count, result["summary"]["highest_protein_diet"])

    recipe_docs = build_recipe_documents(raw, source=f"blob://{blob.name}")
    recipe_count = write_recipes_to_cosmos(recipe_docs)
    logging.info("Stored %d recipe documents in Cosmos (recipes container)", recipe_count)


@app.route(route="process", auth_level=func.AuthLevel.FUNCTION)
def process_http(req: func.HttpRequest) -> func.HttpResponse:
    """Manual invocation: GET/POST /api/process?code=<function key>."""
    try:
        svc = BlobServiceClient.from_connection_string(os.environ["DATA_STORAGE"])
        blob = svc.get_blob_client(container=CONTAINER, blob=BLOB_NAME)
        data = blob.download_blob().readall()

        result = compute_insights(data, source=f"blob://{CONTAINER}/{BLOB_NAME}")
        count = write_to_cosmos(result)

        recipe_docs = build_recipe_documents(data, source=f"blob://{CONTAINER}/{BLOB_NAME}")
        recipe_count = write_recipes_to_cosmos(recipe_docs)

        body = {
            "documents_written": count,
            "recipe_documents_written": recipe_count,
            **result["summary"],
        }
        return func.HttpResponse(json.dumps(body, indent=2),
                                 mimetype="application/json", status_code=200)
    except Exception as e:
        logging.exception("process_http failed")
        return func.HttpResponse(f"Error: {e}", status_code=500)


@app.route(route="get_insights", auth_level=func.AuthLevel.ANONYMOUS)
def get_insights(req: func.HttpRequest) -> func.HttpResponse:
    """Returns all diet nutrition data from Cosmos DB for the dashboard."""
    try:
        from azure.cosmos import CosmosClient

        # Read Cosmos DB connection info from environment variables
        cosmos_conn = os.environ["COSMOS_CONNECTION_STRING"]
        db_name     = os.environ.get("COSMOS_DATABASE",  "diet_analytics")
        cont_name   = os.environ.get("COSMOS_CONTAINER", "nutrition_results")

        # Connect to Cosmos DB and fetch all diet documents
        client    = CosmosClient.from_connection_string(cosmos_conn)
        database  = client.get_database_client(db_name)
        container = database.get_container_client(cont_name)

        # Get all 5 diet documents
        items = list(container.read_all_items())

        # Return as JSON with CORS header so dashboard can access it
        headers = {"Access-Control-Allow-Origin": "*"}
        return func.HttpResponse(
            json.dumps(items, indent=2),
            mimetype="application/json",
            status_code=200,
            headers=headers
        )

    except Exception as e:
        logging.exception("get_insights failed")
        return func.HttpResponse(f"Error: {e}", status_code=500)


def _recipes_container():
    from azure.cosmos import CosmosClient

    conn = os.environ["COSMOS_CONNECTION_STRING"]
    db_name = os.environ.get("COSMOS_DATABASE", "diet_analytics")
    container_name = os.environ.get("COSMOS_RECIPES_CONTAINER", "recipes")

    client = CosmosClient.from_connection_string(conn)
    db = client.get_database_client(db_name)
    return db.get_container_client(container_name)


@app.route(route="recipes", auth_level=func.AuthLevel.ANONYMOUS)
def get_recipes(req: func.HttpRequest) -> func.HttpResponse:
    """
    GET /api/recipes?q=<search>&diet_type=<diet>&page=<n>&page_size=<n>

    Search matches recipe name (case-insensitive substring). diet_type filters
    exactly. page/page_size paginate the combined result. All params optional —
    with none supplied, returns page 1 of everything.
    """
    headers = {"Access-Control-Allow-Origin": "*"}
    try:
        search_term = (req.params.get("q") or "").strip().lower()
        diet_type = (req.params.get("diet_type") or "").strip().lower()

        try:
            page = max(int(req.params.get("page", 1)), 1)
            page_size = min(max(int(req.params.get("page_size", 20)), 1), 100)
        except ValueError:
            return func.HttpResponse(
                json.dumps({"error": "page and page_size must be integers"}),
                status_code=400, mimetype="application/json", headers=headers)

        container = _recipes_container()

        query = "SELECT * FROM c WHERE 1=1"
        params = []
        if diet_type:
            query += " AND c.diet_type = @diet_type"
            params.append({"name": "@diet_type", "value": diet_type})
        if search_term:
            query += " AND CONTAINS(c.recipe_name_lower, @search_term)"
            params.append({"name": "@search_term", "value": search_term})

        matches = list(container.query_items(
            query=query, parameters=params, enable_cross_partition_query=True))

        total_count = len(matches)
        start = (page - 1) * page_size
        page_items = matches[start:start + page_size]

        body = {
            "data": page_items,
            "page": page,
            "page_size": page_size,
            "total_count": total_count,
            "total_pages": max((total_count + page_size - 1) // page_size, 1),
        }
        return func.HttpResponse(json.dumps(body, default=str),
                                  mimetype="application/json", status_code=200, headers=headers)
    except Exception as e:
        logging.exception("get_recipes failed")
        return func.HttpResponse(f"Error: {e}", status_code=500, headers=headers)


@app.route(route="recipes/{id}", auth_level=func.AuthLevel.ANONYMOUS)
def get_recipe_by_id(req: func.HttpRequest) -> func.HttpResponse:
    """GET /api/recipes/{id} - fetch a single recipe document."""
    headers = {"Access-Control-Allow-Origin": "*"}
    try:
        recipe_id = req.route_params.get("id")
        container = _recipes_container()

        results = list(container.query_items(
            query="SELECT * FROM c WHERE c.id = @id",
            parameters=[{"name": "@id", "value": recipe_id}],
            enable_cross_partition_query=True))

        if not results:
            return func.HttpResponse(json.dumps({"error": "Recipe not found"}),
                                      status_code=404, mimetype="application/json", headers=headers)

        return func.HttpResponse(json.dumps(results[0], default=str),
                                  mimetype="application/json", status_code=200, headers=headers)
    except Exception as e:
        logging.exception("get_recipe_by_id failed")
        return func.HttpResponse(f"Error: {e}", status_code=500, headers=headers)
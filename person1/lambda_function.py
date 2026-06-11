# Task 3: Serverless Data Processing (Azurite Simulation)
# Course: Cloud-Native Application Development
# Author: Person 1 - Database Manager
# Description: This script acts as a "serverless function".
#              It connects to Azurite (our local simulation of
#              Azure Blob Storage), downloads the All_Diets.csv
#              file from it, calculates average macronutrients
#              per diet type, and saves the results to a JSON
#              file (simulating a NoSQL database like Cosmos DB).

from azure.storage.blob import BlobServiceClient
import pandas as pd
import json
import io
import os
from datetime import datetime


# STEP 1: Define our connection settings

# This is Azurite's default connection string.
# It tells Python to connect to the local storage emulator
# instead of a real Azure cloud service.

AZURITE_CONNECTION_STRING = "UseDevelopmentStorage=true;"

# The name of the container and file we uploaded earlier
CONTAINER_NAME = "datasets"
BLOB_FILE_NAME = "All_Diets.csv"

# The folder and file where we'll save our results
OUTPUT_FOLDER = "simulated_nosql"
OUTPUT_FILE   = os.path.join(OUTPUT_FOLDER, "results.json")


# STEP 2: Create the output folder if it doesn't exist
os.makedirs(OUTPUT_FOLDER, exist_ok=True)


# STEP 3: Connect to Azurite and download the CSV file
print("Connecting to Azurite Blob Storage...")

try:
    # Create a client that connects to our local Azurite emulator
    blob_service_client = BlobServiceClient.from_connection_string(AZURITE_CONNECTION_STRING)

    # Get a reference to the specific container we created earlier
    container_client = blob_service_client.get_container_client(CONTAINER_NAME)

    # Get a reference to the specific file (blob) inside that container
    blob_client = container_client.get_blob_client(BLOB_FILE_NAME)

    # Download the file content as raw bytes
    print(f"  Downloading '{BLOB_FILE_NAME}' from container '{CONTAINER_NAME}'...")
    blob_data = blob_client.download_blob().readall()

    print("  Download successful!")

except Exception as e:
    # If something goes wrong (e.g. Azurite isn't running), show a helpful message
    print(f"  ERROR: Could not connect to Azurite. Is it running?")
    print(f"  Details: {e}")
    exit(1)   # Stop the script here if we can't connect


# STEP 4: Load the downloaded data into a Pandas DataFrame
# The blob_data is raw bytes, so we wrap it in io.BytesIO
# to make it readable like a file — without saving it to disk.

print("\nLoading data into Pandas...")

df = pd.read_csv(io.BytesIO(blob_data))

# Clean up text columns just like we did in data_analysis.py
df["Diet_type"]    = df["Diet_type"].str.strip().str.lower()
df["Cuisine_type"] = df["Cuisine_type"].str.strip().str.lower()

print(f"  Loaded {len(df)} rows successfully.")
print(f"  Diet types found: {sorted(df['Diet_type'].unique())}")


# STEP 5: Calculate average macronutrients per diet type
print("\nCalculating average macronutrients per diet type...")

avg_macros = (
    df.groupby("Diet_type")[["Protein(g)", "Carbs(g)", "Fat(g)"]]
    .mean()
    .round(2)
)

print("\n  Results:")
print(avg_macros.to_string())


# STEP 6: Save results to a JSON file (simulated NoSQL)
# In a real cloud setup, we'd save this to Cosmos DB.
# Here we simulate that by saving to a local JSON file.
# The format mimics how a NoSQL document would look.

print(f"\nSaving results to '{OUTPUT_FILE}'...")

# Convert the dataframe to a list of dictionaries (JSON-friendly format)
results_list = avg_macros.reset_index().to_dict(orient="records")

# Add some metadata so we know when this was generated
output_data = {
    "description": "Average macronutrients per diet type from All_Diets.csv",
    "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "source_file": BLOB_FILE_NAME,
    "source_container": CONTAINER_NAME,
    "total_recipes_processed": len(df),
    "results": results_list
}

# Write the data to the JSON file
with open(OUTPUT_FILE, "w") as f:
    json.dump(output_data, f, indent=4)   # indent=4 makes it nicely formatted

print("  Saved successfully!")


# STEP 7: Print a preview of the saved JSON
print("\n  Preview of saved JSON output:")
print(json.dumps(output_data, indent=4))


# All done!
print("\n========================================")
print("  Task 3 complete!")
print(f"  Results saved to: {OUTPUT_FILE}")
print("========================================")

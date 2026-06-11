"""
data_analysis.py  -  Task 1: Dataset Analysis & Insights
Cloud-Native Diet Analytics  |  Backend / Data Analysis

Processes All_Diets.csv with pandas and produces:
  - average macronutrient content per diet type
  - top 5 protein-rich recipes per diet type
  - diet type with the highest protein content overall
  - most common cuisine per diet type
  - protein-to-carbs and carbs-to-fat ratios per recipe
  - missing-value cleaning
  - bar charts, heatmap, and scatter plot saved to ./output/

Run:  python3 data_analysis.py
"""

import os
import sys
from datetime import datetime

import pandas as pd
import matplotlib
matplotlib.use("Agg")  # headless: works inside Docker / VM with no display
import matplotlib.pyplot as plt
import seaborn as sns

CSV_PATH = os.environ.get("CSV_PATH", "All_Diets.csv")
OUT_DIR = os.environ.get("OUT_DIR", "output")
MACROS = ["Protein(g)", "Carbs(g)", "Fat(g)"]


def stamp(msg):
    """Print with a timestamp so screenshots show date and time."""
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}")


def normalize_columns(df):
    """Map real-world header variants (extra spaces, casing) to the schema
    names this script expects. Keeps the code working whether the CSV uses
    'Protein(g)' or 'Protein (g)'."""
    wanted = {
        "diet_type": "Diet_type",
        "recipe_name": "Recipe_name",
        "cuisine_type": "Cuisine_type",
        "protein(g)": "Protein(g)",
        "carbs(g)": "Carbs(g)",
        "fat(g)": "Fat(g)",
        "extraction_day": "Extraction_day",
        "extraction_time": "Extraction_time",
    }
    renamed = {}
    for col in df.columns:
        key = col.strip().lower().replace(" ", "")
        if key in wanted:
            renamed[col] = wanted[key]
    return df.rename(columns=renamed)


def load_and_clean(path):
    stamp(f"Loading dataset: {path}")
    if not os.path.exists(path):
        sys.exit(f"ERROR: {path} not found. Place All_Diets.csv next to this script "
                 f"or set CSV_PATH.")
    df = pd.read_csv(path)
    df = normalize_columns(df)

    missing = [c for c in MACROS + ["Diet_type", "Cuisine_type"] if c not in df.columns]
    if missing:
        sys.exit(f"ERROR: missing expected columns: {missing}\nfound: {list(df.columns)}")

    # Normalize diet labels (the raw data mixes 'Paleo' and 'paleo')
    df["Diet_type"] = df["Diet_type"].astype(str).str.strip().str.lower()
    df["Cuisine_type"] = df["Cuisine_type"].astype(str).str.strip().str.lower()

    # Coerce macros to numeric, then report and fill nulls
    for col in MACROS:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    null_counts = df[MACROS].isna().sum()
    stamp(f"Null values before cleaning:\n{null_counts.to_string()}")

    # Fill missing macros with the mean of their own diet type (more honest than
    # a global mean), falling back to the global mean if a whole group is empty.
    for col in MACROS:
        df[col] = df.groupby("Diet_type")[col].transform(
            lambda s: s.fillna(s.mean())
        )
    df[MACROS] = df[MACROS].fillna(df[MACROS].mean())

    stamp(f"Null values after cleaning: {int(df[MACROS].isna().sum().sum())}")
    stamp(f"Rows: {len(df)}  |  Diet types: {df['Diet_type'].nunique()}")
    return df


def average_macros(df):
    avg = df.groupby("Diet_type")[MACROS].mean().round(2)
    stamp("Average macronutrient content per diet type:")
    print(avg.to_string(), "\n")
    return avg


def top_protein(df, n=5):
    top = (df.sort_values("Protein(g)", ascending=False)
             .groupby("Diet_type")
             .head(n)[["Diet_type", "Recipe_name", "Cuisine_type", "Protein(g)"]]
             .sort_values(["Diet_type", "Protein(g)"], ascending=[True, False]))
    stamp(f"Top {n} protein-rich recipes per diet type:")
    print(top.to_string(index=False), "\n")
    return top


def highest_protein_diet(df):
    means = df.groupby("Diet_type")["Protein(g)"].mean()
    diet = means.idxmax()
    stamp(f"Diet type with highest average protein: {diet} ({means.max():.2f} g)\n")
    return diet


def common_cuisines(df):
    common = (df.groupby("Diet_type")["Cuisine_type"]
                .agg(lambda s: s.value_counts().idxmax()))
    stamp("Most common cuisine per diet type:")
    print(common.to_string(), "\n")
    return common


def add_ratios(df):
    eps = 1e-9  # guard against divide-by-zero
    df["Protein_to_Carbs_ratio"] = (df["Protein(g)"] / (df["Carbs(g)"] + eps)).round(3)
    df["Carbs_to_Fat_ratio"] = (df["Carbs(g)"] / (df["Fat(g)"] + eps)).round(3)
    stamp("Added Protein_to_Carbs_ratio and Carbs_to_Fat_ratio.")
    print(df[["Diet_type", "Recipe_name",
              "Protein_to_Carbs_ratio", "Carbs_to_Fat_ratio"]].head().to_string(index=False), "\n")
    return df


# ----------------------------- visualizations ------------------------------ #

def viz_bar(avg, out_dir):
    ax = avg.plot(kind="bar", figsize=(10, 6), width=0.78,
                  color=["#2563eb", "#f59e0b", "#10b981"])
    ax.set_title("Average Macronutrient Content by Diet Type")
    ax.set_ylabel("Grams (g)")
    ax.set_xlabel("Diet Type")
    plt.xticks(rotation=20, ha="right")
    plt.legend(title="Macronutrient")
    plt.tight_layout()
    path = os.path.join(out_dir, "01_avg_macros_bar.png")
    plt.savefig(path, dpi=140)
    plt.close()
    stamp(f"Saved {path}")


def viz_heatmap(avg, out_dir):
    plt.figure(figsize=(8, 6))
    sns.heatmap(avg, annot=True, fmt=".1f", cmap="YlGnBu", cbar_kws={"label": "Grams (g)"})
    plt.title("Macronutrient Content vs Diet Type")
    plt.ylabel("Diet Type")
    plt.xlabel("Macronutrient")
    plt.tight_layout()
    path = os.path.join(out_dir, "02_macros_heatmap.png")
    plt.savefig(path, dpi=140)
    plt.close()
    stamp(f"Saved {path}")


def viz_scatter(top, out_dir):
    plt.figure(figsize=(11, 6))
    sns.scatterplot(data=top, x="Cuisine_type", y="Protein(g)",
                    hue="Diet_type", s=120, alpha=0.85, edgecolor="black")
    plt.title("Top 5 Protein-Rich Recipes by Cuisine and Diet")
    plt.ylabel("Protein (g)")
    plt.xlabel("Cuisine")
    plt.xticks(rotation=30, ha="right")
    plt.legend(title="Diet Type", bbox_to_anchor=(1.02, 1), loc="upper left")
    plt.tight_layout()
    path = os.path.join(out_dir, "03_top_protein_scatter.png")
    plt.savefig(path, dpi=140)
    plt.close()
    stamp(f"Saved {path}")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    stamp("=== Task 1: Dataset Analysis & Insights ===")

    df = load_and_clean(CSV_PATH)
    avg = average_macros(df)
    top = top_protein(df, n=5)
    highest_protein_diet(df)
    common_cuisines(df)
    df = add_ratios(df)

    viz_bar(avg, OUT_DIR)
    viz_heatmap(avg, OUT_DIR)
    viz_scatter(top, OUT_DIR)

    # Persist the enriched dataset and the summary table for downstream tasks
    df.to_csv(os.path.join(OUT_DIR, "all_diets_enriched.csv"), index=False)
    avg.to_csv(os.path.join(OUT_DIR, "avg_macros_by_diet.csv"))
    stamp("Analysis complete. Outputs in ./" + OUT_DIR)


if __name__ == "__main__":
    main()

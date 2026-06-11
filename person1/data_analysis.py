# Task 1: Dataset Analysis & Insights
# Course: Cloud-Native Application Development
# Author: Person 1 - Database Manager
# Description: This script loads the All_Diets.csv dataset,
#              cleans it up, calculates nutritional averages,
#              and creates 3 charts to visualize the results.

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os

# -----------------------------------------------------------
# STEP 1: Create an output folder to save our charts
# -----------------------------------------------------------
# We want all our generated charts saved in one clean place.
# os.makedirs won't crash if the folder already exists.
os.makedirs("outputs", exist_ok=True)


# STEP 2: Load the dataset
print("Loading the dataset...")

df = pd.read_csv("All_Diets.csv")

print(f"  Done! The dataset has {len(df)} rows and {len(df.columns)} columns.")
print(f"  Columns: {list(df.columns)}")


# STEP 3: Clean the data
# Sometimes text data has extra spaces or mixed capitalization
# (e.g. "Paleo" vs "paleo" vs " paleo ").
# We fix that by stripping whitespace and making everything lowercase.

print("\nCleaning the data...")

df["Diet_type"]    = df["Diet_type"].str.strip().str.lower()
df["Cuisine_type"] = df["Cuisine_type"].str.strip().str.lower()

# Remove any rows where nutrition values are missing
before = len(df)
df.dropna(subset=["Protein(g)", "Carbs(g)", "Fat(g)"], inplace=True)
after = len(df)
print(f"  Removed {before - after} rows with missing nutrition values.")

# Remove extreme outliers — values that are more than 3 standard
# deviations away from the average are likely data entry errors.
for col in ["Protein(g)", "Carbs(g)", "Fat(g)"]:
    mean = df[col].mean()
    std  = df[col].std()
    df   = df[df[col].between(mean - 3 * std, mean + 3 * std)]

print(f"  After cleaning, we have {len(df)} rows remaining.")
print(f"  Diet types found: {sorted(df['Diet_type'].unique())}")


# STEP 4: Calculate average macronutrients per diet type
# We group all recipes by their diet type and calculate the
# average protein, carbs, and fat for each group.

print("\nCalculating averages by diet type...")

avg_by_diet = df.groupby("Diet_type")[["Protein(g)", "Carbs(g)", "Fat(g)"]].mean().round(2)

print("\n  Average macronutrients per diet type (in grams):")
print(avg_by_diet.to_string())


# STEP 5: Calculate average macronutrients per cuisine type

print("\nCalculating averages by cuisine type...")

avg_by_cuisine = df.groupby("Cuisine_type")[["Protein(g)", "Carbs(g)", "Fat(g)"]].mean().round(2)

print("\n  Top 5 cuisines by average protein:")
print(avg_by_cuisine["Protein(g)"].sort_values(ascending=False).head(5).to_string())

print("\n  Top 5 cuisines by average carbs:")
print(avg_by_cuisine["Carbs(g)"].sort_values(ascending=False).head(5).to_string())


# STEP 6: Calculate macronutrient ratios per diet type
# Instead of just grams, we want to know:
# "What percentage of total macros is protein? Carbs? Fat?"
# This helps compare diets on a level playing field.

print("\nCalculating macronutrient ratios...")

total_macros      = avg_by_diet.sum(axis=1)   # sum across all 3 columns per diet
macro_ratios      = avg_by_diet.div(total_macros, axis=0).mul(100).round(2)
macro_ratios.columns = ["Protein_%", "Carbs_%", "Fat_%"]

print("\n  Macronutrient ratios per diet type (%):")
print(macro_ratios.to_string())


# STEP 7: Chart 1 — Bar Chart
# Showing average protein, carbs, and fat per diet type
print("\nCreating Chart 1: Bar chart...")

fig, ax = plt.subplots(figsize=(10, 6))

# We need to manually position the bars side by side
diet_labels  = avg_by_diet.index.tolist()
num_diets    = len(diet_labels)
x_positions  = range(num_diets)
bar_width    = 0.25   # how wide each bar is

# Draw one set of bars for each macronutrient
ax.bar([x - bar_width for x in x_positions], avg_by_diet["Protein(g)"], bar_width, label="Protein", color="#4C72B0")
ax.bar([x             for x in x_positions], avg_by_diet["Carbs(g)"],   bar_width, label="Carbs",   color="#DD8452")
ax.bar([x + bar_width for x in x_positions], avg_by_diet["Fat(g)"],     bar_width, label="Fat",     color="#55A868")

# Labels and formatting
ax.set_title("Average Macronutrients by Diet Type", fontsize=14, fontweight="bold")
ax.set_xlabel("Diet Type", fontsize=11)
ax.set_ylabel("Average Amount (grams)", fontsize=11)
ax.set_xticks(x_positions)
ax.set_xticklabels([name.capitalize() for name in diet_labels], rotation=15)
ax.legend(title="Macronutrient")

plt.tight_layout()
plt.savefig("outputs/chart1_bar_macros_by_diet.png", dpi=150)
plt.close()   # close the figure so it doesn't show up during the next chart
print("  Saved: outputs/chart1_bar_macros_by_diet.png")


# STEP 8: Chart 2 — Heatmap
# Showing macros across the top 10 most common cuisines
print("Creating Chart 2: Heatmap...")

# Only use the 10 cuisines that appear most often in the dataset
top_10_cuisines = df["Cuisine_type"].value_counts().head(10).index
cuisine_subset  = df[df["Cuisine_type"].isin(top_10_cuisines)]

# Build a table: rows = cuisines, columns = protein/carbs/fat
heatmap_data = cuisine_subset.groupby("Cuisine_type")[["Protein(g)", "Carbs(g)", "Fat(g)"]].mean().round(2)

fig, ax = plt.subplots(figsize=(9, 6))

sns.heatmap(
    heatmap_data,
    annot=True,          # show numbers inside each cell
    fmt=".1f",           # show 1 decimal place
    cmap="YlOrRd",       # yellow-to-red colour gradient
    linewidths=0.5,      # thin lines between cells
    ax=ax,
    cbar_kws={"label": "Average (grams)"},
)

ax.set_title("Macronutrient Heatmap — Top 10 Cuisines", fontsize=14, fontweight="bold")
ax.set_xlabel("Macronutrient", fontsize=11)
ax.set_ylabel("Cuisine Type", fontsize=11)
ax.set_yticklabels([name.capitalize() for name in heatmap_data.index], rotation=0)

plt.tight_layout()
plt.savefig("outputs/chart2_heatmap_macros_by_cuisine.png", dpi=150)
plt.close()
print("  Saved: outputs/chart2_heatmap_macros_by_cuisine.png")


# STEP 9: Chart 3 — Scatter Plot
# Comparing protein vs fat content, coloured by diet type
print("Creating Chart 3: Scatter plot...")

# Each diet type gets its own colour so we can tell them apart
diet_colours = {
    "paleo":         "#E63946",
    "vegan":         "#2A9D8F",
    "keto":          "#E9C46A",
    "mediterranean": "#457B9D",
    "dash":          "#A8DADC",
}

fig, ax = plt.subplots(figsize=(10, 6))

# Plot each diet type as a separate group so it shows up in the legend
for diet_name, group in df.groupby("Diet_type"):
    colour = diet_colours.get(diet_name, "#999999")
    ax.scatter(
        group["Protein(g)"],
        group["Fat(g)"],
        label=diet_name.capitalize(),
        color=colour,
        alpha=0.45,   # semi-transparent so overlapping points are visible
        s=20,         # dot size
    )

ax.set_title("Protein vs Fat Content by Diet Type", fontsize=14, fontweight="bold")
ax.set_xlabel("Protein (grams)", fontsize=11)
ax.set_ylabel("Fat (grams)", fontsize=11)
ax.legend(title="Diet Type", markerscale=2)

plt.tight_layout()
plt.savefig("outputs/chart3_scatter_protein_vs_fat.png", dpi=150)
plt.close()
print("  Saved: outputs/chart3_scatter_protein_vs_fat.png")


# All done!
print("\n========================================")
print("  Task 1 complete!")
print("  All 3 charts saved in the outputs/ folder.")
print("========================================")

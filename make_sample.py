"""Generates a synthetic All_Diets.csv that mirrors the real Kaggle schema.
Use ONLY for local testing. Replace with the real dataset before submitting."""
import numpy as np, pandas as pd
rng = np.random.default_rng(42)

diets = {
    "paleo":        dict(p=70,  c=60,  f=55),
    "vegan":        dict(p=35,  c=120, f=40),
    "keto":         dict(p=90,  c=20,  f=110),
    "mediterranean":dict(p=60,  c=80,  f=50),
    "dash":         dict(p=55,  c=95,  f=35),
}
cuisines = ["american","mexican","italian","french","chinese","indian",
            "mediterranean","south east asian","british","japanese"]
names = ["Bowl","Stew","Salad","Roast","Soup","Pie","Skillet","Wrap",
         "Curry","Bake","Stir Fry","Hash","Casserole","Tacos","Fritters"]

rows = []
for diet, m in diets.items():
    for _ in range(rng.integers(180, 240)):
        p = max(0.1, rng.normal(m["p"], m["p"]*0.5))
        c = max(0.1, rng.normal(m["c"], m["c"]*0.5))
        f = max(0.1, rng.normal(m["f"], m["f"]*0.5))
        rows.append([
            diet,
            f"{diet.title()} {rng.choice(names)} {rng.integers(1,999)}",
            rng.choice(cuisines),
            round(p,2), round(c,2), round(f,2),
            "10/16/2022", "17:20:09",
        ])

df = pd.DataFrame(rows, columns=["Diet_type","Recipe_name","Cuisine_type",
                                 "Protein(g)","Carbs(g)","Fat(g)",
                                 "Extraction_day","Extraction_time"])
# inject a few nulls so the cleaning step has something to do
for col in ["Protein(g)","Carbs(g)","Fat(g)"]:
    idx = rng.choice(df.index, size=12, replace=False)
    df.loc[idx, col] = np.nan
df.to_csv("All_Diets.csv", index=False)
print(f"Wrote All_Diets.csv  rows={len(df)}  nulls injected")

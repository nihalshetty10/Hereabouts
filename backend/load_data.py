import os
import sys

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.geo import attach_nta_centroids

engine = create_engine(os.getenv("DATABASE_URL"))

activities = {
    "running":    "scored_running.csv",
    "night_out":  "scored_night_out.csv",
    "coffee":     "scored_coffee.csv",
    "biking":     "scored_biking.csv",
    "park":       "scored_park.csv",
    "eating":     "scored_eating.csv",
    "shopping":   "scored_shopping.csv",
    "exploring":  "scored_exploring.csv",
}

dfs = []

for activity_key, filename in activities.items():
    if os.path.exists(filename):
        df = pd.read_csv(filename)
        df = attach_nta_centroids(df)
        df["activity"] = activity_key
        df["summary"] = df["summary"].fillna("")
        df["pros"] = df["pros"].fillna("")
        df["cons"] = df["cons"].fillna("")
        dfs.append(df)
        print(f"Loaded {len(df)} rows for {activity_key}")
    else:
        print(f"Missing: {filename}")

if not dfs:
    raise SystemExit("No CSV files found. Run the recommender for each activity first.")

combined = pd.concat(dfs, ignore_index=True)
combined.to_sql("scored_table", engine, if_exists="replace", index=False)
print(f"Total rows loaded: {len(combined)}")

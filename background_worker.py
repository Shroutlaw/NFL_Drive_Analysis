# background_worker.py
import os
import nfl_data_py as nfl
import pandas as pd

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

for season in range(1999, 2025):
    print(f"Fetching season {season}...")
    df = nfl.import_pbp_data([season])
    df = df[df['play_type'].notna()]
    df.to_parquet(f"{DATA_DIR}/{season}.parquet")
    print(f"Saved data/{season}.parquet")

"""
Build a simple area_risk table for Delhi from a crime CSV.

Goal:
- Input: crime CSV with columns like ["District", "PoliceStation", "Year", "CrimesAgainstWomen"]
- Output: data/area_risk_delhi.csv with columns:
    ["area_key", "area_crime_risk"]

You will later map coordinates to area_key (e.g., by police station / ward), and then
join area_crime_risk into your model features.
"""

import os
import pandas as pd

RAW_CRIME_CSV = "data/raw/delhi_crime.csv"   # put your raw file here
OUT_CSV = "data/area_risk_delhi.csv"

os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)

def load_raw():
    df = pd.read_csv(RAW_CRIME_CSV)
    print(df.head())
    return df

def compute_area_risk(df: pd.DataFrame) -> pd.DataFrame:
    # Example schema; adjust columns to your real CSV
    # Try to derive a stable "area_key" like "District-PoliceStation"
    df["area_key"] = df["District"].astype(str).str.strip() + " - " + df["PoliceStation"].astype(str).str.strip()

    # Aggregate crimes over years
    grouped = (
        df.groupby("area_key")["CrimesAgainstWomen"]
        .sum()
        .reset_index()
        .rename(columns={"CrimesAgainstWomen": "crime_count"})
    )

    # Convert crime_count into 0/1/2 risk buckets
    # You can tweak thresholds based on Delhi distribution
    q1 = grouped["crime_count"].quantile(0.33)
    q2 = grouped["crime_count"].quantile(0.66)

    def bucket(x):
        if x <= q1:
            return 0  # low
        elif x <= q2:
            return 1  # medium
        else:
            return 2  # high

    grouped["area_crime_risk"] = grouped["crime_count"].apply(bucket)
    return grouped[["area_key", "area_crime_risk"]]

def main():
    df = load_raw()
    area_risk = compute_area_risk(df)
    print(area_risk.head())
    area_risk.to_csv(OUT_CSV, index=False)
    print(f"Saved area risk table to {OUT_CSV}")

if __name__ == "__main__":
    main()

# backend/services/area_risk.py

import os
from typing import Dict

import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
AREA_RISK_CSV = os.path.join(DATA_DIR, "area_risk_delhi.csv")


class AreaRiskTable:
    """
    Thin wrapper around area_risk_delhi.csv.

    Expected columns:
      - area_key (string)
      - area_crime_risk (0=low,1=medium,2=high)
    """

    def __init__(self, csv_path: str = AREA_RISK_CSV):
        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"Area risk CSV not found at {csv_path}")
        df = pd.read_csv(csv_path)
        required_cols = {"area_key", "area_crime_risk"}
        missing = required_cols - set(df.columns)
        if missing:
            raise ValueError(f"Area risk CSV is missing required columns: {missing}")
        self.df = df
        self._map: Dict[str, float] = dict(
            zip(df["area_key"].astype(str), df["area_crime_risk"].astype(float))
        )

    def get_risk(self, area_key: str) -> float:
        """
        Return crime risk bucket for area_key, defaulting to 0 if unknown.
        """
        return float(self._map.get(str(area_key), 0.0))

# backend/services/poi_context.py

import os
from math import radians, sin, cos, sqrt, atan2
from typing import Dict, Any, List

import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
POI_CSV = os.path.join(DATA_DIR, "delhi_poi.csv")


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Haversine distance in meters between two lat/lon points.
    """
    R = 6371000.0  # meters
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c


class POIContext:
    """
    Simple helper that loads a POI cache and returns distances to nearest POIs.

    Expected CSV at data/delhi_poi.csv with columns:
      - category  (e.g., metro_station, bus_stop, hospital, police_station)
      - name
      - lat
      - lon
    """

    def __init__(self, csv_path: str = POI_CSV):
        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"POI CSV not found at {csv_path}")
        df = pd.read_csv(csv_path)
        required_cols = {"category", "lat", "lon"}
        missing = required_cols - set(df.columns)
        if missing:
            raise ValueError(f"POI CSV is missing required columns: {missing}")
        self.df = df

    def nearest_distances(self, lat: float, lon: float) -> Dict[str, float]:
        """
        Return distances in meters to nearest metro, bus stop, hospital, police station.
        If no POIs of a type exist, returns 0 for that distance.
        """
        result = {
            "dist_to_metro_m": 0.0,
            "dist_to_bus_m": 0.0,
            "dist_to_hospital_m": 0.0,
            "dist_to_police_m": 0.0,
        }

        if self.df.empty:
            return result

        for category, key in [
            ("metro_station", "dist_to_metro_m"),
            ("bus_stop", "dist_to_bus_m"),
            ("hospital", "dist_to_hospital_m"),
            ("police_station", "dist_to_police_m"),
        ]:
            subset = self.df[self.df["category"] == category]
            if subset.empty:
                result[key] = 0.0
                continue

            dists: List[float] = []
            for _, row in subset.iterrows():
                d = _haversine_m(lat, lon, float(row["lat"]), float(row["lon"]))
                dists.append(d)
            result[key] = float(min(dists)) if dists else 0.0

        return result

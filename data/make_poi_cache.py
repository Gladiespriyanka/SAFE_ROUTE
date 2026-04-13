"""
Utility script to build data/delhi_poi.csv from OpenStreetMap (Overpass API).

Enhanced version with:
- Accurate Delhi NCT bounding box: ~28.46-28.92° N, 76.68-77.34° E [web:20][web:23]
- Improved queries for more complete POI coverage (e.g., platforms, networks)
- Deduplication: Remove near-duplicates within 50m using Haversine distance
- Robustness: Retry on failures, better logging, named POI filter option
- Categories: metro_station, bus_stop, hospital, police_station

Run from project root (saferoute-delhi-ml):
    python -m src.data.make_poi_cache
or with filter for named POIs only:
    python src/data/make_poi_cache.py --named-only
"""

import os
import time
import requests
import csv
import argparse
from typing import List, Dict, Any, Optional
import math  # For Haversine

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Improved Delhi NCT bounding box (south, west, north, east)
DELHI_BBOX = (28.46, 76.68, 28.92, 77.34)

DUPE_DISTANCE_M = 50  # Dedupe POIs within 50 meters

def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance in meters."""
    R = 6371000  # Earth radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def _ensure_data_dir() -> str:
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    data_dir = os.path.join(root, "data")
    os.makedirs(data_dir, exist_ok=True)
    return data_dir

def _run_overpass(query: str, retries: int = 3, pause_s: float = 2.0) -> Dict[str, Any]:
    """Run Overpass query with retries."""
    time.sleep(pause_s)
    for attempt in range(retries):
        try:
            resp = requests.post(OVERPASS_URL, data={"data": query}, timeout=180)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            print(f"Overpass attempt {attempt+1} failed: {e}. Retrying...")
            time.sleep(5 * (attempt + 1))
    raise RuntimeError("Overpass API failed after retries.")

def _extract_points(elements: List[Dict[str, Any]], category: str, named_only: bool) -> List[Dict[str, Any]]:
    points: List[Dict[str, Any]] = []
    for el in elements:
        if el.get("type") != "node":
            continue
        lat = el.get("lat")
        lon = el.get("lon")
        if lat is None or lon is None:
            continue
        tags = el.get("tags", {}) or {}
        name = tags.get("name", "").strip()
        if named_only and not name:
            continue  # Skip unnamed POIs if flag set
        points.append({
            "category": category,
            "name": name or f"{category}_{len(points)}",  # Fallback name
            "lat": float(lat),
            "lon": float(lon),
        })
    return points

def _deduplicate_points(points: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remove duplicates within DUPE_DISTANCE_M using Haversine."""
    kept = []
    for p in points:
        is_dupe = False
        for k in kept:
            dist = haversine(p["lat"], p["lon"], k["lat"], k["lon"])
            if dist < DUPE_DISTANCE_M:
                is_dupe = True
                break
        if not is_dupe:
            kept.append(p)
    return kept

def fetch_poi(category: str, query_template: str, named_only: bool) -> List[Dict[str, Any]]:
    south, west, north, east = DELHI_BBOX
    query = query_template.format(south=south, west=west, north=north, east=east)
    print(f"Fetching {category}...")
    data = _run_overpass(query)
    raw_points = _extract_points(data.get("elements", []), category, named_only)
    print(f"  Raw: {len(raw_points)}")
    deduped = _deduplicate_points(raw_points)
    print(f"  After dedupe: {len(deduped)}")
    return deduped

def build_poi_cache(named_only: bool = False) -> str:
    data_dir = _ensure_data_dir()
    out_path = os.path.join(data_dir, "delhi_poi.csv")

    # Improved queries [web:1][web:2][web:7][web:18]
    queries = {
        "metro_station": """
[out:json][timeout:180];
(
  node["railway"="subway"]({south},{west},{north},{east});
  node["railway"="station"]["network"~"Delhi Metro"]({south},{west},{north},{east});
  node["station"="subway"]({south},{west},{north},{east});
  way["railway"="subway"]({south},{west},{north},{east}); node(w);
);
out center;
""",
        "bus_stop": """
[out:json][timeout:180];
(
  node["highway"="bus_stop"]({south},{west},{north},{east});
  node["public_transport"="platform"]["bus"="yes"]({south},{west},{north},{east});
  node["public_transport"="stop_position"]["bus"="yes"]({south},{west},{north},{east});
);
out center;
""",
        "hospital": """
[out:json][timeout:180];
(
  node["amenity"="hospital"]({south},{west},{north},{east});
  node["healthcare"="hospital"]({south},{west},{north},{east});
);
out center;
""",
        "police_station": """
[out:json][timeout:180];
(
  node["amenity"="police"]({south},{west},{north},{east});
  node["amenity"="police_station"]({south},{west},{north},{east});
);
out center;
"""
    }

    all_points: List[Dict[str, Any]] = []
    for cat, q_template in queries.items():
        poi = fetch_poi(cat, q_template, named_only)
        all_points.extend(poi)

    if not all_points:
        raise RuntimeError("No POI data fetched. Check internet/Overpass.")

    print(f"Total unique POI points: {len(all_points)}")

    fieldnames = ["category", "name", "lat", "lon"]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_points)

    print(f"Saved to: {out_path}")
    return out_path

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build Delhi POI cache.")
    parser.add_argument("--named-only", action="store_true", help="Filter to named POIs only.")
    args = parser.parse_args()
    build_poi_cache(named_only=args.named_only)
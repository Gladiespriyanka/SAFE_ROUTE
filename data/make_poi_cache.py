"""
Utility script to build data/delhi_poi.csv from OpenStreetMap (Overpass API).

It creates a CSV with columns:
    category, name, lat, lon

Categories:
    - metro_station
    - bus_stop
    - hospital
    - police_station

Run from project root (saferoute-delhi-ml):
    python -m src.data.make_poi_cache
or:
    python src/data/make_poi_cache.py
"""

import os
import time
import requests
import csv
from typing import List, Dict, Any, Optional

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Rough bounding box for Delhi region (south, west, north, east)
# You can tweak later if you want tighter bounds.
DELHI_BBOX = (28.4, 76.8, 28.9, 77.4)  # (south, west, north, east)


def _ensure_data_dir() -> str:
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    data_dir = os.path.join(root, "data")
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


def _run_overpass(query: str, pause_s: float = 1.0) -> Dict[str, Any]:
    """Run an Overpass API query and return JSON."""
    time.sleep(pause_s)  # be gentle to the API
    resp = requests.post(OVERPASS_URL, data={"data": query}, timeout=120)
    resp.raise_for_status()
    return resp.json()


def _extract_points(elements: List[Dict[str, Any]], category: str) -> List[Dict[str, Any]]:
    points: List[Dict[str, Any]] = []
    for el in elements:
        # We only care about nodes (points)
        if el.get("type") != "node":
            continue
        lat = el.get("lat")
        lon = el.get("lon")
        if lat is None or lon is None:
            continue
        tags = el.get("tags", {}) or {}
        name = tags.get("name", "").strip()
        points.append(
            {
                "category": category,
                "name": name,
                "lat": float(lat),
                "lon": float(lon),
            }
        )
    return points


def fetch_metro_stations() -> List[Dict[str, Any]]:
    # Delhi metro stations: railway=subway OR railway=station with name containing "Metro"
    south, west, north, east = DELHI_BBOX
    query = f"""
    [out:json][timeout:120];
    (
      node["railway"="subway"]({south},{west},{north},{east});
      node["railway"="station"]["name"~"Metro"]({south},{west},{north},{east});
      node["station"="subway"]({south},{west},{north},{east});
    );
    out body;
    """
    data = _run_overpass(query)
    return _extract_points(data.get("elements", []), category="metro_station")


def fetch_bus_stops() -> List[Dict[str, Any]]:
    south, west, north, east = DELHI_BBOX
    query = f"""
    [out:json][timeout:120];
    (
      node["highway"="bus_stop"]({south},{west},{north},{east});
      node["public_transport"="platform"]["bus"="yes"]({south},{west},{north},{east});
    );
    out body;
    """
    data = _run_overpass(query)
    return _extract_points(data.get("elements", []), category="bus_stop")


def fetch_hospitals() -> List[Dict[str, Any]]:
    south, west, north, east = DELHI_BBOX
    query = f"""
    [out:json][timeout:120];
    (
      node["amenity"="hospital"]({south},{west},{north},{east});
      node["healthcare"="hospital"]({south},{west},{north},{east});
    );
    out body;
    """
    data = _run_overpass(query)
    return _extract_points(data.get("elements", []), category="hospital")


def fetch_police_stations() -> List[Dict[str, Any]]:
    south, west, north, east = DELHI_BBOX
    query = f"""
    [out:json][timeout:120];
    (
      node["amenity"="police"]({south},{west},{north},{east});
    );
    out body;
    """
    data = _run_overpass(query)
    return _extract_points(data.get("elements", []), category="police_station")


def build_poi_cache() -> str:
    data_dir = _ensure_data_dir()
    out_path = os.path.join(data_dir, "delhi_poi.csv")

    all_points: List[Dict[str, Any]] = []

    print("Fetching metro stations...")
    metro = fetch_metro_stations()
    print(f"  got {len(metro)} metro stations")
    all_points.extend(metro)

    print("Fetching bus stops...")
    bus = fetch_bus_stops()
    print(f"  got {len(bus)} bus stops")
    all_points.extend(bus)

    print("Fetching hospitals...")
    hospitals = fetch_hospitals()
    print(f"  got {len(hospitals)} hospitals")
    all_points.extend(hospitals)

    print("Fetching police stations...")
    police = fetch_police_stations()
    print(f"  got {len(police)} police stations")
    all_points.extend(police)

    if not all_points:
        print("WARNING: No POI data fetched. Check Overpass availability or bounding box.")
    else:
        print(f"Total POI points: {len(all_points)}")

    # Write CSV
    fieldnames = ["category", "name", "lat", "lon"]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in all_points:
            writer.writerow(row)

    print(f"Saved POI cache to: {out_path}")
    return out_path


if __name__ == "__main__":
    build_poi_cache()

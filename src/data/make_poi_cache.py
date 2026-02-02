"""
Build a POI cache for Delhi: metro, bus stops, hospitals, police stations.

Output: data/delhi_poi.csv with columns:
["category", "name", "lat", "lon"]

Later you will use this to compute distances to nearest POI for a given point.
"""

import os
import time
import requests
import pandas as pd

OUT_CSV = "data/delhi_poi.csv"
os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Rough bounding box for Delhi (south, west, north, east)
DELHI_BBOX = (28.4, 76.9, 28.9, 77.4)

def build_query(bbox, filters: str) -> str:
    s, w, n, e = bbox
    return f"""
    [out:json][timeout:60];
    (
      node[{filters}]({s},{w},{n},{e});
      way[{filters}]({s},{w},{n},{e});
      relation[{filters}]({s},{w},{n},{e});
    );
    out center;
    """

def fetch_pois(category: str, filters: str):
    q = build_query(DELHI_BBOX, filters)
    resp = requests.post(OVERPASS_URL, data={"data": q}, timeout=90)
    resp.raise_for_status()
    data = resp.json()
    elements = data.get("elements", [])
    rows = []
    for el in elements:
        tags = el.get("tags", {})
        name = tags.get("name", "")
        if "lat" in el and "lon" in el:
            lat, lon = el["lat"], el["lon"]
        else:
            center = el.get("center")
            if not center:
                continue
            lat, lon = center["lat"], center["lon"]
        rows.append(
            {
                "category": category,
                "name": name,
                "lat": lat,
                "lon": lon,
            }
        )
    return rows

def main():
    all_rows = []

    # Metro / subway stations
    metro_filters = '"railway"="station"'
    all_rows.extend(fetch_pois("metro_station", metro_filters))
    time.sleep(5)

    # Major bus stops
    bus_filters = '"highway"="bus_stop"'
    all_rows.extend(fetch_pois("bus_stop", bus_filters))
    time.sleep(5)

    # Hospitals
    hospital_filters = '"amenity"="hospital"'
    all_rows.extend(fetch_pois("hospital", hospital_filters))
    time.sleep(5)

    # Police stations
    police_filters = '"amenity"="police"'
    all_rows.extend(fetch_pois("police_station", police_filters))

    df = pd.DataFrame(all_rows)
    print(df.head())
    df.to_csv(OUT_CSV, index=False)
    print(f"Saved Delhi POI cache to {OUT_CSV}")

if __name__ == "__main__":
    main()

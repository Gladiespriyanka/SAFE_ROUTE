import os

import requests

payload = {
    "latitude": 28.6139,
    "longitude": 77.2090,
    "lighting_level": 1,
    "crowd_level": 1,
    "distance_to_main_road_m": 200,
    "shops_open_at_night": 1,
    "police_station_within_1km": 0,
    "cctv_present": 0,
    "hour_of_day": 21,
    "is_weekend": 0,
    "area_type": 0,
    "near_metro_or_bus": 0,
    "past_incidents_level": 0,
    "group_travel": 0
}

headers = {
   "X-API-Key": os.getenv("API_KEY", "supersecret123")
}

BACKEND_URL = os.getenv("BACKEND_URL", "http://0.0.0.0:8000")

r = requests.post(
    f"{BACKEND_URL}/predict",
    json=payload,
    headers=headers
)

print(r.status_code)
print(r.text)

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
    "X-API-Key": "SAFEROUTE_SECRET_123"
}

r = requests.post(
    "http://127.0.0.1:8000/predict",
    json=payload,
    headers=headers
)

print(r.status_code)
print(r.text)

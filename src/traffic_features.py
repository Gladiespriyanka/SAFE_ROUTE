import requests
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("ORS_API_KEY")


def get_traffic_data(start_lat, start_lon, end_lat, end_lon):
    url = "https://api.openrouteservice.org/v2/directions/driving-car"

    headers = {
        "Authorization": API_KEY,
        "Content-Type": "application/json"
    }

    body = {
        "coordinates": [
            [start_lon, start_lat],
            [end_lon, end_lat]
        ]
    }

    try:
        res = requests.post(url, json=body, headers=headers)

        if res.status_code != 200:
            raise Exception(res.text)

        data = res.json()

        summary = data["features"][0]["properties"]["summary"]

        distance_km = summary["distance"] / 1000
        duration_hr = summary["duration"] / 3600

        congestion = duration_hr / (distance_km + 1e-5)

        return {
            "distance_km": distance_km,
            "duration_hr": duration_hr,
            "congestion": congestion
        }

    except Exception as e:
        print("Traffic API error:", e)
        return {
            "distance_km": 0,
            "duration_hr": 0,
            "congestion": 0
        }
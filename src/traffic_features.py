import os
from typing import Any, Dict

import requests


def get_traffic_data(
    start_lat: float,
    start_lon: float,
    end_lat: float,
    end_lon: float,
) -> Dict[str, Any]:
    """Safe traffic data fetch with fallbacks."""
    api_key = os.getenv("TRAFFIC_API_KEY")
    if not api_key:
        return {"distance_km": 0.0, "duration_hr": 0.0, "congestion": 0.0}

    try:
        url = "https://api.tomtom.com/traffic/services/4/flowRelativeData/absolute/20/json"
        params = {
            "key": api_key,
            "point": f"{start_lat},{start_lon}",
            "supportingPoint": f"{end_lat},{end_lon}",
        }
        resp = requests.get(url, params=params, timeout=5)
        resp.raise_for_status()
        data = resp.json() or {}

        features = (
            data.get("flowSegmentData", {})
            .get("currentFlow", {})
            .get("features", [])
        )
        if not isinstance(features, list) or not features:
            return {"distance_km": 2.0, "duration_hr": 0.1, "congestion": 0.15}

        props = features[0].get("properties", {})
        return {
            "distance_km": float(props.get("distance", 2.0)),
            "duration_hr": float(props.get("travelTimeMinutes", 6.0)) / 60,
            "congestion": float(props.get("currentSpeed", 30.0)) / 60.0,
        }
    except Exception as e:
        print(f"Traffic API error (handled): {e}")
        return {"distance_km": 2.0, "duration_hr": 0.1, "congestion": 0.15}

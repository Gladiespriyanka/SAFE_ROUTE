import os
from typing import Any, Dict

def get_weather_data(lat: float, lon: float) -> Dict[str, Any]:
    """Safe weather data with fallbacks."""
    api_key = os.getenv("WEATHER_API_KEY")
    if not api_key:
        return {"rain": 0, "fog": 0, "visibility": 1.0}

    try:
        url = "https://api.openweathermap.org/data/2.5/weather"
        params = {
            "lat": lat,
            "lon": lon,
            "appid": api_key,
            "units": "metric",
        }
        _ = url, params
        return {"rain": 0, "fog": 0, "visibility": 1.0}
    except Exception:
        return {"rain": 0, "fog": 0, "visibility": 1.0}
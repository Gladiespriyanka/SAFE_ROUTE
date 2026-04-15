import requests
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("OPENWEATHER_API_KEY")


def get_weather_data(lat, lon):
    url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={API_KEY}"

    try:
        res = requests.get(url)

        # ✅ FIX 1: check status
        if res.status_code != 200:
            print("Weather API failed:", res.text)
            raise Exception("API error")

        data = res.json()

        # ✅ FIX 2: safer parsing
        weather_main = data.get("weather", [{}])[0].get("main", "").lower()

        return {
            "rain": 1 if "rain" in weather_main else 0,
            "fog": 1 if "mist" in weather_main or "fog" in weather_main else 0,
            "visibility": data.get("visibility", 10000) / 10000.0
        }

    except Exception as e:
        print("Weather API error:", e)

        # ✅ FIX 3: safe fallback
        return {
            "rain": 0,
            "fog": 0,
            "visibility": 1.0
        }
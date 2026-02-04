import numpy as np
import requests
import streamlit as st
import folium
from streamlit_folium import st_folium
from typing import List, Tuple, Dict, Any

API_URL = "http://127.0.0.1:8000/predict"


def interpolate_points(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
    n_points: int = 20,
) -> List[Tuple[float, float]]:
    """Sample points along a straight line between start and end."""
    lats = np.linspace(lat1, lat2, n_points)
    lons = np.linspace(lon1, lon2, n_points)
    return list(zip(lats, lons))


def call_api_for_point(
    lat: float,
    lon: float,
    base_payload: Dict[str, Any],
) -> Dict[str, Any]:
    """Call your existing /predict API for one point."""
    payload = base_payload.copy()
    payload["latitude"] = float(lat)
    payload["longitude"] = float(lon)

    resp = requests.post(API_URL, json=payload, timeout=5)
    resp.raise_for_status()
    return resp.json()



def score_to_color(label: str) -> str:
    if label == "Safe":
        return "green"
    if label == "Moderate":
        return "orange"
    return "red"


st.set_page_config(page_title="Route safety map", page_icon="🗺️", layout="wide")

st.title("Route safety map 🗺️")

st.markdown(
    """
Estimate route safety between two points:

- Enter start and end coordinates (lat / lon)
- We sample points along the straight line between them
- For each point, we call your existing safety API
- We aggregate the labels → color the route as Safe / Moderate / Unsafe
"""
)

col1, col2 = st.columns(2)

with col1:
    st.subheader("Start point")
    start_lat = st.number_input("Start latitude", value=28.6139, format="%.6f")
    start_lon = st.number_input("Start longitude", value=77.2090, format="%.6f")

with col2:
    st.subheader("End point")
    end_lat = st.number_input("End latitude", value=28.7041, format="%.6f")
    end_lon = st.number_input("End longitude", value=77.1025, format="%.6f")

st.subheader("Context for scoring (same as home page)")

lighting_level = st.selectbox(
    "Lighting level",
    [0, 1, 2],
    format_func=lambda v: ["Very poor", "OK", "Good"][v],
)
crowd_level = st.selectbox(
    "Crowd level",
    [0, 1, 2],
    format_func=lambda v: ["Empty", "Some people", "Busy/Active"][v],
)
distance_to_main_road_m = st.slider(
    "Distance to main road (meters)",
    0,
    2000,
    200,
    step=50,
)
shops_open_at_night = st.selectbox(
    "Shops open at night?",
    [0, 1],
    format_func=lambda v: "Yes" if v else "No",
)
police_station_within_1km = st.selectbox(
    "Police station within 1 km?",
    [0, 1],
    format_func=lambda v: "Yes" if v else "No",
)
cctv_present = st.selectbox(
    "CCTV present?",
    [0, 1],
    format_func=lambda v: "Yes" if v else "No",
)
hour_of_day = st.slider("Hour of day (0–23)", 0, 23, 20)
is_weekend = st.selectbox(
    "Is it weekend?",
    [0, 1],
    format_func=lambda v: "Yes" if v else "No",
)

area_type = st.selectbox(
    "Area type",
    [0, 1, 2],
    format_func=lambda v: ["Residential", "Commercial/Market", "Office/IT park"][v],
)
near_metro_or_bus = st.selectbox(
    "Near metro or major bus stop?",
    [0, 1],
    format_func=lambda v: "Yes" if v else "No",
)
past_incidents_level = st.selectbox(
    "Past incidents level (coarse)",
    [0, 1, 2],
    format_func=lambda v: ["Low", "Medium", "High"][v],
)
group_travel = st.selectbox(
    "Walking alone or in a group?",
    [0, 1],
    format_func=lambda v: "Alone" if v == 0 else "With others",
)

base_payload = {
    "lighting_level": int(lighting_level),
    "crowd_level": int(crowd_level),
    "distance_to_main_road_m": float(distance_to_main_road_m),
    "shops_open_at_night": int(shops_open_at_night),
    "police_station_within_1km": int(police_station_within_1km),
    "cctv_present": int(cctv_present),
    "hour_of_day": int(hour_of_day),
    "is_weekend": int(is_weekend),
    "area_type": int(area_type),
    "near_metro_or_bus": int(near_metro_or_bus),
    "past_incidents_level": int(past_incidents_level),
    "group_travel": int(group_travel),
}

# ---- NEW: button + session_state pattern ----
if "run_route" not in st.session_state:
    st.session_state.run_route = False

clicked = st.button("Compute route safety")

# Only trigger once: set a flag, then use that flag below
if clicked:
    st.session_state.run_route = True

if st.session_state.run_route:
    try:
        # 1) Sample points along route
        points = interpolate_points(
            start_lat,
            start_lon,
            end_lat,
            end_lon,
            n_points=20,
        )

        if not points:
            st.error("No points generated along the route.")
        else:
            # 2) Call API for each point (same payload each time for now)
            labels: List[str] = []
            confidences: List[float] = []

            with st.spinner("Calling safety API along the route..."):
                for lat, lon in points:
                    result = call_api_for_point(lat, lon, base_payload)
                    labels.append(result.get("label"))

                    probs = result.get("probabilities", {})
                    score = max(
                        probs.get("unsafe", 0.0),
                        probs.get("moderate", 0.0),
                        probs.get("safe", 0.0),
                    )
                    confidences.append(score)

            # 3) Aggregate route safety
            if labels:
                majority_label = max(set(labels), key=labels.count)
            else:
                majority_label = "Unknown"

            avg_conf = float(np.mean(confidences)) if confidences else 0.0

            st.markdown(
                f"### Route safety: **{majority_label}** "
                f"(avg confidence {avg_conf:.2f})"
            )

            # 4) Build map
            center_lat = (start_lat + end_lat) / 2
            center_lon = (start_lon + end_lon) / 2

            m = folium.Map(location=[center_lat, center_lon], zoom_start=12)

            folium.Marker(
                location=[start_lat, start_lon],
                popup="Start",
                icon=folium.Icon(color="blue"),
            ).add_to(m)

            folium.Marker(
                location=[end_lat, end_lon],
                popup="End",
                icon=folium.Icon(color="blue"),
            ).add_to(m)

            color = score_to_color(majority_label)

            folium.PolyLine(
                locations=points,
                color=color,
                weight=6,
                tooltip=f"Route safety: {majority_label}",
            ).add_to(m)

            st_folium(m, width=900, height=500)

    except Exception as e:
        st.error(f"Failed to compute route safety: {e}")

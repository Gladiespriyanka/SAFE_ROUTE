import numpy as np
import requests
import streamlit as st
import folium
from streamlit_folium import st_folium
from typing import List, Tuple, Dict, Any
from collections import Counter
import os


API_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000") + "/predict"
API_HEADERS = {
    "X-API-Key": "SAFEROUTE_SECRET_123"
}


# Simple CSS styling
st.markdown("""
<style>
    .metric-card {
        padding: 1rem;
        border-radius: 10px;
        text-align: center;
        color: white;
        margin: 0.5rem 0;
    }
    .safe-card {
        background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%);
    }
    .moderate-card {
        background: linear-gradient(135deg, #FF9800 0%, #F57C00 100%);
    }
    .unsafe-card {
        background: linear-gradient(135deg, #f44336 0%, #d32f2f 100%);
    }
    .section-header {
        font-size: 1.5rem;
        font-weight: bold;
        margin: 2rem 0 1rem 0;
    }
</style>
""", unsafe_allow_html=True)


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

    resp = requests.post(API_URL, json=payload, headers=API_HEADERS, timeout=5)
    resp.raise_for_status()
    return resp.json()


def score_to_color(label: str) -> str:
    if label == "Safe":
        return "green"
    if label == "Moderate":
        return "orange"
    return "red"


def aggregate_factors(all_results: List[Dict[str, Any]]) -> List[str]:
    """Collect and deduplicate factors from all API responses."""
    all_factors = []
    for result in all_results:
        factors = result.get("factors", [])
        all_factors.extend(factors)

    # Remove duplicates while preserving order
    seen = set()
    unique_factors = []
    for factor in all_factors:
        if factor not in seen:
            seen.add(factor)
            unique_factors.append(factor)

    return unique_factors[:5]  # Limit to top 5


def generate_explanation(factors: List[str]) -> str:
    """Convert factors into readable sentence."""
    if not factors:
        return "No major risk factors detected."

    if len(factors) == 1:
        factor_list = factors[0]
    else:
        factor_list = ", ".join(factors[:-1]) + f" and {factors[-1]}"

    label = st.session_state.get("route_label", "Safe")
    return f"This route is {label.lower()} due to {factor_list}."


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

# ---- Session state for results ----
if "run_route" not in st.session_state:
    st.session_state.run_route = False
if "all_results" not in st.session_state:
    st.session_state.all_results = []
if "route_label" not in st.session_state:
    st.session_state.route_label = ""
if "route_confidence" not in st.session_state:
    st.session_state.route_confidence = 0.0
# one-shot trigger flag
if "trigger_compute" not in st.session_state:
    st.session_state.trigger_compute = False

# BUTTON → set one-shot trigger
if st.button("Compute route safety"):
    st.session_state.trigger_compute = True

# MAIN COMPUTATION BLOCK – one-shot
if st.session_state.trigger_compute:
    try:
        # clear trigger immediately so this block runs only once per click
        st.session_state.trigger_compute = False

        # reset results (do NOT touch run_route yet)
        st.session_state.all_results = []

        # 1) Sample points along route
        points = interpolate_points(
            start_lat, start_lon, end_lat, end_lon, n_points=20
        )

        if not points:
            st.error("No points generated along the route.")
        else:
            labels: List[str] = []
            confidences: List[float] = []

            # 2) Call API for each point - fault tolerant
            with st.spinner("Calling safety API along the route..."):
                for lat, lon in points:
                    try:
                        result = call_api_for_point(lat, lon, base_payload)

                        # skip completely broken responses
                        if not result or "label" not in result:
                            continue

                        st.session_state.all_results.append(result)
                        labels.append(result["label"])

                        probs = result.get("probabilities", {})
                        score = max(
                            probs.get("unsafe", 0.0),
                            probs.get("moderate", 0.0),
                            probs.get("safe", 0.0),
                        )
                        confidences.append(score)

                    except Exception as e:
                        print(f"API failed: {e}")
                        continue

            # If nothing succeeded, bail out and keep run_route False
            if not st.session_state.all_results:
                st.error("No results received from backend")
                st.session_state.run_route = False
                st.stop()

            # 3) Aggregate route safety (majority label)
            label_counts = Counter(labels)
            st.session_state.route_label = label_counts.most_common(1)[0][0]
            st.session_state.route_confidence = float(np.mean(confidences)) if confidences else 0.0

            # Only now mark route as valid for rendering
            st.session_state.run_route = True

    except Exception as e:
        st.error(f"Failed: {e}")
        st.session_state.run_route = False

# ---- DASHBOARD LAYOUT ----
if st.session_state.run_route and st.session_state.all_results:

    st.markdown('<div class="section-header">📊 Route Safety Dashboard</div>', unsafe_allow_html=True)

    # Section A: Summary Cards
    col1_dash, col2_dash, col3_dash = st.columns(3)

    label_class = st.session_state.route_label.lower().replace(" ", "-")

    with col1_dash:
        st.markdown(f"""
        <div class="metric-card {label_class}-card">
            <h3 style="margin: 0 0 0.5rem 0;">Risk Score</h3>
            <h1 style="margin: 0; font-size: 2.5rem;">{1-st.session_state.route_confidence:.1%}</h1>
        </div>
        """, unsafe_allow_html=True)

    with col2_dash:
        st.markdown(f"""
        <div class="metric-card {label_class}-card">
            <h3 style="margin: 0 0 0.5rem 0;">Confidence</h3>
            <h1 style="margin: 0; font-size: 2.5rem;">{st.session_state.route_confidence:.1%}</h1>
        </div>
        """, unsafe_allow_html=True)

    with col3_dash:
        st.markdown(f"""
        <div class="metric-card {label_class}-card">
            <h3 style="margin: 0 0 0.5rem 0;">Safety Label</h3>
            <h1 style="margin: 0; font-size: 2.5rem;">{st.session_state.route_label}</h1>
        </div>
        """, unsafe_allow_html=True)

    # Section B: Route Map
    st.markdown('<div class="section-header">🗺️ Route Map</div>', unsafe_allow_html=True)

    points = interpolate_points(
        start_lat,
        start_lon,
        end_lat,
        end_lon,
        n_points=20,
    )

    center_lat = (start_lat + end_lat) / 2
    center_lon = (start_lon + end_lon) / 2

    m = folium.Map(location=[center_lat, center_lon], zoom_start=13)

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

    color = score_to_color(st.session_state.route_label)

    folium.PolyLine(
        locations=points,
        color=color,
        weight=8,
        tooltip=f"Route safety: {st.session_state.route_label}",
    ).add_to(m)

    st_folium(m, width=1200, height=600)

    # Section C: Risk Factors
    st.markdown('<div class="section-header">⚠️ Risk Factors</div>', unsafe_allow_html=True)
    factors = aggregate_factors(st.session_state.all_results)
    if factors:
        for factor in factors:
            st.error(f"• {factor}")
    else:
        st.success("✅ No major risk factors detected")

    # Section D: AI Explanation
    st.markdown('<div class="section-header">🤖 AI Explanation</div>', unsafe_allow_html=True)
    explanation = generate_explanation(factors)
    st.info(explanation)

    # Section E: Context Signals
    st.markdown('<div class="section-header">📈 Context Signals</div>', unsafe_allow_html=True)

    last_result = st.session_state.all_results[-1] if st.session_state.all_results else {}
    weather = last_result.get("weather", {}) or {}
    traffic = last_result.get("traffic", {}) or {}

    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Weather")
        st.metric("Rain", "Yes" if weather.get("rain") else "No")
        st.metric("Fog", "Yes" if weather.get("fog") else "No")
        st.metric("Visibility", f"{weather.get('visibility', 1.0):.2f}")

    with col_right:
        st.subheader("Traffic")
        st.metric("Distance", f"{traffic.get('distance_km', 0.0):.2f} km")
        st.metric("Time", f"{traffic.get('duration_hr', 0.0) * 60:.1f} min")
        st.metric("Congestion", f"{traffic.get('congestion', 0.0):.3f}")
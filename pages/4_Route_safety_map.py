
import os
from typing import List, Tuple, Dict, Any
from collections import Counter
 
import numpy as np
import requests
import streamlit as st
import folium
from streamlit_folium import st_folium
 
# ---- MUST be first Streamlit call ----
st.set_page_config(page_title="Route safety map", page_icon="🗺️", layout="wide")
 
# ---- Anchor at top (for scroll reset) ----
st.markdown("<div id='top'></div>", unsafe_allow_html=True)
 
# ---- Backend config ----
BACKEND_URL = os.getenv("BACKEND_URL", "http://0.0.0.0:8000")

API_HEADERS = {
    "X-API-Key": os.getenv("API_KEY", "supersecret123")
}
 
# ---- Simple CSS styling ----
st.markdown(
    """
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
""",
    unsafe_allow_html=True,
)
 
 
# ---- Helpers ----
def interpolate_points(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
    n_points: int = 8,
) -> List[Tuple[float, float]]:
    lats = np.linspace(lat1, lat2, n_points)
    lons = np.linspace(lon1, lon2, n_points)
    return list(zip(lats, lons))
 
 
def call_api_for_point(
    lat: float,
    lon: float,
    base_payload: Dict[str, Any],
) -> Dict[str, Any]:
    payload = base_payload.copy()
    payload["latitude"] = float(lat)
    payload["longitude"] = float(lon)    
    resp = requests.post(f"{BACKEND_URL}/predict", json=payload, headers=API_HEADERS, timeout=5)
    resp.raise_for_status()
    return resp.json()
 
 
@st.cache_data(show_spinner=False)
def call_api_cached(lat: float, lon: float, base_payload: Dict[str, Any]) -> Dict[str, Any]:
    return call_api_for_point(lat, lon, base_payload)
 
 
def score_to_color(label: str) -> str:
    return {"Safe": "green", "Moderate": "orange"}.get(label, "red")
 
 
def aggregate_factors(all_results: List[Dict[str, Any]]) -> List[str]:
    seen, unique = set(), []
    for r in all_results:
        for f in r.get("factors", []):
            if f not in seen:
                seen.add(f)
                unique.append(f)
    return unique[:5]
 
 
def generate_explanation(factors: List[str]) -> str:
    if not factors:
        return "No major risk factors detected."
    label = st.session_state.get("route_label", "Safe")
    factor_list = (
        factors[0] if len(factors) == 1
        else ", ".join(factors[:-1]) + f" and {factors[-1]}"
    )
    return f"This route is {label.lower()} due to {factor_list}."
 
 
# ---- Session state defaults ----
for key, default in [
    ("run_route", False),
    ("all_results", []),
    ("route_label", ""),
    ("route_confidence", 0.0),
    ("points", []),
    ("show_map", False),
]:
    if key not in st.session_state:
        st.session_state[key] = default
 
 
# ---- Page title & description ----
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
 
# ============================
#  FORM: all inputs + submit
# ============================
with st.form("route_form"):
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
        "Distance to main road (meters)", 0, 2000, 200, step=50,
    )
    shops_open_at_night = st.selectbox(
        "Shops open at night?", [0, 1], format_func=lambda v: "Yes" if v else "No",
    )
    police_station_within_1km = st.selectbox(
        "Police station within 1 km?", [0, 1], format_func=lambda v: "Yes" if v else "No",
    )
    cctv_present = st.selectbox(
        "CCTV present?", [0, 1], format_func=lambda v: "Yes" if v else "No",
    )
    hour_of_day = st.slider("Hour of day (0–23)", 0, 23, 20)
    is_weekend = st.selectbox(
        "Is it weekend?", [0, 1], format_func=lambda v: "Yes" if v else "No",
    )
    area_type = st.selectbox(
        "Area type",
        [0, 1, 2],
        format_func=lambda v: ["Residential", "Commercial/Market", "Office/IT park"][v],
    )
    near_metro_or_bus = st.selectbox(
        "Near metro or major bus stop?", [0, 1], format_func=lambda v: "Yes" if v else "No",
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
 
    submitted = st.form_submit_button("Compute route safety")
 
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
 
# ============================
#  COMPUTE on submit
# ============================
if submitted:
    # Reset everything cleanly before computation so no stale state leaks
    st.session_state.show_map = False
    st.session_state.run_route = False
    st.session_state.all_results = []
 
    points = interpolate_points(start_lat, start_lon, end_lat, end_lon, n_points=8)
    st.session_state.points = points
    labels, confidences = [], []
 
    with st.spinner("Analyzing route safety..."):
        for lat, lon in points:
            try:
                result = call_api_cached(lat, lon, base_payload)
                if not result or "label" not in result:
                    continue
                st.session_state.all_results.append(result)
                labels.append(result["label"])
                probs = result.get("probabilities", {})
                confidences.append(
                    max(probs.get("unsafe", 0.0), probs.get("moderate", 0.0), probs.get("safe", 0.0))
                )
            except Exception as e:
                st.warning(f"API failed at ({lat:.4f}, {lon:.4f}): {e}")
 
    if st.session_state.all_results:
        label_counts = Counter(labels)
        st.session_state.route_label = label_counts.most_common(1)[0][0]
        st.session_state.route_confidence = float(np.mean(confidences))
        st.session_state.run_route = True
        # Only flip show_map=True after ALL computation is done —
        # this and run_route are set together so they're always in sync
        st.session_state.show_map = True
    else:
        st.error("No results received from backend.")
 
# ============================
#  DASHBOARD
# ============================
if st.session_state.run_route and st.session_state.all_results:
 
    st.markdown(
        '<div class="section-header">📊 Route Safety Dashboard</div>',
        unsafe_allow_html=True,
    )
 
    label = st.session_state.route_label
    label_class = label.lower().replace(" ", "-")
    col1_dash, col2_dash, col3_dash = st.columns(3)
 
    with col1_dash:
        st.markdown(
            f"""
        <div class="metric-card {label_class}-card">
            <h3 style="margin: 0 0 0.5rem 0;">Risk Score</h3>
            <h1 style="margin: 0; font-size: 2.5rem;">{1 - st.session_state.route_confidence:.1%}</h1>
        </div>
        """,
            unsafe_allow_html=True,
        )
 
    with col2_dash:
        st.markdown(
            f"""
        <div class="metric-card {label_class}-card">
            <h3 style="margin: 0 0 0.5rem 0;">Confidence</h3>
            <h1 style="margin: 0; font-size: 2.5rem;">{st.session_state.route_confidence:.1%}</h1>
        </div>
        """,
            unsafe_allow_html=True,
        )
 
    with col3_dash:
        st.markdown(
            f"""
        <div class="metric-card {label_class}-card">
            <h3 style="margin: 0 0 0.5rem 0;">Safety Label</h3>
            <h1 style="margin: 0; font-size: 2.5rem;">{label}</h1>
        </div>
        """,
            unsafe_allow_html=True,
        )
 
    # ---- Route Map ----
    st.markdown(
        '<div class="section-header">🗺️ Route Map</div>',
        unsafe_allow_html=True,
    )
 
    # Guard only on show_map — the old `and not loading` check was the
    # root cause of the map vanishing; loading is always False at render time.
    if st.session_state.show_map:
        points = st.session_state.points
        center_lat = sum(p[0] for p in points) / len(points)
        center_lon = sum(p[1] for p in points) / len(points)
 
        m = folium.Map(location=[center_lat, center_lon], zoom_start=13)
 
        folium.Marker(
            location=[points[0][0], points[0][1]],
            popup="Start",
            icon=folium.Icon(color="blue"),
        ).add_to(m)
 
        folium.Marker(
            location=[points[-1][0], points[-1][1]],
            popup="End",
            icon=folium.Icon(color="blue"),
        ).add_to(m)
 
        folium.PolyLine(
            locations=points,
            color=score_to_color(label),
            weight=8,
            tooltip=f"Route safety: {label}",
        ).add_to(m)
 
        # Fixed, stable key — prevents st_folium from re-initialising the
        # widget (and triggering yet another rerun) on map pan/zoom.
        st_folium(m, width=1200, height=600, key="route_safety_map")
    else:
        st.info("Map will appear after the route safety analysis finishes.")
 
    # ---- Risk Factors ----
    st.markdown(
        '<div class="section-header">⚠️ Risk Factors</div>',
        unsafe_allow_html=True,
    )
    factors = aggregate_factors(st.session_state.all_results)
    if factors:
        for f in factors:
            st.error(f"• {f}")
    else:
        st.success("✅ No major risk factors detected")
 
    # ---- AI Explanation ----
    st.markdown(
        '<div class="section-header">🤖 AI Explanation</div>',
        unsafe_allow_html=True,
    )
    st.info(generate_explanation(factors))
 
    # ---- Context Signals ----
    st.markdown(
        '<div class="section-header">📈 Context Signals</div>',
        unsafe_allow_html=True,
    )
 
    last_result = st.session_state.all_results[-1]
    weather = last_result.get("weather") or {}
    traffic = last_result.get("traffic") or {}
 
    if "failed" in str(last_result.get("shap_explanation", "")).lower():
        st.info("Explanation not available for this route segment.")
 
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
 
# ---- Scroll back to top ----
st.markdown(
    """
    <script>
    const topDiv = document.getElementById('top');
    if (topDiv) { topDiv.scrollIntoView({behavior: "smooth"}); }
    </script>
    """,
    unsafe_allow_html=True,
)
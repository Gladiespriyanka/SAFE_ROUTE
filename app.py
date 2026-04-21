import os
import csv
from datetime import datetime
import requests
import streamlit as st
import folium
from streamlit_folium import st_folium

# FORCE the backend URL to 127.0.0.1:8000
BACKEND_URL = "http://127.0.0.1:8000"
API_URL = f"{BACKEND_URL}/predict"
API_BASE = BACKEND_URL
AUDIT_URL = f"{BACKEND_URL}/audit"

API_KEY = os.getenv("API_KEY")
if not API_KEY:
    raise ValueError("API_KEY not set in environment variables")
API_HEADERS = {"X-API-Key": API_KEY}

st.set_page_config(page_title="SafeRoute Delhi", page_icon="🛣️", layout="centered")

LABEL_COLORS = {
    "Unsafe": "red",
    "Moderate": "orange",
    "Safe": "green",
}

st.markdown(
    """
<style>
    .stMetric {
        background-color: #0e1117;
        padding: 15px;
        border-radius: 10px;
        text-align: center;
        border: 1px solid #30363d;
    }
    .mode-header {
        padding: 10px 16px;
        border-radius: 8px;
        margin-bottom: 8px;
    }
</style>
""",
    unsafe_allow_html=True,
)

LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "predictions.csv")


def ensure_log_file_exists():
    os.makedirs(LOG_DIR, exist_ok=True)
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "timestamp",
                    "latitude",
                    "longitude",
                    "lighting_level",
                    "crowd_level",
                    "distance_to_main_road_m",
                    "shops_open_at_night",
                    "police_station_within_1km",
                    "cctv_present",
                    "hour_of_day",
                    "is_weekend",
                    "area_type",
                    "near_metro_or_bus",
                    "past_incidents_level",
                    "group_travel",
                    "predicted_label",
                    "predicted_label_text",
                    "confidence_level",
                    "confidence_score",
                    "prob_unsafe",
                    "prob_moderate",
                    "prob_safe",
                ]
            )


def log_prediction(payload: dict, result: dict):
    ensure_log_file_exists()
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        probs = result["probabilities"]
        confidence_score = result.get("confidence")
        confidence_level = result.get("confidence_level")
        writer.writerow(
            [
                datetime.utcnow().isoformat(),
                payload.get("latitude"),
                payload.get("longitude"),
                payload["lighting_level"],
                payload["crowd_level"],
                payload["distance_to_main_road_m"],
                payload["shops_open_at_night"],
                payload["police_station_within_1km"],
                payload["cctv_present"],
                payload["hour_of_day"],
                payload["is_weekend"],
                payload["area_type"],
                payload["near_metro_or_bus"],
                payload["past_incidents_level"],
                payload["group_travel"],
                result.get("prediction"),
                result["label"],
                confidence_level,
                confidence_score,
                probs["unsafe"],
                probs["moderate"],
                probs["safe"],
            ]
        )


# ─────────────────────────────────────────────
# Page header
# ─────────────────────────────────────────────
st.title("SafeRoute Delhi – Women-centric Route Safety Scorer")
st.write(
    "Estimate how safe a location or route feels for women based on lighting, crowd, "
    "area context, time of day, and nearby public infrastructure."
)

# ─────────────────────────────────────────────
# Mode selector  (drives the whole page)
# ─────────────────────────────────────────────
st.markdown("---")
mode = st.radio(
    "What would you like to do?",
    ["📍 Score a single location", "🗺️ Find the safest route between two points"],
    horizontal=True,
)

# ─────────────────────────────────────────────
# Shared context inputs (apply to both modes)
# ─────────────────────────────────────────────
st.markdown("### Environmental & time context")
st.caption("These inputs describe the conditions at the time of travel.")

col1, col2, col3 = st.columns(3)

with col1:
    lighting = st.selectbox(
        "Lighting level",
        [0, 1, 2],
        format_func=lambda v: ["Very poor", "OK", "Good"][v],
    )
    crowd = st.selectbox(
        "Crowd level",
        [0, 1, 2],
        format_func=lambda v: ["Empty", "Some people", "Busy/Active"][v],
    )
    distance = st.slider("Distance to main road (m)", 0, 2000, 200, step=50)

with col2:
    shops = st.selectbox(
        "Shops open at night?",
        [0, 1],
        format_func=lambda v: "Yes" if v else "No",
    )
    police = st.selectbox(
        "Police station within 1 km?",
        [0, 1],
        format_func=lambda v: "Yes" if v else "No",
    )
    cctv = st.selectbox(
        "CCTV present?",
        [0, 1],
        format_func=lambda v: "Yes" if v else "No",
    )

with col3:
    hour = st.slider("Hour of day (0–23)", 0, 23, 20)
    weekend = st.selectbox(
        "Is it weekend?",
        [0, 1],
        format_func=lambda v: "Yes" if v else "No",
    )
    area_type = st.selectbox(
        "Area type",
        [0, 1, 2],
        format_func=lambda v: ["Residential", "Commercial/Market", "Office/IT park"][v],
    )

col4, col5 = st.columns(2)
with col4:
    near_metro_or_bus = st.selectbox(
        "Near metro or major bus stop?",
        [0, 1],
        format_func=lambda v: "Yes" if v else "No",
    )
    past_incidents_level = st.selectbox(
        "Past incidents level",
        [0, 1, 2],
        format_func=lambda v: ["Low", "Medium", "High"][v],
    )
with col5:
    group_travel = st.selectbox(
        "Travelling alone or with others?",
        [0, 1],
        format_func=lambda v: "Alone" if v == 0 else "With others",
    )

# ─────────────────────────────────────────────────────────────────────────────
# Session state initialisation
# ─────────────────────────────────────────────────────────────────────────────
for key in ("prediction_result", "prediction_payload", "route_options"):
    if key not in st.session_state:
        st.session_state[key] = None

# =============================================================================
# MODE A – Single-point safety score
# =============================================================================
if mode == "📍 Score a single location":

    st.markdown("---")
    st.markdown("### 📍 Location to score")

    col_lat, col_lon = st.columns(2)
    with col_lat:
        latitude = st.number_input(
            "Latitude",
            value=28.6139,
            format="%.6f",
            help="Latitude of the point you want to score",
        )
    with col_lon:
        longitude = st.number_input(
            "Longitude",
            value=77.2090,
            format="%.6f",
            help="Longitude of the point you want to score",
        )

    with st.expander("Don’t know your latitude/longitude?"):
        st.markdown(
            "- Open Google Maps.\n"
            "- Long-press your location on the map.\n"
            "- Tap the dropped pin and copy the decimal coordinates.\n"
            "- Paste them into the fields above."
        )

        preset = st.selectbox(
            "Or quickly try a known area in Delhi",
            ["None", "CP (Rajiv Chowk)", "Saket", "Dwarka Mor"],
        )

        if preset == "CP (Rajiv Chowk)":
            latitude = 28.6328
            longitude = 77.2197
        elif preset == "Saket":
            latitude = 28.5246
            longitude = 77.2066
        elif preset == "Dwarka Mor":
            latitude = 28.6219
            longitude = 77.0424

        # Reflect any preset in the UI
        st.write(
            f"Using coordinates: latitude={latitude:.6f}, longitude={longitude:.6f}"
        )

    # Clear any stale route state when switching modes
    st.session_state.route_options = None

    def run_prediction(lat, lon):
        payload = {
            "latitude": float(lat),
            "longitude": float(lon),
            "lighting_level": int(lighting),
            "crowd_level": int(crowd),
            "distance_to_main_road_m": float(distance),
            "shops_open_at_night": int(shops),
            "police_station_within_1km": int(police),
            "cctv_present": int(cctv),
            "hour_of_day": int(hour),
            "is_weekend": int(weekend),
            "area_type": int(area_type),
            "near_metro_or_bus": int(near_metro_or_bus),
            "past_incidents_level": int(past_incidents_level),
            "group_travel": int(group_travel),
        }
        try:
            resp = requests.post(API_URL, json=payload, headers=API_HEADERS, timeout=5)
            if resp.status_code != 200:
                st.error(f"API error: {resp.status_code} – {resp.text}")
                return
            data = resp.json()
            if "error" in data:
                st.error(f"Backend error: {data['error']}")
                return
            st.session_state.prediction_result = data
            st.session_state.prediction_payload = payload
            log_prediction(payload, data)
        except Exception as e:
            st.error(f"Failed to call API: {e}")

    if st.button("Check safety", type="primary"):
        run_prediction(latitude, longitude)

    # ── Results ──────────────────────────────────────────────────────────────
    data = st.session_state.prediction_result
    payload = st.session_state.prediction_payload

    if data is not None and payload is not None:
        label_text = data["label"]
        probs = data["probabilities"]
        confidence_score = data.get("confidence")
        confidence_level = data.get("confidence_level")
        shap_factors = data.get("shap_explanation", {}).get("top_factors", [])

        # Build a short natural-language verdict summary
        tier = data.get("risk_tier", "")
        factors = data.get("factors", [])
        short_reason = ""
        if factors:
            short_reason = "Main reasons: " + ", ".join(factors[:2]) + "."

        st.write(
            f"This spot is considered **{label_text.lower()}** "
            f"{'('+tier.lower()+') ' if tier else ''}"
            f"for women under the conditions you entered. {short_reason}"
        )

        # Simple safety hint based on label
        if label_text == "Unsafe":
            st.warning(
                "Try choosing a busier, better-lit path or travelling with company if possible."
            )
        elif label_text == "Moderate":
            st.info(
                "Conditions are mixed. Prefer main roads, stay aware of surroundings, and avoid very quiet stretches."
            )

        st.markdown("---")
        st.markdown("## 🧠 Safety Analysis")

        # Summary cards
        m_col1, m_col2, m_col3 = st.columns(3)
        with m_col1:
            st.metric(
                "Risk Score",
                f"{data.get('risk_score', 0)} ({data.get('risk_tier', '')})",
            )
        with m_col2:
            st.metric("Confidence", f"{data.get('confidence', 0):.2f}")
        with m_col3:
            if label_text == "Unsafe":
                st.error("🔴 Unsafe")
            elif label_text == "Moderate":
                st.warning("🟠 Moderate")
            else:
                st.success("🟢 Safe")

        # Point map – clearly scoped to the scored location
        st.markdown("#### 📍 Scored location")
        point_map = folium.Map(location=[payload["latitude"], payload["longitude"]], zoom_start=15)
        folium.Marker(
            [payload["latitude"], payload["longitude"]],
            popup=f"Scored point – {label_text}",
            icon=folium.Icon(color=LABEL_COLORS.get(label_text, "gray").replace("red", "red").replace("orange", "orange").replace("green", "green")),
        ).add_to(point_map)
        st_folium(point_map, width=700, height=350, key="point_map")

        # Verdict
        color = LABEL_COLORS.get(label_text, "gray")
        st.markdown(
            f"<h3 style='color:{color}'>Predicted safety: {label_text}</h3>",
            unsafe_allow_html=True,
        )

        description = data.get("description", "")
        if description:
            st.write(description)

        if confidence_score is not None and confidence_level:
            st.write(
                f"**Confidence**: {confidence_level} "
                f"({confidence_score:.2f} max class probability)"
            )

        st.write(
            f"Probabilities → "
            f"**Unsafe**: {probs['unsafe']:.2f}, "
            f"**Moderate**: {probs['moderate']:.2f}, "
            f"**Safe**: {probs['safe']:.2f}"
        )

        # Analysis details
        st.markdown("### ⚠️ Analysis Details")
        f_col1, f_col2 = st.columns(2)
        factors = data.get("factors", [])

        with f_col1:
            st.markdown("#### Risk Factors")
            if factors:
                for f in factors:
                    st.markdown(f"- {f}")
            else:
                st.success("No major risk factors detected")

        with f_col2:
            st.markdown("#### AI Explanation")
            if factors:
                explanation = f"This location is considered **{label_text.lower()}** due to: "
                explanation += ", ".join(factors) + "."
                st.info(explanation)
            else:
                st.info("Standard conditions detected for this area.")

        # Context signals
        st.markdown("### 🌍 Context Signals")
        ctx_col1, ctx_col2 = st.columns(2)

        with ctx_col1:
            st.markdown("#### 🌧 Weather")
            weather = data.get("weather", {})
            st.write(f"Rain: {'Yes' if weather.get('rain') else 'No'}")
            st.write(f"Fog: {'Yes' if weather.get('fog') else 'No'}")
            st.write(f"Visibility: {weather.get('visibility', 1.0):.2f}")

        with ctx_col2:
            st.markdown("#### 🚦 Traffic")
            traffic = data.get("traffic", {})
            st.write(f"Distance: {traffic.get('distance_km', 0):.2f} km")
            st.write(f"Time: {traffic.get('duration_hr', 0) * 60:.1f} mins")
            st.write(f"Congestion: {traffic.get('congestion', 0):.3f}")

        # SHAP factors
        st.markdown("#### Key contributing factors (SHAP)")
        if shap_factors:
            for factor in shap_factors:
                feature_name = factor.get("feature", "Unknown feature")
                impact = factor.get("impact")
                if impact is not None:
                    st.write(f"- {feature_name} (impact {impact:.4f})")
                else:
                    st.write(f"- {feature_name}")
        else:
            st.info("Detailed factor breakdown is not available for this prediction.")

        # Nearby infrastructure & audits
        st.markdown("### Nearby public infrastructure & audits")
        infra_col, audit_col = st.columns(2)

        with infra_col:
            st.subheader("Nearest public infrastructure")
            try:
                resp_poi = requests.get(
                    f"{API_BASE}/poi_context",
                    params={"lat": payload["latitude"], "lon": payload["longitude"]},
                    headers=API_HEADERS,
                    timeout=5,
                )
                if resp_poi.status_code == 200:
                    poi_data = resp_poi.json()
                    st.write(f"- **Metro**: {poi_data.get('dist_to_metro_m', 0):.0f} m")
                    st.write(f"- **Bus stop**: {poi_data.get('dist_to_bus_m', 0):.0f} m")
                    st.write(f"- **Hospital**: {poi_data.get('dist_to_hospital_m', 0):.0f} m")
                    st.write(f"- **Police station**: {poi_data.get('dist_to_police_m', 0):.0f} m")
                else:
                    st.info("POI context not available right now.")
            except Exception as e:
                st.info(f"Could not load POI context: {e}")

        with audit_col:
            st.subheader("Recent audits within 300 m")
            try:
                resp_audits = requests.get(
                    f"{API_BASE}/audit/nearby",
                    params={
                        "lat": payload["latitude"],
                        "lon": payload["longitude"],
                        "radius_m": 300.0,
                        "limit": 10,
                    },
                    headers=API_HEADERS,
                    timeout=5,
                )
                if resp_audits.status_code == 200:
                    audits = resp_audits.json()
                    if not audits:
                        st.write("No audits logged around this point yet.")
                    else:
                        label_map = {0: "Very unsafe", 1: "Okay", 2: "Feels safe"}
                        for a in audits:
                            _label_text = label_map.get(a.get("perceived_safety", 0), "Unknown")
                            dist_m = a.get("distance_m", 0.0)
                            comment = a.get("comment") or ""
                            st.markdown(
                                f"- {_label_text} ({dist_m:.0f} m away)"
                                + (f" — _{comment}_" if comment else "")
                            )
                else:
                    st.info("Could not load nearby audits.")
            except Exception as e:
                st.info(f"Could not load nearby audits: {e}")

        # Feedback
        st.markdown("---")
        st.markdown("#### Was this prediction helpful?")
        col_yes, col_no = st.columns(2)

        with col_yes:
            if st.button("👍 Yes, feels accurate"):
                fb_payload = {
                    **payload,
                    "predicted_label": data["prediction"],
                    "predicted_label_text": data["label"],
                    "user_agrees": 1,
                    "comment": None,
                }
                fb_resp = requests.post(
                    f"{API_BASE}/feedback",
                    json=fb_payload,
                    headers=API_HEADERS,
                    timeout=5,
                )
                if fb_resp.status_code == 200:
                    st.success("Thanks for your feedback!")
                else:
                    st.error("Failed to send feedback.")

        with col_no:
            if st.button("👎 Not accurate"):
                comment = st.text_input(
                    "What felt wrong or missing?",
                    key="feedback_comment",
                    placeholder="Optional: e.g., 'Area usually feels safer than this score.'",
                )
                if st.button("Submit feedback", key="submit_feedback_button"):
                    fb_payload = {
                        **payload,
                        "predicted_label": data["prediction"],
                        "predicted_label_text": data["label"],
                        "user_agrees": 0,
                        "comment": comment or None,
                    }
                    fb_resp = requests.post(
                        f"{API_BASE}/feedback",
                        json=fb_payload,
                        headers=API_HEADERS,
                        timeout=5,
                    )
                    if fb_resp.status_code == 200:
                        st.success("Feedback recorded, thank you!")
                    else:
                        st.error("Failed to send feedback.")

        # Community audit submission
        st.markdown("---")
        st.markdown("### 📝 Audit this place")
        st.caption(
            "Log how this exact point feels to you right now. "
            "These audits improve the model over time."
        )

        col_a1, col_a2 = st.columns(2)
        with col_a1:
            audit_lighting = st.selectbox(
                "Lighting here now",
                [0, 1, 2],
                format_func=lambda v: ["Very poor", "OK", "Good"][v],
                key="audit_lighting",
            )
            audit_crowd = st.selectbox(
                "Crowd here now",
                [0, 1, 2],
                format_func=lambda v: ["Empty", "Some people", "Busy/Active"][v],
                key="audit_crowd",
            )
        with col_a2:
            perceived_safety = st.selectbox(
                "How safe does it feel overall?",
                [0, 1, 2],
                format_func=lambda v: ["Very unsafe", "Okay", "Feels safe"][v],
                key="perceived_safety",
            )
            audit_area_type = st.selectbox(
                "Area type (optional)",
                [None, 0, 1, 2],
                format_func=lambda v: (
                    "Not specified"
                    if v is None
                    else ["Residential", "Commercial/Market", "Office/IT park"][v]
                ),
                key="audit_area_type",
            )

        audit_comment = st.text_input(
            "Optional comment",
            placeholder="e.g., 'dark corner near park, men loitering'",
            key="audit_comment",
        )

        if st.button("Submit audit"):
            audit_payload = {
                "latitude": float(payload["latitude"]),
                "longitude": float(payload["longitude"]),
                "lighting_level": int(audit_lighting),
                "crowd_level": int(audit_crowd),
                "perceived_safety": int(perceived_safety),
                "comment": audit_comment or None,
                "hour_of_day": int(hour),
                "is_weekend": int(weekend),
                "area_type": None if audit_area_type is None else int(audit_area_type),
            }
            try:
                resp = requests.post(AUDIT_URL, json=audit_payload, headers=API_HEADERS, timeout=5)
                if resp.status_code == 200:
                    st.success("Audit saved. Thank you for contributing!")
                else:
                    st.error(f"Failed to save audit: {resp.status_code} – {resp.text}")
            except Exception as e:
                st.error(f"Failed to call audit API: {e}")


# =============================================================================
# MODE B – Route safety (multi-point)
# =============================================================================
elif mode == "🗺️ Find the safest route between two points":

    # Clear any stale single-point state when switching modes
    st.session_state.prediction_result = None
    st.session_state.prediction_payload = None

    st.markdown("---")
    st.markdown("### 🗺️ Origin & Destination")
    st.caption(
        "Enter the start and end coordinates. The app will fetch several candidate "
        "routes and colour them by predicted safety (🟢 safer → 🟠 moderate → 🔴 unsafe)."
    )

    col_s1, col_s2 = st.columns(2)
    with col_s1:
        st.markdown("**Origin**")
        start_lat = st.number_input("Start latitude", value=28.6139, format="%.6f", key="start_lat")
        start_lon = st.number_input("Start longitude", value=77.2090, format="%.6f", key="start_lon")
    with col_s2:
        st.markdown("**Destination**")
        end_lat = st.number_input("Destination latitude", value=28.6350, format="%.6f", key="end_lat")
        end_lon = st.number_input("Destination longitude", value=77.2200, format="%.6f", key="end_lon")

    if st.button("Find safest routes", type="primary"):
        route_payload = {
            "start_lat": float(start_lat),
            "start_lon": float(start_lon),
            "end_lat": float(end_lat),
            "end_lon": float(end_lon),
            "lighting_level": int(lighting),
            "crowd_level": int(crowd),
            "distance_to_main_road_m": float(distance),
            "shops_open_at_night": int(shops),
            "police_station_within_1km": int(police),
            "cctv_present": int(cctv),
            "hour_of_day": int(hour),
            "is_weekend": int(weekend),
            "area_type": int(area_type),
            "near_metro_or_bus": int(near_metro_or_bus),
            "past_incidents_level": int(past_incidents_level),
            "group_travel": int(group_travel),
        }
        with st.spinner("Fetching candidate routes and scoring them…"):
            try:
                resp = requests.post(
                    f"{API_BASE}/routes/safe_options",
                    params=route_payload,
                    headers=API_HEADERS,
                    timeout=60,
                )
                if resp.status_code != 200:
                    st.error(f"Route API error: {resp.status_code} – {resp.text}")
                    st.session_state.route_options = None
                else:
                    st.session_state.route_options = resp.json()
                    # Remember which origin/destination produced these routes
                    st.session_state.route_origin = (float(start_lat), float(start_lon))
                    st.session_state.route_dest = (float(end_lat), float(end_lon))
            except Exception as e:
                st.error(f"Failed to fetch routes: {e}")
                st.session_state.route_options = None

    # ── Route results ─────────────────────────────────────────────────────────
    data_routes = st.session_state.route_options
    origin = st.session_state.get("route_origin")
    dest = st.session_state.get("route_dest")

    if data_routes and "routes" in data_routes and origin and dest:
        routes = data_routes["routes"]

        if not routes:
            st.warning("No candidate routes were returned. Try adjusting the coordinates.")
        else:
            st.markdown("---")
            st.markdown(f"### Results: {len(routes)} candidate route(s) found")
            st.caption(
                "Routes are sorted safest-first. Colours: 🟢 relatively safer · "
                "🟠 mixed/moderate · 🔴 mostly unsafe"
            )
            st.markdown("Legend: 🟢 relatively safer · 🟠 mixed · 🔴 mostly unsafe · ⭐ safest route")

            # Summary table
            summary_rows = []
            for idx, r in enumerate(routes, start=1):
                length_km = (r.get("approx_length") or 0) / 1000
                summary_rows.append(
                    {
                        "Route": f"Route {idx}",
                        "Safety": r["safety_label"],
                        "Avg risk": f"{r['avg_risk']:.1f}",
                        "Max risk": f"{r['max_risk']:.1f}",
                        "% unsafe pts": f"{r['unsafe_fraction'] * 100:.0f}%",
                        "Length": f"{length_km:.2f} km" if length_km else "—",
                    }
                )
            st.dataframe(summary_rows, use_container_width=True, hide_index=True)

            # Route map – centred between origin and destination
            mid_lat = (origin[0] + dest[0]) / 2
            mid_lon = (origin[1] + dest[1]) / 2
            route_map = folium.Map(location=[mid_lat, mid_lon], zoom_start=13)

            folium.Marker(
                list(origin),
                popup="Origin",
                icon=folium.Icon(color="blue", icon="play"),
            ).add_to(route_map)
            folium.Marker(
                list(dest),
                popup="Destination",
                icon=folium.Icon(color="purple", icon="stop"),
            ).add_to(route_map)

            for idx, route in enumerate(routes, start=1):
                coords = route["coordinates"]
                is_best = idx == 1  # first route is safest (sorted safest-first)

                folium.PolyLine(
                    locations=coords,
                    color=route.get("color", "blue"),
                    weight=7 if is_best else 4,
                    opacity=0.9 if is_best else 0.6,
                    tooltip=(
                        f"{'⭐ ' if is_best else ''}"
                        f"Route {idx}: {route['safety_label']} "
                        f"(avg risk {route['avg_risk']:.1f}, "
                        f"max {route['max_risk']:.1f})"
                    ),
                ).add_to(route_map)

            st_folium(route_map, width=900, height=500, key="route_map")

            # Per-route detail expanders
            st.markdown("#### Route details")
            for idx, route in enumerate(routes, start=1):
                color_emoji = {"green": "🟢", "orange": "🟠", "red": "🔴"}.get(
                    route.get("color", ""), "⚪"
                )
                length_km = (route.get("approx_length") or 0) / 1000
                with st.expander(
                    f"{color_emoji} Route {idx} – {route['safety_label']}"
                    + (f" · {length_km:.2f} km" if length_km else "")
                ):
                    d_col1, d_col2, d_col3 = st.columns(3)
                    d_col1.metric("Avg risk score", f"{route['avg_risk']:.1f}")
                    d_col2.metric("Max risk score", f"{route['max_risk']:.1f}")
                    d_col3.metric(
                        "Unsafe segment share",
                        f"{route['unsafe_fraction'] * 100:.0f}%",
                    )

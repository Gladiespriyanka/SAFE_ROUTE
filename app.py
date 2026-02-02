import os
import csv
from datetime import datetime

import requests
import streamlit as st

API_URL = "http://127.0.0.1:8000/predict"

st.set_page_config(page_title="SafeRoute Delhi", page_icon="🛣️", layout="centered")

LABEL_COLORS = {
    "Unsafe": "red",
    "Moderate": "orange",
    "Safe": "green",
}

LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "predictions.csv")


def ensure_log_file_exists():
    os.makedirs(LOG_DIR, exist_ok=True)
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "timestamp",
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
            ])


def log_prediction(payload: dict, result: dict):
    ensure_log_file_exists()
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        probs = result["probabilities"]
        conf = result.get("confidence", {})
        writer.writerow([
            datetime.utcnow().isoformat(),
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
            result["label"],
            result["label_text"],
            conf.get("level"),
            conf.get("score"),
            probs["unsafe"],
            probs["moderate"],
            probs["safe"],
        ])


st.title("SafeRoute Delhi – Women-centric Route Safety Scorer")
st.write(
    "Estimate how safe a location or route segment feels for women based on lighting, crowd, "
    "area context, time of day, and nearby public infrastructure."
)

# ----------------------------
# 1. Route segment basics
# ----------------------------
st.markdown("### 1. Describe the route segment")

col1, col2 = st.columns(2)

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
    distance = st.slider("Distance to main road (meters)", 0, 2000, 200, step=50)

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

# ----------------------------
# 2. Time context
# ----------------------------
st.markdown("### 2. Time context")

col3, col4 = st.columns(2)

with col3:
    hour = st.slider("Hour of day (0–23)", 0, 23, 20)
with col4:
    weekend = st.selectbox(
        "Is it weekend?",
        [0, 1],
        format_func=lambda v: "Yes" if v else "No",
    )

# ----------------------------
# 3. Area context (new features)
# ----------------------------
st.markdown("### 3. Area context")

col_a, col_b = st.columns(2)
with col_a:
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
with col_b:
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

# ----------------------------
# Prediction + feedback
# ----------------------------
if st.button("Check safety"):
    payload = {
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
        resp = requests.post(API_URL, json=payload, timeout=5)
        if resp.status_code != 200:
            st.error(f"API error: {resp.status_code} – {resp.text}")
        else:
            data = resp.json()
            if "error" in data:
                st.error(f"Backend error: {data['error']}")
            else:
                # Log this prediction
                log_prediction(payload, data)

                label_text = data["label_text"]
                probs = data["probabilities"]
                conf = data.get("confidence", {})
                reasons_grouped = data.get("reasons_grouped", {})

                st.markdown("### 4. Result")

                color = LABEL_COLORS.get(label_text, "gray")
                st.markdown(
                    f"<h3 style='color:{color}'>Predicted safety: {label_text}</h3>",
                    unsafe_allow_html=True,
                )

                if conf:
                    st.write(
                        f"**Confidence**: {conf['level']} "
                        f"({conf['score']:.2f} max class probability)"
                    )

                st.write(
                    f"Probabilities → "
                    f"**Unsafe**: {probs['unsafe']:.2f}, "
                    f"**Moderate**: {probs['moderate']:.2f}, "
                    f"**Safe**: {probs['safe']:.2f}"
                )

                st.markdown("#### Why this prediction?")

                for group_name, items in reasons_grouped.items():
                    if not items:
                        continue
                    with st.expander(group_name, expanded=(group_name in ["Overall"])):
                        for r in items:
                            st.write(f"- {r}")

                st.markdown("#### Was this prediction helpful?")

                col_yes, col_no = st.columns(2)
                with col_yes:
                    if st.button("👍 Yes, feels accurate"):
                        fb_payload = {
                            **payload,
                            "predicted_label": data["label"],
                            "predicted_label_text": data["label_text"],
                            "user_agrees": 1,
                            "comment": None,
                        }
                        fb_resp = requests.post("http://127.0.0.1:8000/feedback", json=fb_payload, timeout=5)
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
                                "predicted_label": data["label"],
                                "predicted_label_text": data["label_text"],
                                "user_agrees": 0,
                                "comment": comment or None,
                            }
                            fb_resp = requests.post("http://127.0.0.1:8000/feedback", json=fb_payload, timeout=5)
                            if fb_resp.status_code == 200:
                                st.success("Feedback recorded, thank you!")
                            else:
                                st.error("Failed to send feedback.")
    except Exception as e:
        st.error(f"Failed to call API: {e}")

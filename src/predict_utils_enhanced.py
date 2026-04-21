import joblib
import numpy as np
import logging
from typing import Dict, Any, Optional
import shap
from realtime_features import get_weather_data  # ✅ REAL-TIME WEATHER
from traffic_features import get_traffic_data  # ✅ REAL-TIME TRAFFIC


# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Label mapping: 0 = Unsafe, 1 = Moderate, 2 = Safe
LABELS = {
    0: "Unsafe",
    1: "Moderate",
    2: "Safe",
}

LABEL_DESCRIPTIONS = {
    0: "⚠️  Unsafe - High risk area. Avoid if possible. If necessary, travel in groups.",
    1: "⚠️  Moderate - Mixed conditions. Use caution, especially at night.",
    2: "✅ Safe - Relatively safer route. Still maintain awareness.",
}

# Feature mapping
FEATURE_NAME_MAP = {
    "lighting_level": "poor lighting",
    "crowd_level": "low crowd density",
    "past_incidents_level": "high past incidents",
    "distance_to_main_road_m": "far from main road",
    "cctv_present": "lack of CCTV coverage",
    "police_station_within_1km": "no nearby police station",
}


def load_model_and_feature_cols(
    model_path: str = "models/saferoute_model_latest.pkl",
    feature_cols_path: str = "models/feature_cols.pkl",
) -> tuple:
    pipeline = joblib.load(model_path)
    feature_cols = joblib.load(feature_cols_path)
    return pipeline, feature_cols


def sanitize_inputs(
    lighting_level: int,
    crowd_level: int,
    distance_to_main_road_m: float,
    shops_open_at_night: int,
    police_station_within_1km: int,
    cctv_present: int,
    hour_of_day: int,
    is_weekend: int,
    area_type: int = 0,
    near_metro_or_bus: int = 0,
    past_incidents_level: int = 0,
    group_travel: int = 0,
    area_crime_risk: Optional[float] = None,
    audit_score_mean: Optional[float] = None,
    dist_to_metro_m: Optional[float] = None,
    dist_to_bus_m: Optional[float] = None,
    dist_to_hospital_m: Optional[float] = None,
    dist_to_police_m: Optional[float] = None,
) -> Dict[str, float]:

    lighting_level = int(np.clip(lighting_level, 0, 2))
    crowd_level = int(np.clip(crowd_level, 0, 2))
    area_type = int(np.clip(area_type, 0, 2))
    past_incidents_level = int(np.clip(past_incidents_level, 0, 2))

    distance_to_main_road_m = float(np.clip(distance_to_main_road_m, 0, 5000))

    shops_open_at_night = 1 if shops_open_at_night else 0
    police_station_within_1km = 1 if police_station_within_1km else 0
    cctv_present = 1 if cctv_present else 0
    is_weekend = 1 if is_weekend else 0
    near_metro_or_bus = 1 if near_metro_or_bus else 0
    group_travel = 1 if group_travel else 0

    hour_of_day = int(np.clip(hour_of_day, 0, 23))
    hour_sin = float(np.sin(2 * np.pi * hour_of_day / 24.0))
    hour_cos = float(np.cos(2 * np.pi * hour_of_day / 24.0))

    clean = {
        "lighting_level": lighting_level,
        "crowd_level": crowd_level,
        "distance_to_main_road_m": distance_to_main_road_m,
        "shops_open_at_night": shops_open_at_night,
        "police_station_within_1km": police_station_within_1km,
        "cctv_present": cctv_present,
        "hour_sin": hour_sin,
        "hour_cos": hour_cos,
        "is_weekend": is_weekend,
        "area_type": area_type,
        "near_metro_or_bus": near_metro_or_bus,
        "past_incidents_level": past_incidents_level,
        "group_travel": group_travel,
    }

    # Optional features (if you trained with them, they must exist)
    if area_crime_risk is not None:
        clean["area_crime_risk"] = float(area_crime_risk)
    if audit_score_mean is not None:
        clean["audit_score_mean"] = float(audit_score_mean)
    if dist_to_metro_m is not None:
        clean["dist_to_metro_m"] = float(dist_to_metro_m)
    if dist_to_bus_m is not None:
        clean["dist_to_bus_m"] = float(dist_to_bus_m)
    if dist_to_hospital_m is not None:
        clean["dist_to_hospital_m"] = float(dist_to_hospital_m)
    if dist_to_police_m is not None:
        clean["dist_to_police_m"] = float(dist_to_police_m)

    return clean


def compute_confidence_level(max_probability: float) -> str:
    if max_probability >= 0.8:
        return "High"
    elif max_probability >= 0.6:
        return "Medium"
    elif max_probability >= 0.4:
        return "Low"
    else:
        return "Very Low"


def risk_tier_from_score(score: int) -> str:
    """Map 0-100 risk score to simple tiers."""
    if score >= 70:
        return "High"
    elif score >= 40:
        return "Medium"
    else:
        return "Low"


def get_shap_explanation(
    pipeline,
    feature_cols,
    feature_values: Dict[str, float],
    predicted_class: int,
) -> Dict[str, Any]:
    try:
        import pandas as pd

        x_df = pd.DataFrame([feature_values])[feature_cols]

        classifier = pipeline.named_steps.get("classifier", pipeline)
        explainer = shap.TreeExplainer(classifier)
        shap_values = explainer.shap_values(x_df.values)

        sv = shap_values[predicted_class][0]

        shap_series = pd.Series(np.abs(sv), index=feature_cols)
        top_factors = shap_series.sort_values(ascending=False).head(3)

        return {
            "status": "success",
            "top_factors": [
                {"feature": str(feat), "impact": float(impact)}
                for feat, impact in top_factors.items()
            ],
        }

    except Exception:
        return {"status": "failed", "top_factors": []}


def predict_safety(
    pipeline,
    feature_cols,
    lighting_level: int,
    crowd_level: int,
    distance_to_main_road_m: float,
    shops_open_at_night: int,
    police_station_within_1km: int,
    cctv_present: int,
    hour_of_day: int,
    is_weekend: int,
    latitude: float = 28.61,
    longitude: float = 77.23,
    dest_lat: float = 28.65,
    dest_lon: float = 77.20,
    area_type: int = 0,
    near_metro_or_bus: int = 0,
    past_incidents_level: int = 0,
    group_travel: int = 0,
    area_crime_risk: Optional[float] = None,
    audit_score_mean: Optional[float] = None,
    dist_to_metro_m: Optional[float] = None,
    dist_to_bus_m: Optional[float] = None,
    dist_to_hospital_m: Optional[float] = None,
    dist_to_police_m: Optional[float] = None,
    include_shap: bool = True,
) -> Dict[str, Any]:

    import pandas as pd

    # 1. Clean inputs
    clean_inputs = sanitize_inputs(
        lighting_level, crowd_level, distance_to_main_road_m,
        shops_open_at_night, police_station_within_1km,
        cctv_present, hour_of_day, is_weekend,
        area_type, near_metro_or_bus,
        past_incidents_level, group_travel,
        area_crime_risk, audit_score_mean,
        dist_to_metro_m, dist_to_bus_m,
        dist_to_hospital_m, dist_to_police_m,
    )

    # 🔹 Fill missing optional features with defaults (so all feature_cols exist)
    optional_features = [
        "area_crime_risk",
        "audit_score_mean",
        "dist_to_metro_m",
        "dist_to_bus_m",
        "dist_to_hospital_m",
        "dist_to_police_m",
    ]
    for f in optional_features:
        if f not in clean_inputs:
            clean_inputs[f] = 0.0

    # 2. REAL-TIME WEATHER
    weather = get_weather_data(lat=latitude, lon=longitude)

    # 3. REAL-TIME TRAFFIC
    traffic = get_traffic_data(
        start_lat=latitude,
        start_lon=longitude,
        end_lat=dest_lat,
        end_lon=dest_lon
    )

    # 4. Model input
    x_df = pd.DataFrame([clean_inputs])[feature_cols]

    probabilities = pipeline.predict_proba(x_df)[0]
    predicted_class = int(np.argmax(probabilities))

    confidence = float(np.max(probabilities))
    confidence_level = compute_confidence_level(confidence)

    # Manual override for extreme unsafe pattern
    if (
        clean_inputs["lighting_level"] == 0
        and clean_inputs["crowd_level"] == 0
        and clean_inputs["distance_to_main_road_m"] >= 200
        and clean_inputs["police_station_within_1km"] == 0
        and clean_inputs["cctv_present"] == 0
        and clean_inputs["group_travel"] == 0
    ):
        predicted_class = 0
        probabilities = np.array([0.9, 0.07, 0.03])

    confidence = float(np.max(probabilities))
    confidence_level = compute_confidence_level(confidence)

    # ---- 1) Model-only base risk on 0-100 scale ----
    unsafe_p = float(probabilities[0])
    moderate_p = float(probabilities[1])
    safe_p = float(probabilities[2])

    base_risk = unsafe_p * 100.0 + moderate_p * 50.0 + safe_p * 0.0
    risk_score = int(round(base_risk))

    # ---- 2) SHAP / model-based factors ----
    model_factors: list[str] = []
    if include_shap:
        shap_explain = get_shap_explanation(
            pipeline, feature_cols, clean_inputs, predicted_class
        )
    else:
        shap_explain = {"status": "skipped", "top_factors": []}

    if shap_explain["status"] == "success":
        model_factors.extend(
            [
                FEATURE_NAME_MAP.get(f["feature"], f["feature"])
                for f in shap_explain["top_factors"]
            ]
        )

    # ---- 3) Context-based risk adjustments (traffic, weather, time) ----
    context_delta = 0
    context_explanations: list[str] = []

    # TRAFFIC RISK LOGIC
    congestion = float(traffic.get("congestion", 0.0))
    if congestion < 0.05 and clean_inputs["crowd_level"] == 0:
        context_delta += 10
        context_explanations.append("low traffic (isolated road) ➜ +10 risk")
    elif congestion > 0.2:
        context_delta -= 5
        context_explanations.append("high traffic (busy road) ➜ −5 risk")

    # WEATHER RISK LOGIC
    if weather.get("rain", 0) == 1 and clean_inputs["lighting_level"] == 0:
        context_delta += 10
        context_explanations.append("rain + poor lighting ➜ +10 risk")

    if weather.get("fog", 0) == 1:
        context_delta += 8
        context_explanations.append("foggy conditions ➜ +8 risk")

    # TIME-OF-DAY RISK LOGIC
    hour = hour_of_day
    if (hour >= 22 or hour <= 4) and clean_inputs["crowd_level"] == 0:
        context_delta += 12
        context_explanations.append("late night + empty area ➜ +12 risk")

    # ---- 4) Final risk score and tier ----
    risk_score = max(0, min(100, risk_score + context_delta))

    if not model_factors:
        model_factors = ["no major model risk factors"]

    # 🔹 CLEAN FACTORS: remove duplicates, preserve order
    seen = set()
    deduped_model_factors: list[str] = []
    for f in model_factors:
        if f not in seen:
            seen.add(f)
            deduped_model_factors.append(f)

    positive_signals = 0
    if clean_inputs["lighting_level"] == 2:
        positive_signals += 1
    if clean_inputs["crowd_level"] == 2:
        positive_signals += 1
    if clean_inputs["shops_open_at_night"] == 1:
        positive_signals += 1
    if clean_inputs["cctv_present"] == 1:
        positive_signals += 1
    if clean_inputs["police_station_within_1km"] == 1:
        positive_signals += 1

    risk_tier = risk_tier_from_score(risk_score)
    if predicted_class == 0 and risk_score <= 80 and positive_signals >= 3:
        predicted_class = 1
        risk_tier = "Medium"

    return {
        "prediction": predicted_class,
        "label": LABELS[predicted_class],
        "description": LABEL_DESCRIPTIONS[predicted_class],
        "risk_score": risk_score,
        "risk_tier": risk_tier,
        "base_risk_score": int(round(base_risk)),
        "context_risk_delta": context_delta,
        "location": {
            "lat": latitude,
            "lon": longitude,
        },
        "model_factors": deduped_model_factors,
        "context_explanations": context_explanations,
        "factors": deduped_model_factors + context_explanations,
        "confidence": confidence,
        "confidence_level": confidence_level,
        "probabilities": {
            "unsafe": unsafe_p,
            "moderate": moderate_p,
            "safe": safe_p,
        },
        "weather": weather,
        "traffic": traffic,
        "shap_explanation": shap_explain,
    }

import joblib
import numpy as np

LABELS = {0: "Unsafe", 1: "Moderate", 2: "Safe"}


def load_model_and_features(
    model_path: str = "models/saferoute_model.pkl",
    feature_cols_path: str = "models/feature_cols.pkl",
):
    """Load the trained model and feature column order."""
    model = joblib.load(model_path)
    feature_cols = joblib.load(feature_cols_path)
    return model, feature_cols


def sanitize_inputs(
    lighting_level: int,
    crowd_level: int,
    distance_to_main_road_m: float,
    shops_open_at_night: int,
    police_station_within_1km: int,
    cctv_present: int,
    hour_of_day: int,
    is_weekend: int,
    area_type: int,
    near_metro_or_bus: int,
    past_incidents_level: int,
    group_travel: int,
):
    """
    Basic validation + clipping so the model never crashes on weird values.
    Returns a tuple of cleaned values.
    """
    # Core numeric features
    lighting_level = int(min(max(lighting_level, 0), 2))
    crowd_level = int(min(max(crowd_level, 0), 2))

    distance_to_main_road_m = float(distance_to_main_road_m)
    if distance_to_main_road_m < 0:
        distance_to_main_road_m = 0.0
    if distance_to_main_road_m > 5000:
        distance_to_main_road_m = 5000.0

    shops_open_at_night = 1 if shops_open_at_night else 0
    police_station_within_1km = 1 if police_station_within_1km else 0
    cctv_present = 1 if cctv_present else 0

    hour_of_day = int(hour_of_day)
    if hour_of_day < 0:
        hour_of_day = 0
    if hour_of_day > 23:
        hour_of_day = 23

    is_weekend = 1 if is_weekend else 0

    # New contextual features
    area_type = int(min(max(area_type, 0), 2))
    near_metro_or_bus = 1 if near_metro_or_bus else 0
    past_incidents_level = int(min(max(past_incidents_level, 0), 2))
    group_travel = 1 if group_travel else 0

    return (
        lighting_level,
        crowd_level,
        distance_to_main_road_m,
        shops_open_at_night,
        police_station_within_1km,
        cctv_present,
        hour_of_day,
        is_weekend,
        area_type,
        near_metro_or_bus,
        past_incidents_level,
        group_travel,
    )


def generate_reasons_grouped(
    lighting_level: int,
    crowd_level: int,
    distance_to_main_road_m: float,
    shops_open_at_night: int,
    police_station_within_1km: int,
    cctv_present: int,
    hour_of_day: int,
    is_weekend: int,
    area_type: int,
    near_metro_or_bus: int,
    past_incidents_level: int,
    group_travel: int,
    predicted_label: int,
):
    """
    Returns a dict of reason groups so the UI can show them in sections.
    """
    groups = {
        "Environment": [],
        "Infrastructure": [],
        "Context & history": [],
        "Time & context": [],
        "Overall": [],
    }

    # Environment: lighting + crowd + distance + area type
    if lighting_level == 0:
        groups["Environment"].append("Very poor street lighting.")
    elif lighting_level == 1:
        groups["Environment"].append("Lighting is average, not fully bright.")
    else:
        groups["Environment"].append("Good lighting on this route.")

    if crowd_level == 0:
        groups["Environment"].append("Area is mostly empty, low natural surveillance.")
    elif crowd_level == 1:
        groups["Environment"].append("Some people around, moderate natural surveillance.")
    else:
        groups["Environment"].append("Busy/active area, more people around.")

    if distance_to_main_road_m > 500:
        groups["Environment"].append("Far from a main road; harder to get quick help.")
    elif distance_to_main_road_m < 150:
        groups["Environment"].append("Close to a main road, easier to find help if needed.")

    if area_type == 0:
        groups["Environment"].append("Residential area; side streets may be quieter at night.")
    elif area_type == 1:
        groups["Environment"].append("Commercial/market area; can be active when shops are open.")
    else:
        groups["Environment"].append("Office/IT park area; may be busy at office hours but quiet late at night.")

    # Infrastructure: shops, police, CCTV, transport
    if shops_open_at_night:
        groups["Infrastructure"].append("Shops are open at night, more activity nearby.")
    else:
        groups["Infrastructure"].append("No shops open at night, fewer open places nearby.")

    if police_station_within_1km:
        groups["Infrastructure"].append("Police station is within 1 km.")
    else:
        groups["Infrastructure"].append("No police station within 1 km.")

    if cctv_present:
        groups["Infrastructure"].append("CCTV present, which can deter incidents.")
    else:
        groups["Infrastructure"].append("No CCTV visible in this area.")

    if near_metro_or_bus:
        groups["Infrastructure"].append("Near a major metro/bus stop; usually more people and security nearby.")
    else:
        groups["Infrastructure"].append("Not near a major public transport hub.")

    # Context & history: incidents + group travel
    if past_incidents_level == 2:
        groups["Context & history"].append(
            "Area has a higher reported incident level; treat scores with extra caution."
        )
    elif past_incidents_level == 1:
        groups["Context & history"].append("Area has a medium incident level historically.")
    else:
        groups["Context & history"].append("Area has a lower reported incident level.")

    if group_travel:
        groups["Context & history"].append("Walking with others generally reduces individual risk compared to walking alone.")
    else:
        groups["Context & history"].append("Walking alone; personal caution is more important.")

    # Time & context
    if hour_of_day >= 22 or hour_of_day <= 5:
        groups["Time & context"].append("Late-night timing, generally higher risk.")
    elif 18 <= hour_of_day < 22:
        groups["Time & context"].append("Evening hours; streets may still be active.")
    else:
        groups["Time & context"].append("Daytime hours; generally safer than late night.")

    if is_weekend:
        groups["Time & context"].append("Weekend; some areas may be more crowded or lively.")

    # Overall summary based on label
    if predicted_label == 0:
        groups["Overall"].append("Overall pattern looks risky; consider a more crowded, well-lit route.")
    elif predicted_label == 1:
        groups["Overall"].append("Mixed conditions; use caution and prefer company if possible.")
    else:
        groups["Overall"].append("Conditions look relatively safer, but always stay aware of surroundings.")

    return groups


def confidence_from_probas(proba_array):
    """
    Compute a simple confidence score + label from class probabilities.
    """
    max_p = float(np.max(proba_array))
    if max_p >= 0.8:
        level = "High"
    elif max_p >= 0.6:
        level = "Medium"
    else:
        level = "Low"
    return {"level": level, "score": max_p}


def predict_safety(
    model,
    feature_cols,
    lighting_level: int,
    crowd_level: int,
    distance_to_main_road_m: float,
    shops_open_at_night: int,
    police_station_within_1km: int,
    cctv_present: int,
    hour_of_day: int,
    is_weekend: int,
    area_type: int,
    near_metro_or_bus: int,
    past_incidents_level: int,
    group_travel: int,
):
    """
    Main helper: sanitize inputs, run model, return label, probs, confidence, reasons.
    """
    (
        lighting_level,
        crowd_level,
        distance_to_main_road_m,
        shops_open_at_night,
        police_station_within_1km,
        cctv_present,
        hour_of_day,
        is_weekend,
        area_type,
        near_metro_or_bus,
        past_incidents_level,
        group_travel,
    ) = sanitize_inputs(
        lighting_level,
        crowd_level,
        distance_to_main_road_m,
        shops_open_at_night,
        police_station_within_1km,
        cctv_present,
        hour_of_day,
        is_weekend,
        area_type,
        near_metro_or_bus,
        past_incidents_level,
        group_travel,
    )

    values = [
        lighting_level,
        crowd_level,
        distance_to_main_road_m,
        shops_open_at_night,
        police_station_within_1km,
        cctv_present,
        hour_of_day,
        is_weekend,
        area_type,
        near_metro_or_bus,
        past_incidents_level,
        group_travel,
    ]

    x = np.array([values])
    pred = model.predict(x)[0]
    proba = model.predict_proba(x)[0]

    reasons_grouped = generate_reasons_grouped(
        lighting_level,
        crowd_level,
        distance_to_main_road_m,
        shops_open_at_night,
        police_station_within_1km,
        cctv_present,
        hour_of_day,
        is_weekend,
        area_type,
        near_metro_or_bus,
        past_incidents_level,
        group_travel,
        predicted_label=int(pred),
    )

    confidence = confidence_from_probas(proba)

    result = {
        "label": int(pred),
        "label_text": LABELS.get(int(pred), "Unknown"),
        "probabilities": {
            "unsafe": float(proba[0]),
            "moderate": float(proba[1]) if len(proba) > 1 else None,
            "safe": float(proba[2]) if len(proba) > 2 else None,
        },
        "confidence": confidence,
        "reasons_grouped": reasons_grouped,
    }
    return result

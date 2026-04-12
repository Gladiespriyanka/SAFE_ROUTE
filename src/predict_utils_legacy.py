"""
Legacy prediction utilities for SafeRoute Delhi.

Maintained for backward compatibility. New code should use predict_utils_enhanced.py
"""

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
    area_crime_risk = None,
    audit_score_mean = None,
    dist_to_metro_m = None,
    dist_to_bus_m = None,
    dist_to_hospital_m = None,
    dist_to_police_m = None,
):
    """Basic validation + clipping so model doesn't crash."""
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
    area_type = int(min(max(area_type, 0), 2))
    near_metro_or_bus = 1 if near_metro_or_bus else 0
    past_incidents_level = int(min(max(past_incidents_level, 0), 2))
    group_travel = 1 if group_travel else 0

    def clip_or_zero(value, lo, hi):
        if value is None:
            return 0.0
        try:
            v = float(value)
        except Exception:
            return 0.0
        if v < lo:
            return lo
        if v > hi:
            return hi
        return v

    area_crime_risk = clip_or_zero(area_crime_risk, 0.0, 3.0)
    audit_score_mean = clip_or_zero(audit_score_mean, 0.0, 2.0)
    dist_to_metro_m = clip_or_zero(dist_to_metro_m, 0.0, 10000.0)
    dist_to_bus_m = clip_or_zero(dist_to_bus_m, 0.0, 10000.0)
    dist_to_hospital_m = clip_or_zero(dist_to_hospital_m, 0.0, 10000.0)
    dist_to_police_m = clip_or_zero(dist_to_police_m, 0.0, 10000.0)

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
        area_crime_risk,
        audit_score_mean,
        dist_to_metro_m,
        dist_to_bus_m,
        dist_to_hospital_m,
        dist_to_police_m,
    )

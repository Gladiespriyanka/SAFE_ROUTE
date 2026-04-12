import sys
import os
import json

# Add src/ to path if running from project root
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from predict_utils_enhanced import (
    load_model_and_feature_cols,
    predict_safety,
    format_prediction_output,
)

def predict_from_input():
    """Interactive CLI for route safety prediction."""
    print("\n" + "="*70)
    print("SAFEROUTE DELHI - INTERACTIVE ROUTE SAFETY PREDICTOR")
    print("="*70)
    print("\nEnter route details to get a safety prediction.\n")

    # Core features
    lighting = int(input("Lighting level (0=very poor, 1=ok, 2=good): "))
    crowd = int(input("Crowd level (0=empty, 1=some people, 2=busy): "))
    distance = float(input("Distance to main road in meters (e.g. 250): "))
    shops = int(input("Shops open at night? (0=no, 1=yes): "))
    police = int(input("Police station within 1 km? (0=no, 1=yes): "))
    cctv = int(input("CCTV present? (0=no, 1=yes): "))
    hour = int(input("Hour of day (0–23, 0 = midnight): "))
    weekend = int(input("Is it weekend? (0=no, 1=yes): "))
    
    # Additional features
    area_type = int(input("Area type (0=residential, 1=commercial, 2=office): "))
    near_transit = int(input("Near metro/bus stop? (0=no, 1=yes): "))
    incidents = int(input("Past incidents level (0=low, 1=medium, 2=high): "))
    group = int(input("Traveling in a group? (0=no, 1=yes): "))

    # Load model
    print("\nLoading model...")
    pipeline, feature_cols = load_model_and_feature_cols()

    # Make prediction
    result = predict_safety(
        pipeline=pipeline,
        feature_cols=feature_cols,
        lighting_level=lighting,
        crowd_level=crowd,
        distance_to_main_road_m=distance,
        shops_open_at_night=shops,
        police_station_within_1km=police,
        cctv_present=cctv,
        hour_of_day=hour,
        is_weekend=weekend,
        area_type=area_type,
        near_metro_or_bus=near_transit,
        past_incidents_level=incidents,
        group_travel=group,
        include_shap=True,
    )

    # Display result
    print(format_prediction_output(result))
    
    # Also show JSON format
    print("\n📋 JSON FORMAT (for API integration):")
    json_result = {
        "prediction": result["prediction"],
        "label": result["label"],
        "confidence": result["confidence"],
        "confidence_level": result["confidence_level"],
        "probabilities": result["probabilities"],
    }
    if "shap_explanation" in result:
        json_result["top_factors"] = [
            f["feature"] for f in result["shap_explanation"].get("top_factors", [])
        ]
    print(json.dumps(json_result, indent=2))


if __name__ == "__main__":
    predict_from_input()


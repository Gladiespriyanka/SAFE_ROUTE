import sys
import os

# Add src/ to path if running from project root
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from predict_utils import load_model_and_features, predict_safety, LABELS
def predict_from_input():
    print("Enter route details to get a safety prediction:\n")

    lighting = int(input("Lighting level (0=very poor, 1=ok, 2=good): "))
    crowd = int(input("Crowd level (0=empty, 1=some people, 2=busy): "))
    distance = float(input("Distance to main road in meters (e.g. 250): "))
    shops = int(input("Shops open at night? (0=no, 1=yes): "))
    police = int(input("Police station within 1 km? (0=no, 1=yes): "))
    cctv = int(input("CCTV present? (0=no, 1=yes): "))
    hour = int(input("Hour of day (0–23, 0 = midnight): "))
    weekend = int(input("Is it weekend? (0=no, 1=yes): "))

    model, feature_cols = load_model_and_features()

    result = predict_safety(
        model=model,
        feature_cols=feature_cols,
        lighting_level=lighting,
        crowd_level=crowd,
        distance_to_main_road_m=distance,
        shops_open_at_night=shops,
        police_station_within_1km=police,
        cctv_present=cctv,
        hour_of_day=hour,
        is_weekend=weekend,
    )

    print("\n=== SafeRoute Delhi Prediction ===")
    print(f"Predicted safety label: {result['label_text']} ({result['label']})")
    probs = result["probabilities"]
    print(
        f"Probabilities -> Unsafe: {probs['unsafe']:.2f}, "
        f"Moderate: {probs['moderate']:.2f}, Safe: {probs['safe']:.2f}"
    )
    print("\nWhy this prediction?")
    for r in result["reasons"]:
        print(f"- {r}")


if __name__ == "__main__":
    predict_from_input()

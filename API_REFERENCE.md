# Enhanced Prediction API - Quick Reference

## Loading the Model

```python
from src.predict_utils_enhanced import load_model_and_feature_cols

pipeline, feature_cols = load_model_and_feature_cols()
# or with custom paths:
# pipeline, feature_cols = load_model_and_feature_cols(
#     model_path="models/saferoute_model_v1_20240115_143022.pkl",
#     feature_cols_path="models/feature_cols.pkl"
# )
```

## Making a Prediction

### Basic Prediction
```python
from src.predict_utils_enhanced import predict_safety

result = predict_safety(
    pipeline=pipeline,
    feature_cols=feature_cols,
    lighting_level=2,          # 0-2
    crowd_level=1,             # 0-2
    distance_to_main_road_m=250.0,
    shops_open_at_night=1,     # 0 or 1
    police_station_within_1km=1,
    cctv_present=0,
    hour_of_day=20,            # 0-23
    is_weekend=0,              # 0 or 1
    area_type=1,               # 0=residential, 1=commercial, 2=office
    near_metro_or_bus=1,
    past_incidents_level=1,    # 0-2
    group_travel=1,
    include_shap=True,         # Include SHAP factors
)
```

## Understanding the Result

```python
{
    # Main prediction
    "prediction": 2,                    # 0=Unsafe, 1=Moderate, 2=Safe
    "label": "Safe",                    # Human-readable
    "description": "✅ Safe - ...",     # Full description
    
    # Confidence
    "confidence": 0.87,         # 0.0-1.0 (as probability)
    "confidence_level": "High", # High/Medium/Low/Very Low
    
    # Full probabilities
    "probabilities": {
        "unsafe": 0.05,
        "moderate": 0.08,
        "safe": 0.87,
    },
    
    # SHAP explanation (if include_shap=True)
    "shap_explanation": {
        "status": "success",
        "top_factors": [
            {"feature": "lighting_level", "impact": 0.42, "rank": 1},
            {"feature": "crowd_level", "impact": 0.38, "rank": 2},
            {"feature": "cctv_present", "impact": 0.21, "rank": 3}
        ]
    }
}
```

## Pretty Print the Result

```python
from src.predict_utils_enhanced import format_prediction_output

print(format_prediction_output(result))
```

**Output:**
```
======================================================================
SAFEROUTE DELHI - ROUTE SAFETY PREDICTION
======================================================================

🎯 PREDICTION: SAFE
   ✅ Safe - Relatively safer route. Still maintain awareness.

📊 CONFIDENCE: High
   Confidence Score: 87.00%

📈 PROBABILITY BREAKDOWN:
   Unsafe       ░░░░░░░░░░░░░░░░░░░░    5.00%
   Moderate     ░░░░░░░░░░░░░░░░░░░░    8.00%
   Safe         ████████████████████   87.00%

🔍 TOP CONTRIBUTING FACTORS:
   1. lighting_level         Impact: 0.4200
   2. crowd_level            Impact: 0.3800
   3. cctv_present           Impact: 0.2100

======================================================================
```

## Convert to JSON

```python
import json

# Prepare for API response
json_response = {
    "prediction": result["prediction"],
    "label": result["label"],
    "confidence": result["confidence"],
    "confidence_level": result["confidence_level"],
    "probabilities": result["probabilities"],
    "top_factors": [f["feature"] for f in result["shap_explanation"]["top_factors"]]
}

print(json.dumps(json_response, indent=2))
```

**Output:**
```json
{
  "prediction": 2,
  "label": "Safe",
  "confidence": 0.87,
  "confidence_level": "High",
  "probabilities": {
    "unsafe": 0.05,
    "moderate": 0.08,
    "safe": 0.87
  },
  "top_factors": [
    "lighting_level",
    "crowd_level",
    "cctv_present"
  ]
}
```

## Error Handling

```python
try:
    result = predict_safety(
        pipeline=pipeline,
        feature_cols=feature_cols,
        # ... parameters
    )
    print("Prediction successful")
except FileNotFoundError as e:
    print(f"Model not found: {e}")
except Exception as e:
    print(f"Prediction failed: {e}")
```

## Required Features

All required:
- `lighting_level` (int, 0-2)
- `crowd_level` (int, 0-2)
- `distance_to_main_road_m` (float, 0-5000)
- `shops_open_at_night` (int, 0-1)
- `police_station_within_1km` (int, 0-1)
- `cctv_present` (int, 0-1)
- `hour_of_day` (int, 0-23)
- `is_weekend` (int, 0-1)

## Optional Features

Defaults to 0 if not provided:
- `area_type` (int, 0-2, default=0)
- `near_metro_or_bus` (int, 0-1, default=0)
- `past_incidents_level` (int, 0-2, default=0)
- `group_travel` (int, 0-1, default=0)
- `area_crime_risk` (float, default=0.0)
- `audit_score_mean` (float, default=0.0)
- `dist_to_metro_m` (float, default=0.0)
- `dist_to_bus_m` (float, default=0.0)
- `dist_to_hospital_m` (float, default=0.0)
- `dist_to_police_m` (float, default=0.0)

## Extracting Information

```python
# Just the prediction
label = result["label"]  # "Safe", "Moderate", or "Unsafe"
numeric_pred = result["prediction"]  # 0, 1, or 2

# Confidence scores
confidence_score = result["confidence"]  # 0.87
confidence_level = result["confidence_level"]  # "High"

# Probabilities for each class
unsafe_prob = result["probabilities"]["unsafe"]  # 0.05
moderate_prob = result["probabilities"]["moderate"]  # 0.08
safe_prob = result["probabilities"]["safe"]  # 0.87

# Top contributing factors
shap_status = result["shap_explanation"]["status"]  # "success" or "failed"
if shap_status == "success":
    for factor in result["shap_explanation"]["top_factors"]:
        print(f"{factor['feature']}: {factor['impact']:.4f}")
```

## Label Meanings

| Code | Label | Meaning |
|------|-------|---------|
| 0 | Unsafe | High risk area. Avoid if possible. If necessary, travel in groups. |
| 1 | Moderate | Mixed conditions. Use caution, especially at night. |
| 2 | Safe | Relatively safer route. Still maintain awareness. |

## Confidence Levels

| Confidence Range | Level |
|------------------|-------|
| ≥ 80% | High |
| 60-79% | Medium |
| 40-59% | Low |
| < 40% | Very Low |

## Common Patterns

### Check if prediction is confident
```python
if result["confidence"] >= 0.8:
    print("High confidence prediction")
else:
    print("Low confidence - use with caution")
```

### Get only top factor
```python
top_factor = result["shap_explanation"]["top_factors"][0] if result["shap_explanation"]["top_factors"] else None
if top_factor:
    print(f"Most important: {top_factor['feature']}")
```

### Convert to risk score (0-100)
```python
# Map Safe(2) -> high score, Unsafe(0) -> low score
risk_reduction_score = (2 - result["prediction"]) / 2 * 100
print(f"Safety Score: {risk_reduction_score:.0f}/100")
```

---

**For more details, see:** `IMPROVEMENTS.md` or `src/predict_utils_enhanced.py`

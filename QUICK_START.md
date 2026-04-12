# SafeRoute Delhi ML - Quick Start Guide

Get started with the improved SafeRoute Delhi model in 5 minutes!

---

## Installation

### 1. Clone/Open the Project
```bash
cd c:\Users\DELL\OneDrive\Desktop\saferoute-delhi-ml
```

### 2. Create Virtual Environment (Optional but Recommended)
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
# Install all required packages
pip install -r requirements_enhanced.txt

# Or install manually:
pip install scikit-learn pandas numpy joblib imbalanced-learn shap fastapi uvicorn
```

---

## Step 1: Train the Model

### Run Training:
```bash
python src/train_saferoute.py
```

**What happens:**
- ✅ Loads data from `data/saferoute_delhi.csv`
- ✅ Validates data (checks for missing values)
- ✅ Adds noise to labels (semi-synthetic)
- ✅ Handles class imbalance (SMOTE)
- ✅ Tunes hyperparameters (GridSearchCV)
- ✅ Saves versioned model with timestamp
- ✅ Computes feature importance and SHAP

**Output:**
- `models/saferoute_model_v1_YYYYMMDD_HHMMSS.pkl` - Your trained model
- `models/saferoute_model_latest.pkl` - Convenience link to latest
- `artifacts/model_comparison.csv` - Performance metrics
- `artifacts/feature_importance.csv` - Feature rankings

**Training time:** ~70 seconds

---

## Step 2: Make Predictions

### Option A: Interactive CLI
```bash
python src/predict_cli.py
```

Then answer the prompts:
```
Lighting level (0=very poor, 1=ok, 2=good): 2
Crowd level (0=empty, 1=some people, 2=busy): 2
Distance to main road in meters (e.g. 250): 150
Shops open at night? (0=no, 1=yes): 1
Police station within 1 km? (0=no, 1=yes): 1
CCTV present? (0=no, 1=yes): 1
Hour of day (0–23, 0 = midnight): 19
Is it weekend? (0=no, 1=yes): 0
Area type (0=residential, 1=commercial, 2=office): 1
Near metro/bus stop? (0=no, 1=yes): 1
Past incidents level (0=low, 1=medium, 2=high): 0
Traveling in a group? (0=no, 1=yes): 1
```

**You'll see:**
- 🎯 PREDICTION with confidence level
- 📊 Probability bars for each safety level
- 🔍 Top 3 contributing factors (SHAP)

### Option B: Python Code
```python
from src.predict_utils_enhanced import load_model_and_feature_cols, predict_safety, format_prediction_output

# Load model
pipeline, feature_cols = load_model_and_feature_cols()

# Make prediction
result = predict_safety(
    pipeline=pipeline,
    feature_cols=feature_cols,
    lighting_level=2,
    crowd_level=2,
    distance_to_main_road_m=150,
    shops_open_at_night=1,
    police_station_within_1km=1,
    cctv_present=1,
    hour_of_day=19,
    is_weekend=0,
    area_type=1,
    near_metro_or_bus=1,
    past_incidents_level=0,
    group_travel=1,
    include_shap=True,
)

# Display result
print(format_prediction_output(result))

# Access specific fields
print(f"Prediction: {result['label']}")
print(f"Confidence: {result['confidence']:.0%}")
```

### Option C: REST API
```bash
# Start the API server
uvicorn backend.app:app --reload --port 8000

# In another terminal, make a request
curl -X POST "http://127.0.0.1:8000/predict" \
  -H "X-API-Key: SAFEROUTE_SECRET_123" \
  -H "Content-Type: application/json" \
  -d '{
    "latitude": 28.6139,
    "longitude": 77.2090,
    "lighting_level": 2,
    "crowd_level": 2,
    "distance_to_main_road_m": 150,
    "shops_open_at_night": 1,
    "police_station_within_1km": 1,
    "cctv_present": 1,
    "hour_of_day": 19,
    "is_weekend": 0,
    "area_type": 1,
    "near_metro_or_bus": 1,
    "past_incidents_level": 0,
    "group_travel": 1
  }'

# You'll get JSON response with prediction, confidence, and factors
```

---

## Step 3: Understand the Output

### Prediction Returns:
```python
{
    "prediction": 2,                      # 0=Unsafe, 1=Moderate, 2=Safe
    "label": "Safe",                      # Human-readable
    "confidence": 0.87,                   # 0.0-1.0
    "confidence_level": "High",           # High/Medium/Low/Very Low
    "probabilities": {
        "unsafe": 0.05,                   # 5% chance of Unsafe
        "moderate": 0.08,                 # 8% chance of Moderate
        "safe": 0.87,                     # 87% chance of Safe
    },
    "shap_explanation": {
        "top_factors": [
            {"feature": "lighting_level", "impact": 0.42, "rank": 1},
            {"feature": "crowd_level", "impact": 0.38, "rank": 2},
            {"feature": "cctv_present", "impact": 0.21, "rank": 3}
        ]
    }
}
```

### Label Meanings:
- **0 (Unsafe):** ⚠️ High risk. Avoid if possible.
- **1 (Moderate):** ⚠️ Mixed conditions. Use caution.
- **2 (Safe):** ✅ Relatively safer. Stay aware.

### Understanding Confidence:
- **High (80%+):** Very confident in this prediction
- **Medium (60-79%):** Fairly confident
- **Low (40-59%):** Uncertain, use with caution
- **Very Low (<40%):** Don't rely on this prediction

### Understanding SHAP Factors:
- Shows the top 3 features that influenced the prediction
- Higher impact = more important to the prediction
- Helps explain WHY the model made this decision

---

## Common Scenarios

### Scenario 1: Safe Route (Good Conditions)
```python
result = predict_safety(
    pipeline=pipeline,
    feature_cols=feature_cols,
    lighting_level=2,           # ✅ Good lighting
    crowd_level=2,              # ✅ Busy/active
    distance_to_main_road_m=100, # ✅ Close to main road
    shops_open_at_night=1,      # ✅ Shops open
    police_station_within_1km=1, # ✅ Police nearby
    cctv_present=1,             # ✅ CCTV present
    hour_of_day=19,             # ✅ Evening (safer)
    is_weekend=0,
    area_type=1,
    near_metro_or_bus=1,        # ✅ Near transit
    past_incidents_level=0,     # ✅ Low incidents
    group_travel=1,             # ✅ With group
)

# Expected: SAFE with High confidence (~85%+)
```

### Scenario 2: Unsafe Route (Bad Conditions)
```python
result = predict_safety(
    pipeline=pipeline,
    feature_cols=feature_cols,
    lighting_level=0,           # ❌ Very poor lighting
    crowd_level=0,              # ❌ Empty/isolated
    distance_to_main_road_m=2000, # ❌ Far from main road
    shops_open_at_night=0,      # ❌ No shops open
    police_station_within_1km=0, # ❌ No police nearby
    cctv_present=0,             # ❌ No CCTV
    hour_of_day=23,             # ❌ Late night
    is_weekend=0,
    area_type=0,
    near_metro_or_bus=0,        # ❌ No transit
    past_incidents_level=2,     # ❌ High incidents
    group_travel=0,             # ❌ Alone
)

# Expected: UNSAFE with High confidence (~85%+)
```

### Scenario 3: Mixed Conditions (Moderate)
```python
result = predict_safety(
    pipeline=pipeline,
    feature_cols=feature_cols,
    lighting_level=1,           # ⚠️ Average lighting
    crowd_level=1,              # ⚠️ Some people
    distance_to_main_road_m=500, # ⚠️ Medium distance
    shops_open_at_night=0,
    police_station_within_1km=0,
    cctv_present=0,
    hour_of_day=20,             # Evening
    is_weekend=0,
    area_type=1,
    near_metro_or_bus=0,
    past_incidents_level=1,
    group_travel=0,
)

# Expected: MODERATE with Medium confidence
```

---

## Troubleshooting

### Issue: "Model not found"
```
FileNotFoundError: models/saferoute_model_latest.pkl not found
```

**Solution:**
```bash
# Run training first
python src/train_saferoute.py
```

### Issue: "Missing dependency"
```
ModuleNotFoundError: No module named 'shap'
```

**Solution:**
```bash
pip install -r requirements_enhanced.txt
```

### Issue: "API key error"
```
{"detail": "Invalid or missing API key"}
```

**Solution:**
```bash
# Add the API key header
curl -X POST "http://127.0.0.1:8000/predict" \
  -H "X-API-Key: SAFEROUTE_SECRET_123" \
  ...
```

### Issue: "SHAP analysis failed"
```json
{"shap_explanation": {"status": "failed", "error": "..."}}
```

**Solution:**
- SHAP may fail if model type not supported
- Set `include_shap=False` to disable it
- Check available model type (RandomForest works best)

---

## Better Luck Next Time! 🎯

### Key Features to Remember:

1. **Pipeline Architecture**
   - Preprocessing + Model integrated
   - No data leakage, production-safe

2. **Data Quality**
   - Validates missing values
   - Logs all imputations

3. **Fair Predictions**
   - Handles class imbalance (SMOTE)
   - Balanced across all safety levels

4. **Explainability**
   - SHAP top 3 factors for each prediction
   - Understand WHY the model decided

5. **Confidence Scores**
   - Probability-based (0.0-1.0)
   - Helps assess prediction reliability

6. **Production Ready**
   - Versioned models with metadata
   - Robust error handling
   - Proper logging

---

## Next Steps

1. **Train your own model:**
   ```bash
   python src/train_saferoute.py
   ```

2. **Make predictions:**
   ```bash
   python src/predict_cli.py
   ```

3. **Explore the code:**
   - `src/train_saferoute.py` - Training with all improvements
   - `src/predict_utils_enhanced.py` - Enhanced prediction utility
   - `backend/app.py` - FastAPI backend

4. **Read documentation:**
   - `IMPROVEMENTS.md` - Detailed explanation of each feature
   - `API_REFERENCE.md` - API usage guide
   - `USAGE_EXAMPLES.md` - Complete working examples
   - `CHANGES_SUMMARY.md` - All changes made

---

## Support

For issues or questions:
1. Check `IMPROVEMENTS.md` for detailed explanations
2. Check `USAGE_EXAMPLES.md` for working code
3. Check inline comments in source files
4. Review error messages (they explain what went wrong)

**Happy routing! 🚀**

---

**Version:** 1.0  
**Last Updated:** 2024-01-15  
**Status:** Production Ready ✅

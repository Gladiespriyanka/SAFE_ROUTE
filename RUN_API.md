## 🚀 Quick Start - Run the API

### Step 1: Verify Environment
```bash
cd saferoute-delhi-ml
python --version  # Should be 3.7+
```

### Step 2: Install Dependencies
```bash
pip install -r requirements.txt
# Or for enhanced features:
pip install -r requirements_enhanced.txt
```

### Step 3: Run the API
```bash
uvicorn backend.app:app --reload
```

You should see:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete
```

### Step 4: Test in Browser
Visit: **http://localhost:8000/docs**

You'll see the Swagger UI with all endpoints!

---

## 🧪 Test the Health Endpoint

```bash
# Using curl
curl http://localhost:8000/health \
  -H "X-API-Key: SAFEROUTE_SECRET_123"

# Expected response:
{
  "status": "ok",
  "model_loaded": true,
  "num_features": 12,
  "version": "1.3.0",
  "num_audits": 0,
  "num_feedback": 0,
  "poi_loaded": true,
  "area_risk_loaded": true,
  "timestamp": "2024-04-12T10:30:45.123456"
}
```

---

## 🎯 Test a Prediction

### Using Swagger UI (Browser)
1. Go to http://localhost:8000/docs
2. Click on `/predict` endpoint
3. Click "Try it out"
4. Fill in sample data (or use example below)
5. Click "Execute"

### Using curl
```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -H "X-API-Key: SAFEROUTE_SECRET_123" \
  -d '{
    "latitude": 28.61,
    "longitude": 77.21,
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
```

### Expected Response
```json
{
  "prediction": 2,
  "label": "Safe",
  "description": "Analysis shows favorable safety indicators...",
  "confidence": 0.87,
  "confidence_level": "High",
  "probabilities": {
    "unsafe": 0.05,
    "moderate": 0.08,
    "safe": 0.87
  },
  "shap_explanation": {
    "top_factors": [
      {
        "factor": "crowd_level",
        "impact": 0.32
      },
      {
        "factor": "cctv_present",
        "impact": 0.28
      },
      {
        "factor": "hour_of_day",
        "impact": 0.15
      }
    ]
  }
}
```

---

## 📊 Test All Endpoints

### Health Check
```bash
curl http://localhost:8000/health \
  -H "X-API-Key: SAFEROUTE_SECRET_123"
```

### Prediction
```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -H "X-API-Key: SAFEROUTE_SECRET_123" \
  -d '{ ... }'
```

### Submit Feedback
```bash
curl -X POST http://localhost:8000/feedback \
  -H "Content-Type: application/json" \
  -H "X-API-Key: SAFEROUTE_SECRET_123" \
  -d '{
    "lighting_level": 2,
    "crowd_level": 2,
    "distance_to_main_road_m": 150,
    "shops_open_at_night": 1,
    "police_station_within_1km": 1,
    "cctv_present": 1,
    "hour_of_day": 19,
    "is_weekend": 0,
    "predicted_label": 2,
    "predicted_label_text": "Safe",
    "user_agrees": 1,
    "comment": "Good prediction!"
  }'
```

### Get Feedback Summary
```bash
curl http://localhost:8000/feedback/summary
```

### Create Audit
```bash
curl -X POST http://localhost:8000/audit \
  -H "Content-Type: application/json" \
  -H "X-API-Key: SAFEROUTE_SECRET_123" \
  -d '{
    "latitude": 28.61,
    "longitude": 77.21,
    "lighting_level": 2,
    "crowd_level": 2,
    "perceived_safety": 2,
    "comment": "Area feels very safe",
    "hour_of_day": 19,
    "is_weekend": 0,
    "area_type": 1
  }'
```

### List Audits
```bash
curl http://localhost:8000/audit
```

### Get Nearby Audits
```bash
curl "http://localhost:8000/audit/nearby?lat=28.61&lon=77.21&radius_m=500" \
  -H "X-API-Key: SAFEROUTE_SECRET_123"
```

### Get POI Context
```bash
curl "http://localhost:8000/poi_context?lat=28.61&lon=77.21" \
  -H "X-API-Key: SAFEROUTE_SECRET_123"
```

### Get Area Risk
```bash
curl "http://localhost:8000/area_risk?area_key=central_delhi" \
  -H "X-API-Key: SAFEROUTE_SECRET_123"
```

---

## 🐍 Test in Python

### Basic Test
```python
import requests

API_URL = "http://0.0.0.0:8000"
API_KEY = "SAFEROUTE_SECRET_123"

headers = {"X-API-Key": API_KEY}

# Test health
response = requests.get(f"{API_URL}/health", headers=headers)
print("Health:", response.json())

# Test prediction
data = {
    "latitude": 28.61,
    "longitude": 77.21,
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
}

response = requests.post(
    f"{API_URL}/predict",
    json=data,
    headers=headers
)
result = response.json()
print(f"Prediction: {result['label']} ({result['confidence']:.0%})")
```

### Batch Test
```python
import requests
from backend.model_service import get_model_service

# Use ModelService directly (no HTTP overhead)
service = get_model_service()

test_cases = [
    {"latitude": 28.61, "longitude": 77.21, ... },
    {"latitude": 28.62, "longitude": 77.22, ... },
    # ... more cases
]

for case in test_cases:
    result = service.predict(case)
    print(f"{case} → {result['label']}")
```

---

## 🐛 Troubleshooting

### Port Already in Use
```bash
# Use a different port
uvicorn backend.app:app --reload --port 8001
```

### Module Not Found
```bash
# Make sure you're in the right directory
cd saferoute-delhi-ml

# And requirements are installed
pip install -r requirements.txt
```

### Model Not Loading
```bash
# Check models directory exists
ls -la ml/models/

# Should see:
# saferoute_model_latest.pkl
# feature_cols.pkl
```

### API Key Error
```bash
# Make sure to include header in requests:
-H "X-API-Key: SAFEROUTE_SECRET_123"
```

### Server Not Responding
```bash
# Check if it's actually running:
curl http://localhost:8000/

# Should return: {"message": "SafeRoute Delhi API is running"}
```

---

## 📱 Use with Streamlit

Your Streamlit app should already work! No changes needed.

Just make sure:
1. ✅ API is running: `uvicorn backend.app:app --reload`
2. ✅ Streamlit is in same directory
3. ✅ Streamlit calls `http://localhost:8000/predict`
4. ✅ Streamlit sends `X-API-Key` header

```python
# In your Streamlit app
import requests

headers = {"X-API-Key": "SAFEROUTE_SECRET_123"}
response = requests.post(
    "http://localhost:8000/predict",
    json=user_input,
    headers=headers
)
result = response.json()
```

---

## 📈 Performance Tips

### Run in Production Mode
```bash
# Much faster than --reload
gunicorn -w 4 -b 0.0.0.0:8000 backend.app:app
```

### Pre-warm the Model
```python
# Before serving, load the model once
from backend.model_service import get_model_service
service = get_model_service()
assert service.is_ready()
```

### Use Async Routes for I/O
```python
# In routes.py, for slow operations
@router.get("/slow_endpoint")
async def slow_endpoint():
    # Won't block other requests
    return await some_async_operation()
```

---

## 🎯 Next Steps

1. ✅ Run the API: `uvicorn backend.app:app --reload`
2. ✅ Test endpoints: http://localhost:8000/docs
3. ✅ Verify predictions work
4. ✅ Integrate with Streamlit
5. ✅ Deploy to production

---

## 📚 Documentation

- **QUICK_REFERENCE.md** - Quick commands & tips
- **BACKEND_USAGE_GUIDE.md** - Complete usage guide
- **FINAL_SUMMARY.md** - Architecture summary
- **CODE_MIGRATION.md** - What moved where

---

**You're ready to go! 🚀**

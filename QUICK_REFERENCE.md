## 🎯 Quick Reference - Backend Architecture

### 🏗️ Structure at a Glance
```
backend/
├── app.py                    [27 lines]     FastAPI setup only
├── schemas.py                [80+ lines]    Request/response validation
├── model_service.py          [250+ lines]   ML logic & enrichment
├── routes.py                 [200+ lines]   API endpoints
└── services/                              Existing services (unchanged)
```

---

### ⚡ Quick Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run API
uvicorn backend.app:app --reload

# View API docs
# Browser: http://localhost:8000/docs

# Test health
curl http://localhost:8000/health -H "X-API-Key: SAFEROUTE_SECRET_123"
```

---

### 📍 Where to Add Things

| Want to... | Go to... | Example |
|------------|----------|---------|
| Add new endpoint | `routes.py` | `@router.post("/my_endpoint")` |
| Change API response | `schemas.py` | Add field to `PredictionResponse` |
| Add ML logic | `model_service.py` | `def new_method(self): ...` |
| Fix API setup | `app.py` | Add middleware, CORS config |
| Change auth | `routes.py` | Modify `verify_api_key()` |

---

### 🔌 Key Functions

#### Make a Prediction
```python
from backend.model_service import get_model_service

service = get_model_service()
result = service.predict({
    "latitude": 28.61,
    "longitude": 77.21,
    "lighting_level": 2,
    "crowd_level": 2,
    "distance_to_main_road_m": 150,
    # ... 8 more fields
})
```

#### Create New Endpoint
```python
from fastapi import APIRouter, Depends
from backend.schemas import MyRequestModel
from backend.model_service import get_model_service
from backend.routes import verify_api_key

router = APIRouter()  # Already exists

@router.post("/my_endpoint")
def my_endpoint(
    data: MyRequestModel,
    ok: bool = Depends(verify_api_key)
):
    service = get_model_service()
    result = service.predict(data.dict())
    return result
```

#### Use in CLI/Notebook
```python
from backend.model_service import get_model_service

service = get_model_service()

for user_data in batch_predictions:
    result = service.predict(user_data)
    print(f"Prediction: {result['label']} ({result['confidence']:.2%})")
```

---

### 🔐 API Key Authentication

**All protected endpoints need:**
```
Header: X-API-Key: SAFEROUTE_SECRET_123
```

**To change key:** Edit `routes.py`:
```python
API_KEY = "YOUR_NEW_SECRET_KEY"
```

---

### 📊 Response Format

```json
{
  "prediction": 2,
  "label": "Safe",
  "description": "...",
  "confidence": 0.87,
  "confidence_level": "High",
  "probabilities": {
    "unsafe": 0.05,
    "moderate": 0.08,
    "safe": 0.87
  },
  "shap_explanation": {
    "top_factors": [
      {"factor": "feature_name", "impact": 0.32}
    ]
  }
}
```

---

### 🛠️ Common Tasks

#### Add Database Support
1. Create `backend/db.py`
2. Import in `routes.py`
3. Replace in-memory: `AUDITS_STORE` → `db.get_audits()`

#### Add Logging
1. Import logging in `model_service.py`
2. Add: `logger.info(f"Prediction: {result}")` 
3. Configure in `app.py` if needed

#### Add Caching
1. Import `functools.lru_cache` in `model_service.py`
2. Decorate expensive methods: `@lru_cache(maxsize=128)`

#### Deploy to Production
```bash
# Use gunicorn for production
gunicorn -w 4 -b 0.0.0.0:8000 backend.app:app
```

---

### 📚 File Descriptions

#### `app.py` (27 lines) ✨
**Role:** Entry point for FastAPI  
**Contains:** App initialization, middleware, router  
**Modify:** When changing CORS, adding middleware, changing title/version  
**Don't:** Put routes or ML logic here!

#### `schemas.py` (80+ lines) 📝
**Role:** Data validation  
**Contains:** All Pydantic models  
**Modify:** When changing API request/response format  
**Auto-generates:** OpenAPI/Swagger docs

#### `model_service.py` (250+ lines) 🧠
**Role:** Core ML logic  
**Contains:** Model loading, prediction, feature enrichment  
**Modify:** When changing ML logic or adding features  
**Reusable:** In CLI, notebooks, batch jobs

#### `routes.py` (200+ lines) 🛣️
**Role:** HTTP endpoints  
**Contains:** Route handlers, auth, data stores  
**Modify:** When adding/changing endpoints  
**Import from:** `model_service.py`, `schemas.py`

---

### 🧪 Testing

```python
# Test ModelService directly
from backend.model_service import ModelService

service = ModelService()
assert service.is_ready()

result = service.predict({"latitude": 28.61, ...})
assert result["prediction"] in [0, 1, 2]
assert "confidence" in result

# Test routes with FastAPI TestClient
from fastapi.testclient import TestClient
from backend.app import app

client = TestClient(app)
response = client.get("/health", headers={"X-API-Key": "TEST_KEY"})
assert response.status_code == 200
```

---

### 💡 Design Principles

1. **app.py** = Setup only
2. **schemas.py** = Validation
3. **model_service.py** = Logic (pure, testable)
4. **routes.py** = HTTP handlers (thin)
5. **services/** = Existing utilities

---

### 🚀 Performance Tips

- Model is loaded **once** (singleton pattern)
- POI and area risk tables are **cached** in memory
- Predictions are **fast** (no model reload)
- Use `async` routes for I/O-heavy operations

---

### 🔍 Debugging

```python
# Check service status
service = get_model_service()
print(service.get_status())
# Output: {'model_loaded': True, 'num_features': 12, ...}

# Check loaded features
print(service.feature_cols)

# Test prediction directly
result = service.predict(test_data)
print(result)
```

---

### 📖 API Endpoints Summary

```
GET  /                        Root info
GET  /health                  Service status
POST /predict                 Make prediction
POST /feedback                Submit feedback
GET  /feedback/summary        Feedback stats
POST /audit                   Create audit
GET  /audit                   List audits
GET  /audit/nearby            Nearby audits
GET  /poi_context             POI distances
GET  /area_risk               Area crime risk
```

---

**Current Versions:**
- FastAPI: Latest
- Pydantic: v2+
- scikit-learn: 1.2+
- Python: 3.7+

**Made with ❤️ for cleaner, better code!**

## 📋 Code Migration Map

This document shows exactly what code moved where during the refactoring.

---

## ✂️ `backend/app.py` - What Was Removed

### Removed Code (OLD)
| What | Lines | Moved To |
|------|-------|----------|
| Model loading | 5 | `model_service.py` |
| POI/Area table loading | 10 | `model_service.py` |
| Pydantic models (RouteFeatures, etc) | 80+ | `schemas.py` |
| Helper functions (haversine, area mapping) | 40 | `model_service.py` |
| All route handlers | 150+ | `routes.py` |
| API key verification | 10 | `routes.py` |
| In-memory stores (FEEDBACK, AUDITS) | 5 | `routes.py` |

### What Remains (NEW)
```python
# Just FastAPI setup!
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.routes import router

app = FastAPI(title="SafeRoute Delhi API")
app.add_middleware(CORSMiddleware, allow_origins=["*"])
app.include_router(router)
```

---

## 📦 New File: `backend/schemas.py` (80+ lines)

### Pydantic Models (from `app.py`)
```python
class PredictionInput(BaseModel):           # NEW name
    # Was: RouteFeatures
    latitude: float
    longitude: float
    lighting_level: int
    # ... 10 more fields
    
class RouteFeatures(BaseModel):             # Backward compat alias
    # Same as PredictionInput
    
class FeedbackPayload(BaseModel):           # Moved from app.py
class SafetyAudit(BaseModel):              # Moved from app.py
class HealthResponse(BaseModel):           # NEW
class PredictionResponse(BaseModel):       # NEW
```

**Benefits:**
- Centralized data contracts
- Auto-generates API docs
- Input validation built-in
- Easy to evolve schema

---

## 🤖 New File: `backend/model_service.py` (250+ lines)

### Classes
```python
class ModelService:
    def __init__(self):
        # From app.py load section:
        self.pipeline = load_model_and_feature_cols()
        self.poi_context = POIContext()
        self.area_risk_table = AreaRiskTable()
    
    def predict(self, data: dict) -> dict:
        # Core ML prediction logic
        # (was in /predict route handler)
```

### Methods (Moved from `app.py`)
| Method | From | Purpose |
|--------|------|---------|
| `is_ready()` | NEW | Check if model loaded |
| `get_status()` | NEW | Return status dict |
| `_haversine_m()` | `app.py` helper | Distance calculation |
| `_get_area_key_from_coords()` | `app.py` helper | Area mapping |
| `compute_audit_score_mean()` | `app.py` helper | Audit averaging |
| `predict()` | `/predict` route | Main ML logic |

### Global Instance
```python
def get_model_service() -> ModelService:
    """Singleton - reuses loaded model"""
    global _model_service
    if _model_service is None:
        _model_service = ModelService()
    return _model_service
```

**Why separate?**
- Reusable in CLI, notebooks, batch jobs
- Testable in isolation
- Clear data flow
- Single responsibility

---

## 🛣️ New File: `backend/routes.py` (200+ lines)

### Routes (Moved from `app.py`)

#### Health Routes
```python
@router.get("/")              # Was: @app.get("/")
@router.get("/health")         # Was: @app.get("/health")
```

#### Prediction Route
```python
@router.post("/predict")       # Was: @app.post("/predict")
# Now uses: service = get_model_service()
```

#### Feedback Routes
```python
@router.post("/feedback")      # Was: @app.post("/feedback")
@router.get("/feedback/summary") # Was: @app.get("/feedback/summary")
```

#### Audit Routes
```python
@router.post("/audit")         # Was: @app.post("/audit")
@router.get("/audit")          # Was: @app.get("/audit")
@router.get("/audit/nearby")   # Was: @app.get("/audit/nearby")
```

#### POI/Area Routes
```python
@router.get("/poi_context")    # Was: @app.get("/poi_context")
@router.get("/area_risk")      # Was: @app.get("/area_risk")
```

### In-Memory Stores (Moved from `app.py`)
```python
FEEDBACK_STORE = []    # Was in app.py
AUDITS_STORE = []      # Was in app.py
_next_audit_id = 1     # Was in app.py
```

### Authentication (Moved from `app.py`)
```python
API_KEY = "SAFEROUTE_SECRET_123"
API_KEY_HEADER_NAME = "X-API-Key"

def verify_api_key(x_api_key: str = Header(...)) -> bool:
    """Moved from app.py"""
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401)
    return True
```

---

## 📊 Code Movement Summary

```
OLD: backend/app.py (500+ lines)
├─ FastAPI setup (kept, simplified)
├─ Model loading → model_service.py
├─ Pydantic models → schemas.py  
├─ Helper functions → model_service.py
├─ Route handlers → routes.py
├─ API key logic → routes.py
├─ In-memory stores → routes.py
└─ Data tables → model_service.py

NEW Structure:
├─ app.py (27 lines)
├─ schemas.py (80 lines)
├─ model_service.py (250 lines)
├─ routes.py (200 lines)
└─ services/ (unchanged)
```

---

## 🔗 Dependency Flow

**Before (Circular/Tangled):**
```
app.py
├─ Creates model
├─ Creates routes
├─ Has schemas
└─ Has helpers
```

**After (Clean Dependencies):**
```
app.py
└─ imports → routes.py
    ├─ imports → model_service.py
    │   ├─ imports → predict_utils_enhanced
    │   ├─ imports → POIContext
    │   └─ imports → AreaRiskTable
    └─ imports → schemas.py
```

---

## ✅ Line-by-Line Mapping

### GET `/health`
```python
# OLD (app.py):
@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "model_loaded": pipeline is not None,
        # ...
    }

# NEW (routes.py):
@router.get("/health")
def health_check():
    service = get_model_service()
    status_info = service.get_status()
    return {
        "status": "ok",
        "model_loaded": status_info["model_loaded"],
        # ...
    }
```

### POST `/predict`
```python
# OLD (app.py):
@app.post("/predict")
def predict_route_safety(payload: RouteFeatures, ok: bool = Depends(verify_api_key)):
    try:
        data = payload.dict()
        # ... lots of enrichment logic ...
        result = predict_safety(pipeline=pipeline, ...)
        return result
    except Exception as e:
        return {"error": str(e)}

# NEW (routes.py + model_service.py):
@router.post("/predict", response_model=PredictionResponse)
def predict_route_safety(payload: RouteFeatures, ok: bool = Depends(verify_api_key)):
    service = get_model_service()
    if not service.is_ready():
        raise HTTPException(status_code=503)
    result = service.predict(payload.dict(), audits=AUDITS_STORE)
    return result

# Enrichment logic moved to ModelService.predict()
```

---

## 🧩 What Stayed the Same

**Services (Unchanged):**
- `backend/services/poi_context.py` ✅ (same)
- `backend/services/area_risk.py` ✅ (same)

**Data/Storage (Unchanged):**
- `backend/data/` ✅ (same)
- All CSV files ✅ (same)

**API Contract (Unchanged):**
- Request format ✅ (same)
- Response format ✅ (same)  
- Endpoint URLs ✅ (same)
- Error handling ✅ (similar)

**From src/ (Unchanged):**
- `src/predict_utils_enhanced.py` ✅ (same)
- ML model files ✅ (same)

---

## 🎯 Why This Structure?

### Clean Separation
- **app.py**: Just FastAPI wiring
- **schemas.py**: Data contracts
- **model_service.py**: ML logic
- **routes.py**: HTTP handlers

### Testability
```python
# Easy to test model service in isolation
from backend.model_service import ModelService

service = ModelService()
result = service.predict(data)
assert result["prediction"] in [0, 1, 2]
```

### Reusability
```python
# Model service usable in CLI
from backend.model_service import get_model_service

service = get_model_service()
for item in batch:
    result = service.predict(item)
```

### Maintainability
```
Adding feature?
├─ API contract → Update schemas.py
├─ ML logic → Update model_service.py
├─ Endpoint → Update routes.py
└─ Setup → Update app.py (rare)
```

---

## 📈 Metrics

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| **app.py lines** | 500+ | 27 | -92% ⬇️ |
| **Modules** | 1 | 4 | +300% ⬆️ |
| **Single responsibility** | ❌ | ✅ | Better |
| **Testable code** | Hard | Easy | Better |
| **Reusable logic** | Limited | Full | Better |
| **Documentation clarity** | Poor | Clear | Better |

---

## 🚀 Next Steps

1. **Understand the structure** → Read this file + code files
2. **Run the API** → `uvicorn backend.app:app --reload`
3. **Test endpoints** → Use Swagger UI at `/docs`
4. **Add features** → Follow patterns in `routes.py`
5. **Deploy** → Same FastAPI app, just point to `backend.app:app`

---

**Summary:** Your code went from messy to clean! 🧹✨

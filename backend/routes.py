"""
API routes for SafeRoute backend.
Organized by functionality: health, predictions, feedback, audits, POI/area data.
"""

import traceback
from datetime import datetime
from typing import List, Dict, Any

from fastapi import APIRouter, HTTPException, Depends, Header, status

from backend.config import settings
from backend.schemas import (
    PredictionInput,
    RouteFeatures,
    FeedbackPayload,
    SafetyAudit,
    PredictionResponse,
)
from backend.model_service import get_model_service

# In-memory data stores (can be replaced with DB later)
FEEDBACK_STORE: List[Dict[str, Any]] = []
AUDITS_STORE: List[Dict[str, Any]] = []
_next_audit_id = 1

# API Key auth
API_KEY_HEADER_NAME = "X-API-Key"


def verify_api_key(x_api_key: str | None = Header(None, alias=API_KEY_HEADER_NAME)) -> bool:
    """Verify API key from request headers."""
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key",
        )

    if x_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
    return True


# --- Router setup ---
router = APIRouter()

# ============================================================================
# Health & Status
# ============================================================================

@router.get("/")
def root():
    """Root endpoint."""
    return {
        "message": "SafeRoute Delhi API is running",
        "docs": "/docs",
        "health": "/health",
    }


@router.get("/health")
def health_check():
    """Health check endpoint with status information."""
    try:
        service = get_model_service()
        status_info = service.get_status()

        return {
            "status": "ok",
            "model_loaded": status_info["model_loaded"],
            "num_features": status_info["num_features"],
            "version": "1.3.0",
            "num_audits": len(AUDITS_STORE),
            "num_feedback": len(FEEDBACK_STORE),
            "poi_loaded": status_info["poi_loaded"],
            "area_risk_loaded": status_info["area_risk_loaded"],
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        print("❌ Model service failed:", e)
        raise HTTPException(status_code=500, detail="Model service not available")

# ============================================================================
# Predictions
# ============================================================================

@router.post("/predict", response_model=PredictionResponse)
def predict_route_safety(
    payload: RouteFeatures,
    ok: bool = Depends(verify_api_key),
):
    """
    Run the SafeRoute model and return comprehensive prediction.

    Returns:
      - prediction (0=Unsafe, 1=Moderate, 2=Safe)
      - label (human-readable)
      - confidence (0.0-1.0)
      - confidence_level (Very Low, Low, Medium, High)
      - probabilities (all three classes)
      - shap_explanation (top 3 contributing factors)
    """
    try:
        service = get_model_service()
        if not service.is_ready():
            raise HTTPException(status_code=503, detail="Model not initialized")

        data = payload.dict()
        # Accept location from user or use defaults
        data["latitude"] = data.get("latitude", 28.61)
        data["longitude"] = data.get("longitude", 77.23)
        data["dest_lat"] = data.get("dest_lat", 28.65)
        data["dest_lon"] = data.get("dest_lon", 77.20)

        result = service.predict(data, audits=AUDITS_STORE)
        return result

    except Exception as e:
        print(f"[ERROR] Prediction failed: {e}")
        traceback.print_exc()
        raise HTTPException(
            status_code=500, detail=f"Prediction failed: {str(e)}"
        )

# ============================================================================
# Feedback
# ============================================================================

@router.post("/feedback")
def submit_feedback(
    payload: FeedbackPayload,
    ok: bool = Depends(verify_api_key),
):
    """Submit prediction feedback (thumbs up/down)."""
    fb = payload.dict()
    fb["received_at"] = datetime.utcnow().isoformat()
    FEEDBACK_STORE.append(fb)
    return {
        "status": "received",
        "stored_items": len(FEEDBACK_STORE),
        "feedback_id": len(FEEDBACK_STORE) - 1,
    }


@router.get("/feedback/summary")
def feedback_summary():
    """Get aggregate feedback statistics."""
    total = len(FEEDBACK_STORE)
    if total == 0:
        return {
            "total": 0,
            "agree_count": 0,
            "disagree_count": 0,
            "agree_ratio": None,
        }

    agree_count = sum(1 for f in FEEDBACK_STORE if f.get("user_agrees") == 1)
    disagree_count = total - agree_count
    agree_ratio = agree_count / total if total > 0 else None

    return {
        "total": total,
        "agree_count": agree_count,
        "disagree_count": disagree_count,
        "agree_ratio": agree_ratio,
    }

# ============================================================================
# Audits (Community Safety Data)
# ============================================================================

@router.post("/audit")
def create_audit(
    audit: SafetyAudit,
    ok: bool = Depends(verify_api_key),
):
    """Create a new safety audit record."""
    global _next_audit_id
    record = audit.dict()
    record["id"] = _next_audit_id
    record["created_at"] = datetime.utcnow().isoformat()
    _next_audit_id += 1
    AUDITS_STORE.append(record)
    return record


@router.get("/audit")
def list_audits(limit: int = 100):
    """List recent audits (most recent first)."""
    return list(reversed(AUDITS_STORE))[:limit]


@router.get("/audit/nearby")
def audits_nearby(
    lat: float,
    lon: float,
    radius_m: float = 300.0,
    limit: int = 50,
    ok: bool = Depends(verify_api_key),
):
    """Get audits near a location (within radius_m)."""
    if not AUDITS_STORE:
        return []

    service = get_model_service()
    results: List[Dict[str, Any]] = []

    for audit in AUDITS_STORE:
        distance = service._haversine_m(
            lat, lon, audit["latitude"], audit["longitude"]
        )
        if distance <= radius_m:
            item = dict(audit)
            item["distance_m"] = distance
            results.append(item)

    results.sort(key=lambda x: x["distance_m"])
    return results[:limit]

# ============================================================================
# POI & Area Data
# ============================================================================

@router.get("/poi_context")
def get_poi_context(
    lat: float,
    lon: float,
    ok: bool = Depends(verify_api_key),
):
    """
    Get distances to nearest POI (metro, bus, hospital, police)
    for a given point.
    """
    service = get_model_service()
    if service.poi_context is None:
        raise HTTPException(status_code=503, detail="POI context not loaded")
    try:
        return service.poi_context.nearest_distances(lat=lat, lon=lon)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"POI lookup failed: {str(e)}")


@router.get("/area_risk")
def get_area_risk(
    area_key: str,
    ok: bool = Depends(verify_api_key),
):
    """
    Get crime risk level (0/1/2) for a given area.
    area_key: 'central_delhi', 'north_delhi', 'south_delhi', 'east_delhi', 'west_delhi'
    """
    service = get_model_service()
    if service.area_risk_table is None:
        raise HTTPException(status_code=503, detail="Area risk table not loaded")
    try:
        risk = service.area_risk_table.get_risk(area_key)
        return {
            "area_key": area_key,
            "area_crime_risk": risk,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Area risk lookup failed: {str(e)}")
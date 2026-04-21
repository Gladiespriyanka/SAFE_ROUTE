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
from backend.services.routing import get_candidate_routes

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


@router.post("/routes/safe_options")
def safe_routes(
    start_lat: float,
    start_lon: float,
    end_lat: float,
    end_lon: float,
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
    ok: bool = Depends(verify_api_key),
):
    """Return candidate routes colored by sampled safety risk."""
    try:
        service = get_model_service()
        if not service.is_ready():
            raise HTTPException(status_code=503, detail="Model not initialized")

        routes = get_candidate_routes(start_lat, start_lon, end_lat, end_lon, k=5)

        results = []
        for route in routes:
            coords = route["coordinates"]
            step = max(1, len(coords) // 10)
            sampled = coords[::step] if len(coords) > 1 else coords

            per_point_scores = []
            per_point_labels = []

            for lat, lon in sampled:
                data = {
                    "latitude": lat,
                    "longitude": lon,
                    "lighting_level": lighting_level,
                    "crowd_level": crowd_level,
                    "distance_to_main_road_m": distance_to_main_road_m,
                    "shops_open_at_night": shops_open_at_night,
                    "police_station_within_1km": police_station_within_1km,
                    "cctv_present": cctv_present,
                    "hour_of_day": hour_of_day,
                    "is_weekend": is_weekend,
                    "area_type": area_type,
                    "near_metro_or_bus": near_metro_or_bus,
                    "past_incidents_level": past_incidents_level,
                    "group_travel": group_travel,
                }
                pred = service.predict(data, audits=AUDITS_STORE)
                per_point_scores.append(pred["risk_score"])
                per_point_labels.append(pred["prediction"])

            if not per_point_scores:
                continue

            avg_risk = sum(per_point_scores) / len(per_point_scores)
            max_risk = max(per_point_scores)
            unsafe_fraction = (
                sum(1 for label in per_point_labels if label == 0)
                / len(per_point_labels)
            )

            if max_risk >= 80 or unsafe_fraction >= 0.3:
                safety_label = "Mostly unsafe"
                color = "red"
            elif avg_risk >= 40:
                safety_label = "Mixed / moderate"
                color = "orange"
            else:
                safety_label = "Relatively safer"
                color = "green"

            results.append(
                {
                    "coordinates": coords,
                    "avg_risk": avg_risk,
                    "max_risk": max_risk,
                    "unsafe_fraction": unsafe_fraction,
                    "safety_label": safety_label,
                    "color": color,
                    "approx_length": route.get("approx_length"),
                }
            )

        results.sort(key=lambda r: r["avg_risk"])
        return {"routes": results}

    except HTTPException:
        raise
    except ImportError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Route dependencies are not installed: {str(e)}",
        )
    except Exception as e:
        print(f"[ERROR] Route safety failed: {e}")
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Route safety failed: {str(e)}",
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

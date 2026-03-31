import os
import sys
import traceback
from typing import Literal, List, Dict, Any, Optional

from fastapi import FastAPI, HTTPException, Depends, Header, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.services.poi_context import POIContext
from backend.services.area_risk import AreaRiskTable

# --- Make src/ importable so we can reuse predict_utils ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(BASE_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.append(SRC_DIR)

from predict_utils import load_model_and_features, predict_safety  # noqa: E402


app = FastAPI(
    title="SafeRoute Delhi API",
    description="FastAPI backend serving the SafeRoute Delhi women-centric safety model.",
    version="1.3.0",
)

# Allow local Streamlit / future frontend to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # in production you can restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------- Simple API key auth --------
API_KEY = "SAFEROUTE_SECRET_123"  # simple demo key
API_KEY_HEADER_NAME = "X-API-Key"


def verify_api_key(x_api_key: str = Header(..., alias=API_KEY_HEADER_NAME)):
    """
    Simple API key check using header 'X-API-Key'.
    """
    if x_api_key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
    return True


# -------- Load ML model --------
model, feature_cols = load_model_and_features()

# -------- Optional data tables (realistic data helpers) --------
POI_CONTEXT: POIContext | None = None
AREA_RISK_TABLE: AreaRiskTable | None = None

try:
    POI_CONTEXT = POIContext()
except Exception as e:
    print(f"[WARN] Could not load POI context: {e}")

try:
    AREA_RISK_TABLE = AreaRiskTable()
except Exception as e:
    print(f"[WARN] Could not load area risk table: {e}")


# --- Simple lat/lon -> area_key mapping for Delhi ---
def _get_area_key_from_coords(lat: float, lon: float) -> str:
    """
    Map a (lat, lon) in the Delhi region to a coarse area_key.

    This is a simple heuristic grid, not official boundaries.
    It should match keys present in backend/data/area_risk_delhi.csv:
        central_delhi, north_delhi, south_delhi, east_delhi, west_delhi
    """
    # Rough central reference (Rajiv Chowk / New Delhi area)
    center_lat = 28.61
    center_lon = 77.21

    # Thresholds to distinguish central from others (degrees)
    lat_band = 0.04  # ~4–5 km
    lon_band = 0.05  # ~5–6 km

    # Inside central box
    if (center_lat - lat_band) <= lat <= (center_lat + lat_band) and \
       (center_lon - lon_band) <= lon <= (center_lon + lon_band):
        return "central_delhi"

    # Outside central: decide by relative position
    if lat > center_lat:
        # North of center
        return "north_delhi"
    elif lat < center_lat:
        # South of center
        return "south_delhi"
    else:
        # Same latitude as center: split east/west by longitude
        if lon >= center_lon:
            return "east_delhi"
        else:
            return "west_delhi"


# -------- In-memory stores --------
FEEDBACK_STORE: List[Dict[str, Any]] = []
AUDITS_STORE: List[Dict[str, Any]] = []
_next_audit_id = 1


# -------- Pydantic models --------
class RouteFeatures(BaseModel):
    """
    Core tabular features + basic geo coords.
    """
    # Geo
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)

    # Existing tabular inputs
    lighting_level: int = Field(..., ge=0, le=2, description="0=very poor, 1=ok, 2=good")
    crowd_level: int = Field(..., ge=0, le=2, description="0=empty, 1=some people, 2=busy")
    distance_to_main_road_m: float = Field(..., ge=0, le=5000, description="Distance to main road in meters")
    shops_open_at_night: Literal[0, 1]
    police_station_within_1km: Literal[0, 1]
    cctv_present: Literal[0, 1]
    hour_of_day: int = Field(..., ge=0, le=23)
    is_weekend: Literal[0, 1]

    area_type: int = Field(..., ge=0, le=2, description="0=residential, 1=commercial, 2=office/IT park")
    near_metro_or_bus: Literal[0, 1]
    past_incidents_level: int = Field(..., ge=0, le=2)
    group_travel: Literal[0, 1]


class FeedbackPayload(BaseModel):
    """
    Simple thumbs-up / thumbs-down feedback from UI.
    """
    lighting_level: int
    crowd_level: int
    distance_to_main_road_m: float
    shops_open_at_night: Literal[0, 1]
    police_station_within_1km: Literal[0, 1]
    cctv_present: Literal[0, 1]
    hour_of_day: int
    is_weekend: Literal[0, 1]

    predicted_label: int
    predicted_label_text: str
    user_agrees: Literal[0, 1]
    comment: Optional[str] = Field(default=None, max_length=280)


class SafetyAudit(BaseModel):
    """
    Basic Safetipin-style audit for a point on the map.
    """
    latitude: float
    longitude: float
    # 0=very poor, 1=ok, 2=good
    lighting_level: int = Field(..., ge=0, le=2)
    # 0=empty, 1=some people, 2=busy
    crowd_level: int = Field(..., ge=0, le=2)
    # 0=very unsafe, 1=okay, 2=feels safe
    perceived_safety: int = Field(..., ge=0, le=2)
    comment: Optional[str] = Field(default=None, max_length=500)
    hour_of_day: int = Field(..., ge=0, le=23)
    is_weekend: Literal[0, 1]
    area_type: Optional[int] = Field(default=None, ge=0, le=2)


# -------- Small helpers --------
def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    from math import radians, sin, cos, sqrt, atan2
    R = 6371000.0  # meters
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c


def compute_audit_score_mean(lat: float, lon: float, radius_m: float = 300.0) -> float:
    """
    Simple average of perceived_safety for audits within radius_m of (lat, lon).
    Returns 0.0 if no audits.
    """
    if not AUDITS_STORE:
        return 0.0

    scores: List[float] = []
    for a in AUDITS_STORE:
        d = _haversine_m(lat, lon, a["latitude"], a["longitude"])
        if d <= radius_m:
            # 0/1/2 scale
            scores.append(float(a.get("perceived_safety", 0)))

    if not scores:
        return 0.0
    return float(sum(scores) / len(scores))


# -------- Routes --------
@app.get("/")
def root():
    return {"message": "SafeRoute Delhi API is running"}


@app.get("/health")
def health_check():
    """
    Lightweight health/metadata endpoint.
    """
    return {
        "status": "ok",
        "model_loaded": model is not None,
        "num_features": len(feature_cols),
        "version": app.version,
        "num_audits": len(AUDITS_STORE),
        "num_feedback": len(FEEDBACK_STORE),
        "poi_loaded": POI_CONTEXT is not None,
        "area_risk_loaded": AREA_RISK_TABLE is not None,
    }


@app.post("/predict")
def predict_route_safety(
    payload: RouteFeatures,
    ok: bool = Depends(verify_api_key),
):
    """
    Run the SafeRoute Delhi model and return label, probabilities, confidence, and reasons.

    Steps:
      - Take UI fields + lat/lon.
      - Compute realistic-data features:
          * audit_score_mean from nearby audits
          * POI distances from precomputed cache
          * area_crime_risk from area_risk_delhi.csv via area_key mapping
      - Call predict_safety with all features.
    """
    try:
        data = payload.dict()

        lat = data["latitude"]
        lon = data["longitude"]

        # 1) From audits: perceived safety around this point
        audit_score_mean = compute_audit_score_mean(lat, lon)

        # 2) From POI cache: distances to metro/bus/hospital/police
        dist_to_metro_m = None
        dist_to_bus_m = None
        dist_to_hospital_m = None
        dist_to_police_m = None
        if POI_CONTEXT is not None:
            poi_dists = POI_CONTEXT.nearest_distances(lat=lat, lon=lon)
            dist_to_metro_m = poi_dists.get("dist_to_metro_m")
            dist_to_bus_m = poi_dists.get("dist_to_bus_m")
            dist_to_hospital_m = poi_dists.get("dist_to_hospital_m")
            dist_to_police_m = poi_dists.get("dist_to_police_m")

        # 3) Map coords -> area_key -> area_crime_risk from AREA_RISK_TABLE
        area_crime_risk = 0.0
        if AREA_RISK_TABLE is not None:
            try:
                area_key = _get_area_key_from_coords(lat, lon)
                area_crime_risk = float(AREA_RISK_TABLE.get_risk(area_key))
            except Exception:
                area_crime_risk = 0.0

        result = predict_safety(
            model=model,
            feature_cols=feature_cols,
            lighting_level=data["lighting_level"],
            crowd_level=data["crowd_level"],
            distance_to_main_road_m=data["distance_to_main_road_m"],
            shops_open_at_night=data["shops_open_at_night"],
            police_station_within_1km=data["police_station_within_1km"],
            cctv_present=data["cctv_present"],
            hour_of_day=data["hour_of_day"],
            is_weekend=data["is_weekend"],
            area_type=data["area_type"],
            near_metro_or_bus=data["near_metro_or_bus"],
            past_incidents_level=data["past_incidents_level"],
            group_travel=data["group_travel"],
            area_crime_risk=area_crime_risk,
            audit_score_mean=audit_score_mean,
            dist_to_metro_m=dist_to_metro_m,
            dist_to_bus_m=dist_to_bus_m,
            dist_to_hospital_m=dist_to_hospital_m,
            dist_to_police_m=dist_to_police_m,
        )
        return result
    except Exception as e:
        traceback.print_exc()
        return {"error": str(e)}


@app.post("/feedback")
def submit_feedback(
    payload: FeedbackPayload,
    ok: bool = Depends(verify_api_key),
):
    """
    Store simple feedback about predictions (in-memory demo).
    """
    fb = payload.dict()
    fb["received_at"] = __import__("datetime").datetime.utcnow().isoformat()
    FEEDBACK_STORE.append(fb)
    return {"status": "received", "stored_items": len(FEEDBACK_STORE)}


@app.get("/feedback/summary")
def feedback_summary():
    """
    Returns aggregate feedback counts so the UI / analytics can show trust levels.
    """
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


@app.post("/audit")
def create_audit(
    audit: SafetyAudit,
    ok: bool = Depends(verify_api_key),
):
    """
    Store a new safety audit from a user.
    For now this is in-memory; later you can persist to CSV/SQLite/Postgres.
    """
    global _next_audit_id
    record = audit.dict()
    record["id"] = _next_audit_id
    record["created_at"] = __import__("datetime").datetime.utcnow().isoformat()
    _next_audit_id += 1
    AUDITS_STORE.append(record)
    return record


@app.get("/audit")
def list_audits(limit: int = 100):
    """
    List recent safety audits (most recent first).
    """
    return list(reversed(AUDITS_STORE))[:limit]


@app.get("/audit/nearby")
def audits_nearby(
    lat: float,
    lon: float,
    radius_m: float = 300.0,
    limit: int = 50,
    ok: bool = Depends(verify_api_key),
):
    """
    Return audits near a given point using a simple Haversine distance filter.
    """
    if not AUDITS_STORE:
        return []

    results: List[Dict[str, Any]] = []
    for a in AUDITS_STORE:
        d = _haversine_m(lat, lon, a["latitude"], a["longitude"])
        if d <= radius_m:
            item = dict(a)
            item["distance_m"] = d
            results.append(item)

    results.sort(key=lambda x: x["distance_m"])
    return results[:limit]


@app.get("/poi_context")
def get_poi_context(
    lat: float,
    lon: float,
    ok: bool = Depends(verify_api_key),
):
    """
    Given a point, return distances to nearest metro, bus, hospital, police
    using the precomputed Delhi POI cache.
    """
    if POI_CONTEXT is None:
        raise HTTPException(status_code=503, detail="POI context not loaded")
    return POI_CONTEXT.nearest_distances(lat=lat, lon=lon)


@app.get("/area_risk")
def get_area_risk(
    area_key: str,
    ok: bool = Depends(verify_api_key),
):
    """
    Return crime risk bucket (0/1/2) for a given area_key,
    using the precomputed area_risk_delhi.csv table.
    """
    if AREA_RISK_TABLE is None:
        raise HTTPException(status_code=503, detail="Area risk table not loaded")
    risk = AREA_RISK_TABLE.get_risk(area_key)
    return {
        "area_key": area_key,
        "area_crime_risk": risk,
    }
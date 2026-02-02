import os
import sys
from typing import Literal, List, Dict, Any

from fastapi import FastAPI
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
import traceback

# --- Make src/ importable so we can reuse predict_utils ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # project root
SRC_DIR = os.path.join(BASE_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.append(SRC_DIR)

from predict_utils import load_model_and_features, predict_safety  # noqa: E402

app = FastAPI(
    title="SafeRoute Delhi API",
    description="FastAPI backend serving the SafeRoute Delhi women-centric safety model.",
    version="1.1.0",
)

# Allow local Streamlit / future frontend to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # in production you can restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load model once at startup
model, feature_cols = load_model_and_features()

# Simple in-memory feedback store (for demo; in real life use DB)
FEEDBACK_STORE: List[Dict[str, Any]] = []

class RouteFeatures(BaseModel):
    lighting_level: int = Field(..., ge=0, le=2, description="0=very poor, 1=ok, 2=good")
    crowd_level: int = Field(..., ge=0, le=2, description="0=empty, 1=some people, 2=busy")
    distance_to_main_road_m: float = Field(..., ge=0, le=5000, description="Distance to main road in meters")
    shops_open_at_night: Literal[0, 1] = Field(..., description="0=no, 1=yes")
    police_station_within_1km: Literal[0, 1] = Field(..., description="0=no, 1=yes")
    cctv_present: Literal[0, 1] = Field(..., description="0=no, 1=yes")
    hour_of_day: int = Field(..., ge=0, le=23, description="Hour of day (0–23)")
    is_weekend: Literal[0, 1] = Field(..., description="0=weekday, 1=weekend")

    area_type: int = Field(..., ge=0, le=2, description="0=residential, 1=commercial, 2=office/IT park")
    near_metro_or_bus: Literal[0, 1] = Field(..., description="0=no, 1=yes")
    past_incidents_level: int = Field(..., ge=0, le=2, description="0=low, 1=medium, 2=high")
    group_travel: Literal[0, 1] = Field(..., description="0=alone, 1=with others")


class FeedbackPayload(BaseModel):
    """
    Feedback from the UI about a past prediction.
    In a real app you'd store prediction_id etc.; here we just log general signals.
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
    user_agrees: Literal[0, 1] = Field(..., description="1 if user felt the prediction was reasonable, 0 otherwise")
    comment: str | None = Field(default=None, max_length=280)


@app.get("/")
def root():
    return {"message": "SafeRoute Delhi API is running"}


@app.get("/health")
def health_check():
    """
    Lightweight health/metadata endpoint.
    Lets monitoring or the frontend quickly check if the API and model are alive.
    """
    return {
        "status": "ok",
        "model_loaded": model is not None,
        "num_features": len(feature_cols),
        "version": app.version,
    }


@app.post("/predict")
def predict_route_safety(payload: RouteFeatures):
    """
    Run the SafeRoute Delhi model and return label, probabilities, confidence, and reasons.
    """
    try:
        data = payload.dict()

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
        )

        return result
    except Exception as e:
        traceback.print_exc()
        return {"error": str(e)}


@app.post("/feedback")
def submit_feedback(payload: FeedbackPayload):
    """
    Accept simple thumbs-up / thumbs-down style feedback on predictions.
    Stored in memory for demo; can later be moved to DB or file.
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

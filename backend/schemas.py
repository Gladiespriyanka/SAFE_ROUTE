"""
Pydantic request/response models for SafeRoute API.
"""

from typing import Literal, Optional
from pydantic import BaseModel, Field


class PredictionInput(BaseModel):
    """Core tabular features for safety prediction."""
    
    # Geo
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)

    # Tabular features
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


class RouteFeatures(BaseModel):
    """
    Core tabular features + basic geo coords.
    Alias for PredictionInput for backward compatibility.
    """
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
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
    """Simple thumbs-up / thumbs-down feedback from UI."""
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
    """Basic Safetipin-style audit for a point on the map."""
    latitude: float
    longitude: float
    lighting_level: int = Field(..., ge=0, le=2)
    crowd_level: int = Field(..., ge=0, le=2)
    perceived_safety: int = Field(..., ge=0, le=2)
    comment: Optional[str] = Field(default=None, max_length=500)
    hour_of_day: int = Field(..., ge=0, le=23)
    is_weekend: Literal[0, 1]
    area_type: Optional[int] = Field(default=None, ge=0, le=2)


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    model_loaded: bool
    num_features: int
    version: str
    num_audits: int
    num_feedback: int
    poi_loaded: bool
    area_risk_loaded: bool


class PredictionResponse(BaseModel):
    """Enhanced prediction response with ALL fields."""
    prediction: int
    label: str
    description: str
    risk_score: int
    risk_tier: str
    base_risk_score: int
    context_risk_delta: int
    location: dict
    model_factors: list[str]
    context_explanations: list[str]
    factors: list[str]
    confidence: float
    confidence_level: str
    probabilities: dict
    weather: dict
    traffic: dict
    shap_explanation: dict

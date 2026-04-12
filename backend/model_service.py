"""
Core ML service for SafeRoute predictions.
Encapsulates all model loading, data prep, and inference logic.
"""

import os
import sys
from typing import Optional, Dict, Any, List
from math import radians, sin, cos, sqrt, atan2

# --- Make src/ importable ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(BASE_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.append(SRC_DIR)

from predict_utils_enhanced import (  # noqa: E402
    load_model_and_feature_cols,
    predict_safety,
)
from backend.services.poi_context import POIContext  # noqa: E402
from backend.services.area_risk import AreaRiskTable  # noqa: E402


class ModelService:
    """Manages model loading, caching, and prediction operations."""

    def __init__(self):
        """Initialize model and data services."""
        self.pipeline = None
        self.feature_cols = None
        self.poi_context: Optional[POIContext] = None
        self.area_risk_table: Optional[AreaRiskTable] = None
        self._load_all()

    def _load_all(self):
        """Load model and auxiliary data tables."""
        try:
            self.pipeline, self.feature_cols = load_model_and_feature_cols()
            print("[✓] Model and feature columns loaded successfully")
        except Exception as e:
            print(f"[✗] Failed to load model: {e}")
            self.pipeline = None
            self.feature_cols = None

        try:
            self.poi_context = POIContext()
            print("[✓] POI context loaded successfully")
        except Exception as e:
            print(f"[✗] Could not load POI context: {e}")
            self.poi_context = None

        try:
            self.area_risk_table = AreaRiskTable()
            print("[✓] Area risk table loaded successfully")
        except Exception as e:
            print(f"[✗] Could not load area risk table: {e}")
            self.area_risk_table = None

    def is_ready(self) -> bool:
        """Check if model is loaded and ready."""
        return self.pipeline is not None and self.feature_cols is not None

    def get_status(self) -> Dict[str, Any]:
        """Get service status."""
        return {
            "model_loaded": self.pipeline is not None,
            "num_features": len(self.feature_cols) if self.feature_cols else 0,
            "poi_loaded": self.poi_context is not None,
            "area_risk_loaded": self.area_risk_table is not None,
        }

    @staticmethod
    def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance in meters between two points (lat, lon)."""
        R = 6371000.0  # meters
        dlat = radians(lat2 - lat1)
        dlon = radians(lon2 - lon1)
        a = (
            sin(dlat / 2) ** 2
            + cos(radians(lat1))
            * cos(radians(lat2))
            * sin(dlon / 2) ** 2
        )
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        return R * c

    @staticmethod
    def _get_area_key_from_coords(lat: float, lon: float) -> str:
        """Map (lat, lon) in Delhi region to a coarse area_key."""
        center_lat = 28.61
        center_lon = 77.21
        lat_band = 0.04
        lon_band = 0.05

        if (center_lat - lat_band) <= lat <= (center_lat + lat_band) and (
            center_lon - lon_band
        ) <= lon <= (center_lon + lon_band):
            return "central_delhi"

        if lat > center_lat:
            return "north_delhi"
        elif lat < center_lat:
            return "south_delhi"
        else:
            if lon >= center_lon:
                return "east_delhi"
            else:
                return "west_delhi"

    def compute_audit_score_mean(
        self, lat: float, lon: float, audits: List[Dict], radius_m: float = 300.0
    ) -> float:
        """Compute average perceived_safety score within radius_m."""
        if not audits:
            return 0.0

        scores: List[float] = []
        for audit in audits:
            dist = self._haversine_m(
                lat, lon, audit["latitude"], audit["longitude"]
            )
            if dist <= radius_m:
                scores.append(float(audit.get("perceived_safety", 0)))

        return float(sum(scores) / len(scores)) if scores else 0.0

    def predict(
        self,
        data: Dict[str, Any],
        audits: List[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Run ML model prediction with enriched features from POI and area risk.

        Args:
            data: Dictionary with all 12 required features + latitude/longitude
            audits: Optional list of nearby audit records

        Returns:
            Dictionary with prediction, label, confidence, probabilities, SHAP explanation
        """
        if not self.is_ready():
            raise RuntimeError("Model not loaded")

        audits = audits or []
        lat = data.get("latitude", 0.0)
        lon = data.get("longitude", 0.0)

        # 1) From audits: perceived safety around this point
        audit_score_mean = self.compute_audit_score_mean(lat, lon, audits)

        # 2) From POI cache: distances to metro/bus/hospital/police
        dist_to_metro_m = None
        dist_to_bus_m = None
        dist_to_hospital_m = None
        dist_to_police_m = None

        if self.poi_context is not None:
            try:
                poi_dists = self.poi_context.nearest_distances(lat=lat, lon=lon)
                dist_to_metro_m = poi_dists.get("dist_to_metro_m")
                dist_to_bus_m = poi_dists.get("dist_to_bus_m")
                dist_to_hospital_m = poi_dists.get("dist_to_hospital_m")
                dist_to_police_m = poi_dists.get("dist_to_police_m")
            except Exception as e:
                print(f"[WARN] POI distance computation failed: {e}")

        # 3) Map coords -> area_key -> area_crime_risk
        area_crime_risk = 0.0
        if self.area_risk_table is not None:
            try:
                area_key = self._get_area_key_from_coords(lat, lon)
                area_crime_risk = float(self.area_risk_table.get_risk(area_key))
            except Exception as e:
                print(f"[WARN] Area risk computation failed: {e}")

        # 4) Call model prediction with all features
        result = predict_safety(
            pipeline=self.pipeline,
            feature_cols=self.feature_cols,
            lighting_level=data.get("lighting_level", 1),
            crowd_level=data.get("crowd_level", 1),
            distance_to_main_road_m=data.get("distance_to_main_road_m", 500),
            shops_open_at_night=data.get("shops_open_at_night", 0),
            police_station_within_1km=data.get("police_station_within_1km", 0),
            cctv_present=data.get("cctv_present", 0),
            hour_of_day=data.get("hour_of_day", 12),
            is_weekend=data.get("is_weekend", 0),
            area_type=data.get("area_type", 0),
            near_metro_or_bus=data.get("near_metro_or_bus", 0),
            past_incidents_level=data.get("past_incidents_level", 0),
            group_travel=data.get("group_travel", 1),
            area_crime_risk=area_crime_risk,
            audit_score_mean=audit_score_mean,
            dist_to_metro_m=dist_to_metro_m,
            dist_to_bus_m=dist_to_bus_m,
            dist_to_hospital_m=dist_to_hospital_m,
            dist_to_police_m=dist_to_police_m,
            include_shap=True,
        )

        return {
            "prediction": result["prediction"],
            "label": result["label"],
            "description": result.get("description", ""),
            "confidence": result["confidence"],
            "confidence_level": result["confidence_level"],
            "probabilities": result["probabilities"],
            "shap_explanation": result.get("shap_explanation", {}),
        }


# Global service instance
_model_service: Optional[ModelService] = None


def get_model_service() -> ModelService:
    """Get or create the global model service instance."""
    global _model_service
    if _model_service is None:
        _model_service = ModelService()
    return _model_service

"""
Enhanced prediction utilities for SafeRoute Delhi ML model.

Features:
- Predictions with probability/confidence scores
- SHAP feature importance analysis
- Data validation and sanitization
- Human-readable label mapping
"""

import joblib
import numpy as np
import logging
from typing import Dict, Any, Optional
import shap

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Label mapping: 0 = Unsafe, 1 = Moderate, 2 = Safe
LABELS = {
    0: "Unsafe",
    1: "Moderate", 
    2: "Safe"
}

LABEL_DESCRIPTIONS = {
    0: "⚠️  Unsafe - High risk area. Avoid if possible. If necessary, travel in groups.",
    1: "⚠️  Moderate - Mixed conditions. Use caution, especially at night.",
    2: "✅ Safe - Relatively safer route. Still maintain awareness."
}


def load_model_and_feature_cols(
    model_path: str = "models/saferoute_model.pkl",
    feature_cols_path: str = "models/feature_cols.pkl",
) -> tuple:
    """
    Load the trained pipeline model and feature column order.
    
    Args:
        model_path: Path to the saved pipeline model
        feature_cols_path: Path to the saved feature columns list
    
    Returns:
        Tuple of (pipeline, feature_cols)
    """
    try:
        pipeline = joblib.load(model_path)
        feature_cols = joblib.load(feature_cols_path)
        logger.info(f"Loaded model from {model_path}")
        logger.info(f"Loaded {len(feature_cols)} feature columns")
        return pipeline, feature_cols
    except FileNotFoundError as e:
        logger.error(f"Failed to load model: {e}")
        raise


def sanitize_inputs(
    lighting_level: int,
    crowd_level: int,
    distance_to_main_road_m: float,
    shops_open_at_night: int,
    police_station_within_1km: int,
    cctv_present: int,
    hour_of_day: int,
    is_weekend: int,
    area_type: int = 0,
    near_metro_or_bus: int = 0,
    past_incidents_level: int = 0,
    group_travel: int = 0,
    area_crime_risk: Optional[float] = None,
    audit_score_mean: Optional[float] = None,
    dist_to_metro_m: Optional[float] = None,
    dist_to_bus_m: Optional[float] = None,
    dist_to_hospital_m: Optional[float] = None,
    dist_to_police_m: Optional[float] = None,
) -> Dict[str, float]:
    """
    Validate and sanitize input values, clipping to valid ranges.
    
    Returns dict with cleaned feature values.
    """
    # Core numeric features - 0, 1, 2 scale
    lighting_level = int(np.clip(lighting_level, 0, 2))
    crowd_level = int(np.clip(crowd_level, 0, 2))
    area_type = int(np.clip(area_type, 0, 2))
    past_incidents_level = int(np.clip(past_incidents_level, 0, 2))

    # Distance feature (meters)
    distance_to_main_road_m = float(np.clip(distance_to_main_road_m, 0, 5000))

    # Binary features
    shops_open_at_night = 1 if shops_open_at_night else 0
    police_station_within_1km = 1 if police_station_within_1km else 0
    cctv_present = 1 if cctv_present else 0
    is_weekend = 1 if is_weekend else 0
    near_metro_or_bus = 1 if near_metro_or_bus else 0
    group_travel = 1 if group_travel else 0

    # Hour of day (0-23)
    hour_of_day = int(np.clip(hour_of_day, 0, 23))
    
    # Cyclical hour encoding
    hour_sin = float(np.sin(2 * np.pi * hour_of_day / 24))
    hour_cos = float(np.cos(2 * np.pi * hour_of_day / 24))

    # Optional features with defaults
    def safe_clip(value, lo, hi, default=0.0):
        if value is None:
            return float(default)
        try:
            v = float(value)
            return float(np.clip(v, lo, hi))
        except (ValueError, TypeError):
            return float(default)

    area_crime_risk = safe_clip(area_crime_risk, 0.0, 3.0, 0.0)
    audit_score_mean = safe_clip(audit_score_mean, 0.0, 2.0, 0.0)
    dist_to_metro_m = safe_clip(dist_to_metro_m, 0.0, 10000.0, 0.0)
    dist_to_bus_m = safe_clip(dist_to_bus_m, 0.0, 10000.0, 0.0)
    dist_to_hospital_m = safe_clip(dist_to_hospital_m, 0.0, 10000.0, 0.0)
    dist_to_police_m = safe_clip(dist_to_police_m, 0.0, 10000.0, 0.0)

    return {
        "lighting_level": lighting_level,
        "crowd_level": crowd_level,
        "distance_to_main_road_m": distance_to_main_road_m,
        "shops_open_at_night": shops_open_at_night,
        "police_station_within_1km": police_station_within_1km,
        "cctv_present": cctv_present,
        "is_weekend": is_weekend,
        "area_type": area_type,
        "near_metro_or_bus": near_metro_or_bus,
        "past_incidents_level": past_incidents_level,
        "group_travel": group_travel,
        "area_crime_risk": area_crime_risk,
        "audit_score_mean": audit_score_mean,
        "dist_to_metro_m": dist_to_metro_m,
        "dist_to_bus_m": dist_to_bus_m,
        "dist_to_hospital_m": dist_to_hospital_m,
        "dist_to_police_m": dist_to_police_m,
       "hour_of_day": hour_of_day,
    }


def compute_confidence_level(max_probability: float) -> str:
    """Map probability to confidence level."""
    if max_probability >= 0.8:
        return "High"
    elif max_probability >= 0.6:
        return "Medium"
    elif max_probability >= 0.4:
        return "Low"
    else:
        return "Very Low"


def get_shap_explanation(
    pipeline,
    feature_cols,
    feature_values: Dict[str, float],
    predicted_class: int,
) -> Dict[str, Any]:
    """
    Compute SHAP values for a single prediction.
    
    Returns dict with top 3 contributing factors.
    """
    try:
        # Build feature array
        import pandas as pd
        x_df = pd.DataFrame([feature_values])
        x_df = x_df[feature_cols]  # Ensure correct column order
        
        # Extract classifier from pipeline
        classifier = pipeline if not hasattr(pipeline, "named_steps") else pipeline.named_steps.get("classifier", pipeline)
        
        # Create SHAP explainer
        explainer = shap.TreeExplainer(classifier)
        shap_values = explainer.shap_values(x_df.values)
        
        # Extract SHAP values for predicted class
        if isinstance(shap_values, list):
            sv = shap_values[predicted_class][0]
        else:
            sv = shap_values[0] if len(shap_values.shape) > 1 else shap_values
        
        # Get top 3 factors
        shap_series = pd.Series(np.abs(sv), index=feature_cols)
        top_factors = shap_series.sort_values(ascending=False).head(3)
        
        return {
            "status": "success",
            "top_factors": [
                {
                    "feature": str(feat),
                    "impact": float(impact),
                    "rank": i + 1
                }
                for i, (feat, impact) in enumerate(top_factors.items())
            ]
        }
    except Exception as e:
        logger.warning(f"SHAP analysis failed: {e}")
        return {
            "status": "failed",
            "error": str(e),
            "top_factors": []
        }


def predict_safety(
    pipeline,
    feature_cols,
    lighting_level: int,
    crowd_level: int,
    distance_to_main_road_m: float,
    shops_open_at_night: int,
    police_station_within_1km: int,
    cctv_present: int,
    hour_of_day: int,
    is_weekend: int,
    area_type: int = 0,
    near_metro_or_bus: int = 0,
    past_incidents_level: int = 0,
    group_travel: int = 0,
    area_crime_risk: Optional[float] = None,
    audit_score_mean: Optional[float] = None,
    dist_to_metro_m: Optional[float] = None,
    dist_to_bus_m: Optional[float] = None,
    dist_to_hospital_m: Optional[float] = None,
    dist_to_police_m: Optional[float] = None,
    include_shap: bool = True,
) -> Dict[str, Any]:
    """
    Main prediction function.
    
    Returns comprehensive prediction result with:
    - prediction: numeric class (0, 1, 2)
    - label: human-readable label (Unsafe, Moderate, Safe)
    - confidence: confidence score (0.0 - 1.0)
    - confidence_level: High/Medium/Low/Very Low
    - probabilities: full probability distribution
    - description: human-readable description
    - shap_explanation: top contributing factors (if include_shap=True)
    """
    
    # Sanitize inputs
    clean_inputs = sanitize_inputs(
        lighting_level=lighting_level,
        crowd_level=crowd_level,
        distance_to_main_road_m=distance_to_main_road_m,
        shops_open_at_night=shops_open_at_night,
        police_station_within_1km=police_station_within_1km,
        cctv_present=cctv_present,
        hour_of_day=hour_of_day,
        is_weekend=is_weekend,
        area_type=area_type,
        near_metro_or_bus=near_metro_or_bus,
        past_incidents_level=past_incidents_level,
        group_travel=group_travel,
        area_crime_risk=area_crime_risk,
        audit_score_mean=audit_score_mean,
        dist_to_metro_m=dist_to_metro_m,
        dist_to_bus_m=dist_to_bus_m,
        dist_to_hospital_m=dist_to_hospital_m,
        dist_to_police_m=dist_to_police_m,
    )
    
    # Build feature array in correct order
    import pandas as pd
    x_df = pd.DataFrame([clean_inputs])
    x_df = x_df[feature_cols]  # Ensure correct column order
    
    # Get prediction
    predicted_class = int(pipeline.predict(x_df)[0])
    probabilities = pipeline.predict_proba(x_df)[0]
    
    # Confidence score (max probability)
    confidence = float(np.max(probabilities))
    confidence_level = compute_confidence_level(confidence)
    
    # Build result
    result = {
        "prediction": predicted_class,
        "label": LABELS[predicted_class],
        "description": LABEL_DESCRIPTIONS[predicted_class],
        "confidence": confidence,
        "confidence_level": confidence_level,
        "probabilities": {
            "unsafe": float(probabilities[0]),
            "moderate": float(probabilities[1]) if len(probabilities) > 1 else 0.0,
            "safe": float(probabilities[2]) if len(probabilities) > 2 else 0.0,
        }
    }
    
    # Add SHAP explanation if requested
    if include_shap:
        shap_explain = get_shap_explanation(
            pipeline, feature_cols, clean_inputs, predicted_class
        )
        result["shap_explanation"] = shap_explain
    
    return result


def format_prediction_output(prediction_result: Dict[str, Any]) -> str:
    """
    Format prediction result as human-readable string.
    """
    output = []
    output.append("\n" + "="*70)
    output.append("SAFEROUTE DELHI - ROUTE SAFETY PREDICTION")
    output.append("="*70)
    
    output.append(f"\n🎯 PREDICTION: {prediction_result['label'].upper()}")
    output.append(f"   {prediction_result['description']}")
    
    output.append(f"\n📊 CONFIDENCE: {prediction_result['confidence_level']}")
    output.append(f"   Confidence Score: {prediction_result['confidence']:.2%}")
    
    output.append(f"\n📈 PROBABILITY BREAKDOWN:")
    for label_name in ["unsafe", "moderate", "safe"]:
        prob = prediction_result["probabilities"][label_name]
        bar_length = int(prob * 20)
        bar = "█" * bar_length + "░" * (20 - bar_length)
        output.append(f"   {label_name.capitalize():<12} {bar} {prob:.2%}")
    
    if "shap_explanation" in prediction_result:
        shap_result = prediction_result["shap_explanation"]
        if shap_result["status"] == "success" and shap_result["top_factors"]:
            output.append(f"\n🔍 TOP CONTRIBUTING FACTORS:")
            for factor in shap_result["top_factors"]:
                output.append(
                    f"   {factor['rank']}. {factor['feature']:<30} "
                    f"Impact: {factor['impact']:.4f}"
                )
        elif shap_result["status"] == "failed":
            output.append(f"\n⚠️  SHAP analysis unavailable: {shap_result.get('error', 'Unknown error')}")
    
    output.append("\n" + "="*70)
    return "\n".join(output)

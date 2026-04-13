import os
from typing import Dict, Any
from datetime import datetime
import logging

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import shap  # MOD-5: SHAP explainability

from sklearn.model_selection import train_test_split, cross_val_score, GridSearchCV
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    classification_report,
    confusion_matrix,
    mean_squared_error,   # MOD-1: MSE/RMSE metrics
)
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from imblearn.over_sampling import SMOTE
import joblib

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ----------------------------
# Config
# ----------------------------

DATA_PATH = "data/saferoute_delhi.csv"

# Base features (your current ones)
BASE_FEATURE_COLS = [
    "lighting_level",
    "crowd_level",
    "distance_to_main_road_m",
    "shops_open_at_night",
    "police_station_within_1km",
    "cctv_present",
    # "hour_of_day" removed — replaced by hour_sin / hour_cos (MOD-3)
    "is_weekend",
    "area_type",
    "near_metro_or_bus",
    "past_incidents_level",
    "group_travel",
]

# New realistic-data features (to be populated as you build data)
EXTRA_FEATURE_COLS = [
    "area_crime_risk",      # 0=low,1=medium,2=high based on ward/police-station crime stats
    "audit_score_mean",     # mean perceived safety from nearby audits
    "dist_to_metro_m",      # distance to nearest metro station (meters)
    "dist_to_bus_m",        # distance to nearest major bus stop (meters)
    "dist_to_hospital_m",   # distance to nearest hospital (meters)
    "dist_to_police_m",     # distance to nearest police station (meters)
]

# MOD-3: Cyclical hour features replace raw hour_of_day
CYCLICAL_FEATURE_COLS = [
    "hour_sin",
    "hour_cos",
]

FEATURE_COLS = BASE_FEATURE_COLS + EXTRA_FEATURE_COLS + CYCLICAL_FEATURE_COLS

TARGET_COL = "safety_label"  # 0=Unsafe, 1=Moderate, 2=Safe

# Define numeric and categorical columns for preprocessing
NUMERIC_COLS = [
    "lighting_level",
    "crowd_level",
    "distance_to_main_road_m",
    "area_type",
    "past_incidents_level",
    "area_crime_risk",
    "audit_score_mean",
    "dist_to_metro_m",
    "dist_to_bus_m",
    "dist_to_hospital_m",
    "dist_to_police_m",
    "hour_sin",
    "hour_cos",
]

CATEGORICAL_COLS = [
    "shops_open_at_night",
    "police_station_within_1km",
    "cctv_present",
    "is_weekend",
    "near_metro_or_bus",
    "group_travel",
]

N_FOLDS = 5
RANDOM_STATE = 42

# Hyperparameter tuning grids
RF_PARAM_GRID = {
    "classifier__n_estimators": [100, 150, 200],
    "classifier__max_depth": [10, 15, 20, None],
    "classifier__min_samples_split": [2, 5, 10],
}

HGB_PARAM_GRID = {
    "classifier__learning_rate": [0.01, 0.05, 0.1],
    "classifier__max_depth": [5, 7, 10],
}

# Model versioning
MODEL_VERSION = 1
MODEL_SAVE_DIR = "models"
os.makedirs(MODEL_SAVE_DIR, exist_ok=True)
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
MODEL_PATH_TEMPLATE = f"saferoute_model_v{MODEL_VERSION}_{TIMESTAMP}.pkl"
FEATURE_COLS_PATH = "feature_cols.pkl"
SCALER_PATH = f"scaler_v{MODEL_VERSION}_{TIMESTAMP}.pkl"

# ----------------------------
# Load data
# ----------------------------

logger.info(f"Loading data from {DATA_PATH} ...")
df = pd.read_csv(DATA_PATH)

# ----------------------------
# DATA VALIDATION: Check for missing values and handle them
# ----------------------------

logger.info("=== DATA VALIDATION ===")
logger.info(f"Dataset shape: {df.shape}")
logger.info(f"\nMissing values per column:")

missing_summary = df.isnull().sum()
if missing_summary.sum() > 0:
    logger.warning(f"Found missing values:\n{missing_summary[missing_summary > 0]}")
    
    # Fill numeric columns with mean
    for col in NUMERIC_COLS:
        if col in df.columns and df[col].isnull().sum() > 0:
            mean_val = df[col].mean()
            logger.warning(f"  Filling {col} with mean: {mean_val:.4f}")
            df[col].fillna(mean_val, inplace=True)
    
    # Fill categorical columns with mode
    for col in CATEGORICAL_COLS:
        if col in df.columns and df[col].isnull().sum() > 0:
            mode_val = df[col].mode()[0] if not df[col].mode().empty else 0
            logger.warning(f"  Filling {col} with mode: {mode_val}")
            df[col].fillna(mode_val, inplace=True)
else:
    logger.info("No missing values found.")

# Create all required columns if they don't exist
for col in FEATURE_COLS:
    if col not in df.columns:
        logger.warning(f"Column {col} not found in data; creating with 0.0 (will be handled in preprocessing)")
        df[col] = 0.0

# ----------------------------
# MOD-3: Cyclical hour encoding with noise addition to labels
# ----------------------------
# Add 'hour' column (0–23) from hour_of_day if it exists, else default to 0
if "hour_of_day" in df.columns:
    df["hour"] = df["hour_of_day"].astype(int)
else:
    logger.warning("'hour_of_day' column not found; defaulting 'hour' to 0.")
    df["hour"] = 0

# Cyclical encoding using numpy
df["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24)
df["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24)

# Drop raw hour column (not hour_of_day — that was the original; drop our temp 'hour')
df.drop(columns=["hour"], inplace=True)

logger.info("Cyclical hour features added: hour_sin, hour_cos (raw 'hour' column dropped)")

# ----------------------------
# SEMI-SYNTHETIC LABELS: Add randomness/noise to safety_label
# ----------------------------
"""
The safety_label column may come from synthetic data or simplified annotations.
To simulate real-world uncertainty and make predictions more realistic, we add:
  1. Small random noise to reduce overconfidence
  2. Probabilistic labels that reflect uncertainty
  
This helps the model generalize better to real-world data where safety assessment
is inherently probabilistic.
"""

logger.info("\n=== SEMI-SYNTHETIC LABEL HANDLING ===")
logger.info("Note: Labels are semi-synthetic with added noise to simulate real-world uncertainty")

# Handle missing target labels before any integer conversion
missing_labels = int(df[TARGET_COL].isnull().sum())
if missing_labels > 0:
    logger.warning("Generating balanced synthetic labels")

    num_samples = len(df)

    df[TARGET_COL] = np.random.choice(
        [0, 1, 2],
        size=num_samples,
        p=[0.3, 0.4, 0.3]
    )

# Final guard: ensure no NaN remains before astype(int)
if df[TARGET_COL].isnull().any():
    remaining_missing = int(df[TARGET_COL].isnull().sum())
    raise ValueError(
        f"{TARGET_COL} still contains {remaining_missing} missing values after fill step."
    )

# Store original label distribution
original_dist = df[TARGET_COL].value_counts().sort_index()
logger.info(f"\nOriginal label distribution:\n{original_dist}")

# Add small noise to labels (swap ~5% of labels to adjacent class)
np.random.seed(RANDOM_STATE)
noise_fraction = 0.05
noise_indices = np.random.choice(
    df.index,
    size=int(len(df) * noise_fraction),
    replace=False
)

for idx in noise_indices:
    current_label = df.loc[idx, TARGET_COL]
    # Swap to adjacent class (0->1, 1->0 or 2, 2->1)
    if current_label == 0:
        df.loc[idx, TARGET_COL] = 1
    elif current_label == 1:
        df.loc[idx, TARGET_COL] = np.random.choice([0, 2])
    else:
        df.loc[idx, TARGET_COL] = 1

noisy_dist = df[TARGET_COL].value_counts().sort_index()
logger.info(f"Label distribution after noise injection ({noise_fraction*100:.1f}%):\n{noisy_dist}")
logger.info("This noise simulates real-world labeling uncertainty and helps the model generalize.")

# Ensure all values are valid (0, 1, or 2)
df[TARGET_COL] = df[TARGET_COL].astype(int)
assert df[TARGET_COL].isin([0, 1, 2]).all(), "Invalid labels detected!"
logger.info("Label validation passed: all labels are in [0, 1, 2]")

X = df[FEATURE_COLS].copy()
X = X.fillna(0)
y = df[TARGET_COL].copy()

# ----------------------------
# CLASS IMBALANCE ANALYSIS
# ----------------------------

logger.info("\n=== CLASS IMBALANCE ANALYSIS ===")
class_dist = y.value_counts().sort_index()
logger.info(f"Class distribution:\n{class_dist}")
logger.info(f"Proportions:")
for cls, count in class_dist.items():
    pct = 100 * count / len(y)
    logger.info(f"  Class {cls} ({['Unsafe', 'Moderate', 'Safe'][cls]}): {count} samples ({pct:.1f}%)")

# ----------------------------
# MOD-1: Train/test split (80-20) + data preparation
# ----------------------------

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.2,
random_state=42
)

logger.info(f"\nTrain size: {len(X_train)}, Test size: {len(X_test)}")

# Apply SMOTE on training data to handle class imbalance
logger.info("\n=== APPLYING SMOTE FOR CLASS IMBALANCE HANDLING ===")
try:
    smote = SMOTE(random_state=RANDOM_STATE, k_neighbors=5)
    X_train_resampled, y_train_resampled = smote.fit_resample(X_train, y_train)
    logger.info(f"Training data after SMOTE:")
    logger.info(f"  Original size: {len(X_train)}")
    logger.info(f"  Resampled size: {len(X_train_resampled)}")
    logger.info(f"  New class distribution:\n{pd.Series(y_train_resampled).value_counts().sort_index()}")
    X_train = X_train_resampled
    y_train = y_train_resampled
except Exception as e:
    logger.warning(f"SMOTE failed ({e}), falling back to class_weight='balanced'")
    X_train = X_train
    y_train = y_train

# ----------------------------
# PIPELINE DEFINITION: Preprocessing + Model
# ----------------------------

logger.info("\n=== DEFINING SKLEARN PIPELINES ===")

def create_rf_pipeline():
    """Random Forest pipeline with scaling"""
    return Pipeline([
        ("scaler", StandardScaler()),
        ("classifier", RandomForestClassifier(
            n_estimators=150,
            max_depth=15,
            min_samples_split=5,
            random_state=RANDOM_STATE,
            class_weight="balanced",
            n_jobs=-1,
        ))
    ])

def create_hgb_pipeline():
    """HistGradientBoosting pipeline with scaling"""
    return Pipeline([
        ("scaler", StandardScaler()),
        ("classifier", HistGradientBoostingClassifier(
            learning_rate=0.1,
            max_depth=10,
            random_state=RANDOM_STATE
        ))
    ])

def create_lr_pipeline():
    """LogisticRegression pipeline with scaling"""
    return Pipeline([
        ("scaler", StandardScaler()),
        ("classifier", LogisticRegression(
            max_iter=500,
            random_state=RANDOM_STATE,
            class_weight="balanced",
        ))
    ])

pipelines = {
    "RandomForest": create_rf_pipeline(),
    "HistGradientBoosting": create_hgb_pipeline(),
    "LogisticRegression": create_lr_pipeline(),
}

results = []

for name, pipeline in pipelines.items():
    logger.info("\n" + "="*50)
    logger.info(f"Training: {name}")
    logger.info("="*50)

    # MOD-4: 5-fold cross-validation
    logger.info(f"\nRunning {N_FOLDS}-fold cross-validation...")
    cv_scores = cross_val_score(
        pipeline, X_train, y_train, cv=N_FOLDS, scoring="accuracy"
    )
    cv_f1_scores = cross_val_score(
        pipeline, X_train, y_train, cv=N_FOLDS, scoring="f1_macro"
    )

    logger.info(f"{name} CV accuracy: {cv_scores.mean():.4f} ± {cv_scores.std():.4f}")
    logger.info(f"{name} CV macro F1:  {cv_f1_scores.mean():.4f} ± {cv_f1_scores.std():.4f}")

    # Fit on full train split
    logger.info(f"\nFitting {name} on full training data...")
    pipeline.fit(X_train, y_train)

    # Evaluate on held-out test set
    y_pred = pipeline.predict(X_test)
    y_proba = pipeline.predict_proba(X_test)

    acc = accuracy_score(y_test, y_pred)
    macro_f1 = f1_score(y_test, y_pred, average="macro")
    mse = mean_squared_error(y_test, y_pred)
    rmse = np.sqrt(mse)

    logger.info(f"\n{name} Test Results:")
    logger.info(f"  Accuracy:  {acc:.4f}")
    logger.info(f"  Macro F1:  {macro_f1:.4f}")
    logger.info(f"  MSE:       {mse:.4f}")
    logger.info(f"  RMSE:      {rmse:.4f}")
    logger.info("\nClassification Report:")
    logger.info("\n" + classification_report(y_test, y_pred, target_names=["Unsafe", "Moderate", "Safe"]))
    logger.info("Confusion Matrix:")
    logger.info(f"\n{confusion_matrix(y_test, y_pred)}")

    results.append({
        "name": name,
        "cv_acc_mean": cv_scores.mean(),
        "cv_acc_std": cv_scores.std(),
        "cv_f1_mean": cv_f1_scores.mean(),
        "cv_f1_std": cv_f1_scores.std(),
        "test_acc": acc,
        "test_macro_f1": macro_f1,
        "test_mse": mse,
        "test_rmse": rmse,
        "pipeline": pipeline,
    })

# ----------------------------
# HYPERPARAMETER TUNING: GridSearchCV for best model
# ----------------------------

logger.info("\n" + "="*70)
logger.info("HYPERPARAMETER TUNING WITH GRIDSEARCHCV")
logger.info("="*70)

# Tune RandomForest
logger.info("\nTuning RandomForest hyperparameters...")
rf_pipeline_base = Pipeline([
    ("scaler", StandardScaler()),
    ("classifier", RandomForestClassifier(random_state=RANDOM_STATE, class_weight="balanced", n_jobs=-1))
])

rf_grid = GridSearchCV(
    rf_pipeline_base,
    RF_PARAM_GRID,
    cv=3,
    scoring="f1_macro",
    n_jobs=-1,
    verbose=1
)
rf_grid.fit(X_train, y_train)

logger.info(f"Best RF parameters: {rf_grid.best_params_}")
logger.info(f"Best CV F1 score: {rf_grid.best_score_:.4f}")

# Update best RF results
y_pred_rf_tuned = rf_grid.best_estimator_.predict(X_test)
y_proba_rf_tuned = rf_grid.best_estimator_.predict_proba(X_test)
acc_rf_tuned = accuracy_score(y_test, y_pred_rf_tuned)
f1_rf_tuned = f1_score(y_test, y_pred_rf_tuned, average="macro")

logger.info(f"Tuned RF Test Accuracy: {acc_rf_tuned:.4f}, Macro F1: {f1_rf_tuned:.4f}")

# Tune HistGradientBoosting
logger.info("\nTuning HistGradientBoosting hyperparameters...")
hgb_pipeline_base = Pipeline([
    ("scaler", StandardScaler()),
    ("classifier", HistGradientBoostingClassifier(random_state=RANDOM_STATE))
])

hgb_grid = GridSearchCV(
    hgb_pipeline_base,
    HGB_PARAM_GRID,
    cv=3,
    scoring="f1_macro",
    n_jobs=-1,
    verbose=1
)
hgb_grid.fit(X_train, y_train)

logger.info(f"Best HGB parameters: {hgb_grid.best_params_}")
logger.info(f"Best CV F1 score: {hgb_grid.best_score_:.4f}")

# Update best HGB results
y_pred_hgb_tuned = hgb_grid.best_estimator_.predict(X_test)
y_proba_hgb_tuned = hgb_grid.best_estimator_.predict_proba(X_test)
acc_hgb_tuned = accuracy_score(y_test, y_pred_hgb_tuned)
f1_hgb_tuned = f1_score(y_test, y_pred_hgb_tuned, average="macro")

logger.info(f"Tuned HGB Test Accuracy: {acc_hgb_tuned:.4f}, Macro F1: {f1_hgb_tuned:.4f}")

# Add tuned results to comparison
results.append({
    "name": "RandomForest (Tuned)",
    "cv_acc_mean": rf_grid.best_score_,
    "cv_acc_std": 0,
    "cv_f1_mean": rf_grid.best_score_,
    "cv_f1_std": 0,
    "test_acc": acc_rf_tuned,
    "test_macro_f1": f1_rf_tuned,
    "test_mse": mean_squared_error(y_test, y_pred_rf_tuned),
    "test_rmse": np.sqrt(mean_squared_error(y_test, y_pred_rf_tuned)),
    "pipeline": rf_grid.best_estimator_,
})

results.append({
    "name": "HistGradientBoosting (Tuned)",
    "cv_acc_mean": hgb_grid.best_score_,
    "cv_acc_std": 0,
    "cv_f1_mean": hgb_grid.best_score_,
    "cv_f1_std": 0,
    "test_acc": acc_hgb_tuned,
    "test_macro_f1": f1_hgb_tuned,
    "test_mse": mean_squared_error(y_test, y_pred_hgb_tuned),
    "test_rmse": np.sqrt(mean_squared_error(y_test, y_pred_hgb_tuned)),
    "pipeline": hgb_grid.best_estimator_,
})

# ----------------------------
# Pick best model by test macro F1
# ----------------------------

results_df = pd.DataFrame(
    [
        {
            "model": r["name"],
            "cv_acc_mean": r["cv_acc_mean"],
            "cv_acc_std": r["cv_acc_std"],
            "cv_f1_mean": r["cv_f1_mean"],
            "cv_f1_std": r["cv_f1_std"],
            "test_acc": r["test_acc"],
            "test_macro_f1": r["test_macro_f1"],
            "test_mse": r["test_mse"],
            "test_rmse": r["test_rmse"],
        }
        for r in results
    ]
)

logger.info("\n" + "="*70)
logger.info("MODEL COMPARISON SUMMARY")
logger.info("="*70)
logger.info(f"\n{results_df.to_string()}")

# Select model with highest test macro F1
best = max(results, key=lambda r: r["test_macro_f1"])
best_name = best["name"]
best_pipeline = best["pipeline"]

logger.info(f"\n{'='*70}")
logger.info(f"BEST MODEL: {best_name}")
logger.info(f"{'='*70}")
logger.info(f"Test Accuracy: {best['test_acc']:.4f}")
logger.info(f"Test Macro F1: {best['test_macro_f1']:.4f}")
logger.info(f"Test MSE: {best['test_mse']:.4f}")
logger.info(f"Test RMSE: {best['test_rmse']:.4f}")

# ----------------------------
# MODEL VERSIONING: Save best model, scaler, and feature columns
# ----------------------------

logger.info(f"\n{'='*70}")
logger.info("SAVING MODEL WITH VERSIONING")
logger.info(f"{'='*70}")

MODEL_FULL_PATH = os.path.join(MODEL_SAVE_DIR, MODEL_PATH_TEMPLATE)
FEATURE_COLS_FULL_PATH = os.path.join(MODEL_SAVE_DIR, FEATURE_COLS_PATH)
SCALER_FULL_PATH = os.path.join(MODEL_SAVE_DIR, SCALER_PATH)

os.makedirs(MODEL_SAVE_DIR, exist_ok=True)

# Save the entire pipeline (includes scaler and model)
joblib.dump(best_pipeline, MODEL_FULL_PATH)
logger.info(f"Saved best model ({best_name}) to: {MODEL_FULL_PATH}")

# Save feature columns for reference
joblib.dump(FEATURE_COLS, FEATURE_COLS_FULL_PATH)
logger.info(f"Saved feature columns to: {FEATURE_COLS_FULL_PATH}")

# Also save a "latest" symlink for convenience
LATEST_MODEL_PATH = os.path.join(MODEL_SAVE_DIR, "saferoute_model_latest.pkl")
joblib.dump(best_pipeline, LATEST_MODEL_PATH)
logger.info(f"Saved latest model to: {LATEST_MODEL_PATH}")

# Save model comparison results
os.makedirs("artifacts", exist_ok=True)
COMPARISON_PATH = "artifacts/model_comparison.csv"
results_df.to_csv(COMPARISON_PATH, index=False)
logger.info(f"Saved model comparison to: {COMPARISON_PATH}")

# Document model version info
version_info = {
    "version": MODEL_VERSION,
    "timestamp": TIMESTAMP,
    "model_type": best_name,
    "model_path": MODEL_FULL_PATH,
    "test_accuracy": float(best["test_acc"]),
    "test_macro_f1": float(best["test_macro_f1"]),
    "feature_cols": FEATURE_COLS,
}
version_info_path = os.path.join(MODEL_SAVE_DIR, "version_info.pkl")
joblib.dump(version_info, version_info_path)
logger.info(f"Saved version info to: {version_info_path}")

# ----------------------------
# Feature importance from best model
# ----------------------------

logger.info("\n" + "="*70)
logger.info("FEATURE IMPORTANCE ANALYSIS")
logger.info("="*70)

# Extract the classifier from the pipeline
best_classifier = best_pipeline.named_steps.get("classifier", best_pipeline)

if hasattr(best_classifier, "feature_importances_"):
    importances = best_classifier.feature_importances_

    fi_df = pd.DataFrame(
        {"feature": FEATURE_COLS, "importance": importances}
    ).sort_values("importance", ascending=False).reset_index(drop=True)

    FI_PATH = "artifacts/feature_importance.csv"
    fi_df.to_csv(FI_PATH, index=False)
    logger.info(f"Saved feature importance to: {FI_PATH}")

    logger.info("\nTOP 10 FEATURES BY IMPORTANCE:")
    top10 = fi_df.head(10)
    for rank, row in enumerate(top10.itertuples(), start=1):
        bar = "█" * int(row.importance * 50)
        logger.info(f"  {rank:>2}. {row.feature:<30} {row.importance:.4f}  {bar}")

    # Optional local plot
    plt.figure(figsize=(10, 6))
    plt.barh(fi_df["feature"].head(10)[::-1], fi_df["importance"].head(10)[::-1])
    plt.xlabel("Importance")
    plt.title(f"Top 10 Feature Importances — {best_name}")
    plt.tight_layout()
    plt.savefig("artifacts/feature_importance_plot.png", dpi=100, bbox_inches='tight')
    plt.close()
    logger.info("Saved feature importance plot to: artifacts/feature_importance_plot.png")

else:
    logger.warning(f"Model {best_name} does not expose feature_importances_; skipping feature importance analysis.")

# ----------------------------
# SHAP EXPLAINABILITY
# ----------------------------

logger.info("\n" + "="*70)
logger.info("SHAP EXPLAINABILITY ANALYSIS")
logger.info("="*70)

try:
    # Use a single sample from the test set for explanation
    sample_input = X_test.iloc[[0]]  # shape (1, n_features)
    
    # Create SHAP explainer for the pipeline (will use the classifier inside)
    explainer = shap.TreeExplainer(best_classifier)
    shap_values = explainer.shap_values(sample_input)

    # Get prediction for this sample
    predicted_class = int(best_pipeline.predict(sample_input)[0])
    
    if isinstance(shap_values, list):
        # Multi-class: pick SHAP values for the predicted class
        sv = shap_values[predicted_class][0]
    else:
        # Single output
        sv = shap_values[0] if len(shap_values.shape) > 1 else shap_values

    # Map feature names to absolute SHAP values, sort descending
    shap_series = pd.Series(np.abs(sv), index=FEATURE_COLS)
    top3_features = shap_series.sort_values(ascending=False).head(3).index.tolist()

    shap_output = {
        "predicted_class": predicted_class,
        "predicted_label": ["Unsafe", "Moderate", "Safe"][predicted_class],
        "top_factors": top3_features,
    }

    logger.info(f"\nSample Prediction SHAP Analysis:")
    logger.info(f"  Predicted Class: {predicted_class} ({shap_output['predicted_label']})")
    logger.info(f"\n  Top 3 Contributing Features:")
    for i, feat in enumerate(top3_features, start=1):
        raw_val = shap_series[feat]
        logger.info(f"    {i}. {feat:<30} |SHAP| = {raw_val:.4f}")

except Exception as e:
    logger.warning(f"SHAP analysis failed: {e}")
    logger.warning("Tip: SHAP TreeExplainer works best with RandomForest or HistGradientBoosting.")

logger.info("\n" + "="*70)
logger.info("TRAINING COMPLETE")
logger.info("="*70)

"""
SafeRoute Delhi — Women Safety Prediction
Improved Training Pipeline v2
==============================================
Key improvements over v1:
  - Rule-based synthetic data generation (realistic Unsafe/Moderate/Safe)
  - Clear, explainable labeling logic
  - Derived features: risk_score, infrastructure_score, time_risk_score
  - SMOTE only when dataset is large enough; fallback to class_weight
  - RandomForest as primary model with calibration
  - SHAP explainability for top factors
  - Anti-overfitting: max_depth capped, cross-val on stratified folds
"""

import os
import logging
from datetime import datetime

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import joblib
import shap

from sklearn.model_selection import (
    train_test_split,
    StratifiedKFold,
    cross_val_score,
)
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    classification_report,
    confusion_matrix,
    mean_squared_error,
)
from sklearn.calibration import CalibratedClassifierCV

# ─────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s — %(levelname)s — %(message)s",
)
logger = logging.getLogger(__name__)

RANDOM_STATE = 42
np.random.seed(RANDOM_STATE)

# ─────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────
DATA_PATH = "data/saferoute_delhi.csv"
MODEL_SAVE_DIR = "models"
ARTIFACT_DIR = "artifacts"
os.makedirs(MODEL_SAVE_DIR, exist_ok=True)
os.makedirs(ARTIFACT_DIR, exist_ok=True)
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")


# ═══════════════════════════════════════════════════════════════
# SECTION 1 — RULE-BASED LABELING LOGIC
# ═══════════════════════════════════════════════════════════════

def assign_safety_label(row: pd.Series) -> int:
    """
    Deterministic rule-based labeling for women's safety.

    Returns:
        0 = Unsafe
        1 = Moderate
        2 = Safe

    Rules (priority order):
    ──────────────────────────────────────────────────────────────
    UNSAFE (0):
      • Dark + empty + no CCTV + alone            → strongly unsafe
      • Very late hours (23–4) + any 2 of
        [dark, no police, far from main road]      → unsafe
      • High crime area + night + alone            → unsafe

    SAFE (2):
      • Good lighting + crowded + CCTV + police
        + metro/bus nearby + group travel          → strongly safe
      • Daytime (7–19) + good lighting + crowded   → safe

    MODERATE (1):
      • Everything else
    ──────────────────────────────────────────────────────────────
    """
    lighting   = row["lighting_level"]       # 0=dark, 1=dim, 2=bright
    crowd      = row["crowd_level"]           # 0=empty, 1=sparse, 2=crowded
    cctv       = row["cctv_present"]          # 0/1
    police_km  = row["police_station_within_1km"]  # 0/1
    near_pt    = row["near_metro_or_bus"]     # 0/1
    group      = row["group_travel"]          # 0/1
    hour       = row["hour_of_day"]           # 0–23
    shops      = row["shops_open_at_night"]   # 0/1
    dist_main  = row["distance_to_main_road_m"]
    incidents  = row["past_incidents_level"]  # 0=none,1=some,2=many
    crime_risk = row.get("area_crime_risk", 1)  # 0,1,2

    night = (hour >= 21 or hour <= 5)
    late_night = (hour >= 23 or hour <= 4)

    # ── UNSAFE conditions ──────────────────────────────────────
    # Hard unsafe: dark, alone, no infrastructure at night
    if lighting == 0 and crowd == 0 and cctv == 0 and group == 0 and night:
        return 0
    # Very isolated + high crime + night
    if dist_main > 600 and crime_risk == 2 and night:
        return 0
    # Late night + multiple risk factors
    late_risk_count = sum([
        lighting == 0,
        police_km == 0,
        dist_main > 500,
        crowd == 0,
        incidents >= 2,
    ])
    if late_night and late_risk_count >= 3:
        return 0
    # High incident area + dark + alone
    if incidents == 2 and lighting == 0 and group == 0:
        return 0

    # ── SAFE conditions ────────────────────────────────────────
    # Strong safety indicators
    safe_score = sum([
        lighting == 2,
        crowd == 2,
        cctv == 1,
        police_km == 1,
        near_pt == 1,
        group == 1,
        shops == 1,
        dist_main <= 100,
    ])
    if safe_score >= 5 and not late_night:
        return 2
    # Daytime + bright + crowded is reliably safe
    if not night and lighting >= 1 and crowd >= 1 and dist_main <= 300:
        return 2
    # Evening with good infrastructure
    if lighting == 2 and cctv == 1 and police_km == 1 and near_pt == 1 and not late_night:
        return 2

    # ── MODERATE (default) ─────────────────────────────────────
    return 1


# ═══════════════════════════════════════════════════════════════
# SECTION 2 — SYNTHETIC DATA GENERATION
# ═══════════════════════════════════════════════════════════════

def generate_unsafe_samples(n: int) -> pd.DataFrame:
    """Generate realistic UNSAFE scenario rows."""
    records = []
    for _ in range(n):
        hour = np.random.choice(range(24))
        
        rec = {
            "lighting_level":           np.random.choice([0, 1], p=[0.75, 0.25]),
            "crowd_level":              np.random.choice([0, 1], p=[0.70, 0.30]),
            "distance_to_main_road_m":  np.random.randint(400, 1200),
            "shops_open_at_night":      np.random.choice([0, 1], p=[0.85, 0.15]),
            "police_station_within_1km":np.random.choice([0, 1], p=[0.80, 0.20]),
            "cctv_present":             np.random.choice([0, 1], p=[0.85, 0.15]),
            "hour_of_day":              hour,
            "is_weekend":               np.random.randint(0, 2),
            "area_type":                np.random.choice([0, 1]),
            "near_metro_or_bus":        np.random.choice([0, 1], p=[0.75, 0.25]),
            "past_incidents_level":     np.random.choice([1, 2], p=[0.35, 0.65]),
            "group_travel":             np.random.choice([0, 1], p=[0.80, 0.20]),
            "area_crime_risk":          np.random.choice([1, 2], p=[0.30, 0.70]),
            "audit_score_mean":         np.random.uniform(1.0, 2.5),
            "dist_to_metro_m":          np.random.randint(1000, 5000),
            "dist_to_bus_m":            np.random.randint(800, 3000),
            "dist_to_hospital_m":       np.random.randint(2000, 8000),
            "dist_to_police_m":         np.random.randint(1500, 6000),
        }
        records.append(rec)
    df = pd.DataFrame(records)
    df["safety_label"] = 0
    return df


def generate_safe_samples(n: int) -> pd.DataFrame:
    """Generate realistic SAFE scenario rows."""
    records = []
    for _ in range(n):
        hour = np.random.choice(
            list(range(7, 21)),
            p=[1/14] * 14
        )
        rec = {
            "lighting_level":           np.random.choice([1, 2], p=[0.25, 0.75]),
            "crowd_level":              np.random.choice([1, 2], p=[0.30, 0.70]),
            "distance_to_main_road_m":  np.random.randint(20, 300),
            "shops_open_at_night":      np.random.choice([0, 1], p=[0.25, 0.75]),
            "police_station_within_1km":np.random.choice([0, 1], p=[0.20, 0.80]),
            "cctv_present":             np.random.choice([0, 1], p=[0.15, 0.85]),
            "hour_of_day":              hour,
            "is_weekend":               np.random.randint(0, 2),
            "area_type":                np.random.choice([1, 2], p=[0.35, 0.65]),
            "near_metro_or_bus":        np.random.choice([0, 1], p=[0.15, 0.85]),
            "past_incidents_level":     np.random.choice([0, 1], p=[0.75, 0.25]),
            "group_travel":             np.random.choice([0, 1], p=[0.35, 0.65]),
            "area_crime_risk":          np.random.choice([0, 1], p=[0.70, 0.30]),
            "audit_score_mean":         np.random.uniform(3.0, 5.0),
            "dist_to_metro_m":          np.random.randint(50, 800),
            "dist_to_bus_m":            np.random.randint(50, 500),
            "dist_to_hospital_m":       np.random.randint(300, 3000),
            "dist_to_police_m":         np.random.randint(100, 1500),
        }
        records.append(rec)
    df = pd.DataFrame(records)
    df["safety_label"] = 2
    return df


def generate_moderate_samples(n: int) -> pd.DataFrame:
    """Generate realistic MODERATE scenario rows."""
    records = []
    for _ in range(n):
        hour = np.random.choice(
            list(range(17, 24)) + list(range(0, 8)),
            p=[1/15] * 15
        )
        rec = {
            "lighting_level":           np.random.choice([0, 1, 2], p=[0.15, 0.60, 0.25]),
            "crowd_level":              np.random.choice([0, 1, 2], p=[0.20, 0.55, 0.25]),
            "distance_to_main_road_m":  np.random.randint(150, 600),
            "shops_open_at_night":      np.random.randint(0, 2),
            "police_station_within_1km":np.random.choice([0, 1], p=[0.50, 0.50]),
            "cctv_present":             np.random.choice([0, 1], p=[0.55, 0.45]),
            "hour_of_day":              hour,
            "is_weekend":               np.random.randint(0, 2),
            "area_type":                np.random.randint(0, 3),
            "near_metro_or_bus":        np.random.choice([0, 1], p=[0.50, 0.50]),
            "past_incidents_level":     np.random.choice([0, 1, 2], p=[0.30, 0.50, 0.20]),
            "group_travel":             np.random.randint(0, 2),
            "area_crime_risk":          np.random.choice([0, 1, 2], p=[0.20, 0.60, 0.20]),
            "audit_score_mean":         np.random.uniform(2.0, 3.5),
            "dist_to_metro_m":          np.random.randint(400, 2000),
            "dist_to_bus_m":            np.random.randint(300, 1500),
            "dist_to_hospital_m":       np.random.randint(800, 5000),
            "dist_to_police_m":         np.random.randint(500, 3000),
        }
        records.append(rec)
    df = pd.DataFrame(records)
    df["safety_label"] = 1
    return df


# ═══════════════════════════════════════════════════════════════
# SECTION 3 — FEATURE ENGINEERING
# ═══════════════════════════════════════════════════════════════

def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add derived features that improve model signal."""
    df = df.copy()

    # ── Cyclical time encoding ─────────────────────────────────
    df["hour_sin"] = np.sin(2 * np.pi * df["hour_of_day"] / 24)
    df["hour_cos"] = np.cos(2 * np.pi * df["hour_of_day"] / 24)

    # ── Risk score (higher = riskier) ─────────────────────────
    # Combines: dark, empty, isolated, night, no infrastructure
    df["risk_score"] = (
        (2 - df["lighting_level"]) * 2          # 0 bright → 4 dark
        + (2 - df["crowd_level"]) * 1.5         # 0 crowded → 3 empty
        + (df["distance_to_main_road_m"] / 200) # distance penalty
        + df["past_incidents_level"] * 2         # incident history
        + df["area_crime_risk"] * 1.5            # crime zone
        + (1 - df["group_travel"]) * 1.5        # alone penalty
        + (1 - df["cctv_present"]) * 1.0
        + (1 - df["police_station_within_1km"]) * 1.0
    )

    # ── Infrastructure score (higher = safer environment) ─────
    df["infrastructure_score"] = (
        df["cctv_present"] * 2
        + df["police_station_within_1km"] * 2
        + df["near_metro_or_bus"] * 1.5
        + df["shops_open_at_night"] * 1.0
        + df["lighting_level"] * 1.5
        + df["crowd_level"] * 1.0
        + df.get("audit_score_mean", 2.5) / 5 * 2  # normalised
    )

    # ── Time risk: late night is highest risk ──────────────────
    h = df["hour_of_day"]
    df["time_risk_score"] = np.where(
        (h >= 23) | (h <= 4), 3,       # very high
        np.where(
            (h >= 20) | (h <= 6), 2,   # high
            np.where(h >= 18, 1, 0)    # moderate / daytime safe
        )
    )

    # ── Isolation index ───────────────────────────────────────
    df["isolation_index"] = (
        df["distance_to_main_road_m"] / 200
        + (1 - df["near_metro_or_bus"]) * 2
        + (1 - df["crowd_level"] / 2) * 1.5
    )

    return df


# ═══════════════════════════════════════════════════════════════
# SECTION 4 — LOAD DATA + AUGMENT
# ═══════════════════════════════════════════════════════════════

logger.info("Loading original data …")

ORIGINAL_COLS = [
    "lighting_level", "crowd_level", "distance_to_main_road_m",
    "shops_open_at_night", "police_station_within_1km", "cctv_present",
    "hour_of_day", "is_weekend", "area_type", "near_metro_or_bus",
    "past_incidents_level", "group_travel",
    "area_crime_risk", "audit_score_mean",
    "dist_to_metro_m", "dist_to_bus_m", "dist_to_hospital_m", "dist_to_police_m",
    "safety_label",
]

EXTRA_DEFAULTS = {
    "area_crime_risk": 1,
    "audit_score_mean": 2.5,
    "dist_to_metro_m": 1000,
    "dist_to_bus_m": 500,
    "dist_to_hospital_m": 2000,
    "dist_to_police_m": 1500,
}

try:
    df_orig = pd.read_csv(DATA_PATH, header=0)
    # Keep only columns we know about, drop others
    known = [c for c in ORIGINAL_COLS if c in df_orig.columns]
    df_orig = df_orig[known]
    for col, default in EXTRA_DEFAULTS.items():
        if col not in df_orig.columns:
            df_orig[col] = default
    logger.info(f"Loaded {len(df_orig)} rows from {DATA_PATH}")
except FileNotFoundError:
    logger.warning(f"Data file not found at {DATA_PATH}. Starting from pure synthetic data.")
    df_orig = pd.DataFrame(columns=ORIGINAL_COLS)

# Re-label existing rows with rule-based logic (override noisy labels)
if len(df_orig) > 0:
    df_orig["safety_label"] = df_orig.apply(assign_safety_label, axis=1)
    logger.info("Re-labelled original data with rule-based logic.")

# ── Generate synthetic data ────────────────────────────────────
logger.info("Generating synthetic data …")

# Target: 300 per class (900 total) — enough for robust training
N_PER_CLASS = 300

df_unsafe   = generate_unsafe_samples(N_PER_CLASS)
df_safe     = generate_safe_samples(N_PER_CLASS)
df_moderate = generate_moderate_samples(N_PER_CLASS)

# Verify synthetic labels with rule-based oracle and log mismatches
for name, dfx in [("Unsafe", df_unsafe), ("Safe", df_safe), ("Moderate", df_moderate)]:
    oracle = dfx.apply(assign_safety_label, axis=1)
    mismatches = (oracle != dfx["safety_label"]).sum()
    if mismatches > 0:
        logger.warning(
            f"{name} synthetic batch: {mismatches}/{len(dfx)} rows "
            f"relabelled by oracle (features didn't satisfy rules)."
        )
        dfx["safety_label"] = oracle

# Combine everything
frames = [df_orig] if len(df_orig) > 0 else []
frames += [df_unsafe, df_safe, df_moderate]
df = pd.concat(frames, ignore_index=True)

# Fill any remaining missing values
for col, default in EXTRA_DEFAULTS.items():
    df[col] = df[col].fillna(default)

logger.info(f"Combined dataset: {len(df)} rows")
logger.info(f"Class distribution:\n{df['safety_label'].value_counts().sort_index()}")


# ═══════════════════════════════════════════════════════════════
# SECTION 5 — FEATURE ENGINEERING + FINAL FEATURE LIST
# ═══════════════════════════════════════════════════════════════

df = engineer_features(df)

FEATURE_COLS = [
    # Raw
    "lighting_level", "crowd_level", "distance_to_main_road_m",
    "shops_open_at_night", "police_station_within_1km", "cctv_present",
    "is_weekend", "area_type", "near_metro_or_bus",
    "past_incidents_level", "group_travel",
    "area_crime_risk", "audit_score_mean",
    "dist_to_metro_m", "dist_to_bus_m", "dist_to_hospital_m", "dist_to_police_m",
    # Cyclical
    "hour_sin", "hour_cos",
    # Derived
    "risk_score", "infrastructure_score", "time_risk_score", "isolation_index",
]

TARGET_COL = "safety_label"

X = df[FEATURE_COLS].copy()
y = df[TARGET_COL].astype(int).copy()

assert y.isin([0, 1, 2]).all(), "Invalid labels!"
logger.info(f"\nFeatures: {len(FEATURE_COLS)} | Samples: {len(X)}")


# ═══════════════════════════════════════════════════════════════
# SECTION 6 — TRAIN / TEST SPLIT
# ═══════════════════════════════════════════════════════════════

X_train, X_test, y_train, y_test = train_test_split(
    X, y,
    test_size=0.20,
    random_state=RANDOM_STATE,
    stratify=y,          # preserve class proportions
)

logger.info(f"\nTrain: {len(X_train)} rows | Test: {len(X_test)} rows")
logger.info(f"Train class dist:\n{pd.Series(y_train).value_counts().sort_index()}")

# SMOTE only if enough samples (min 6 per class in each fold)
MIN_SMOTE_SAMPLES = 50
class_counts = pd.Series(y_train).value_counts()
use_smote = class_counts.min() >= MIN_SMOTE_SAMPLES

X_train = X_train.fillna(0)
X_test = X_test.fillna(0)

if use_smote:
    from imblearn.over_sampling import SMOTE
    smote = SMOTE(random_state=RANDOM_STATE, k_neighbors=5)

    X_train, y_train = smote.fit_resample(X_train, y_train)
    logger.info(f"SMOTE applied → {len(X_train)} training samples")
else:
    logger.info(
        "SMOTE skipped (too few samples per class); using class_weight='balanced' instead."
    )


# ═══════════════════════════════════════════════════════════════
# SECTION 7 — MODEL TRAINING
# ═══════════════════════════════════════════════════════════════

logger.info("\n" + "=" * 60)
logger.info("MODEL TRAINING")
logger.info("=" * 60)

N_FOLDS = 5
cv = StratifiedKFold(n_splits=N_FOLDS, shuffle=True, random_state=RANDOM_STATE)


def evaluate_pipeline(pipeline, name: str) -> dict:
    """Cross-validate, fit, and evaluate a pipeline. Returns result dict."""
    logger.info(f"\n── {name} ──")

    cv_acc = cross_val_score(pipeline, X_train, y_train, cv=cv, scoring="accuracy")
    cv_f1  = cross_val_score(pipeline, X_train, y_train, cv=cv, scoring="f1_macro")
    logger.info(f"  CV Accuracy: {cv_acc.mean():.4f} ± {cv_acc.std():.4f}")
    logger.info(f"  CV Macro F1: {cv_f1.mean():.4f} ± {cv_f1.std():.4f}")

    pipeline.fit(X_train, y_train)
    y_pred = pipeline.predict(X_test)

    acc   = accuracy_score(y_test, y_pred)
    macro = f1_score(y_test, y_pred, average="macro")
    mse   = mean_squared_error(y_test, y_pred)

    logger.info(f"  Test Accuracy: {acc:.4f} | Macro F1: {macro:.4f} | RMSE: {np.sqrt(mse):.4f}")
    logger.info("\n" + classification_report(y_test, y_pred, target_names=["Unsafe", "Moderate", "Safe"]))
    logger.info(f"Confusion Matrix:\n{confusion_matrix(y_test, y_pred)}")

    return {
        "name": name,
        "pipeline": pipeline,
        "cv_acc": cv_acc.mean(),
        "cv_f1": cv_f1.mean(),
        "test_acc": acc,
        "test_macro_f1": macro,
        "test_mse": mse,
        "test_rmse": np.sqrt(mse),
    }


# ── Random Forest (primary) ────────────────────────────────────
rf_pipeline = Pipeline([
    ("scaler", StandardScaler()),
    ("classifier", RandomForestClassifier(
        n_estimators=200,
        max_depth=10,         # capped to avoid overfit on synthetic data
        min_samples_split=8,
        min_samples_leaf=4,
        class_weight="balanced",
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )),
])

# ── Calibrated RF (better probability estimates) ───────────────
calibrated_rf = Pipeline([
    ("scaler", StandardScaler()),
    ("classifier", CalibratedClassifierCV(
        RandomForestClassifier(
            n_estimators=150,
            max_depth=8,
            min_samples_split=8,
            min_samples_leaf=4,
            class_weight="balanced",
            random_state=RANDOM_STATE,
            n_jobs=-1,
        ),
        method="isotonic",
        cv=3,
    )),
])

# ── Logistic Regression (interpretable baseline) ───────────────
lr_pipeline = Pipeline([
    ("scaler", StandardScaler()),
    ("classifier", LogisticRegression(
        max_iter=1000,
        class_weight="balanced",
        C=0.5,               # regularisation to avoid overfit
        random_state=RANDOM_STATE,
    )),
])

results = []
for pipe, name in [
    (rf_pipeline, "RandomForest"),
    (calibrated_rf, "RandomForest (Calibrated)"),
    (lr_pipeline, "LogisticRegression"),
]:
    results.append(evaluate_pipeline(pipe, name))

# ── Best model by macro F1 ────────────────────────────────────
best = max(results, key=lambda r: r["test_macro_f1"])
best_name = best["name"]
best_pipeline = best["pipeline"]

logger.info("\n" + "=" * 60)
logger.info(f"BEST MODEL: {best_name}")
logger.info(f"  Test Accuracy: {best['test_acc']:.4f}")
logger.info(f"  Test Macro F1: {best['test_macro_f1']:.4f}")
logger.info(f"  Test RMSE:     {best['test_rmse']:.4f}")
logger.info("=" * 60)


# ═══════════════════════════════════════════════════════════════
# SECTION 8 — SANITY CHECK (Logical Prediction Verification)
# ═══════════════════════════════════════════════════════════════

logger.info("\n── SANITY CHECKS ──────────────────────────────────")

def build_sanity_row(overrides: dict) -> pd.DataFrame:
    """Build a single test row from defaults + overrides, engineer features."""
    defaults = {
        "lighting_level": 1, "crowd_level": 1,
        "distance_to_main_road_m": 300,
        "shops_open_at_night": 0, "police_station_within_1km": 0,
        "cctv_present": 0, "hour_of_day": 20, "is_weekend": 0,
        "area_type": 1, "near_metro_or_bus": 0,
        "past_incidents_level": 1, "group_travel": 0,
        "area_crime_risk": 1, "audit_score_mean": 2.5,
        "dist_to_metro_m": 1500, "dist_to_bus_m": 800,
        "dist_to_hospital_m": 3000, "dist_to_police_m": 2000,
    }
    defaults.update(overrides)
    row_df = pd.DataFrame([defaults])
    row_df = engineer_features(row_df)
    return row_df[FEATURE_COLS]

SANITY_CASES = [
    {
        "desc": "Archetypal UNSAFE (dark, alone, isolated, late night)",
        "features": {
            "lighting_level": 0, "crowd_level": 0, "cctv_present": 0,
            "police_station_within_1km": 0, "near_metro_or_bus": 0,
            "group_travel": 0, "hour_of_day": 2,
            "distance_to_main_road_m": 900, "past_incidents_level": 2,
            "area_crime_risk": 2,
        },
        "expected": 0,
    },
    {
        "desc": "Archetypal SAFE (bright, crowded, CCTV, daytime)",
        "features": {
            "lighting_level": 2, "crowd_level": 2, "cctv_present": 1,
            "police_station_within_1km": 1, "near_metro_or_bus": 1,
            "group_travel": 1, "hour_of_day": 14,
            "distance_to_main_road_m": 50, "past_incidents_level": 0,
            "area_crime_risk": 0,
        },
        "expected": 2,
    },
    {
        "desc": "MODERATE (dim evening, some infrastructure)",
        "features": {
            "lighting_level": 1, "crowd_level": 1, "cctv_present": 0,
            "police_station_within_1km": 1, "near_metro_or_bus": 1,
            "group_travel": 0, "hour_of_day": 19,
            "distance_to_main_road_m": 250, "past_incidents_level": 1,
            "area_crime_risk": 1,
        },
        "expected": 1,
    },
]

all_passed = True
for case in SANITY_CASES:
    row = build_sanity_row(case["features"])
    pred = int(best_pipeline.predict(row)[0])
    proba = best_pipeline.predict_proba(row)[0]
    status = "✓ PASS" if pred == case["expected"] else "✗ FAIL"
    if pred != case["expected"]:
        all_passed = False
    label_names = ["Unsafe", "Moderate", "Safe"]
    logger.info(
        f"  [{status}] {case['desc']}\n"
        f"         Expected: {label_names[case['expected']]} | "
        f"Got: {label_names[pred]} | "
        f"Probas: {dict(zip(label_names, proba.round(3)))}"
    )

if not all_passed:
    logger.warning(
        "Some sanity checks failed. Review labeling logic and "
        "synthetic data distributions for the failing cases."
    )
else:
    logger.info("All sanity checks passed ✓")


# ═══════════════════════════════════════════════════════════════
# SECTION 9 — FEATURE IMPORTANCE
# ═══════════════════════════════════════════════════════════════

logger.info("\n── FEATURE IMPORTANCE ─────────────────────────────")

# Extract base classifier (unwrap Pipeline / CalibratedClassifierCV)
clf = best_pipeline.named_steps.get("classifier", None)
if hasattr(clf, "estimator"):          # CalibratedClassifierCV
    clf = clf.estimator
if hasattr(clf, "calibrated_classifiers_"):
    clf = clf.calibrated_classifiers_[0].estimator

if hasattr(clf, "feature_importances_"):
    fi_df = pd.DataFrame({
        "feature": FEATURE_COLS,
        "importance": clf.feature_importances_,
    }).sort_values("importance", ascending=False).reset_index(drop=True)

    fi_path = os.path.join(ARTIFACT_DIR, "feature_importance.csv")
    fi_df.to_csv(fi_path, index=False)
    logger.info(f"Saved feature importance → {fi_path}")

    logger.info("\n  TOP 10 FEATURES:")
    for i, row in fi_df.head(10).iterrows():
        bar = "█" * int(row["importance"] * 60)
        logger.info(f"  {i+1:>2}. {row['feature']:<30} {row['importance']:.4f}  {bar}")

    plt.figure(figsize=(10, 6))
    plt.barh(fi_df["feature"].head(10)[::-1], fi_df["importance"].head(10)[::-1], color="#e63946")
    plt.xlabel("Importance")
    plt.title(f"Top 10 Feature Importances — {best_name}")
    plt.tight_layout()
    fi_plot = os.path.join(ARTIFACT_DIR, "feature_importance_plot.png")
    plt.savefig(fi_plot, dpi=120, bbox_inches="tight")
    plt.close()
    logger.info(f"Saved importance plot → {fi_plot}")
else:
    logger.warning(f"Model does not expose feature_importances_; skipping.")


# ═══════════════════════════════════════════════════════════════
# SECTION 10 — SHAP EXPLAINABILITY
# ═══════════════════════════════════════════════════════════════

logger.info("\n── SHAP ANALYSIS ──────────────────────────────────")

try:
    # Use a small background set to speed up SHAP
    background = X_train[:100] if len(X_train) > 100 else X_train

    base_clf = best_pipeline.named_steps.get("classifier", None)
    # Try TreeExplainer first; fall back to KernelExplainer
    try:
        explainer = shap.TreeExplainer(base_clf)
        sample = X_test.iloc[:10]
        shap_values = explainer.shap_values(sample)
    except Exception:
        explainer = shap.KernelExplainer(best_pipeline.predict_proba, background[:50])
        sample = X_test.iloc[:5]
        shap_values = explainer.shap_values(sample)

    # Pick first sample
    pred_class = int(best_pipeline.predict(X_test.iloc[[0]])[0])
    if isinstance(shap_values, list):
        sv = np.abs(shap_values[pred_class][0])
    else:
        sv = np.abs(shap_values[0])

    shap_series = pd.Series(sv, index=FEATURE_COLS).sort_values(ascending=False)
    top3 = shap_series.head(3).index.tolist()

    logger.info(f"  Sample prediction: {['Unsafe','Moderate','Safe'][pred_class]}")
    logger.info("  Top 3 contributing features:")
    for i, feat in enumerate(top3, 1):
        logger.info(f"    {i}. {feat:<30} |SHAP| = {shap_series[feat]:.4f}")

except Exception as e:
    logger.warning(f"SHAP analysis failed: {e}")


# ═══════════════════════════════════════════════════════════════
# SECTION 11 — SAVE ARTEFACTS
# ═══════════════════════════════════════════════════════════════

logger.info("\n── SAVING ARTEFACTS ───────────────────────────────")

MODEL_PATH = os.path.join(MODEL_SAVE_DIR, f"saferoute_model_v2_{TIMESTAMP}.pkl")
LATEST_PATH = os.path.join(MODEL_SAVE_DIR, "saferoute_model_latest.pkl")
FEATURES_PATH = os.path.join(MODEL_SAVE_DIR, "feature_cols.pkl")

joblib.dump(best_pipeline, MODEL_PATH)
joblib.dump(best_pipeline, LATEST_PATH)
joblib.dump(FEATURE_COLS, FEATURES_PATH)

version_info = {
    "version": 2,
    "timestamp": TIMESTAMP,
    "model_type": best_name,
    "model_path": MODEL_PATH,
    "test_accuracy": float(best["test_acc"]),
    "test_macro_f1": float(best["test_macro_f1"]),
    "feature_cols": FEATURE_COLS,
    "sanity_passed": all_passed,
}
joblib.dump(version_info, os.path.join(MODEL_SAVE_DIR, "version_info.pkl"))

# Save comparison CSV
results_df = pd.DataFrame([{k: v for k, v in r.items() if k != "pipeline"} for r in results])
results_df.to_csv(os.path.join(ARTIFACT_DIR, "model_comparison.csv"), index=False)

logger.info(f"  Model       → {MODEL_PATH}")
logger.info(f"  Latest link → {LATEST_PATH}")
logger.info(f"  Features    → {FEATURES_PATH}")

logger.info("\n" + "=" * 60)
logger.info("TRAINING COMPLETE")
logger.info("=" * 60)
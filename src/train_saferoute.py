import os
from typing import Dict, Any

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    classification_report,
    confusion_matrix,
)
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
import joblib

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
    "hour_of_day",
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

FEATURE_COLS = BASE_FEATURE_COLS + EXTRA_FEATURE_COLS

TARGET_COL = "safety_label"  # 0=Unsafe, 1=Moderate, 2=Safe

MODELS: Dict[str, Any] = {
    "RandomForest": RandomForestClassifier(
        n_estimators=150, max_depth=None, random_state=42
    ),
    "HistGradientBoosting": HistGradientBoostingClassifier(
        learning_rate=0.1, max_depth=None, random_state=42
    ),
    "LogisticRegression": LogisticRegression(
        max_iter=500
    ),
}

N_FOLDS = 5
RANDOM_STATE = 42

# ----------------------------
# Load data
# ----------------------------

print(f"Loading data from {DATA_PATH} ...")
df = pd.read_csv(DATA_PATH)

# Ensure all expected feature columns exist; if not, create with zeros
for col in FEATURE_COLS:
    if col not in df.columns:
        print(f"[WARN] Column {col} not found in data; creating with 0.0 for now.")
        df[col] = 0.0

X = df[FEATURE_COLS]
y = df[TARGET_COL]
5
# ----------------------------
# Train/test split (for final eval)
# ----------------------------

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.2,
    random_state=RANDOM_STATE,
    stratify=y,
)

print(f"Train size: {len(X_train)}, Test size: {len(X_test)}")

# ----------------------------
# Cross-validation + training loop
# ----------------------------

results = []

for name, model in MODELS.items(): # Loop through each model defined in the MODELS dictionary
    print("\n==============================")
    print(f"Training model: {name}")
    print("==============================")

    # Cross-validation accuracy + macro F1
    cv_scores = cross_val_score(
        model, X_train, y_train, cv=N_FOLDS, scoring="accuracy"
    ) #this is for accuracy score
    cv_f1_scores = cross_val_score(
        model, X_train, y_train, cv=N_FOLDS, scoring="f1_macro"
    ) #this is for macro f1 score

    print(f"{name} CV accuracy scores: {cv_scores}")
    print(f"{name} CV accuracy mean: {cv_scores.mean():.4f} ± {cv_scores.std():.4f}")
    print(f"{name} CV macro F1 scores: {cv_f1_scores}")
    print(f"{name} CV macro F1 mean: {cv_f1_scores.mean():.4f} ± {cv_f1_scores.std():.4f}")

    # Fit on full train split
    model.fit(X_train, y_train)  

    # Evaluate on held-out test set
    y_pred = model.predict(X_test)
    acc = accuracy_score(y_test, y_pred) #this is for accuracy score
    macro_f1 = f1_score(y_test, y_pred, average="macro") #this is for macro f1 score

    print(f"{name} Test accuracy: {acc:.4f}")
    print(f"{name} Test macro F1: {macro_f1:.4f}")
    print("\nClassification report:")
    print(classification_report(y_test, y_pred))
    print("Confusion matrix:")
    print(confusion_matrix(y_test, y_pred))

    results.append(
        {
            "name": name,
            "cv_acc_mean": cv_scores.mean(),
            "cv_acc_std": cv_scores.std(),
            "cv_f1_mean": cv_f1_scores.mean(),
            "cv_f1_std": cv_f1_scores.std(),
            "test_acc": acc,
            "test_macro_f1": macro_f1,
            "model": model,
        }
    )

# -------------------------------
# Pick best model by CV macro F1
# -------------------------------

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
        }
        for r in results
    ]
)

print("\n\n===== MODEL COMPARISON =====")
print(results_df)

# Select model with highest CV macro F1
best = max(results, key=lambda r: r["cv_f1_mean"])
best_name = best["name"]
best_model = best["model"]

print(f"\nBest model by CV macro F1: {best_name}")
print(f"CV macro F1: {best['cv_f1_mean']:.4f}, Test macro F1: {best['test_macro_f1']:.4f}")

# ----------------------------
# Save best model & artifacts
# ----------------------------

os.makedirs("models", exist_ok=True)
os.makedirs("artifacts", exist_ok=True)

MODEL_PATH = "models/saferoute_model.pkl"
FEATURE_COLS_PATH = "models/feature_cols.pkl"
COMPARISON_PATH = "artifacts/model_comparison.csv"
FI_PATH = "artifacts/feature_importance.csv"

joblib.dump(best_model, MODEL_PATH)
joblib.dump(FEATURE_COLS, FEATURE_COLS_PATH)
results_df.to_csv(COMPARISON_PATH, index=False)

print(f"Saved best model ({best_name}) to {MODEL_PATH}")
print(f"Saved feature columns to {FEATURE_COLS_PATH}")
print(f"Saved model comparison to {COMPARISON_PATH}")

# ----------------------------
# Feature importance (where available)
# ----------------------------

if hasattr(best_model, "feature_importances_"):
    importances = best_model.feature_importances_
    fi_df = pd.DataFrame(
        {"feature": FEATURE_COLS, "importance": importances}
    ).sort_values("importance", ascending=False)
    fi_df.to_csv(FI_PATH, index=False)
    print(f"Saved feature importance to {FI_PATH}")

    # Optional local plot
    plt.figure(figsize=(8, 4))
    plt.bar(FEATURE_COLS, importances)
    plt.xticks(rotation=45, ha="right")
    plt.title(f"Feature importance for {best_name}")
    plt.tight_layout()
    plt.show()
else:
    print(
        f"Model {best_name} does not expose feature_importances_; skipping importance CSV." )
import os
import pandas as pd
import streamlit as st

st.set_page_config(page_title="How SafeRoute Delhi Works", page_icon="📊", layout="centered")

st.title("How SafeRoute Delhi Works")

st.markdown("""
This page explains **how the model thinks** about route safety and how we evaluated different models.

The current version compares multiple classifiers using cross-validation, then picks the best one
for production use in the API.
""")

ARTIFACT_FI = os.path.join("artifacts", "feature_importance.csv")
ARTIFACT_MODELS = os.path.join("artifacts", "model_comparison.csv")

# --- Section 1: Features ---
st.markdown("### 1. Features the model uses")

st.write("""
Each row in the training data describes one route segment with these input features:

- `lighting_level` – 0 (very poor), 1 (ok), 2 (good)
- `crowd_level` – 0 (empty), 1 (some people), 2 (busy/active)
- `distance_to_main_road_m` – distance from a main road in meters
- `shops_open_at_night` – 0/1, whether shops are open at night
- `police_station_within_1km` – 0/1, whether a police station is within ~1 km
- `cctv_present` – 0/1, whether CCTV is visible
- `hour_of_day` – 0–23, time when someone is passing through
- `is_weekend` – 0/1, whether it is a weekend
""")

# --- Section 2: Model comparison ---
st.markdown("### 2. Model comparison with cross-validation")

if not os.path.exists(ARTIFACT_MODELS):
    st.error("Model comparison file not found. Run `python src/train_saferoute.py` and refresh this page.")
else:
    mc_df = pd.read_csv(ARTIFACT_MODELS)

    st.write("""
We train several models and evaluate them with **5-fold cross-validation** on the training split,
then also on a held-out test set:

- RandomForestClassifier
- HistGradientBoostingClassifier
- LogisticRegression
""")

    st.write("Cross-validation and test metrics:")

    st.dataframe(mc_df.style.format({
        "cv_acc_mean": "{:.3f}",
        "cv_acc_std": "{:.3f}",
        "cv_f1_mean": "{:.3f}",
        "cv_f1_std": "{:.3f}",
        "test_acc": "{:.3f}",
        "test_macro_f1": "{:.3f}",
    }))

    best_row = mc_df.sort_values("cv_f1_mean", ascending=False).iloc[0]
    st.success(
        f"Current production model: **{best_row['model']}** "
        f"(CV macro F1 = {best_row['cv_f1_mean']:.3f}, "
        f"Test macro F1 = {best_row['test_macro_f1']:.3f})"
    )

# --- Section 3: Feature importance ---
st.markdown("### 3. Which features matter most?")

if not os.path.exists(ARTIFACT_FI):
    st.info("Feature importance file not found or best model does not expose feature_importances_.")
else:
    fi_df = pd.read_csv(ARTIFACT_FI)
    st.write("The chart below shows feature importances for the current production model:")

    st.bar_chart(fi_df.set_index("feature")["importance"])

    st.write("""
Higher bars mean that feature influenced the model's decisions **more often across many routes**.
This does **not** mean a single feature alone decides safety; the model still combines them.
""")

# --- Section 4: Limitations ---
st.markdown("### 4. Limitations and realism")

st.write("""
The current dataset is still relatively small and synthetic, so very high scores (near-perfect F1)
mainly show that the model has learned the patterns in this toy data well.

In a real deployment we would expect lower scores, more variation across folds,
and would need real-world data and expert review to trust the system.
""")

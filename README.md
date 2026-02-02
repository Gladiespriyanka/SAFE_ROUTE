
# SafeRoute Delhi – Women-centric Route & Area Safety Scorer

## Problem

Women in cities like Delhi often have to choose between a faster route and a route that *feels* safer at night. Traditional map apps optimize for travel time, not lighting, crowd presence, or nearby safety infrastructure.

SafeRoute Delhi focuses on **perceived safety** of places and short route segments, so someone can quickly answer:  
> “Does this way home feel safe enough right now?”

---

## What this project does

SafeRoute Delhi is a mini end‑to‑end ML system:

- **Models perceived safety** of a location / route segment using features such as:
  - Lighting level
  - Crowd level
  - Distance to main road
  - Shops open at night
  - Nearby police station
  - CCTV presence
  - Time of day and weekend vs weekday
  - Area type (residential / market / office)
  - Near metro or major bus stop
  - Past incidents level (coarse)
  - Walking alone vs in a group

- **Trains and compares multiple models** (RandomForest, HistGradientBoosting, LogisticRegression) with cross‑validation, then automatically picks the best model for production.

- **Exposes a FastAPI backend** that serves the safety model over `/predict` with:
  - Safety label: **Unsafe / Moderate / Safe**
  - Class probabilities for each label
  - A confidence score (max class probability)
  - Grouped natural‑language reasons (“Why this prediction?”)
  - A `/feedback` endpoint to log whether users agree with the prediction.

- **Provides a Streamlit frontend** with multiple pages:
  - **Home** (`app.py`):  
    - Input the current conditions (lighting, crowd, time, area context).  
    - Get a safety label, probabilities, and expandable “Why this prediction?” reasons.  
    - Give quick feedback (Agree / Not accurate) with optional comments.
  - **How it works** (`pages/1_How_it_works.py`):  
    - Explains features and model pipeline.  
    - Shows model comparison metrics (CV + test) from `artifacts/model_comparison.csv`.  
    - Shows feature importance for the selected model from `artifacts/feature_importance.csv`.
  - **About & Limitations** (`pages/2_About_and_Limitations.py`):  
    - Describes the motivation, ethical considerations, and limitations (no real crime data yet, synthetic/hand‑crafted dataset, not a replacement for police/emergency services).
  - **Route insights & feedback analytics** (`pages/3_Route_Insights.py`):  
    - Simple analytics over logged predictions and feedback (from `logs/predictions.csv` and `/feedback/summary`).  
    - Helps understand how often users agree with the model and which contexts are most common.
  - **Route safety map** (`pages/4_Route_safety_map.py`):  
    - Enter start and end coordinates (lat / lon).  
    - Sample points along the straight line between them.  
    - Call `/predict` for each sampled point (using the same context) and aggregate labels.  
    - Draw a route on a Folium map and color it **green / orange / red** based on overall safety.
    - Gives a quick visual sense of how “safe” a route feels under chosen conditions.

- **Includes a local SOS helper** on the Home page:
  - “🚨 Generate SOS summary” builds a short text with current conditions (lighting, crowd, time, area type, etc.) that you can copy‑paste to a trusted contact.
  - Provides a quick link to open WhatsApp and a reminder to call emergency services (e.g., 112 in India).  
  - This is a **support tool**, not a replacement for official emergency apps.

---

## Tech stack

**ML & data**

- Python
- Pandas, NumPy
- Scikit‑learn (RandomForest, HistGradientBoosting, LogisticRegression, cross‑validation, classification metrics)
- Joblib (model + feature list persistence)
- Matplotlib (local feature importance plots)

**Backend**

- FastAPI (REST API)
- Uvicorn (ASGI server)
- Pydantic (request/response schemas)

**Frontend**

- Streamlit (multi‑page app)
- Folium + `streamlit-folium` (route safety map)
- PyDeck (optional for map/visual experiments)

**Project structure**

- `data/`
  - `saferoute_delhi.csv` – training data with 12+ features and `safety_label`.
- `src/`
  - `train_saferoute.py` – multi‑model training + cross‑val, saves best model & artifacts.
  - `predict_utils.py` – model loading, input sanitization, prediction logic, grouped reasons.
- `backend/`
  - `app.py` – FastAPI app with:
    - `/` root
    - `/health` – simple health/metadata
    - `/predict` – model inference
    - `/feedback` + `/feedback/summary` – user feedback collection and summary.
- `models/`
  - `saferoute_model.pkl` – best model (currently RandomForest).
  - `feature_cols.pkl` – ordered feature column names.
- `artifacts/`
  - `feature_importance.csv` – feature importance for the selected model (if supported).
  - `model_comparison.csv` – CV + test metrics for each candidate model.
- `logs/`
  - `predictions.csv` – log of Streamlit predictions (inputs, label, probs, confidence).
- `pages/`
  - `1_How_it_works.py`
  - `2_About_and_Limitations.py`
  - `3_Route_Insights.py`
  - `4_Route_safety_map.py`
- `app.py` – Streamlit main app (Home + SOS).
- `requirements.txt` – shared dependencies for backend + frontend.
- `README.md` – this file.

---

## How to run locally

### 1. Create and activate virtualenv (Windows)

```bash
cd saferoute-delhi-ml

python -m venv venv
.\venv\Scripts\activate

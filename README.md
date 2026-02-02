# SafeRoute Delhi – Women-centric Route & Area Safety Scorer

## Problem

Women in cities like Delhi often have to choose between a faster route and a route that *feels* safer at night. Existing map apps optimize for travel time, not lighting, crowd presence, or nearby safety infrastructure.

## What this project does

- Models perceived safety of a location/route segment using features such as lighting level, crowd level, distance to main road, shops open at night, nearby police stations, and CCTV presence.
- Trains a Random Forest classifier to predict safety as **Unsafe / Moderate / Safe**.
- Provides:
  - A training pipeline (`src/train_saferoute.py`) with evaluation metrics and feature importance plots.
  - A CLI demo (`src/predict_cli.py`) to test the model from the terminal.
  - An interactive Streamlit app (`app.py`) where users can adjust conditions and see safety predictions instantly.

## Tech stack

- Python, Pandas, NumPy, Scikit-learn, Matplotlib, Joblib, Streamlit
- Project structure:
  - `data/` – tabular dataset (`saferoute_delhi.csv`)
  - `src/train_saferoute.py` – training + evaluation + model saving
  - `src/predict_cli.py` – command-line prediction demo
  - `models/` – saved model (`saferoute_model.pkl`) and feature list
  - `app.py` – Streamlit web UI
  - `requirements.txt` – dependencies

## How to run

```bash
# create and activate venv (Windows)
python -m venv venv
.\venv\Scripts\activate

pip install -r requirements.txt

# train model
python src/train_saferoute.py

# run CLI demo
python src/predict_cli.py

# run web app
streamlit run app.py

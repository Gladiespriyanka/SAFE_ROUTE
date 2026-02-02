import streamlit as st

st.set_page_config(page_title="About SafeRoute Delhi", page_icon="ℹ️", layout="centered")

st.title("About SafeRoute Delhi")

st.markdown("""
SafeRoute Delhi is a **women-centric route safety scorer**.

The goal is to estimate whether a short route segment feels **Unsafe, Moderate, or Safe**
based on factors like lighting, crowd, distance to main roads, nearby public infrastructure,
and time of day.
""")

st.markdown("### Why this project?")

st.write("""
Many map apps optimize for *fastest* or *shortest* route, not how it feels to walk there at night.
For women and other vulnerable groups, perceived safety (lighting, crowd, visibility, help nearby)
can matter more than saving 3–4 minutes.

This project demonstrates how we can turn that intuition into a small, explainable ML system.
""")

st.markdown("### What the system does today")

st.write("""
- Lets a user describe a route segment: lighting, crowd, distance to main road, shops, police, CCTV, time.
- Uses a Random Forest model to classify: 0 = Unsafe, 1 = Moderate, 2 = Safe.
- Returns:
  - A safety label and class probabilities.
  - Explanation bullets (lighting, crowd, distance, time, etc.) for *why* it predicted that way.
- Exposes a FastAPI backend (`/predict`) and a Streamlit frontend that calls the API.
""")

st.markdown("### What this project is **not**")

st.error("""
This is **not** a guarantee of safety.

It is a prototype built on synthetic data and simplified assumptions.
Real-world safety is influenced by many more factors (local incidents, social context, real-time events).
""")

st.markdown("### Data and realism")

st.write("""
- Training data is synthetic and designed to resemble Delhi-like conditions.
- It captures broad patterns (e.g., well-lit, busy, near main road tends to be safer).
- It does **not** use real crime reports or live map data.
- In a real deployment, we would need:
  - Historical incident data.
  - Local expert feedback (e.g., NGOs, safety cells).
  - Continuous evaluation and updates.
""")

st.markdown("### Ethical considerations")

st.write("""
Any safety scoring system can have side effects:

- **Stigma / bias**: Over-penalizing certain neighborhoods can reinforce stigma.
- **Over-trust**: Users might treat scores as absolute truth.
- **Data gaps**: Areas with less data might be misclassified.

To mitigate this, the project:
- Emphasizes that scores are *advisory*, not absolute.
- Surfaces explanations so users see *why* a route was scored that way.
- Documents limitations openly instead of hiding them.
""")

st.markdown("### Future directions")

st.write("""
Possible next steps:

- Ingest real data sources (where available) with proper anonymization and consent.
- Add feedback: let users flag whether a prediction felt accurate.
- Integrate with a routing engine to suggest safer alternative paths, not just scores.
- Collaborate with local organizations to validate and refine the model.
""")

st.success("This page exists so recruiters and reviewers see that the project is thoughtful, not just a raw model.")

import os
from datetime import datetime

import pandas as pd
import streamlit as st

LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "predictions.csv")

st.set_page_config(page_title="Route Insights", page_icon="📈", layout="centered")

st.title("Route Insights")

st.write("""
This page summarizes the routes that have been scored so far.
It’s mainly for analysis and for showing that the system is instrumented, not a black box.
""")

if not os.path.exists(LOG_FILE):
    st.info("No predictions logged yet. Use the main page to score some routes first.")
else:
    df = pd.read_csv(LOG_FILE)

    st.markdown("### 1. Basic counts")

    total = len(df)
    st.write(f"Total predictions logged: **{total}**")

    label_counts = df["predicted_label_text"].value_counts().rename_axis("label").reset_index(name="count")
    st.write("Predictions by label:")
    st.dataframe(label_counts)

    st.markdown("### 2. Time of day patterns")

    df["hour_bucket"] = df["hour_of_day"].apply(
        lambda h: "Late night (22–5)" if (h >= 22 or h <= 5)
        else ("Evening (18–21)" if 18 <= h <= 21 else "Daytime (6–17)")
    )
    bucket_counts = df["hour_bucket"].value_counts().rename_axis("time_of_day").reset_index(name="count")

    st.write("Predictions by time of day bucket:")
    st.dataframe(bucket_counts)

    st.bar_chart(
        bucket_counts.set_index("time_of_day")["count"]
    )

    st.markdown("### 3. Weekend vs weekday")

    df["is_weekend_text"] = df["is_weekend"].map({0: "Weekday", 1: "Weekend"})
    weekend_counts = df["is_weekend_text"].value_counts().rename_axis("day_type").reset_index(name="count")

    st.write("Predictions by day type:")
    st.dataframe(weekend_counts)

    st.markdown("### 4. Raw log (for debugging)")

    with st.expander("Show raw logged data"):
        st.dataframe(df)

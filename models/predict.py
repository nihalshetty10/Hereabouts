"""
vybe/models/predict.py
----------------------
Assemble model_table_final from model_table + trained model outputs.
This is what gets exported to CSV and loaded by the recommender.
"""

import pandas as pd


FINAL_COLS = [
    "ntaname", "prediction_time", "latitude", "longitude",
    "prob_active_noise_next_2h", "prob_active_complaints_next_2h",
    "prob_high_traffic_volume_next_2h",
    "prob_active_subway_ridership_next_2h",
    "prob_active_subway_transfers_next_2h",
    "crime_last_7d", "crashes_last_7d",
    "persons_injured_last_7d", "pedestrians_injured_last_7d",
    "cyclists_injured_last_7d",
    "noise_last_24h", "complaints_last_24h",
    "subway_ridership_last_24h", "traffic_volume_last_24h",
    "temp_f", "precip_prob", "wind_mph", "weather_main",
    "bluesky_negative_signal",
    "hour", "day_of_week", "is_weekend"
]


def build_model_table_final(
    model_table: pd.DataFrame,
    model_table_subway: pd.DataFrame,
    model_table_traffic: pd.DataFrame,
    weather_table: pd.DataFrame,
    nta_centroids: pd.DataFrame
) -> pd.DataFrame:
    """
    Assemble the final 243-row prediction table.

    Args:
        model_table:         base table with noise/complaint probs already added
        model_table_subway:  historical subway table with prob columns
        model_table_traffic: historical traffic table with prob column
        weather_table:       one row per NTA with raw weather fields
        nta_centroids:       NTA centroids with [ntaname, latitude, longitude]

    Returns:
        model_table_final: 243 rows ready for the recommender
    """
    # pull only prob columns from subway/traffic (no prediction_time merge)
    subway_probs = (
        model_table_subway[[
            "ntaname",
            "prob_active_subway_ridership_next_2h",
            "prob_active_subway_transfers_next_2h"
        ]]
        .drop_duplicates("ntaname")
    )

    traffic_probs = (
        model_table_traffic[["ntaname", "prob_high_traffic_volume_next_2h"]]
        .drop_duplicates("ntaname")
    )

    df = model_table.copy()
    df = df.merge(subway_probs,  on="ntaname", how="left")
    df = df.merge(traffic_probs, on="ntaname", how="left")
    df = df.merge(weather_table, on="ntaname", how="left")
    df = df.merge(nta_centroids[["ntaname", "latitude", "longitude"]], on="ntaname", how="left")

    # placeholder — Bluesky signals added in recommender sprint
    df["bluesky_negative_signal"] = 0

    df = df.fillna(0)

    # keep only final columns that exist
    keep = [c for c in FINAL_COLS if c in df.columns]
    df = df[keep]

    print(f"model_table_final: {df.shape}")
    return df

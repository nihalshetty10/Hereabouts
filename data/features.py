import pandas as pd
from datetime import datetime


def build_model_table(gdf_311: pd.DataFrame) -> pd.DataFrame:
    """
    Initialize model_table with 243 NTA rows and prediction_time = now.
    """
    prediction_time = datetime.now().replace(minute=0, second=0, microsecond=0)
    all_neighborhoods = gdf_311["ntaname"].dropna().unique()

    model_table = pd.DataFrame({
        "ntaname":         all_neighborhoods,
        "prediction_time": prediction_time,
        "hour":            prediction_time.hour,
        "day_of_week":     prediction_time.weekday(),
        "is_weekend":      int(prediction_time.weekday() >= 5)
    }).sort_values("ntaname").reset_index(drop=True)

    return model_table


def add_noise_features(model_table: pd.DataFrame, noise_events: pd.DataFrame) -> pd.DataFrame:
    if "noise_last_24h" in model_table.columns:
        model_table = model_table.drop(columns=["noise_last_24h"])

    noise_events = noise_events.copy()
    noise_events["created_date"] = pd.to_datetime(noise_events["created_date"], errors="coerce")
    noise_events = noise_events.dropna(subset=["created_date", "ntaname"])
    noise_events["ntaname"] = noise_events["ntaname"].str.strip()

    cutoff = noise_events["created_date"].max() - pd.Timedelta(hours=24)
    agg = (
        noise_events[noise_events["created_date"] >= cutoff]
        .groupby("ntaname").size()
        .reset_index(name="noise_last_24h")
    )
    model_table = model_table.merge(agg, on="ntaname", how="left")
    model_table["noise_last_24h"] = model_table["noise_last_24h"].fillna(0)
    return model_table


def add_complaint_features(model_table: pd.DataFrame, complaint_events: pd.DataFrame) -> pd.DataFrame:
    if "complaints_last_24h" in model_table.columns:
        model_table = model_table.drop(columns=["complaints_last_24h"])

    complaint_events = complaint_events.copy()
    complaint_events["created_date"] = pd.to_datetime(complaint_events["created_date"], errors="coerce")
    complaint_events = complaint_events.dropna(subset=["created_date", "ntaname"])
    complaint_events["ntaname"] = complaint_events["ntaname"].str.strip()

    cutoff = complaint_events["created_date"].max() - pd.Timedelta(hours=24)
    agg = (
        complaint_events[complaint_events["created_date"] >= cutoff]
        .groupby("ntaname").size()
        .reset_index(name="complaints_last_24h")
    )
    model_table = model_table.merge(agg, on="ntaname", how="left")
    model_table["complaints_last_24h"] = model_table["complaints_last_24h"].fillna(0)
    return model_table


def add_crime_features(model_table: pd.DataFrame, crime_events: pd.DataFrame) -> pd.DataFrame:
    for col in ["crime_last_7d"]:
        if col in model_table.columns:
            model_table = model_table.drop(columns=[col])

    crime_events = crime_events.copy()
    crime_events["cmplnt_fr_dt"] = pd.to_datetime(crime_events["cmplnt_fr_dt"], errors="coerce")
    crime_events = crime_events.dropna(subset=["cmplnt_fr_dt", "ntaname"])
    crime_events["ntaname"] = crime_events["ntaname"].str.strip()

    cutoff = crime_events["cmplnt_fr_dt"].max() - pd.Timedelta(days=7)
    agg = (
        crime_events[crime_events["cmplnt_fr_dt"] >= cutoff]
        .groupby("ntaname").size()
        .reset_index(name="crime_last_7d")
    )
    model_table = model_table.merge(agg, on="ntaname", how="left")
    model_table["crime_last_7d"] = model_table["crime_last_7d"].fillna(0)
    return model_table


def add_crash_features(model_table: pd.DataFrame, crash_events: pd.DataFrame) -> pd.DataFrame:
    drop_cols = ["crashes_last_7d", "persons_injured_last_7d",
                 "pedestrians_injured_last_7d", "cyclists_injured_last_7d"]
    model_table = model_table.drop(columns=[c for c in drop_cols if c in model_table.columns])

    crash_events = crash_events.copy()
    crash_events["crash_datetime"] = pd.to_datetime(crash_events["crash_datetime"], errors="coerce")
    crash_events = crash_events.dropna(subset=["crash_datetime", "ntaname"])
    crash_events["ntaname"] = crash_events["ntaname"].str.strip()

    cutoff = crash_events["crash_datetime"].max() - pd.Timedelta(days=7)
    recent = crash_events[crash_events["crash_datetime"] >= cutoff]

    agg = recent.groupby("ntaname").agg(
        crashes_last_7d=("collision_id", "count"),
        persons_injured_last_7d=("number_of_persons_injured", "sum"),
        pedestrians_injured_last_7d=("number_of_pedestrians_injured", "sum"),
        cyclists_injured_last_7d=("number_of_cyclist_injured", "sum")
    ).reset_index()

    model_table = model_table.merge(agg, on="ntaname", how="left")
    for col in ["crashes_last_7d", "persons_injured_last_7d",
                "pedestrians_injured_last_7d", "cyclists_injured_last_7d"]:
        model_table[col] = model_table[col].fillna(0)
    return model_table


def add_subway_features(model_table: pd.DataFrame, model_table_subway: pd.DataFrame) -> pd.DataFrame:
    drop_cols = ["subway_ridership_last_24h", "subway_transfers_last_24h"]
    model_table = model_table.drop(columns=[c for c in drop_cols if c in model_table.columns])

    subway_now = (
        model_table_subway
        .sort_values("prediction_time")
        .groupby("ntaname")
        .agg(
            subway_ridership_last_24h=("subway_ridership_last_24h", "last"),
            subway_transfers_last_24h=("subway_transfers_last_24h", "last")
        )
        .reset_index()
    )
    model_table = model_table.merge(subway_now, on="ntaname", how="left")
    model_table[["subway_ridership_last_24h", "subway_transfers_last_24h"]] = (
        model_table[["subway_ridership_last_24h", "subway_transfers_last_24h"]].fillna(0)
    )
    return model_table


def add_traffic_features(model_table: pd.DataFrame, model_table_traffic: pd.DataFrame) -> pd.DataFrame:
    if "traffic_volume_last_24h" in model_table.columns:
        model_table = model_table.drop(columns=["traffic_volume_last_24h"])

    traffic_now = (
        model_table_traffic
        .sort_values("prediction_time")
        .groupby("ntaname")
        .agg(traffic_volume_last_24h=("traffic_volume_last_24h", "last"))
        .reset_index()
    )
    model_table = model_table.merge(traffic_now, on="ntaname", how="left")
    model_table["traffic_volume_last_24h"] = model_table["traffic_volume_last_24h"].fillna(0)
    return model_table


def add_weather_features(model_table: pd.DataFrame, weather_table: pd.DataFrame) -> pd.DataFrame:
    drop_cols = ["temp_f", "feels_like_f", "humidity", "wind_mph",
                 "precip_prob", "rain_3h", "snow_3h", "weather_main", "weather_description"]
    model_table = model_table.drop(columns=[c for c in drop_cols if c in model_table.columns])
    model_table = model_table.merge(weather_table, on="ntaname", how="left")
    return model_table

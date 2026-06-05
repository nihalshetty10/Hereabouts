import os
import time
import requests
import pandas as pd
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()
TICKETMASTER_API_KEY = os.getenv("TICKETMASTER_API_KEY")
BASE_URL = "https://app.ticketmaster.com/discovery/v2/events.json"

def get_events_near(lat:float, lon:float, radius_miles: int =1) -> list:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    params = {
        "apikey": TICKETMASTER_API_KEY,
        "latlong": f"{lat},{lon}",
        "radius": str(radius_miles),
        "unit": "miles",
        "startDateTime": now,
        "size": 10,
        "sort": "date,asc"
    }

    try: 
        r= requests.get(BASE_URL, params= params, timeout=10)
        r.raise_for_status()
        data = r.json()
        events = data.get("_embedded", {}).get("events", [])
        results = []
        for event in events:
            venue = event.get("_embedded", {}).get("venues", [{}])[0]
            classification = event.get("classifications", [{}])[0]
            results.append({
                "event_name": event.get("name", ""),
                "event_type": classification.get("segment", {}).get("name",""),
                "event_genre": classification.get("genre", {}).get("name",""),
                "event_date": event.get("dates", {}).get("start", {}).get("dateTime", ""),
                "venue_name": venue.get("name", ""),
                "event_url": event.get("url", "")
            })

        return results

    except Exception as e:
        print(f"Error getting events near {lat},{lon}: {e}")
        return []

def pull_ticketmaster_events(model_table_path: str="model_table_final.csv", radius_miles: int =1) -> pd.DataFrame:
    df = pd.read_csv(model_table_path)
    if "latitude" not in df.columns or "longitude" not in df.columns:
        raise ValueError("model_table_final.csv must contain latitude and longitude columns")

    nta_points = df[["ntaname", "latitude", "longitude"]].drop_duplicates("ntaname")
    
    all_rows = []
    for i, row in nta_points.iterrows():
        events = get_events_near(row["latitude"], row["longitude"], radius_miles)
        if events:
            for event in events:
                event["ntaname"] = row["ntaname"]
                all_rows.append(event)
        else:
            all_rows.append({
                "ntaname":        row["ntaname"],
                "event_name":     "",
                "event_type":     "",
                "event_genre":    "",
                "event_datetime": "",
                "venue_name":     "",
                "event_url":      ""
            })
        time.sleep(0.1)

    df_events = pd.DataFrame(all_rows)
    return df_events

def build_Event_features(df_events: pd.DataFrame) -> pd.DataFrame:
    has_event = df_events[df_events["event_name"] != ""]
    if has_event.empty:
        return df_events[["ntaname"]].drop_duplicates().assign(nearby_events_count=0,
            nearby_event_titles="",
            nearby_event_types="",
            has_major_event=0)

    agg = has_event.groupby("ntaname").agg(
    nearby_events_count=("event_name", "count"),
    nearby_event_titles=("event_name", lambda x: ", ".join(x.dropna().unique()[:3])),
    nearby_event_types=("event_type", lambda x: ", ".join(x.dropna().unique()[:3]))).reset_index()

    major_types = ["Music", "Theater", "Comedy", "Sports"]
    has_event["is_major"] = has_event["event_type"].isin(major_types)
    major_agg = has_event.groupby("ntaname")["is_major"].max().reset_index().rename(columns={"is_major": "has_major_event"})
    major_agg["has_major_event"] = major_agg["has_major_event"].astype(int)

    agg = agg.merge(major_agg, on="ntaname", how="left")

    all_ntas = df_events[["ntaname"]].drop_duplicates()
    agg = all_ntas.merge(agg, on="ntaname", how="left").fillna(0)
    agg["nearby_events_count"] = agg["nearby_events_count"].fillna(0).astype(int)
    agg["nearby_event_titles"] = agg["nearby_event_titles"].fillna("")
    agg["nearby_event_types"]  = agg["nearby_event_types"].fillna("")
    agg["has_major_event"] = agg["has_major_event"].fillna(0).astype(int)

    return agg

def add_events_to_model_table(model_table: pd.DataFrame, df_events: pd.DataFrame) -> pd.DataFrame:
    events_cols = ["nearby_events_count", "nearby_event_titles",
                  "nearby_event_types", "has_major_event"]
    model_table = model_table.drop(columns = [c for c in events_cols if c in model_table.columns])
    model_table = model_table.merge(df_events, on="ntaname", how="left")
    model_table["nearby_events_count"] = model_table["nearby_events_count"].fillna(0).astype(int)
    model_table["nearby_event_titles"] = model_table["nearby_event_titles"].fillna("")
    model_table["nearby_event_types"]  = model_table["nearby_event_types"].fillna("")
    model_table["has_major_event"]     = model_table["has_major_event"].fillna(0).astype(int)
 
    return model_table

if __name__ == "__main__":
    model_path = os.getenv("MODEL_TABLE_PATH", "model_table_final.csv")
    output_path = os.getenv("EVENTS_OUTPUT_PATH", "data_events.csv")

    print("Pulling Ticketmaster events...")
    df_events = pull_ticketmaster_events(model_path)
    df_events.to_csv(output_path, index=False)
    print(f"Saved raw events to {output_path}")

    print("Building event features...")
    events_features = build_Event_features(df_events)
    events_features.to_csv(output_path, index=False)
    print(f"Saved event features to {output_path}")

    print("Merging into model_table_final...")
    model_table= pd.read_csv(model_path)
    model_table = add_events_to_model_table(model_table, events_features)
    model_table.to_csv(model_path, index=False)
    print(f"Updated {model_path} with event columns")
    print(model_table[["ntaname", "nearby_events_count", "nearby_event_titles", "has_major_event"]].head(10))
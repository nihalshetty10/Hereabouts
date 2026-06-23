import os
import re
import json
import time
import argparse
import pandas as pd
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
_client: Groq | None = None


def client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    return _client


SIGNAL_COLS = [
    "prob_active_noise_next_2h",
    "prob_active_complaints_next_2h",
    "prob_high_traffic_volume_next_2h",
    "prob_active_subway_ridership_next_2h",
    "prob_active_subway_transfers_next_2h",
    "bluesky_noise_signal",
    "bluesky_traffic_signal",
    "bluesky_crowding_signal",
    "bluesky_safety_signal",
    "bluesky_negative_signal",
    "nearby_events_count",
    "has_major_event",
    "crime_last_7d",
    "crashes_last_7d",
    "persons_injured_last_7d",
    "weather_score"
]

TOP_N_EXPLANATIONS = 20

def get_activity_weights(activity: str) -> dict:
    prompt = f"""You are helping score NYC neighborhoods for someone who wants to: "{activity}"

Think carefully about what this activity actually needs:
- Running/biking: low noise, low traffic, low crime, good weather. Crowds and events are BAD.
- Night out/bars/clubs: nearby events, active subway, lively atmosphere. Noise and crowding are GOOD. Low noise is NOT a bonus.
- Coffee/study: very quiet, low crowding, low noise. Events nearby are BAD.
- Park/outdoor/picnic: low crime, good weather, low traffic. Events neutral.
- Eating/dinner/brunch: transit access, moderate crowding OK, crime matters. Events neutral. Noise neutral.
- Dating/romantic: quiet, safe, good weather, low crowding. Some events OK.
- Shopping: transit access, low crime, moderate crowding fine. Events neutral.
- Commuting/travel: high subway ridership = GOOD. Traffic neutral. Everything else secondary.
- Meditation/yoga: very quiet, very low crowding, low noise. Like coffee but even more quiet.
- Exploring/photography: low crime, good weather. Everything else neutral.

For each signal below, assign a weight from -2 to +2 based on the specific activity above:
- Negative = makes neighborhood WORSE for this activity
- Positive = makes neighborhood BETTER for this activity
- 0 = irrelevant

Signals:
- prob_active_noise_next_2h: probability of high noise in next 2h
- prob_active_complaints_next_2h: probability of high 311 complaints in next 2h
- prob_high_traffic_volume_next_2h: probability of high traffic in next 2h
- prob_active_subway_ridership_next_2h: probability of high subway ridership
- prob_active_subway_transfers_next_2h: probability of high subway transfers
- bluesky_noise_signal: social media noise signal
- bluesky_traffic_signal: social media traffic signal
- bluesky_crowding_signal: social media crowding signal
- bluesky_safety_signal: social media safety concern signal
- bluesky_negative_signal: overall negative social sentiment
- nearby_events_count: number of nearby events tonight
- has_major_event: whether a major event (concert/game) is nearby
- crime_last_7d: crime incidents in last 7 days
- crashes_last_7d: vehicle crashes in last 7 days
- persons_injured_last_7d: persons injured in crashes last 7 days
- weather_score: weather quality (0=bad, 1=good)

Return ONLY a valid JSON object with exactly these keys and float values between -2 and +2.
No explanation. No markdown."""

    try:
        response = client().chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        text = response.choices[0].message.content.strip()
        text = text.replace("```json", "").replace("```", "").strip()
        text = re.sub(r",\s*}", "}", text)
        text = re.sub(r",\s*]", "]", text)
        weights = json.loads(text)
        cleaned = {}
        for key, value in weights.items():
            try:
                cleaned[key] = float(value)
            except (TypeError, ValueError):
                continue

        if sum(abs(v) for v in cleaned.values()) < 0.01:
            print(f"LLM returned zero weights for {activity} — using defaults")
            return default_weights(activity)

        merged = default_weights(activity)
        for key, value in cleaned.items():
            if key in merged:
                merged[key] = value
        print(f"Weights generated for: {activity}")
        return merged
    except Exception as e:
        print(f"LLM weight generation failed: {e} — using defaults")
        return default_weights(activity)


def default_weights(activity: str) -> dict:
    activity_lower = activity.lower()
    if any(w in activity_lower for w in ["run", "jog", "walk", "bike", "cycling"]):
        return {
            "prob_active_noise_next_2h": -1.5,
            "prob_active_complaints_next_2h": -1.0,
            "prob_high_traffic_volume_next_2h": -2.0,
            "prob_active_subway_ridership_next_2h": 0.0,
            "prob_active_subway_transfers_next_2h": 0.0,
            "bluesky_noise_signal": -1.0,
            "bluesky_traffic_signal": -1.5,
            "bluesky_crowding_signal": -1.0,
            "bluesky_safety_signal": -2.0,
            "bluesky_negative_signal": -1.0,
            "nearby_events_count": -0.5,
            "has_major_event": -1.0,
            "crime_last_7d": -1.5,
            "crashes_last_7d": -1.5,
            "persons_injured_last_7d": -1.0,
            "weather_score": 2.0
        }
    elif any(w in activity_lower for w in ["night", "bar", "drink", "club", "out"]):
        return {
            "prob_active_noise_next_2h": 0.5,
            "prob_active_complaints_next_2h": 0.0,
            "prob_high_traffic_volume_next_2h": 0.0,
            "prob_active_subway_ridership_next_2h": 1.5,
            "prob_active_subway_transfers_next_2h": 1.0,
            "bluesky_noise_signal": 0.5,
            "bluesky_traffic_signal": 0.0,
            "bluesky_crowding_signal": 0.5,
            "bluesky_safety_signal": -1.5,
            "bluesky_negative_signal": -1.0,
            "nearby_events_count": 2.0,
            "has_major_event": 1.5,
            "crime_last_7d": -1.0,
            "crashes_last_7d": -0.5,
            "persons_injured_last_7d": -0.5,
            "weather_score": 0.5
        }
    elif any(w in activity_lower for w in ["coffee", "study", "work", "read", "cafe"]):
        return {
            "prob_active_noise_next_2h": -2.0,
            "prob_active_complaints_next_2h": -1.0,
            "prob_high_traffic_volume_next_2h": 0.0,
            "prob_active_subway_ridership_next_2h": 0.5,
            "prob_active_subway_transfers_next_2h": 0.5,
            "bluesky_noise_signal": -1.5,
            "bluesky_traffic_signal": 0.0,
            "bluesky_crowding_signal": -1.5,
            "bluesky_safety_signal": -1.5,
            "bluesky_negative_signal": -1.0,
            "nearby_events_count": -1.0,
            "has_major_event": -1.5,
            "crime_last_7d": -1.0,
            "crashes_last_7d": -0.5,
            "persons_injured_last_7d": -0.5,
            "weather_score": 1.0
        }
    elif any(w in activity_lower for w in ["eat", "dinner", "lunch", "brunch", "food", "restaurant"]):
        return {
            "prob_active_noise_next_2h": 0.0,
            "prob_active_complaints_next_2h": -0.5,
            "prob_high_traffic_volume_next_2h": 0.0,
            "prob_active_subway_ridership_next_2h": 1.5,
            "prob_active_subway_transfers_next_2h": 1.0,
            "bluesky_noise_signal": 0.0,
            "bluesky_traffic_signal": 0.0,
            "bluesky_crowding_signal": 0.5,
            "bluesky_safety_signal": -1.5,
            "bluesky_negative_signal": -1.0,
            "nearby_events_count": 0.0,
            "has_major_event": 0.0,
            "crime_last_7d": -1.5,
            "crashes_last_7d": -0.5,
            "persons_injured_last_7d": -0.5,
            "weather_score": 1.0
        }
    elif any(w in activity_lower for w in ["date", "dating", "romantic"]):
        return {
            "prob_active_noise_next_2h": -1.0,
            "prob_active_complaints_next_2h": -0.5,
            "prob_high_traffic_volume_next_2h": -0.5,
            "prob_active_subway_ridership_next_2h": 1.0,
            "prob_active_subway_transfers_next_2h": 0.5,
            "bluesky_noise_signal": -1.0,
            "bluesky_traffic_signal": -0.5,
            "bluesky_crowding_signal": -1.0,
            "bluesky_safety_signal": -2.0,
            "bluesky_negative_signal": -1.0,
            "nearby_events_count": 0.5,
            "has_major_event": 0.0,
            "crime_last_7d": -2.0,
            "crashes_last_7d": -0.5,
            "persons_injured_last_7d": -0.5,
            "weather_score": 1.5
        }
    elif any(w in activity_lower for w in ["shop", "shopping", "market", "store"]):
        return {
            "prob_active_noise_next_2h": 0.0,
            "prob_active_complaints_next_2h": -0.5,
            "prob_high_traffic_volume_next_2h": -0.5,
            "prob_active_subway_ridership_next_2h": 2.0,
            "prob_active_subway_transfers_next_2h": 1.5,
            "bluesky_noise_signal": 0.0,
            "bluesky_traffic_signal": -0.5,
            "bluesky_crowding_signal": 0.5,
            "bluesky_safety_signal": -1.5,
            "bluesky_negative_signal": -1.0,
            "nearby_events_count": 0.5,
            "has_major_event": 0.0,
            "crime_last_7d": -1.5,
            "crashes_last_7d": -0.5,
            "persons_injured_last_7d": -0.5,
            "weather_score": 1.0
        }
    elif any(w in activity_lower for w in ["commute", "travel", "transit", "subway"]):
        return {
            "prob_active_noise_next_2h": 0.0,
            "prob_active_complaints_next_2h": 0.0,
            "prob_high_traffic_volume_next_2h": -1.0,
            "prob_active_subway_ridership_next_2h": 2.0,
            "prob_active_subway_transfers_next_2h": 2.0,
            "bluesky_noise_signal": 0.0,
            "bluesky_traffic_signal": -1.0,
            "bluesky_crowding_signal": 0.0,
            "bluesky_safety_signal": -1.0,
            "bluesky_negative_signal": -0.5,
            "nearby_events_count": 0.0,
            "has_major_event": 0.0,
            "crime_last_7d": -1.0,
            "crashes_last_7d": -0.5,
            "persons_injured_last_7d": -0.5,
            "weather_score": 0.5
        }
    elif any(w in activity_lower for w in ["meditate", "yoga", "mindful", "quiet"]):
        return {
            "prob_active_noise_next_2h": -2.0,
            "prob_active_complaints_next_2h": -1.5,
            "prob_high_traffic_volume_next_2h": -1.0,
            "prob_active_subway_ridership_next_2h": 0.0,
            "prob_active_subway_transfers_next_2h": 0.0,
            "bluesky_noise_signal": -2.0,
            "bluesky_traffic_signal": -1.0,
            "bluesky_crowding_signal": -2.0,
            "bluesky_safety_signal": -1.5,
            "bluesky_negative_signal": -1.0,
            "nearby_events_count": -1.5,
            "has_major_event": -2.0,
            "crime_last_7d": -1.5,
            "crashes_last_7d": -0.5,
            "persons_injured_last_7d": -0.5,
            "weather_score": 2.0
        }
    elif any(w in activity_lower for w in ["explore", "photo", "walk around", "wander", "tourist"]):
        return {
            "prob_active_noise_next_2h": 0.0,
            "prob_active_complaints_next_2h": -0.5,
            "prob_high_traffic_volume_next_2h": -0.5,
            "prob_active_subway_ridership_next_2h": 1.0,
            "prob_active_subway_transfers_next_2h": 0.5,
            "bluesky_noise_signal": 0.0,
            "bluesky_traffic_signal": -0.5,
            "bluesky_crowding_signal": 0.0,
            "bluesky_safety_signal": -1.5,
            "bluesky_negative_signal": -1.0,
            "nearby_events_count": 1.0,
            "has_major_event": 0.5,
            "crime_last_7d": -2.0,
            "crashes_last_7d": -0.5,
            "persons_injured_last_7d": -0.5,
            "weather_score": 2.0
        }
    elif any(w in activity_lower for w in ["soccer", "football", "sport", "sports", "basketball", "tennis", "hockey", "baseball", "athletic"]):
        return {
            "prob_active_noise_next_2h": -1.0,
            "prob_active_complaints_next_2h": -0.5,
            "prob_high_traffic_volume_next_2h": -1.5,
            "prob_active_subway_ridership_next_2h": 0.5,
            "prob_active_subway_transfers_next_2h": 0.5,
            "bluesky_noise_signal": -0.5,
            "bluesky_traffic_signal": -1.0,
            "bluesky_crowding_signal": 0.0,
            "bluesky_safety_signal": -2.0,
            "bluesky_negative_signal": -1.0,
            "nearby_events_count": 0.5,
            "has_major_event": 0.5,
            "crime_last_7d": -1.5,
            "crashes_last_7d": -1.0,
            "persons_injured_last_7d": -0.5,
            "weather_score": 2.0
        }
    else:
        return {
            "prob_active_noise_next_2h": -1.5,
            "prob_active_complaints_next_2h": -1.0,
            "prob_high_traffic_volume_next_2h": -1.0,
            "prob_active_subway_ridership_next_2h": 0.5,
            "prob_active_subway_transfers_next_2h": 0.5,
            "bluesky_noise_signal": -1.0,
            "bluesky_traffic_signal": -1.0,
            "bluesky_crowding_signal": -1.0,
            "bluesky_safety_signal": -1.5,
            "bluesky_negative_signal": -1.0,
            "nearby_events_count": 0.5,
            "has_major_event": 0.0,
            "crime_last_7d": -1.0,
            "crashes_last_7d": -1.0,
            "persons_injured_last_7d": -0.5,
            "weather_score": 1.5
        }

def add_weather_score(df: pd.DataFrame) -> pd.DataFrame:
    if "weather_score" in df.columns and df["weather_score"].notna().any():
        return df
    score = pd.Series(0.7, index=df.index)
    if "precip_prob" in df.columns:
        score = score - df["precip_prob"].fillna(0) * 0.4
    if "temp_f" in df.columns:
        score = score + ((df["temp_f"].fillna(65) - 50) / 50).clip(0, 0.3)
    if "weather_main" in df.columns:
        bad = df["weather_main"].fillna("").str.lower().isin(
            ["rain", "snow", "thunderstorm", "drizzle"]
        )
        score = score - bad.astype(float) * 0.3
    df = df.copy()
    df["weather_score"] = score.clip(0, 1)
    return df

def math_score(row: pd.Series, weights: dict) -> float:
    raw = 0
    for col in SIGNAL_COLS:
        if col in row.index:
            raw += weights.get(col, 0) * float(row.get(col, 0))
    return raw

def generate_explanation(row: pd.Series, activity: str) -> dict:
    prompt = f"""You are generating a neighborhood recommendation for a NYC app called Hereabouts.

Activity: {activity}
Neighborhood: {row["ntaname"]}
Score: {row["score"]}/100 ({row["label"]})

Current conditions:
- Noise probability (next 2h): {row.get("prob_active_noise_next_2h", 0):.2f}
- Traffic probability (next 2h): {row.get("prob_high_traffic_volume_next_2h", 0):.2f}
- Subway ridership probability: {row.get("prob_active_subway_ridership_next_2h", 0):.2f}
- Weather: {row.get("weather_main", "unknown")} {row.get("temp_f", "")}°F
- Nearby events: {row.get("nearby_event_titles", "none") or "none"}
- Social negative signal: {row.get("bluesky_negative_signal", 0):.2f}
- Crime last 7d: {row.get("crime_last_7d", 0):.0f}

Return ONLY a valid JSON object with:
- summary: one sentence explaining why this neighborhood fits or doesn't fit the activity
- pros: list of exactly 2 short pros (each under 10 words)
- cons: list of exactly 1 short con (under 10 words)

Base everything only on the signals above. Do not invent facts."""

    try:
        response = client().chat.completions.create(
            model="llama-3.1-8b-instant",
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        text = response.choices[0].message.content.strip()
        text = text.replace("```json", "").replace("```", "").strip()
        text = re.sub(r",\s*}", "}", text)
        text = re.sub(r",\s*]", "]", text)
        result = json.loads(text)
        cons_raw = result.get("cons", [])
        if isinstance(cons_raw, str):
            cons_str = cons_raw
        elif isinstance(cons_raw, list) and cons_raw:
            cons_str = cons_raw[0]
        else:
            cons_str = ""
        return {
            "summary": result.get("summary", ""),
            "pros":    result.get("pros", [])[:2],
            "cons":    cons_str
        }
    except Exception as e:
        print(f"Explanation failed for {row['ntaname']}: {e}")
        return fallback_explanation(row, activity)


def fallback_explanation(row: pd.Series, activity: str) -> dict:
    noise   = row.get("prob_active_noise_next_2h", 0)
    traffic = row.get("prob_high_traffic_volume_next_2h", 0)
    weather = row.get("weather_score", 0.5)
    return {
        "summary": f"{row['ntaname']} scored {row['score']}/100 for {activity} based on current conditions.",
        "pros": [
            "Low noise predicted" if noise < 0.4 else "Good weather conditions",
            "Favorable weather" if weather > 0.6 else "Subway access available"
        ],
        "cons": [
            "High traffic predicted" if traffic > 0.5 else "Limited signal data"
        ]
    }

def score_activity(
    activity: str,
    model_table_path: str = "model_table_final.csv",
) -> pd.DataFrame:
    """Score all neighborhoods for an activity. Returns full feature dataframe."""
    model_table = pd.read_csv(model_table_path)

    has_coords = (
        "latitude" in model_table.columns
        and "longitude" in model_table.columns
        and model_table["latitude"].notna().all()
        and model_table["longitude"].notna().all()
    )
    if not has_coords:
        import sys
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from data.geo import attach_nta_centroids
        model_table = attach_nta_centroids(model_table)

    weights = get_activity_weights(activity)
    scored = add_weather_score(model_table.copy())
    original_events_count = scored["nearby_events_count"].copy()

    for col in ["nearby_events_count", "crime_last_7d", "crashes_last_7d",
                "persons_injured_last_7d", "noise_last_24h", "complaints_last_24h",
                "subway_ridership_last_24h", "subway_transfers_last_24h",
                "traffic_volume_last_24h"]:
        if col in scored.columns:
            col_max = scored[col].max()
            if col_max > 0:
                scored[col] = scored[col] / col_max

    scored["score"] = scored.apply(lambda row: math_score(row, weights), axis=1)
    scored["nearby_event_count"] = original_events_count

    lo, hi = scored["score"].min(), scored["score"].max()
    if hi > lo:
        scored["score"] = ((scored["score"] - lo) / (hi - lo) * 100).round(1)
    else:
        scored["score"] = 50.0

    scored["label"] = pd.cut(
        scored["score"],
        bins=[0, 40, 60, 80, 100],
        labels=["Poor", "Fair", "Good", "Great"],
        include_lowest=True
    )
    return scored.sort_values("score", ascending=False).reset_index(drop=True)


def explain_neighborhood(scored: pd.DataFrame, activity: str, ntaname: str) -> dict:
    """Generate summary/pros/cons for one neighborhood. Does not persist."""
    matches = scored[scored["ntaname"] == ntaname]
    if matches.empty:
        raise ValueError(f"Neighborhood not found: {ntaname}")

    row = matches.iloc[0]
    result = generate_explanation(row, activity)
    return {
        "ntaname": ntaname,
        "summary": result.get("summary", ""),
        "pros": " | ".join(result.get("pros", [])) if result.get("pros") else "",
        "cons": result.get("cons", ""),
    }


def run_recommender(
    activity: str,
    model_table_path: str = "model_table_final.csv",
    output_path: str = "scored_table.csv",
    generate_explanations: bool = True,
) -> pd.DataFrame:
    print(f"\nRunning recommender for: '{activity}'")
    print(f"Loaded model table from {model_table_path}")

    scored = score_activity(activity, model_table_path)
    print(f"Scored {len(scored)} neighborhoods")
    print(scored[["ntaname", "score", "label"]].head(5).to_string())

    print(f"\nGenerating explanations for top {TOP_N_EXPLANATIONS} neighborhoods...")
    scored["summary"] = ""
    scored["pros"]    = ""
    scored["cons"]    = ""

    if generate_explanations:
        for i, row in scored.head(TOP_N_EXPLANATIONS).iterrows():
            print(f"  {i+1}/{TOP_N_EXPLANATIONS} — {row['ntaname']}")
            result = generate_explanation(row, activity)
            scored.at[i, "summary"] = result["summary"]
            scored.at[i, "pros"]    = " | ".join(result["pros"]) if result["pros"] else ""
            scored.at[i, "cons"]    = result["cons"]
            time.sleep(2)

    output_cols = [
        "ntaname", "score", "label", "summary", "pros", "cons",
        "nearby_events_count", "nearby_event_titles", "nearby_event_types",
        "has_major_event", "latitude", "longitude"
    ]
    output_cols = [c for c in output_cols if c in scored.columns]
    output = scored[output_cols]

    output.to_csv(output_path, index=False)
    print(f"\nSaved scored_table to {output_path}")
    print(output[["ntaname", "score", "label", "summary"]].head(10).to_string())
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--activity",    type=str, required=True)
    parser.add_argument("--model_table", type=str, default="model_table_final.csv")
    parser.add_argument("--output",      type=str, default="scored_table.csv")
    args = parser.parse_args()
    run_recommender(
        activity=args.activity,
        model_table_path=args.model_table,
        output_path=args.output
    )
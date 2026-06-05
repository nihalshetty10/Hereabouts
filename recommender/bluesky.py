import os
import re
import json
import time
import pandas as pd
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

_client: Groq | None = None
_llm_warned = False


def _groq_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    return _client


def pull_bluesky_by_nta(
    username: str,
    password: str,
    nta_csv_path: str = "model_table_final.csv",
    posts_per_nta: int = 10,
    hours_back: int = 24
) -> pd.DataFrame:
    from atproto import Client

    client_bsky = Client()
    client_bsky.login(username, password)

    since_time = (
        datetime.now(timezone.utc) - timedelta(hours=hours_back)
    ).isoformat().replace("+00:00", "Z")

    nta_names = pd.read_csv(nta_csv_path)["ntaname"].unique().tolist()

    neighborhood_queries = [(f"{nta} NYC", nta) for nta in nta_names]
    general_queries = [
        ("NYC noise",        "NYC"),
        ("NYC traffic",      "NYC"),
        ("NYC crowded",      "NYC"),
        ("NYC subway",       "NYC"),
        ("NYC event",        "NYC"),
        ("NYC protest",      "NYC"),
        ("NYC construction", "NYC"),
    ]
    all_queries = neighborhood_queries + general_queries

    unique_posts = {}

    for query, ntaname in all_queries:
        cursor = None
        query_count = 0

        while query_count < posts_per_nta:
            params = {
                "q": query, "limit": posts_per_nta,
                "since": since_time, "sort": "latest", "lang": "en"
            }
            if cursor:
                params["cursor"] = cursor

            try:
                response = client_bsky.app.bsky.feed.search_posts(params)
            except Exception as e:
                print(f"Error on '{query}': {e}")
                break

            if not response.posts:
                break

            for post in response.posts:
                text_clean = " ".join(post.record.text.lower().strip().split())
                if text_clean not in unique_posts:
                    unique_posts[text_clean] = {
                        "ntaname":         ntaname,
                        "query":           query,
                        "text":            post.record.text,
                        "created_at":      post.record.created_at,
                        "author":          post.author.display_name,
                        "author_username": post.author.handle,
                        "uri":             post.uri,
                        "likes":           post.like_count,
                        "replies":         post.reply_count,
                        "reposts":         post.repost_count
                    }
                query_count += 1

            cursor = response.cursor
            if not cursor:
                break
            time.sleep(0.5)

        time.sleep(0.3)

    df = pd.DataFrame(unique_posts.values())
    print(f"Pulled {len(df)} unique Bluesky posts across {len(nta_names)} NTAs")
    return df


def classify_social_post(post_text: str) -> dict:
    prompt = f"""Classify this social media post for a neighborhood recommendation app.

Return ONLY a valid JSON object with these exact keys:
- noise_signal: 0 or 1
- traffic_signal: 0 or 1
- crowding_signal: 0 or 1
- transit_signal: 0 or 1
- event_signal: 0 or 1
- safety_signal: 0 or 1
- negative_signal: 0 or 1
- summary: short phrase

Post:
{post_text}"""

    try:
        response = _groq_client().chat.completions.create(
            model="llama-3.1-8b-instant",
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}]
        )
        text = response.choices[0].message.content.strip()
        text = text.replace("```json", "").replace("```", "").strip()
        return json.loads(text)

    except Exception as e:
        global _llm_warned
        if not _llm_warned:
            print(f"LLM classification failed, using keyword fallback: {e}")
            _llm_warned = True
        return _keyword_fallback(post_text)


def build_bluesky_signals(df_bluesky: pd.DataFrame) -> pd.DataFrame:
    if df_bluesky.empty:
        print("No Bluesky posts to classify")
        return pd.DataFrame()

    print(f"Classifying {len(df_bluesky)} posts...")
    classifications = []
    for i, row in df_bluesky.iterrows():
        result = classify_social_post(row["text"])
        result["ntaname"] = row["ntaname"]
        classifications.append(result)
        if i % 50 == 0:
            print(f"  {i}/{len(df_bluesky)} classified")

    df_classified = pd.DataFrame(classifications)

    signal_cols = [
        "noise_signal", "traffic_signal", "crowding_signal",
        "transit_signal", "event_signal", "safety_signal", "negative_signal"
    ]

    agg = (
        df_classified
        .groupby("ntaname")[signal_cols]
        .mean()
        .reset_index()
    )

    post_counts = df_bluesky.groupby("ntaname").size().reset_index(name="bluesky_post_count")
    agg = agg.merge(post_counts, on="ntaname", how="left")
    agg = agg.rename(columns={col: f"bluesky_{col}" for col in signal_cols})

    print(f"Bluesky signals built for {len(agg)} NTAs")
    return agg


def add_bluesky_to_model_table(
    model_table: pd.DataFrame,
    bluesky_signals: pd.DataFrame
) -> pd.DataFrame:
    bluesky_cols = [c for c in model_table.columns if c.startswith("bluesky_")]
    if bluesky_cols:
        model_table = model_table.drop(columns=bluesky_cols)

    model_table = model_table.merge(bluesky_signals, on="ntaname", how="left")

    fill_cols = [c for c in model_table.columns if c.startswith("bluesky_")]
    model_table[fill_cols] = model_table[fill_cols].fillna(0)

    return model_table


SIGNAL_KEYWORDS = {
    "noise_signal":    ["noise", "noisy", "loud", "sirens", "honking", "blasting", "blaring"],
    "traffic_signal":  ["traffic", "gridlock", "standstill", "jam", "congestion", "backed up"],
    "crowding_signal": ["packed", "crowded", "busy", "mobbed", "slammed", "rammed", "wall to wall", "no space"],
    "transit_signal":  ["subway", "train", "mta", "delay", "delayed", "skipping", "no service"],
    "event_signal":    ["event", "concert", "game", "protest", "parade", "festival", "show"],
    "safety_signal":   ["unsafe", "police", "fight", "danger", "crime", "shooting", "arrest"],
    "negative_signal": ["avoid", "bad", "terrible", "awful", "delayed", "packed", "unsafe", "nightmare"],
}


def _keyword_fallback(post_text: str) -> dict:
    t = post_text.lower()
    result = {}
    for key, words in SIGNAL_KEYWORDS.items():
        pattern = r'\b(' + '|'.join(re.escape(w) for w in words) + r')\b'
        result[key] = int(bool(re.search(pattern, t)))
    result["summary"] = "keyword fallback"
    return result


if __name__ == "__main__":
    username = os.getenv("BLUESKY_USERNAME") or os.getenv("BSKY_USERNAME")
    password = os.getenv("BLUESKY_PASSWORD") or os.getenv("BSKY_PASSWORD")
    if not username or not password:
        raise SystemExit(
            "Set BLUESKY_USERNAME and BLUESKY_PASSWORD (or BSKY_USERNAME / BSKY_PASSWORD)."
        )
    if not os.getenv("GROQ_API_KEY"):
        raise SystemExit("Set GROQ_API_KEY in .env")

    model_path = os.getenv("MODEL_TABLE_PATH", "model_table_final.csv")
    output_path = os.getenv("BLUESKY_OUTPUT_PATH", "data_bluesky_signals.csv")

    df_posts = pull_bluesky_by_nta(username, password, nta_csv_path=model_path)
    if not df_posts.empty:
        df_posts.to_csv("data_bluesky_raw.csv", index=False)
        print(f"Saved raw posts to data_bluesky_raw.csv")

    signals = build_bluesky_signals(df_posts)
    if not signals.empty:
        signals.to_csv(output_path, index=False)
        print(f"Saved signals to {output_path}")

    if os.path.isfile(model_path):
        model_table = pd.read_csv(model_path)
        updated = add_bluesky_to_model_table(model_table, signals)
        updated.to_csv(model_path, index=False)
        print(f"Updated {model_path} with Bluesky columns")
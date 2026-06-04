import time
import pandas as pd
import requests
from io import StringIO
from datetime import datetime, timedelta, timezone

def read_socrata_data(url: str, params: dict = None) -> pd.DataFrame:
    response = requests.get(url, params=params, timeout=60)
    response.raise_for_status()
    return pd.read_csv(StringIO(response.text))


def pull_311(months_back: int = 6) -> pd.DataFrame:
    since = (datetime.now() - timedelta(days=months_back * 30)).strftime("%Y-%m-%dT%H:%M:%S")
    return read_socrata_data(
        "https://data.cityofnewyork.us/resource/erm2-nwe9.csv",
        {
            "$where": f"created_date >= '{since}'",
            "$limit": 500000,
            "$order": "created_date DESC"
        }
    )


def pull_crime(days_back: int = 30) -> pd.DataFrame:
    since = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%dT%H:%M:%S")
    return read_socrata_data(
        "https://data.cityofnewyork.us/resource/5uac-w243.csv",
        {
            "$where": f"cmplnt_fr_dt >= '{since}'",
            "$limit": 100000,
            "$order": "cmplnt_fr_dt DESC"
        }
    )


def pull_crashes(days_back: int = 30) -> pd.DataFrame:
    since = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%dT%H:%M:%S")
    return read_socrata_data(
        "https://data.cityofnewyork.us/resource/h9gi-nx95.csv",
        {
            "$where": f"crash_date >= '{since}'",
            "$limit": 100000,
            "$order": "crash_date DESC"
        }
    )


def pull_traffic() -> pd.DataFrame:
    return read_socrata_data(
        "https://data.cityofnewyork.us/resource/7ym2-wayt.csv",
        {"$limit": 500000}
    )


def pull_subway() -> pd.DataFrame:
    return read_socrata_data(
        "https://data.ny.gov/resource/5wq4-mkjj.csv",
        {"$limit": 500000}
    )


def pull_pedestrian() -> pd.DataFrame:
    return read_socrata_data(
        "https://data.cityofnewyork.us/resource/cqsj-cfgu.csv",
        {"$limit": 500000}
    )

def pull_bluesky(username: str, password: str, max_posts: int = 100) -> pd.DataFrame:
    from atproto import Client

    client = Client()
    client.login(username, password)

    since_time = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat().replace("+00:00", "Z")

    queries = [
        "NYC noise", "New York City noise", "New York noise",
        "New York City traffic", "New York City construction",
        "New York City crowded", "New York City subway",
        "New York City event", "New York City protest",
        "NYC traffic", "NYC construction", "NYC crowded",
        "NYC subway", "NYC event", "NYC protest"
    ]

    unique_posts = {}

    for query in queries:
        cursor = None
        while len(unique_posts) < max_posts:
            params = {
                "q": query, "limit": 100,
                "since": since_time, "sort": "latest", "lang": "en"
            }
            if cursor:
                params["cursor"] = cursor

            response = client.app.bsky.feed.search_posts(params)
            if not response.posts:
                break

            for post in response.posts:
                text_clean = " ".join(post.record.text.lower().strip().split())
                if text_clean not in unique_posts:
                    unique_posts[text_clean] = {
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
                if len(unique_posts) >= max_posts:
                    break

            cursor = response.cursor
            if not cursor:
                break
            time.sleep(1)

        if len(unique_posts) >= max_posts:
            break

    return pd.DataFrame(unique_posts.values())

def pull_weather(nta_points: pd.DataFrame, api_key: str) -> pd.DataFrame:
    """
    nta_points: DataFrame with columns [ntaname, latitude, longitude]
    Returns one weather row per NTA (nearest forecast slot).
    """
    rows = []

    for _, row in nta_points.iterrows():
        for attempt in range(3):
            try:
                r = requests.get(
                    "https://api.openweathermap.org/data/2.5/forecast",
                    params={
                        "lat": row["latitude"], "lon": row["longitude"],
                        "appid": api_key, "units": "imperial", "cnt": 1
                    },
                    timeout=10
                )
                r.raise_for_status()
                item = r.json()["list"][0]
                rows.append({
                    "ntaname":             row["ntaname"],
                    "temp_f":              item["main"]["temp"],
                    "feels_like_f":        item["main"]["feels_like"],
                    "humidity":            item["main"]["humidity"],
                    "wind_mph":            item["wind"]["speed"],
                    "precip_prob":         item.get("pop", 0),
                    "rain_3h":             item.get("rain", {}).get("3h", 0),
                    "snow_3h":             item.get("snow", {}).get("3h", 0),
                    "weather_main":        item["weather"][0]["main"],
                    "weather_description": item["weather"][0]["description"]
                })
                break
            except Exception as e:
                print(f"  Attempt {attempt+1} failed for {row['ntaname']}: {e}")
                time.sleep(2)

        time.sleep(0.1)

    return pd.DataFrame(rows)

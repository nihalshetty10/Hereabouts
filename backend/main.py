import os
import sys
import json
import pandas as pd
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine, text
from pydantic import BaseModel
from dotenv import load_dotenv
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.concurrency import run_in_threadpool

load_dotenv()

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))


def _resolve_model_table_path() -> str:
    env_path = os.getenv("MODEL_TABLE_PATH")
    if env_path and os.path.exists(env_path):
        return env_path
    for candidate in (
        os.path.join(BACKEND_DIR, "model_table_final.csv"),
        os.path.join(ROOT_DIR, "data", "model_table_final.csv"),
        os.path.join(ROOT_DIR, "model_table_final.csv"),
    ):
        if os.path.exists(candidate):
            return candidate
    raise FileNotFoundError("model_table_final.csv not found in backend/ or data/")


DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

limiter= Limiter(key_func=get_remote_address)
app = FastAPI(title = "Hereabouts", version = "1.0.0")
app.state.limiter = limiter


async def rate_limit_exception_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"error": "Rate limit exceeded. Custom activity requests are limited to 1 per day."}
    )


app.add_exception_handler(RateLimitExceeded, rate_limit_exception_handler)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_methods=["*"],
    allow_headers=["*"]
)

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/recommendations")
def get_recommendations(activity: str = "night_out"):
    activity_key = activity.lower().replace(" ", "_").replace("-", "_")
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT * FROM scored_table WHERE activity = :activity ORDER BY score DESC"),
                {"activity": activity_key}
            )
            rows = result.mappings().fetchall()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if not rows:
        raise HTTPException(status_code=404, detail=f"No recommendations found for activity: {activity}")

    return [dict(row) for row in rows]

@app.get("/neighborhoods/{ntaname}")
def get_neighborhood(ntaname: str, activity: str = "night_out"):
    activity_key = activity.lower().replace(" ", "_").replace("-", "_")
 
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT * FROM scored_table 
                    WHERE ntaname = :ntaname AND activity = :activity
                """),
                {"ntaname": ntaname, "activity": activity_key}
            )
            row = result.mappings().first()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
 
    if not row:
        raise HTTPException(status_code=404, detail=f"Neighborhood not found: {ntaname}")
 
    row_dict = dict(row)
    if not row_dict.get("summary"):
        row_dict = _generate_and_cache(row_dict, activity_key)
        
    return row_dict

def _generate_and_cache(row: dict, activity_key: str) -> dict:
    rec = _load_recommender()
    row_series = pd.Series(row)
    result = rec.generate_explanation(row_series, activity_key)
    summary = result.get("summary", "")
    pros = " | ".join(result.get("pros", [])) if result.get("pros") else ""
    cons = result.get("cons", "") if isinstance(result.get("cons"), str) else (result.get("cons", [""])[0] if result.get("cons") else "")

    try:
        with engine.connect() as conn:
            conn.execute(
                text("""
                    UPDATE scored_table
                    SET summary = :summary, pros = :pros, cons = :cons
                    WHERE ntaname = :ntaname AND activity = :activity
                """),
                {"summary": summary, "pros": pros, "cons": cons,
                 "ntaname": row["ntaname"], "activity": activity_key}
            )
            conn.commit()
    except Exception as e:
        print(f"Failed to cache explanation: {e}")
 
    row["summary"] = summary
    row["pros"]    = pros
    row["cons"]    = cons
    return row

class CustomRequest(BaseModel):
    activity: str


class CustomExplainRequest(BaseModel):
    activity: str
    ntaname: str


_custom_score_cache: dict[str, pd.DataFrame] = {}


def _load_recommender():
    for path in (BACKEND_DIR, ROOT_DIR):
        if path not in sys.path:
            sys.path.insert(0, path)
    from recommender import recommender as rec
    return rec


def _load_run_recommender():
    return _load_recommender().run_recommender


def _cache_key(activity: str) -> str:
    return activity.strip().lower()


def _score_custom_activity(activity: str) -> list:
    rec = _load_recommender()
    scored = rec.score_activity(activity, _resolve_model_table_path())
    _custom_score_cache[_cache_key(activity)] = scored

    output_cols = [
        "ntaname", "score", "label", "summary", "pros", "cons",
        "nearby_events_count", "nearby_event_titles", "nearby_event_types",
        "has_major_event", "latitude", "longitude",
    ]
    output = scored.copy()
    output["summary"] = ""
    output["pros"] = ""
    output["cons"] = ""
    output_cols = [c for c in output_cols if c in output.columns]
    output = output[output_cols]
    for col in output.select_dtypes(include=["category"]).columns:
        output[col] = output[col].astype(str)
    return json.loads(output.fillna("").to_json(orient="records"))


def _explain_custom_neighborhood(activity: str, ntaname: str) -> dict:
    rec = _load_recommender()
    key = _cache_key(activity)
    scored = _custom_score_cache.get(key)
    if scored is None:
        scored = rec.score_activity(activity, _resolve_model_table_path())
        _custom_score_cache[key] = scored
    return rec.explain_neighborhood(scored, activity, ntaname)


@app.post("/recommendations/custom")
@limiter.limit("1/day")
async def custom_recommendations(request: Request, body: CustomRequest):
    activity = body.activity.strip()
    if not activity:
        raise HTTPException(status_code=400, detail="Activity cannot be empty")

    try:
        return await run_in_threadpool(_score_custom_activity, activity)
    except ImportError as e:
        raise HTTPException(status_code=500, detail=f"Recommender module unavailable: {e}")
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/recommendations/custom/explain")
async def explain_custom_neighborhood(body: CustomExplainRequest):
    activity = body.activity.strip()
    ntaname = body.ntaname.strip()
    if not activity or not ntaname:
        raise HTTPException(status_code=400, detail="Activity and ntaname are required")

    try:
        return await run_in_threadpool(_explain_custom_neighborhood, activity, ntaname)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host = "0.0.0.0", port = 8000, reload=True)

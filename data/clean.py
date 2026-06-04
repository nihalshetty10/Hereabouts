import pandas as pd


def clean_311(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["created_date"] = pd.to_datetime(df["created_date"], errors="coerce")
    df["latitude"]  = pd.to_numeric(df["latitude"],  errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    df = df.dropna(subset=["created_date", "latitude", "longitude"])
    df = df.drop_duplicates(subset=["unique_key"])
    return df


def clean_crime(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["cmplnt_fr_dt"] = pd.to_datetime(df["cmplnt_fr_dt"], errors="coerce")
    df["latitude"]  = pd.to_numeric(df["latitude"],  errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    df["cmplnt_num"] = df["cmplnt_num"].astype(str)

    text_cols = [
        "ofns_desc", "pd_desc", "crm_atpt_cptd_cd", "law_cat_cd",
        "boro_nm", "loc_of_occur_desc", "prem_typ_desc",
        "juris_desc", "patrol_boro", "station_name"
    ]
    for col in text_cols:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().str.lower()

    df = df.dropna(subset=["cmplnt_fr_dt", "latitude", "longitude"])
    df = df.drop_duplicates(subset=["cmplnt_num"])
    return df


def clean_crime(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["cmplnt_fr_dt"] = pd.to_datetime(df["cmplnt_fr_dt"], errors="coerce")
    df["latitude"]  = pd.to_numeric(df["latitude"],  errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    df["cmplnt_num"] = df["cmplnt_num"].astype(str)
    df["addr_pct_cd"] = df["addr_pct_cd"].astype(str).str.replace(".0", "", regex=False)
    df["ky_cd"] = df["ky_cd"].astype(str).str.replace(".0", "", regex=False)
    df["pd_cd"] = (
        pd.to_numeric(df["pd_cd"], errors="coerce")
        .astype("Int64")
        .astype(str)
        .replace("<NA>", pd.NA)
    )

    text_cols = [
        "ofns_desc", "pd_desc", "crm_atpt_cptd_cd", "law_cat_cd",
        "boro_nm", "loc_of_occur_desc", "prem_typ_desc",
        "juris_desc", "patrol_boro", "station_name"
    ]
    for col in text_cols:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().str.lower()
    df = df.dropna(subset=["cmplnt_fr_dt"])
    df = df.drop_duplicates(subset=["cmplnt_num"])
    return df


def clean_traffic(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in ["yr", "m", "d", "hh", "mm", "vol"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if all(c in df.columns for c in ["yr", "m", "d", "hh", "mm"]):
        df["traffic_datetime"] = pd.to_datetime(
            dict(year=df["yr"], month=df["m"], day=df["d"], hour=df["hh"], minute=df["mm"]),
            errors="coerce"
        )

    df["hour"] = df["hh"]
    for col in ["boro", "street", "fromst", "tost", "direction"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().str.lower()
    return df


def clean_subway(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["transit_timestamp"] = pd.to_datetime(df["transit_timestamp"], errors="coerce")
    df["latitude"]  = pd.to_numeric(df["latitude"],  errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    for col in ["ridership", "transfers"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    df = df.dropna(subset=["latitude", "longitude"])
    return df


def clean_bluesky(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
    for col in ["likes", "replies", "reposts"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
    df["engagement"] = df.get("likes", 0) + df.get("replies", 0) + df.get("reposts", 0)
    for col in ["query", "text", "author", "author_username"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()
    df = df.drop_duplicates(subset=["uri"])
    return df

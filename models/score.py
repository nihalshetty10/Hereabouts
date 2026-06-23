import pandas as pd
from xgboost import XGBClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, roc_auc_score

def train_best(X_train, Y_train, X_test, Y_test, verbose: bool = True):
    """
    Train both XGBoost and RF, return whichever has higher AUC.
    Falls back to RF only if only one class exists in the split.
    """
    neg = (Y_train == 0).sum()
    pos = (Y_train == 1).sum()

    xgb = XGBClassifier(
        n_estimators=500, max_depth=6, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8,
        scale_pos_weight=neg / pos if pos > 0 else 1,
        random_state=42, n_jobs=-1, eval_metric="auc", verbosity=0
    )
    rf = RandomForestClassifier(
        n_estimators=500, max_depth=8, min_samples_leaf=5,
        max_features="sqrt", class_weight="balanced",
        random_state=42, n_jobs=-1
    )

    if len(Y_train.unique()) < 2 or len(Y_test.unique()) < 2:
        if verbose:
            print("  → only one class in split, using RF only")
        rf.fit(X_train, Y_train)
        return rf, 0.5

    xgb.fit(X_train, Y_train)
    rf.fit(X_train, Y_train)

    xgb_auc = roc_auc_score(Y_test, xgb.predict_proba(X_test)[:, 1])
    rf_auc  = roc_auc_score(Y_test, rf.predict_proba(X_test)[:, 1])

    if xgb_auc >= rf_auc:
        if verbose:
            print(f"  → XGBoost wins (AUC {xgb_auc:.3f} vs RF {rf_auc:.3f})")
        return xgb, xgb_auc
    else:
        if verbose:
            print(f"  → RF wins (AUC {rf_auc:.3f} vs XGBoost {xgb_auc:.3f})")
        return rf, rf_auc


def date_split(df: pd.DataFrame, features: list, target_col: str, quantile: float = 0.8):
    split_date = df["prediction_time"].quantile(quantile)
    X_train = df[df["prediction_time"] < split_date][features].fillna(0)
    Y_train = df[df["prediction_time"] < split_date][target_col]
    X_test  = df[df["prediction_time"] >= split_date][features].fillna(0)
    Y_test  = df[df["prediction_time"] >= split_date][target_col]
    return X_train, Y_train, X_test, Y_test

NOISE_COMPLAINT_FEATURES = [
    "noise_last_24h", "complaints_last_24h",
    "crime_last_7d", "crashes_last_7d",
    "persons_injured_last_7d", "pedestrians_injured_last_7d",
    "cyclists_injured_last_7d",
    "subway_ridership_last_24h", "traffic_volume_last_24h",
    "hour", "day_of_week", "is_weekend"
]


def build_noise_complaint_training_data(
    noise_events: pd.DataFrame,
    complaint_events: pd.DataFrame,
    model_table: pd.DataFrame
) -> pd.DataFrame:
    noise_events = noise_events.copy()
    complaint_events = complaint_events.copy()

    noise_events["prediction_time"] = noise_events["created_date"].dt.floor("h")
    complaint_events["prediction_time"] = complaint_events["created_date"].dt.floor("h")

    noise_hourly = (
        noise_events.groupby(["ntaname", "prediction_time"])
        .size().reset_index(name="noise_count")
        .sort_values(["ntaname", "prediction_time"])
    )
    noise_hourly["noise_last_24h"] = (
        noise_hourly.groupby("ntaname")["noise_count"]
        .transform(lambda s: s.rolling(24, min_periods=1).sum())
    )
    noise_hourly["noise_next_2h"] = (
        noise_hourly.groupby("ntaname")["noise_count"]
        .transform(lambda s: s.shift(-1) + s.shift(-2))
    ).fillna(0)
    noise_threshold = noise_hourly["noise_next_2h"].quantile(0.75)
    noise_hourly["active_noise_next_2h"] = (noise_hourly["noise_next_2h"] > noise_threshold).astype(int)
    noise_hourly["hour"]        = noise_hourly["prediction_time"].dt.hour
    noise_hourly["day_of_week"] = noise_hourly["prediction_time"].dt.dayofweek
    noise_hourly["is_weekend"]  = noise_hourly["day_of_week"].isin([5, 6]).astype(int)

    complaint_hourly = (
        complaint_events.groupby(["ntaname", "prediction_time"])
        .size().reset_index(name="complaints_count")
        .sort_values(["ntaname", "prediction_time"])
    )
    complaint_hourly["complaints_last_24h"] = (
        complaint_hourly.groupby("ntaname")["complaints_count"]
        .transform(lambda s: s.rolling(24, min_periods=1).sum())
    )
    complaint_hourly["complaints_next_2h"] = (
        complaint_hourly.groupby("ntaname")["complaints_count"]
        .transform(lambda s: s.shift(-1) + s.shift(-2))
    ).fillna(0)
    complaints_threshold = complaint_hourly["complaints_next_2h"].quantile(0.75)
    complaint_hourly["active_complaints_next_2h"] = (
        complaint_hourly["complaints_next_2h"] > complaints_threshold
    ).astype(int)
    complaint_hourly["hour"]        = complaint_hourly["prediction_time"].dt.hour
    complaint_hourly["day_of_week"] = complaint_hourly["prediction_time"].dt.dayofweek
    complaint_hourly["is_weekend"]  = complaint_hourly["day_of_week"].isin([5, 6]).astype(int)

    train_df = noise_hourly.merge(
        complaint_hourly[["ntaname", "prediction_time", "complaints_last_24h", "active_complaints_next_2h"]],
        on=["ntaname", "prediction_time"], how="inner"
    )

    static = model_table[[
        "ntaname", "crime_last_7d", "crashes_last_7d",
        "persons_injured_last_7d", "pedestrians_injured_last_7d",
        "cyclists_injured_last_7d",
        "subway_ridership_last_24h", "traffic_volume_last_24h"
    ]].copy()
    train_df = train_df.merge(static, on="ntaname", how="left")

    return train_df.sort_values("prediction_time").dropna(subset=NOISE_COMPLAINT_FEATURES)


def train_noise_complaint_models(train_df: pd.DataFrame, model_table: pd.DataFrame):
    targets = {
        "noise_next_2h":      "active_noise_next_2h",
        "complaints_next_2h": "active_complaints_next_2h"
    }
    models = {}
    results = {}

    for target_name, active_col in targets.items():
        print(f"\nTraining: {target_name}")
        print(train_df[active_col].value_counts(normalize=True))

        X_train, Y_train, X_test, Y_test = date_split(train_df, NOISE_COMPLAINT_FEATURES, active_col)
        clf, best_auc = train_best(X_train, Y_train, X_test, Y_test)

        prob = clf.predict_proba(X_test)[:, 1]
        pred = (prob >= 0.5).astype(int)
        print("Accuracy:", accuracy_score(Y_test, pred))
        print("AUC:", best_auc)
        print(classification_report(Y_test, pred))

        models[target_name] = clf
        results[target_name] = {"accuracy": accuracy_score(Y_test, pred), "auc": best_auc}

    X_now = model_table[NOISE_COMPLAINT_FEATURES].fillna(0)
    model_table["prob_active_noise_next_2h"]      = models["noise_next_2h"].predict_proba(X_now)[:, 1]
    model_table["prob_active_complaints_next_2h"] = models["complaints_next_2h"].predict_proba(X_now)[:, 1]

    return models, results, model_table

SUBWAY_FEATURES = [
    "subway_ridership_last_24h", "subway_transfers_last_24h",
    "hour", "day_of_week", "is_weekend"
]

SUBWAY_TARGETS = ["subway_ridership_next_2h", "subway_transfers_next_2h"]


def train_subway_models(model_table_subway: pd.DataFrame):
    model_table_subway = model_table_subway.sort_values("prediction_time").copy()
    model_table_subway[SUBWAY_FEATURES] = model_table_subway[SUBWAY_FEATURES].fillna(0)

    subway_models = {}
    subway_results = {}

    for target in SUBWAY_TARGETS:
        print(f"\nTraining: {target}")

        activity_col = "active_" + target
        threshold = model_table_subway[target].fillna(0).quantile(0.75)
        model_table_subway[activity_col] = (model_table_subway[target].fillna(0) > threshold).astype(int)
        print(model_table_subway[activity_col].value_counts(normalize=True))

        X_train, Y_train, X_test, Y_test = date_split(model_table_subway, SUBWAY_FEATURES, activity_col)

        neg = (Y_train == 0).sum()
        pos = (Y_train == 1).sum()

        xgb = XGBClassifier(
            n_estimators=500, max_depth=6, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.8,
            scale_pos_weight=neg / pos if pos > 0 else 1,
            random_state=42, n_jobs=-1, eval_metric="auc", verbosity=0
        )
        rf = RandomForestClassifier(
            n_estimators=500, max_depth=8, min_samples_leaf=5,
            max_features="sqrt", class_weight="balanced",
            random_state=42, n_jobs=-1
        )

        if len(Y_train.unique()) < 2 or len(Y_test.unique()) < 2:
            print("  → only one class in split, using RF with dummy score")
            rf.fit(X_train, Y_train)
            clf = rf
            prob_all = clf.predict_proba(model_table_subway[SUBWAY_FEATURES].fillna(0))
            prob_col = "prob_active_" + target
            model_table_subway[prob_col] = prob_all[:, 1] if prob_all.shape[1] > 1 else float(Y_train.iloc[0])
            subway_models[target] = clf
            subway_results[target] = {"accuracy": None, "auc": 0.5}
            continue

        clf, best_auc = train_best(X_train, Y_train, X_test, Y_test)

        prob = clf.predict_proba(X_test)[:, 1]
        pred = (prob >= 0.5).astype(int)
        print("Accuracy:", accuracy_score(Y_test, pred))
        print("AUC:", best_auc)
        print(classification_report(Y_test, pred))

        prob_col = "prob_active_" + target
        model_table_subway[prob_col] = clf.predict_proba(
            model_table_subway[SUBWAY_FEATURES].fillna(0)
        )[:, 1]

        subway_models[target] = clf
        subway_results[target] = {"accuracy": accuracy_score(Y_test, pred), "auc": best_auc}

    return subway_models, subway_results, model_table_subway

TRAFFIC_FEATURES = ["traffic_volume_last_24h", "hour", "day_of_week", "is_weekend"]


def train_traffic_model(model_table_traffic: pd.DataFrame):
    model_table_traffic = model_table_traffic.sort_values("prediction_time").copy()
    target = "traffic_volume_next_2h"
    model_table_traffic[target] = model_table_traffic[target].fillna(0)

    traffic_threshold = model_table_traffic[target].quantile(0.75)
    model_table_traffic["high_traffic_volume_next_2h"] = (
        model_table_traffic[target] >= traffic_threshold
    ).astype(int)

    print("High traffic threshold:", traffic_threshold)
    print(model_table_traffic["high_traffic_volume_next_2h"].value_counts(normalize=True))

    X_train, Y_train, X_test, Y_test = date_split(
        model_table_traffic, TRAFFIC_FEATURES, "high_traffic_volume_next_2h"
    )

    clf, best_auc = train_best(X_train, Y_train, X_test, Y_test)

    prob = clf.predict_proba(X_test)[:, 1]
    pred = (prob >= 0.5).astype(int)
    print("Accuracy:", accuracy_score(Y_test, pred))
    print("AUC:", best_auc)
    print(classification_report(Y_test, pred))

    model_table_traffic["prob_high_traffic_volume_next_2h"] = clf.predict_proba(
        model_table_traffic[TRAFFIC_FEATURES].fillna(0)
    )[:, 1]

    return clf, {"accuracy": accuracy_score(Y_test, pred), "auc": best_auc}, model_table_traffic

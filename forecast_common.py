"""Shared feature engineering, model definitions, scoring, and persistence helpers
used by both train_model.py (fit + save) and predict_model.py (load + evaluate).
"""

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import RidgeCV
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

SEED = 0


def yoy(s: pd.Series) -> pd.Series:
    return 100 * (s / s.shift(12) - 1)


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Every feature at row t uses only data observed at or before month t."""
    infl = yoy(df["us_cpi"])
    f = pd.DataFrame(index=df.index)
    f["infl_yoy"] = infl
    # Short-run momentum: 1- and 3-month CPI changes, annualized
    f["infl_1m_ann"] = 100 * ((df["us_cpi"] / df["us_cpi"].shift(1)) ** 12 - 1)
    f["infl_3m_ann"] = 100 * ((df["us_cpi"] / df["us_cpi"].shift(3)) ** 4 - 1)
    for lag in (3, 6, 12):
        f[f"infl_yoy_lag{lag}"] = infl.shift(lag)
    f["unemp"] = df["us_unemployment_pct"]
    f["unemp_chg12"] = df["us_unemployment_pct"].diff(12)
    f["fedfunds"] = df["us_fed_funds_pct"]
    f["fedfunds_chg12"] = df["us_fed_funds_pct"].diff(12)
    f["real_rate"] = df["us_fed_funds_pct"] - infl
    f["dgs10"] = df["us_10y_treasury_pct"]
    f["term_spread"] = df["us_10y_treasury_pct"] - df["us_fed_funds_pct"]
    f["indpro_yoy"] = yoy(df["us_industrial_production"])
    return f


def make_models() -> dict:
    return {
        "ridge": make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-2, 3, 20))),
        "random_forest": RandomForestRegressor(
            n_estimators=300, min_samples_leaf=5, max_features=0.5, n_jobs=-1, random_state=SEED
        ),
        "grad_boost": HistGradientBoostingRegressor(
            max_iter=300, learning_rate=0.05, max_depth=3, min_samples_leaf=20, random_state=SEED
        ),
    }


def score(pred_change: pd.DataFrame, actual_change: pd.Series) -> pd.DataFrame:
    err = pred_change.sub(actual_change, axis=0)
    out = pd.DataFrame({"MAE": err.abs().mean(), "RMSE": np.sqrt((err**2).mean())})
    out["RMSE_vs_no_change"] = out["RMSE"] / out.loc["no_change", "RMSE"]
    return out.sort_values("RMSE")


def load_data_and_features(data_path: str, horizon: int):
    """Read the merged CSV, build features, and return (X_full, X_all, y_all) where
    X_full retains all rows (for the latest forecast) and X_all/y_all are the subset
    with complete features and a realized target for the given horizon.
    """
    df = pd.read_csv(data_path, parse_dates=["date"], index_col="date")
    X = build_features(df)
    target = X["infl_yoy"].shift(-horizon) - X["infl_yoy"]  # change in YoY inflation over h months
    usable = X.notna().all(axis=1) & target.notna()
    return X, X[usable], target[usable]


def save_models(models: dict, feature_names: list, horizon: int, path: Path) -> None:
    """Persist fitted models + metadata needed to reproduce features/target at inference time."""
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"models": models, "feature_names": feature_names, "horizon": horizon}, path)
    print(f"\nSaved models to {path}")


def load_models(path: Path) -> dict:
    bundle = joblib.load(path)
    print(f"Loaded models from {path} (horizon={bundle['horizon']}, "
          f"features={len(bundle['feature_names'])})")
    return bundle

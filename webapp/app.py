"""Minimal Flask web app that serves US inflation forecasts from a saved model bundle.

Reuses forecast_common.py (same feature engineering as train_model.py / predict_model.py)
so the served predictions are produced identically to the CLI scripts.

Two ways to get a forecast:
  1. GET /api/forecast        -> uses the configured --data file on the server.
  2. POST /api/forecast/upload (multipart file field "file") or the web form at "/"
     -> uses an uploaded CSV instead, with the same saved model (no retraining).

The uploaded CSV must have the same columns/format as data/fred_monthly_merged.csv
(a "date" column plus the columns forecast_common.build_features expects).

Usage:
  python webapp/app.py --model ../output/models_h12.joblib --data ../data/fred_monthly_merged.csv
  # then open http://127.0.0.1:5000/

Environment variables (used if CLI args are omitted):
  MODEL_PATH, DATA_PATH, PORT
"""

import argparse
import io
import os
import sys
from pathlib import Path

import pandas as pd
from flask import Flask, jsonify, render_template, request

# Allow running this file directly (python webapp/app.py) by adding the repo root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from forecast_common import build_features, load_models, score  # noqa: E402

FRONTEND_DIR = Path(__file__).resolve().parent / "frontend"
app = Flask(
    __name__,
    template_folder=str(FRONTEND_DIR),
    static_folder=str(FRONTEND_DIR / "static"),
)

STATE = {"model_path": None, "data_path": None}


def _bundle():
    return load_models(Path(STATE["model_path"]))


def forecast_from_dataframe(df: pd.DataFrame, bundle: dict) -> dict:
    """Core forecasting logic, parameterized by an already-loaded dataframe and model bundle
    so it can be reused for both the configured server-side data file and uploaded CSVs."""
    models, h = bundle["models"], bundle["horizon"]

    X = build_features(df)
    target = X["infl_yoy"].shift(-h) - X["infl_yoy"]
    usable = X.notna().all(axis=1) & target.notna()
    X_all, y_all = X[usable], target[usable]

    if X_all.empty:
        raise ValueError(
            "No usable rows: need at least ~24 months of history with all required "
            "columns (us_cpi, us_unemployment_pct, us_fed_funds_pct, "
            "us_industrial_production, us_10y_treasury_pct) and no gaps."
        )

    preds = pd.DataFrame({name: model.predict(X_all) for name, model in models.items()}, index=X_all.index)
    preds["no_change"] = 0.0
    eval_table = score(preds, y_all).round(3)

    latest = X[X.notna().all(axis=1)].iloc[[-1]]
    origin = latest.index[0]
    current_yoy = float(latest["infl_yoy"].iloc[0])
    target_month = origin + pd.DateOffset(months=h)

    forecasts = []
    for name, model in models.items():
        level = current_yoy + float(model.predict(latest)[0])
        forecasts.append({"model": name, "forecast_yoy_pct": round(level, 2)})

    return {
        "horizon_months": h,
        "origin": origin.strftime("%Y-%m"),
        "current_yoy_pct": round(current_yoy, 2),
        "target_month": target_month.strftime("%Y-%m"),
        "forecasts": forecasts,
        "evaluation": eval_table.reset_index().rename(columns={"index": "model"}).to_dict(orient="records"),
        "rows_used": int(len(X_all)),
    }


def get_forecast() -> dict:
    """Forecast using the server-configured --data file."""
    df = pd.read_csv(STATE["data_path"], parse_dates=["date"], index_col="date")
    return forecast_from_dataframe(df, _bundle())


def get_forecast_from_upload(file_storage) -> dict:
    """Forecast using an uploaded CSV instead of the server's configured data file."""
    raw = file_storage.read()
    df = pd.read_csv(io.BytesIO(raw), parse_dates=["date"], index_col="date")
    result = forecast_from_dataframe(df, _bundle())
    result["source"] = f"uploaded:{file_storage.filename}"
    return result


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/forecast")
def api_forecast():
    try:
        return jsonify(get_forecast())
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:  # noqa: BLE001
        return jsonify({"error": str(e)}), 500


@app.route("/api/forecast/upload", methods=["POST"])
def api_forecast_upload():
    if "file" not in request.files or request.files["file"].filename == "":
        return jsonify({"error": "No file uploaded. Send multipart/form-data with field 'file'."}), 400
    file = request.files["file"]
    if not file.filename.lower().endswith(".csv"):
        return jsonify({"error": "Only .csv files are supported."}), 400
    try:
        return jsonify(get_forecast_from_upload(file))
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:  # noqa: BLE001
        return jsonify({"error": f"Could not process uploaded CSV: {e}"}), 400


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", default=os.environ.get("MODEL_PATH", "output/models_h12.joblib"),
                         help="Path to a saved model bundle (joblib) created by train_model.py --save-model")
    parser.add_argument("--data", default=os.environ.get("DATA_PATH", "data/fred_monthly_merged.csv"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", 5000)))
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    STATE["model_path"] = str((repo_root / args.model).resolve()) if not Path(args.model).is_absolute() else args.model
    STATE["data_path"] = str((repo_root / args.data).resolve()) if not Path(args.data).is_absolute() else args.data

    print(f"Model: {STATE['model_path']}")
    print(f"Data:  {STATE['data_path']}")
    app.run(host="127.0.0.1", port=args.port, debug=args.debug)


if __name__ == "__main__":

    main()

"""Minimal Flask web app that serves US inflation forecasts from a saved model bundle.

Reuses forecast_common.py (same feature engineering as train_model.py / predict_model.py)
so the served predictions are produced identically to the CLI scripts.

Usage:
  python webapp/app.py --model ../output/models_h12.joblib --data ../data/fred_monthly_merged.csv
  # then open http://127.0.0.1:5000/

Environment variables (used if CLI args are omitted):
  MODEL_PATH, DATA_PATH, PORT
"""

import argparse
import os
import sys
from pathlib import Path

import pandas as pd
from flask import Flask, jsonify, render_template

# Allow running this file directly (python webapp/app.py) by adding the repo root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from forecast_common import build_features, load_models, score  # noqa: E402

app = Flask(__name__)

STATE = {"model_path": None, "data_path": None}


def get_forecast():
    bundle = load_models(Path(STATE["model_path"]))
    models, h = bundle["models"], bundle["horizon"]

    df = pd.read_csv(STATE["data_path"], parse_dates=["date"], index_col="date")
    X = build_features(df)
    target = X["infl_yoy"].shift(-h) - X["infl_yoy"]
    usable = X.notna().all(axis=1) & target.notna()
    X_all, y_all = X[usable], target[usable]

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
    }


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

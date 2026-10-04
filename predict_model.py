"""Load a previously saved inflation forecasting model bundle and use it for
evaluation and the latest forecast, without retraining.

The model bundle is produced by train_model.py --save-model ...

Usage:
  python predict_model.py --load-model output/models_h12.joblib
  python predict_model.py --load-model output/models_h12.joblib --data data/fred_monthly_merged.csv
"""

import argparse
from pathlib import Path

import pandas as pd

from forecast_common import build_features, load_models, score


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", default="data/fred_monthly_merged.csv")
    parser.add_argument("--load-model", required=True,
                         help="Path to a saved model bundle (joblib) created by train_model.py --save-model")
    args = parser.parse_args()

    bundle = load_models(Path(args.load_model))
    models, h = bundle["models"], bundle["horizon"]

    df = pd.read_csv(args.data, parse_dates=["date"], index_col="date")
    X = build_features(df)
    target = X["infl_yoy"].shift(-h) - X["infl_yoy"]
    usable = X.notna().all(axis=1) & target.notna()
    X_all, y_all = X[usable], target[usable]

    preds = pd.DataFrame({name: model.predict(X_all) for name, model in models.items()}, index=X_all.index)
    preds["no_change"] = 0.0
    print(f"Evaluation of loaded models on {args.data} "
          f"({X_all.index.min():%Y-%m} .. {X_all.index.max():%Y-%m}):")
    print(score(preds, y_all).round(3).to_string())

    latest = X[X.notna().all(axis=1)].iloc[[-1]]
    print(f"\nLatest forecast (origin {latest.index[0]:%Y-%m}, current YoY {latest['infl_yoy'].iloc[0]:.2f}%):")
    for name, model in models.items():
        level = latest["infl_yoy"].iloc[0] + model.predict(latest)[0]
        print(f"  {name:14s} -> {level:.2f}% YoY in {latest.index[0] + pd.DateOffset(months=h):%Y-%m}")


if __name__ == "__main__":
    main()

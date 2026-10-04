"""Train and evaluate US CPI inflation forecasting models, then optionally save them.

Reads data/fred_monthly_merged.csv (produced by fetch_economic_data.py), builds lagged
macro features, and evaluates models with an expanding-window walk-forward backtest:
at each yearly forecast origin T, models are trained only on data whose targets were
already known at T, then predict the next 12 origins. This avoids look-ahead leakage.

Models are trained to predict the *change* in YoY inflation over the horizon
(infl[t+h] - infl[t]) rather than its level, so tree models are not limited to the
range of levels seen in training and the "no change" baseline is simply 0.

After backtesting, final models are fit on all available data and (optionally) saved
to disk with --save-model for later reuse via predict_model.py.

Usage:
  python train_model.py                                    # 12-month horizon, test from 2000
  python train_model.py --horizon 6 --test-start 2010-01-01
  python train_model.py --horizon 12 --save-model output/models_h12.joblib
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.inspection import permutation_importance

from forecast_common import SEED, load_data_and_features, make_models, save_models, score


def walk_forward(X: pd.DataFrame, y: pd.Series, horizon: int, test_start: str):
    """Refit every 12 months on an expanding window; return out-of-sample predictions."""
    origins = X.index[X.index >= test_start]
    preds = {name: pd.Series(np.nan, index=origins) for name in make_models()}
    preds["no_change"] = pd.Series(0.0, index=origins)

    for block_start in origins[::12]:
        # Target of row t is realized at t + horizon, so at origin T we can only train
        # on rows with t + horizon <= T.
        train_end = block_start - pd.DateOffset(months=horizon)
        train = X.index <= train_end
        block = origins[(origins >= block_start) & (origins < block_start + pd.DateOffset(months=12))]
        for name, model in make_models().items():
            model.fit(X[train], y[train])
            preds[name][block] = model.predict(X.loc[block])
    return pd.DataFrame(preds)


def plot(pred: pd.DataFrame, infl: pd.Series, target: pd.Series, h: int, out: Path) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("\n(matplotlib not installed; skipping plot)")
        return
    out.mkdir(parents=True, exist_ok=True)
    # Convert predicted changes back to inflation levels, plotted at the target date
    shift = pd.DateOffset(months=h)
    fig, ax = plt.subplots(figsize=(11, 5))
    actual_level = infl[pred.index] + target[pred.index]
    ax.plot(pred.index + shift, actual_level, color="black", lw=2, label="actual")
    for name in ["no_change", "ridge", "grad_boost"]:
        ax.plot(pred.index + shift, infl[pred.index] + pred[name], lw=1, label=f"{name} forecast")
    ax.axhline(0, color="grey", lw=0.5)
    ax.set_ylabel("US CPI inflation, YoY %")
    ax.set_title(f"{h}-month-ahead inflation forecasts (walk-forward, out-of-sample)")
    ax.legend()
    fig.tight_layout()
    path = out / f"inflation_forecast_h{h}.png"
    fig.savefig(path, dpi=120)
    print(f"\nSaved {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", default="data/fred_monthly_merged.csv")
    parser.add_argument("--horizon", type=int, default=12, help="Forecast horizon in months (default: 12)")
    parser.add_argument("--test-start", default="2000-01-01", help="First forecast origin of the backtest")
    parser.add_argument("--out", default="output", help="Directory for the plot (default: output)")
    parser.add_argument("--save-model", default=None,
                         help="Path to save fitted models (joblib), e.g. output/models_h12.joblib")
    args = parser.parse_args()
    h = args.horizon

    X, X_all, y_all = load_data_and_features(args.data, h)
    print(f"Samples: {len(X_all)} months, {X_all.index.min():%Y-%m} .. {X_all.index.max():%Y-%m}; "
          f"{X_all.shape[1]} features; horizon {h} months")

    pred = walk_forward(X_all, y_all, h, args.test_start)
    actual = y_all[pred.index]

    print(f"\nOut-of-sample error, forecast origins {pred.index.min():%Y-%m} .. {pred.index.max():%Y-%m}"
          f" (percentage points of YoY inflation)")
    print(score(pred, actual).round(3).to_string())
    covid = pred.index >= "2020-01-01"
    if covid.any() and (~covid).any():
        print("\nRMSE by period:")
        print(pd.DataFrame({
            "before_2020": score(pred[~covid], actual[~covid])["RMSE"],
            "2020_onward": score(pred[covid], actual[covid])["RMSE"],
        }).round(3).to_string())

    # Which features drive the gradient-boosting model, measured on the most recent 10 years
    # of the backtest with a model trained only on data before them.
    split = X_all.index.max() - pd.DateOffset(years=10)
    fit_rows = X_all.index <= split - pd.DateOffset(months=h)
    model = make_models()["grad_boost"].fit(X_all[fit_rows], y_all[fit_rows])
    imp = permutation_importance(
        model, X_all[X_all.index > split], y_all[X_all.index > split],
        n_repeats=20, random_state=SEED, n_jobs=-1, scoring="neg_root_mean_squared_error",
    )
    print(f"\nPermutation importance (grad_boost, eval after {split:%Y-%m}, RMSE increase):")
    print(pd.Series(imp.importances_mean, index=X_all.columns).sort_values(ascending=False).round(3).head(8).to_string())

    # Forecast from the latest month with complete features, using a model trained on all data
    latest = X[X.notna().all(axis=1)].iloc[[-1]]
    print(f"\nLatest forecast (origin {latest.index[0]:%Y-%m}, current YoY {latest['infl_yoy'].iloc[0]:.2f}%):")
    final_models = {}
    for name, model in make_models().items():
        model.fit(X_all, y_all)
        final_models[name] = model
        level = latest["infl_yoy"].iloc[0] + model.predict(latest)[0]
        print(f"  {name:14s} -> {level:.2f}% YoY in {latest.index[0] + pd.DateOffset(months=h):%Y-%m}")

    if args.save_model:
        save_models(final_models, list(X_all.columns), h, Path(args.save_model))

    plot(pred, X_all["infl_yoy"], y_all, h, Path(args.out))


if __name__ == "__main__":
    main()

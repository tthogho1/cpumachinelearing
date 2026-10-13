"""Minimal Flask API + static HTML form that predicts Telco customer churn from the
model bundle saved by train_churn.py (output/churn_xgb.joblib).

Endpoints:
  GET  /             -> input form (webappchrun/static/index.html)
  GET  /api/schema   -> input fields (numeric ranges / categorical choices) used to build the form
  POST /api/predict  -> JSON body with the 19 input fields -> churn probability

The saved model is a sklearn Pipeline (StandardScaler + OneHotEncoder + XGBoost), so it
takes the raw columns of WA_Fn-UseC_-Telco-Customer-Churn.csv minus customerID/Churn.
Categorical values are validated here because the encoder uses handle_unknown="ignore"
and would otherwise silently treat a typo as "no information".

Usage:
  python train_churn.py               # creates output/churn_xgb.joblib
  python webappchrun/app.py           # then open http://127.0.0.1:5001/

Environment variables (used if CLI args are omitted):
  MODEL_PATH, PORT, HOST
"""

import argparse
import os
from pathlib import Path

import joblib
import pandas as pd
from flask import Flask, jsonify, request, send_from_directory

STATIC_DIR = Path(__file__).resolve().parent / "static"
app = Flask(__name__, static_folder=None)

STATE = {"model": None, "model_path": None}

YES_NO = ["Yes", "No"]
INTERNET_ADDON = ["Yes", "No", "No internet service"]

# Input fields in display order. "num" fields are floats within [min, max];
# "cat" fields must be one of the listed values (exact spelling used in training).
FIELDS = [
    {"name": "gender", "label": "Gender", "type": "cat", "choices": ["Female", "Male"]},
    {"name": "SeniorCitizen", "label": "Senior citizen", "type": "cat", "choices": [0, 1]},
    {"name": "Partner", "label": "Partner", "type": "cat", "choices": YES_NO},
    {"name": "Dependents", "label": "Dependents", "type": "cat", "choices": YES_NO},
    {"name": "tenure", "label": "Tenure (months)", "type": "num", "min": 0, "max": 72, "step": 1},
    {"name": "PhoneService", "label": "Phone service", "type": "cat", "choices": YES_NO},
    {"name": "MultipleLines", "label": "Multiple lines", "type": "cat",
     "choices": ["Yes", "No", "No phone service"]},
    {"name": "InternetService", "label": "Internet service", "type": "cat",
     "choices": ["DSL", "Fiber optic", "No"]},
    {"name": "OnlineSecurity", "label": "Online security", "type": "cat", "choices": INTERNET_ADDON},
    {"name": "OnlineBackup", "label": "Online backup", "type": "cat", "choices": INTERNET_ADDON},
    {"name": "DeviceProtection", "label": "Device protection", "type": "cat", "choices": INTERNET_ADDON},
    {"name": "TechSupport", "label": "Tech support", "type": "cat", "choices": INTERNET_ADDON},
    {"name": "StreamingTV", "label": "Streaming TV", "type": "cat", "choices": INTERNET_ADDON},
    {"name": "StreamingMovies", "label": "Streaming movies", "type": "cat", "choices": INTERNET_ADDON},
    {"name": "Contract", "label": "Contract", "type": "cat",
     "choices": ["Month-to-month", "One year", "Two year"]},
    {"name": "PaperlessBilling", "label": "Paperless billing", "type": "cat", "choices": YES_NO},
    {"name": "PaymentMethod", "label": "Payment method", "type": "cat",
     "choices": ["Electronic check", "Mailed check", "Bank transfer (automatic)", "Credit card (automatic)"]},
    {"name": "MonthlyCharges", "label": "Monthly charges", "type": "num", "min": 0, "max": 200, "step": 0.01},
    {"name": "TotalCharges", "label": "Total charges (blank = monthly x tenure)", "type": "num",
     "min": 0, "max": 20000, "step": 0.01, "optional": True},
]

THRESHOLD = 0.5


def parse_input(payload: dict) -> dict:
    """Validate the JSON body and return one row of model input. Raises ValueError."""
    row, errors = {}, []
    for f in FIELDS:
        name, value = f["name"], payload.get(f["name"])
        if f["type"] == "num":
            if value is None or value == "":
                if f.get("optional"):
                    continue
                errors.append(f"{name}: required")
                continue
            try:
                num = float(value)
            except (TypeError, ValueError):
                errors.append(f"{name}: must be a number")
                continue
            if not f["min"] <= num <= f["max"]:
                errors.append(f"{name}: must be between {f['min']} and {f['max']}")
                continue
            row[name] = num
        else:
            # SeniorCitizen choices are ints; accept "0"/"1" from form posts too
            match = next((c for c in f["choices"] if str(c) == str(value)), None)
            if match is None:
                errors.append(f"{name}: must be one of {f['choices']}")
                continue
            row[name] = match
    if errors:
        raise ValueError("; ".join(errors))

    # Training dropped rows with blank TotalCharges (new customers); approximate it instead
    if "TotalCharges" not in row:
        row["TotalCharges"] = row["MonthlyCharges"] * row["tenure"]
    return row


@app.route("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")


@app.route("/api/schema")
def api_schema():
    return jsonify({"fields": FIELDS, "threshold": THRESHOLD})


@app.route("/api/predict", methods=["POST"])
def api_predict():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Send a JSON object with the input fields."}), 400
    try:
        row = parse_input(payload)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    prob = float(STATE["model"].predict_proba(pd.DataFrame([row]))[0, 1])
    return jsonify({
        "churn_probability": round(prob, 4),
        "churn": prob >= THRESHOLD,
        "threshold": THRESHOLD,
        "total_charges_used": round(row["TotalCharges"], 2),
    })


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", default=os.environ.get("MODEL_PATH", "output/churn_xgb.joblib"),
                         help="Path to the model saved by train_churn.py")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", 5001)))
    parser.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"),
                         help="Bind address (use 0.0.0.0 inside Docker)")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    model_path = Path(args.model) if Path(args.model).is_absolute() else (repo_root / args.model).resolve()
    STATE["model_path"] = str(model_path)
    STATE["model"] = joblib.load(model_path)

    print(f"Model: {STATE['model_path']}")
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()

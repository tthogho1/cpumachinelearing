# --- Stage 1: build the React (Vite) frontend -------------------------------
FROM node:20-slim AS frontend-build
WORKDIR /app/webapp/frontend
COPY webapp/frontend/package.json webapp/frontend/package-lock.json ./
RUN npm ci
COPY webapp/frontend/ ./
RUN npm run build

# --- Stage 2: Python runtime --------------------------------------------------
FROM python:3.12-slim AS runtime
WORKDIR /app

# System deps for scikit-learn/matplotlib wheels are generally not required on slim,
# but keep build tools available in case a source build is needed.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# App code
COPY fetch_economic_data.py forecast_common.py train_model.py predict_model.py ./
COPY webapp/app.py webapp/app.py
COPY data/ data/

# Built frontend from stage 1
COPY --from=frontend-build /app/webapp/frontend/dist webapp/frontend/dist

# Model bundle(s) and plots live here; mounted as a volume in docker-compose
RUN mkdir -p output

ENV HOST=0.0.0.0 \
    PORT=5000 \
    MODEL_PATH=output/models_h12.joblib \
    DATA_PATH=data/fred_monthly_merged.csv

EXPOSE 5000

CMD ["python", "webapp/app.py"]

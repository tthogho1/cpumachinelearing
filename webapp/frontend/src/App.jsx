import ServerForecastPanel from "./ServerForecastPanel.jsx";
import UploadForecastPanel from "./UploadForecastPanel.jsx";

export default function App() {
  return (
    <div className="container">
      <h1>US CPI Inflation Forecast</h1>
      <p className="muted">
        Served from a saved model bundle (train_model.py --save-model), via
        forecast_common.py feature engineering.
      </p>
      <ServerForecastPanel />
      <UploadForecastPanel />
    </div>
  );
}

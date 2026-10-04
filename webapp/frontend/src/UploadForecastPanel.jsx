import { useRef, useState } from "react";
import ForecastResult from "./ForecastResult.jsx";

export default function UploadForecastPanel() {
  const fileInputRef = useRef(null);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    const file = fileInputRef.current?.files?.[0];
    if (!file) return;

    setError(null);
    setData(null);
    setLoading(true);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch("/api/forecast/upload", { method: "POST", body: formData });
      const json = await res.json();
      if (json.error) {
        setError(json.error);
      } else {
        setData(json);
      }
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="panel">
      <h2>Forecast from an uploaded CSV</h2>
      <p className="muted">
        CSV must have a <code>date</code> column plus the columns the model expects
        (us_cpi, us_unemployment_pct, us_fed_funds_pct, us_industrial_production,
        us_10y_treasury_pct), same format as data/fred_monthly_merged.csv. The saved model is
        reused as-is (no retraining).
      </p>
      <form onSubmit={handleSubmit}>
        <input type="file" accept=".csv" ref={fileInputRef} required />
        <button type="submit" disabled={loading}>
          {loading ? "Processing…" : "Forecast"}
        </button>
      </form>
      {error && <div className="error">Error: {error}</div>}
      <ForecastResult data={data} />
    </div>
  );
}

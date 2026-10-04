import { useEffect, useState } from "react";
import ForecastResult from "./ForecastResult.jsx";

export default function ServerForecastPanel() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/forecast")
      .then((r) => r.json())
      .then((json) => {
        if (json.error) {
          setError(json.error);
        } else {
          setData(json);
        }
      })
      .catch((err) => setError(String(err)))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="panel">
      <h2>Server data forecast</h2>
      {error && <div className="error">Error: {error}</div>}
      {loading && !error && <p>Loading…</p>}
      <ForecastResult data={data} />
    </div>
  );
}

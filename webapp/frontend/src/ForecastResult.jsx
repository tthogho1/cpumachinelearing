export default function ForecastResult({ data }) {
  if (!data) return null;

  return (
    <div>
      <p>
        <strong>Origin:</strong> {data.origin} &nbsp;
        <strong>Current YoY:</strong> {data.current_yoy_pct}% &nbsp;
        <strong>Horizon:</strong> {data.horizon_months} months &nbsp;
        <strong>Target month:</strong> {data.target_month} &nbsp;
        <strong>Rows used:</strong> {data.rows_used}
        {data.source && (
          <>
            {" "}&nbsp;<strong>Source:</strong> {data.source}
          </>
        )}
      </p>

      <h3>Forecasts</h3>
      <table>
        <thead>
          <tr>
            <th>Model</th>
            <th>Forecast YoY %</th>
          </tr>
        </thead>
        <tbody>
          {data.forecasts.map((f) => (
            <tr key={f.model}>
              <td>{f.model}</td>
              <td>{f.forecast_yoy_pct}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3>Evaluation</h3>
      <table>
        <thead>
          <tr>
            <th>Model</th>
            <th>MAE</th>
            <th>RMSE</th>
            <th>RMSE vs no-change</th>
          </tr>
        </thead>
        <tbody>
          {data.evaluation.map((row) => (
            <tr key={row.model}>
              <td>{row.model}</td>
              <td>{row.MAE}</td>
              <td>{row.RMSE}</td>
              <td>{row.RMSE_vs_no_change}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

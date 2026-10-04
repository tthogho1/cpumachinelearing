function renderForecast(containerId, data) {
  let html = `<p><strong>Origin:</strong> ${data.origin} &nbsp; `
           + `<strong>Current YoY:</strong> ${data.current_yoy_pct}% &nbsp; `
           + `<strong>Horizon:</strong> ${data.horizon_months} months &nbsp; `
           + `<strong>Target month:</strong> ${data.target_month} &nbsp; `
           + `<strong>Rows used:</strong> ${data.rows_used}</p>`;

  html += "<h3>Forecasts</h3><table><tr><th>Model</th><th>Forecast YoY %</th></tr>";
  for (const f of data.forecasts) {
    html += `<tr><td>${f.model}</td><td>${f.forecast_yoy_pct}</td></tr>`;
  }
  html += "</table>";

  html += "<h3>Evaluation</h3><table><tr><th>Model</th><th>MAE</th><th>RMSE</th><th>RMSE vs no-change</th></tr>";
  for (const row of data.evaluation) {
    html += `<tr><td>${row.model}</td><td>${row.MAE}</td><td>${row.RMSE}</td><td>${row.RMSE_vs_no_change}</td></tr>`;
  }
  html += "</table>";
  document.getElementById(containerId).innerHTML = html;
}

fetch("/api/forecast")
  .then(r => r.json())
  .then(data => {
    if (data.error) {
      document.getElementById("error").textContent = "Error: " + data.error;
      document.getElementById("content").textContent = "";
      return;
    }
    renderForecast("content", data);
  })
  .catch(err => {
    document.getElementById("error").textContent = "Fetch failed: " + err;
  });

document.getElementById("upload-form").addEventListener("submit", (e) => {
  e.preventDefault();
  document.getElementById("upload-error").textContent = "";
  document.getElementById("upload-content").textContent = "Processing…";

  const fileInput = document.getElementById("csv-file");
  if (!fileInput.files.length) return;

  const formData = new FormData();
  formData.append("file", fileInput.files[0]);

  fetch("/api/forecast/upload", { method: "POST", body: formData })
    .then(r => r.json())
    .then(data => {
      if (data.error) {
        document.getElementById("upload-error").textContent = "Error: " + data.error;
        document.getElementById("upload-content").textContent = "";
        return;
      }
      renderForecast("upload-content", data);
    })
    .catch(err => {
      document.getElementById("upload-error").textContent = "Upload failed: " + err;
      document.getElementById("upload-content").textContent = "";
    });
});

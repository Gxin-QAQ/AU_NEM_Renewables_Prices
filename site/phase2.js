(() => {
  const names = {
    seasonal_naive: "168-hour seasonal naive",
    seasonal_frequency: "Seasonal frequency",
    statistical_control: "Price / event / demand control",
    renewable_candidate: "Control + wind & solar",
  };
  const period = document.getElementById("risk-period");
  const region = document.getElementById("risk-region");
  function render() {
    const rows = window.NEM_PHASE2[period.value].filter(row => row.scope === region.value);
    const control = rows.find(row => row.model === "statistical_control");
    const candidate = rows.find(row => row.model === "renewable_candidate");
    document.getElementById("risk-improvement").textContent =
      ((1 - candidate.brier_score / control.brier_score) * 100).toFixed(2) + "%";
    document.getElementById("risk-bias").textContent = candidate.calibration_bias_pp.toFixed(2) + " pp";
    document.getElementById("risk-count").textContent = candidate.nobs.toLocaleString("en-GB");
    document.getElementById("risk-exposure-prob").textContent =
      (candidate.mean_predicted * 100).toFixed(2) + "%";
    document.getElementById("risk-exposure-observed").textContent =
      (candidate.observed_rate * 100).toFixed(2) + "%";
    const exposureRegion = region.value === "pooled" ? "all four regions" : region.value;
    document.getElementById("risk-exposure-context").textContent =
      `For ${exposureRegion} in ${period.options[period.selectedIndex].text}, compare the average forecast probability with the observed share of region-hours containing a negative five-minute price.`;
    document.getElementById("risk-caption").textContent =
      `${period.options[period.selectedIndex].text} · ${region.options[region.selectedIndex].text}`;
    const body = document.getElementById("risk-rows");
    body.replaceChildren();
    for (const row of rows) {
      const tr = document.createElement("tr");
      if (row.model === "renewable_candidate") tr.className = "risk-candidate";
      for (const value of [names[row.model], row.brier_score.toFixed(5),
        (row.mean_predicted * 100).toFixed(2) + "%", (row.observed_rate * 100).toFixed(2) + "%"]) {
        const td = document.createElement("td");
        td.textContent = value;
        tr.appendChild(td);
      }
      body.appendChild(tr);
    }
    const image = document.getElementById("risk-calibration");
    image.src = `data/${period.value}_calibration.png`;
    image.alt = `${period.value} calibration curves across all four regions and models`;
    document.getElementById("risk-calibration-caption").textContent =
      `${period.options[period.selectedIndex].text}: pooled calibration across all four regions; this figure does not change with the region selector. Each point uses the bin's actual mean predicted probability.`;
  }
  period.addEventListener("change", render);
  region.addEventListener("change", render);
  render();
})();

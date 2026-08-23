"use strict";

const COLORS = { navy: "#102a43", blue: "#1677c8", teal: "#008f83", grey: "#6b7f91", grid: "#d9e2ec", muted: "#486581" };
const number = new Intl.NumberFormat("en-AU", { maximumFractionDigits: 2, minimumFractionDigits: 2 });
let payload, selectedRegion = "NSW1";
const signed = (value, unit) => `${number.format(Math.abs(value))} ${unit} ${value < 0 ? "lower" : "higher"}`;

function renderHeadline(data) {
  const { priceLevel, negativePriceProbabilityPp, intrahourVolatility } = data.headline;
  document.querySelector("#metric-price").textContent = signed(priceLevel.estimate, "A$/MWh");
  document.querySelector("#metric-price-se").textContent = `SE A$${number.format(priceLevel.stdError)} · ${priceLevel.nobs.toLocaleString("en-AU")} region-hours`;
  document.querySelector("#metric-negative").textContent = signed(negativePriceProbabilityPp.estimate, "pp");
  document.querySelector("#metric-negative-se").textContent = `SE ${number.format(negativePriceProbabilityPp.stdError)} pp · any negative 5-minute price`;
  document.querySelector("#metric-volatility").textContent = signed(intrahourVolatility.estimate, "A$/MWh");
  document.querySelector("#metric-volatility-se").textContent = `SE A$${number.format(intrahourVolatility.stdError)} · within-hour 5-minute SD`;
}

function canvasFor(id, height) {
  const host = document.querySelector(`#${id}`); host.replaceChildren();
  const canvas = document.createElement("canvas"), width = Math.max(280, host.clientWidth || 700), ratio = window.devicePixelRatio || 1;
  canvas.width = width * ratio; canvas.height = height * ratio; canvas.style.cssText = `width:${width}px;height:${height}px`; canvas.setAttribute("aria-hidden", "true"); host.append(canvas);
  const ctx = canvas.getContext("2d"); ctx.scale(ratio, ratio); ctx.font = "12px Inter, system-ui, sans-serif";
  return { ctx, width, height };
}

function line(ctx, x1, y1, x2, y2, color, width = 1) { ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.strokeStyle = color; ctx.lineWidth = width; ctx.stroke(); }
function yScale(value, minimum, maximum, top, bottom) { return bottom - ((value - minimum) / (maximum - minimum || 1)) * (bottom - top); }

function renderTrend() {
  const rows = payload.trends.filter((row) => row.region === selectedRegion), { ctx, width, height } = canvasFor("trend-chart", 390);
  const left = 62, right = 64, top = 45, bottom = 52, chartWidth = width - left - right, chartHeight = height - top - bottom;
  const prices = rows.map((row) => row.meanPriceAudMwh), shares = rows.map((row) => row.renewableShareWs * 100), priceMin = Math.min(0, ...prices), priceMax = Math.max(...prices) * 1.08, shareMax = Math.max(...shares) * 1.12;
  ctx.fillStyle = COLORS.navy; ctx.font = "600 14px Inter, system-ui, sans-serif";
  const name = { NSW1: "New South Wales", VIC1: "Victoria", QLD1: "Queensland", SA1: "South Australia" }[selectedRegion]; ctx.fillText(`${selectedRegion} · ${name}`, left, 22);
  for (let i = 0; i < 5; i += 1) { const y = top + (chartHeight * i) / 4; line(ctx, left, y, width - right, y, COLORS.grid); ctx.fillStyle = COLORS.muted; ctx.font = "11px Inter, system-ui, sans-serif"; ctx.fillText(`A$${Math.round(priceMax - ((priceMax - priceMin) * i) / 4)}`, 5, y + 4); ctx.fillText(`${Math.round(shareMax - (shareMax * i) / 4)}%`, width - right + 9, y + 4); }
  const draw = (values, minimum, maximum, color) => { ctx.beginPath(); values.forEach((value, index) => { const x = left + (chartWidth * index) / (values.length - 1), y = yScale(value, minimum, maximum, top, top + chartHeight); index ? ctx.lineTo(x, y) : ctx.moveTo(x, y); }); ctx.strokeStyle = color; ctx.lineWidth = 2.4; ctx.stroke(); };
  draw(prices, priceMin, priceMax, COLORS.blue); draw(shares, 0, shareMax, COLORS.teal);
  ctx.fillStyle = COLORS.blue; ctx.fillRect(left, height - 24, 11, 3); ctx.fillStyle = COLORS.muted; ctx.fillText("Mean RRP", left + 17, height - 19); ctx.fillStyle = COLORS.teal; ctx.fillRect(left + 118, height - 24, 11, 3); ctx.fillStyle = COLORS.muted; ctx.fillText("Wind + utility solar share", left + 135, height - 19); ctx.fillText(rows[0].month, left, height - 39); ctx.fillText(rows.at(-1).month, width - right - 50, height - 39);
}

function renderIntervals(id, rows, label, title) {
  const { ctx, width, height } = canvasFor(id, 365), left = 154, right = 25, top = 45, bottom = 45, chartWidth = width - left - right, chartHeight = height - top - bottom;
  const minimum = Math.min(-0.05, ...rows.map((row) => row.ciLower)) * 1.1, maximum = Math.max(0.05, ...rows.map((row) => row.ciUpper)) * 1.1, x = (value) => left + ((value - minimum) / (maximum - minimum || 1)) * chartWidth;
  ctx.fillStyle = COLORS.muted; ctx.font = "12px Inter, system-ui, sans-serif"; ctx.fillText(title, left, 21); line(ctx, x(0), top, x(0), top + chartHeight, COLORS.navy);
  rows.forEach((row, index) => { const y = top + (chartHeight * (index + 0.5)) / rows.length; ctx.fillStyle = COLORS.navy; ctx.font = "11px Inter, system-ui, sans-serif"; ctx.fillText(label(row), 4, y + 4); line(ctx, left, y, width - right, y, COLORS.grid); line(ctx, x(row.ciLower), y, x(row.ciUpper), y, COLORS.grey, 2); ctx.beginPath(); ctx.arc(x(row.estimate), y, 5, 0, Math.PI * 2); ctx.fillStyle = COLORS.blue; ctx.fill(); });
  ctx.fillStyle = COLORS.muted; ctx.font = "11px Inter, system-ui, sans-serif"; ctx.fillText("Negative", left, height - 14); ctx.fillText("Positive", width - right - 42, height - 14);
}

function render() { renderTrend(); renderIntervals("heterogeneity-chart", payload.regionalHeterogeneity, (row) => row.region, "Outcome: asinh(RRP)"); renderIntervals("robustness-chart", payload.priceRobustness, (row) => row.label, "Outcome: asinh(RRP)"); }
function initialise() {
  payload = window.__AU_NEM_DASHBOARD_DATA__; if (!payload) return;
  renderHeadline(payload); document.querySelector("#sample-window").textContent = `${payload.meta.sample} · ${payload.meta.primaryRegions.join(" · ")}`; document.querySelector("#method-sample").textContent = payload.meta.sample; document.querySelector("#method-inference").textContent = `${payload.headline.priceLevel.weekClusters} AEST-week clusters`;
  document.querySelector("#region-select").addEventListener("change", (event) => { selectedRegion = event.target.value; renderTrend(); }); window.addEventListener("resize", () => window.requestAnimationFrame(render)); render();
}
window.addEventListener("DOMContentLoaded", initialise);

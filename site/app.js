const DATA_VERSION = "20260624131612";

const dataUrl = (path) => `${path}?v=${DATA_VERSION}`;

const state = {
  reports: [],
  activeId: "",
  category: "All",
  boardQuery: "",
  minExpansionDays: 0,
  boardSort: "duration",
  onlyConfirmed: false,
};

const categoryOrder = [
  "Actionable Now",
  "Breakout Confirmed / Manage",
  "Breakout Watch",
  "Constructive Base",
  "Developing Setup",
  "Repair Needed",
  "Data Missing",
];

const badgeClass = (category) => {
  if (category === "Actionable Now") return "hot";
  if (category === "Breakout Confirmed / Manage") return "hot";
  if (category === "Breakout Watch") return "watch";
  if (category === "Constructive Base") return "base";
  if (category === "Repair Needed" || category === "Data Missing") return "danger";
  return "";
};

const fmtPct = (value) => {
  if (value === null || value === undefined) return "Data Missing";
  return `${(value * 100).toFixed(1)}%`;
};

const fmtRatio = (value) => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "Data Missing";
  return `${Number(value).toFixed(2)}x`;
};

const fmtDate = (iso) => {
  if (!iso) return "Data Missing";
  return new Date(iso).toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
};

const currentReport = () => state.reports.find((report) => report.id === state.activeId) || state.reports[0];

function setInitialReport() {
  const first = [...state.reports].sort((a, b) => new Date(b.generated_at_local) - new Date(a.generated_at_local))[0] || state.reports[0];
  state.activeId = first?.id || "";
}

function renderTabs() {
  const report = currentReport();
  const el = document.querySelector("#latestContext");
  if (!el || !report) return;
  el.textContent = `Latest update: ${report.date} / generated ${fmtDate(report.generated_at_local)}`;
}

function renderSelect() {
  return;
}

function renderSummary(report) {
  document.querySelector("#timestamp").textContent = `Generated ${fmtDate(report.generated_at_local)}`;
}

function renderAttention(report) {
  const items = report.core_attention?.length ? report.core_attention : ["No core attention items in this report."];
  document.querySelector("#coreAttention").innerHTML = items.map((item) => `<li>${item}</li>`).join("");
}

function renderClassification(report) {
  const grouped = categoryOrder
    .map((name) => [name, report.scores.filter((item) => item.category === name)])
    .filter(([, items]) => items.length);
  document.querySelector("#classificationGrid").innerHTML = grouped.map(([name, items]) => `
    <article class="classification-card">
      <h3>${name}</h3>
      <p>${items.map((item) => `${item.ticker} (${item.timing_score})`).join(", ")}</p>
    </article>
  `).join("");
}

function renderFocus(report) {
  const focusByTicker = new Map(report.focus.map((item) => [item.ticker, item]));
  const fallback = report.scores
    .filter((item) => ["Actionable Now", "Breakout Confirmed / Manage", "Breakout Watch", "Constructive Base", "Developing Setup"].includes(item.category))
    .slice(0, 5)
    .map((item) => ({ ticker: item.ticker, title: `${item.ticker} - ${item.category}`, bullets: { why_it_matters: item.comment, today_trigger: item.key_level, risk_invalidation: item.invalidation } }));
  const focus = report.focus.length ? report.scores
    .filter((score) => focusByTicker.has(score.ticker))
    .map((score) => focusByTicker.get(score.ticker)) : fallback;
  document.querySelector("#focusGrid").innerHTML = focus.map((item) => `
    <article class="focus-card">
      ${(() => {
        const score = report.scores.find((row) => row.ticker === item.ticker);
        return score ? `
          <div class="focus-title">
            <div>
              <h3>${score.ticker}</h3>
              <span class="badge ${badgeClass(score.category)}">${score.category}</span>
            </div>
            <div class="score">${score.timing_score}</div>
          </div>
          <div class="score-breakdown">
            <span>Setup ${score.setup_quality_score}/35</span>
            <span>Breakout ${score.breakout_readiness_score}/30</span>
            <span>Demand ${score.demand_score}/20</span>
            <span>Risk ${score.entry_risk_score}/15</span>
          </div>
          <div class="lifecycle-strip">
            <span>${score.trend_signal}</span>
            <span>${score.trend_phase}</span>
            <span>Age ${score.trend_age}d</span>
            <span>${score.session_label} ${fmtPct(score.session_move_pct)}</span>
          </div>
        ` : `<h3>${item.title}</h3>`;
      })()}
      <ul>
        <li><strong>Why:</strong> ${item.bullets.why_it_matters || "Data Missing"}</li>
        <li><strong>Trigger:</strong> ${item.bullets.today_trigger || "Data Missing"}</li>
        <li><strong>Risk:</strong> ${item.bullets.risk_invalidation || "Data Missing"}</li>
      </ul>
    </article>
  `).join("");
}

const toneFor = (value = "") => {
  const text = String(value).toLowerCase();
  if (text === "intact" || text.includes("stack intact")) return "positive";
  if (text.includes("not expanded")) return "warning";
  if (text.includes("pass") || text.includes("bullish") || text.includes("confirmed") || text.includes("expansion")) return "positive";
  if (text.includes("watch") || text.includes("neutral") || text.includes("entangled")) return "warning";
  if (text.includes("fail") || text.includes("repair") || text.includes("weak") || text.includes("break")) return "danger";
  return "";
};

const gainText = (value) => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "";
  const prefix = Number(value) >= 0 ? "+" : "";
  const cls = Number(value) >= 0 ? "gain-pos" : "gain-neg";
  return `<span class="${cls}">${prefix}${(Number(value) * 100).toFixed(1)}%</span>`;
};

function renderCategoryFilter(report) {
  const search = document.querySelector("#boardSearch");
  const minDays = document.querySelector("#minDaysFilter");
  const sortDays = document.querySelector("#btnSortDays");
  const sortPivot = document.querySelector("#btnSortPivot");
  const onlyConfirmed = document.querySelector("#btnOnlyConfirmed");
  if (!search || !minDays || !sortDays || !sortPivot || !onlyConfirmed) return;
  search.value = state.boardQuery;
  minDays.value = String(state.minExpansionDays);
  sortDays.classList.toggle("active", state.boardSort === "duration");
  sortPivot.classList.toggle("active", state.boardSort === "pivot");
  onlyConfirmed.classList.toggle("active", state.onlyConfirmed);
  search.oninput = () => {
    state.boardQuery = search.value.trim().toLowerCase();
    renderWatchlist(report);
  };
  minDays.onchange = () => {
    state.minExpansionDays = Number(minDays.value || 0);
    renderWatchlist(report);
  };
  sortDays.onclick = () => {
    state.boardSort = "duration";
    renderCategoryFilter(report);
    renderWatchlist(report);
  };
  sortPivot.onclick = () => {
    state.boardSort = "pivot";
    renderCategoryFilter(report);
    renderWatchlist(report);
  };
  onlyConfirmed.onclick = () => {
    state.onlyConfirmed = !state.onlyConfirmed;
    renderCategoryFilter(report);
    renderWatchlist(report);
  };
}

function renderWatchlist(report) {
  const items = report.scores
    .filter((item) => !state.boardQuery || item.ticker.toLowerCase().includes(state.boardQuery))
    .filter((item) => (item.ma_expansion_age || 0) >= state.minExpansionDays)
    .filter((item) => !state.onlyConfirmed || item.trend_signal === "Pass")
    .sort((a, b) => {
      if (state.boardSort === "pivot") return (b.pivot_gap_pct ?? -99) - (a.pivot_gap_pct ?? -99);
      return (b.ma_expansion_age ?? 0) - (a.ma_expansion_age ?? 0);
    });
  const counter = document.querySelector("#countDisplay");
  if (counter) counter.textContent = `${items.length} / ${report.scores.length}`;
  document.querySelector("#watchlistGrid").innerHTML = items.map((item) => `
    <article class="stock-card">
      <div class="stock-top">
        <div>
          <div class="ticker">${item.ticker}</div>
          <span class="badge ${item.trend_signal === "Pass" ? "hot" : "danger"}">Trend ${item.trend_signal}</span>
        </div>
        <div class="card-badges">
          <span class="badge badge-days">${item.ma_expansion_age || 0}d</span>
          <span class="badge badge-gap">Pivot ${fmtPct(item.pivot_gap_pct)}</span>
          ${item.expma_start_date ? `<span class="badge badge-expma">EXPMA ${item.expma_start_date}</span>` : ""}
        </div>
      </div>
      <div class="card-meta">
        <span>Latest <span class="val">${item.price_fmt}</span></span>
        <span>Session <span class="val">${item.session_price_fmt} / ${fmtPct(item.session_move_pct)}</span></span>
        <span><span style="color:#56d364">MA Expansion</span> <span class="val">${item.ma_expansion_start_date || "Data Missing"}</span></span>
        <span>Trend Phase <span class="val">${item.trend_phase}</span></span>
      </div>
      <div class="expma-info">
        <span class="lbl">EXPMA Expansion</span>
        <span>Start <b>${item.expma_start_date || "Data Missing"}</b></span>
        <span>EXPMA→MA ${gainText(item.gain_expma_to_ma_pct) || "<b>Data Missing</b>"}</span>
        <span>MA→Now ${gainText(item.gain_ma_to_now_pct) || "<b>Data Missing</b>"}</span>
        <span>EXPMA Total ${gainText(item.gain_expma_to_now_pct) || "<b>Data Missing</b>"}</span>
      </div>
      <div class="trend-chart-shell">
        <div class="chart-core">
          <div class="mini-chart-wrap">
            <div class="mini-chart" data-ticker="${item.ticker}"></div>
            <div class="mini-legend">
              <span class="legend-k">K</span>
              <span class="legend-ma5">MA5</span>
              <span class="legend-ma10">MA10</span>
              <span class="legend-ma20">MA20</span>
              <span class="legend-ma30">MA30</span>
              <span class="legend-ma60">MA60</span>
              <span class="legend-pivot">Pivot</span>
              <span class="legend-support">Support</span>
            </div>
          </div>
        </div>
      </div>
      <div class="chart-metric-row">
        <div class="metric-box ${toneFor(item.trend_signal)}"><span>Trend</span><b>${item.trend_signal}</b></div>
        <div class="metric-box ${toneFor(item.expma_state)}"><span>EMA Expansion</span><b>${item.expma_state}</b></div>
        <div class="metric-box"><span>EXPMA Days</span><b>${item.expma_stack_age}d</b></div>
        <div class="metric-box ${toneFor(item.expma_break_state)}"><span>EMA Break</span><b>${item.expma_break_state}${item.expma_break_date ? ` ${item.expma_break_date}` : ""}</b></div>
        <div class="metric-box wide ${toneFor(item.expma_break_state)}"><span>EMA Break Reason</span><b>${item.expma_break_reason}</b></div>
        <div class="metric-box ${toneFor(item.ma_expansion_state)}"><span>MA Expansion</span><b>${item.ma_expansion_state}</b></div>
        <div class="metric-box"><span>MA Days</span><b>${item.ma_expansion_age || 0}d</b></div>
        <div class="metric-box ${toneFor(item.ma_break_state)}"><span>MA Break</span><b>${item.ma_break_state}${item.ma_break_date ? ` ${item.ma_break_date}` : ""}</b></div>
        <div class="metric-box wide ${toneFor(item.ma_break_state)}"><span>MA Break Reason</span><b>${item.ma_break_reason}</b></div>
        <div class="metric-box hot-cell"><span>Pivot</span><b>${item.pivot_fmt}</b></div>
        <div class="metric-box danger-cell"><span>Support</span><b>${item.support_fmt}</b></div>
        <div class="metric-box wide"><span>Support Basis</span><b>${item.support_basis}</b></div>
        <div class="metric-box ${Number(item.pivot_gap_pct || 0) >= 0 ? "positive" : "warning"}"><span>Pivot Gap</span><b>${fmtPct(item.pivot_gap_pct)}</b></div>
        <div class="metric-box ${toneFor(item.volume_state)}"><span>VCP Volume</span><b>${item.volume_state}</b></div>
        <div class="metric-box ${toneFor(item.tightness_state)}"><span>VCP Tightness</span><b>${item.tightness_state}</b></div>
        <div class="metric-box"><span>Today / 20D Avg</span><b>${fmtRatio(item.volume_vs_avg_20)}</b></div>
        <div class="metric-box"><span>20D Avg Vol</span><b>${item.avg_volume_20_fmt}</b></div>
        <div class="metric-box"><span>Today / 20D Max</span><b>${fmtRatio(item.volume_vs_max_20)}</b></div>
        <div class="metric-box"><span>20D Max Vol</span><b>${item.max_volume_20_fmt}</b></div>
        <div class="metric-box wide"><span>Pullback Depths</span><b>${item.contraction_sequence}</b></div>
        <div class="metric-box extra-wide"><span>Pullback Volume</span><b>${item.pullback_volume_detail}</b></div>
        <div class="metric-box extra-wide"><span>Key Level</span><b>${item.key_level}</b></div>
      </div>
    </article>
  `).join("");
  window.dispatchEvent(new CustomEvent("dashboard:rendered"));
}

function render() {
  const report = currentReport();
  if (!report) return;
  renderTabs();
  renderSelect();
  renderSummary(report);
  renderAttention(report);
  renderClassification(report);
  renderFocus(report);
  renderCategoryFilter(report);
  renderWatchlist(report);
}

async function boot() {
  const response = await fetch(dataUrl("data/reports.json"), { cache: "no-store" });
  const payload = await response.json();
  state.reports = payload.reports.sort((a, b) => b.id.localeCompare(a.id));
  setInitialReport();
  render();
}

boot().catch((error) => {
  document.body.innerHTML = `<main class="shell"><h1>Unable to load dashboard</h1><p>${error.message}</p></main>`;
});

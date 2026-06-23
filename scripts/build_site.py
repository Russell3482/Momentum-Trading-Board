from __future__ import annotations

import csv
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
REPORT_DIR = ROOT / "reports"
SITE_DIR = ROOT / "site"
SITE_DATA_DIR = SITE_DIR / "data"

LEGACY_TEXT_REPLACEMENTS = {
    "Extended / Do Not Chase": "Breakout Confirmed / Manage",
    "Do not chase": "Pivot management",
    "No chase. ": "",
    "too extended; wait for digestion or a controlled pullback": "above pivot; monitor pivot hold and trend health",
    "fresh entries should avoid chasing a wide intraday extension": "confirm trend and volume remain healthy",
    "Risk is poor if chased; ": "",
    "Strength is real, but extension makes risk/reward poor until price digests.": "Review pivot hold, support, and MA/EMA expansion.",
}


def clean_legacy_text(value: str) -> str:
    for old, new in LEGACY_TEXT_REPLACEMENTS.items():
        value = value.replace(old, new)
    return value


def clean_legacy_value(value: object) -> object:
    if isinstance(value, str):
        return clean_legacy_text(value)
    if isinstance(value, list):
        return [clean_legacy_value(item) for item in value]
    if isinstance(value, dict):
        return {key: clean_legacy_value(item) for key, item in value.items()}
    return value


def category(score: dict) -> str:
    status = score.get("status", "")
    if score.get("data_missing"):
        return "Data Missing"
    if status == "Extended / Do Not Chase":
        return "Breakout Confirmed / Manage"
    if status in {"Actionable Now", "Breakout Confirmed / Manage", "Breakout Watch", "Constructive Base", "Developing Setup"}:
        return status
    if status in {"Trend Break", "Structure Break", "Early Warning", "Repair Needed"}:
        return "Repair Needed"
    # Compatibility with reports generated before the timing-score model.
    trend_score = score.get("trend_score") or 0
    rs_score = score.get("rs_score") or 0
    momentum_score = score.get("momentum_score") or 0
    if status in {"Trend Broken", "Failed Breakout", "Ignore"}:
        return "Repair Needed"
    if status in {"Breakout Watch", "Breakout Attempt", "A+ Breakout"}:
        return "Breakout Watch"
    if trend_score == 30 and rs_score >= 13 and momentum_score >= 50:
        return "Constructive Base"
    if trend_score == 30:
        return "Developing Setup"
    return "Repair Needed"


def fmt_number(value: object, digits: int = 2) -> str:
    if value is None:
        return "Data Missing"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "Data Missing"
    return f"{number:.{digits}f}"


def distance_to_pivot(score: dict) -> float | None:
    price = score.get("price")
    pivot = score.get("pivot")
    if price is None or pivot in (None, 0):
        return None
    return (float(price) / float(pivot)) - 1


def as_percent(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def extract_section(markdown: str, heading: str) -> list[str]:
    pattern = rf"^## {re.escape(heading)}\n(?P<body>.*?)(?=^## |\Z)"
    match = re.search(pattern, markdown, flags=re.MULTILINE | re.DOTALL)
    if not match:
        return []
    lines = []
    for line in match.group("body").splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            lines.append(stripped[2:])
    return lines


def extract_focus(markdown: str) -> list[dict]:
    match = re.search(r"^## Focus Stock Analysis\n(?P<body>.*?)(?=^## |\Z)", markdown, flags=re.MULTILINE | re.DOTALL)
    if not match:
        return []
    body = match.group("body")
    blocks = re.split(r"^### ", body, flags=re.MULTILINE)
    focus = []
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        title, *rest = block.splitlines()
        bullets = {}
        for line in rest:
            stripped = line.strip()
            if not stripped.startswith("- ") or ": " not in stripped:
                continue
            key, value = stripped[2:].split(": ", 1)
            bullets[key.lower().replace(" / ", "_").replace(" ", "_")] = value
        ticker = title.split(" - ", 1)[0].strip()
        focus.append({"ticker": ticker, "title": title.strip(), "bullets": bullets})
    return focus


def load_report(snapshot_path: Path) -> dict:
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    stem = snapshot_path.name.replace("_snapshot.json", "")
    report_path = REPORT_DIR / f"{stem}.md"
    markdown = report_path.read_text(encoding="utf-8") if report_path.exists() else ""
    scores = []
    for score in snapshot.get("scores", []):
        enriched = dict(score)
        enriched["category"] = category(score)
        enriched["distance_to_pivot"] = distance_to_pivot(score)
        enriched["timing_score"] = score.get("timing_score", score.get("momentum_score", 0))
        enriched["setup_quality_score"] = score.get("setup_quality_score", score.get("setup_score", 0))
        enriched["breakout_readiness_score"] = score.get("breakout_readiness_score", 0)
        enriched["demand_score"] = score.get("demand_score", score.get("volume_score", 0))
        enriched["entry_risk_score"] = score.get("entry_risk_score", score.get("risk_score", 0))
        enriched["trend_gate"] = bool(score.get("trend_gate", (score.get("trend_score") or 0) == 30))
        enriched["trend_signal"] = score.get("trend_signal", "Pass" if enriched["trend_gate"] else "Fail")
        enriched["trend_age"] = score.get("trend_age", 0)
        enriched["trend_phase"] = score.get("trend_phase", "Data Missing")
        enriched["short_ma_state"] = score.get("short_ma_state", "Data Missing")
        enriched["short_ma_spread_pct"] = as_percent(score.get("short_ma_spread_pct"))
        enriched["ma_expansion_state"] = score.get("ma_expansion_state", "Data Missing")
        enriched["ma_expansion_start_date"] = score.get("ma_expansion_start_date", "")
        enriched["ma_expansion_age"] = score.get("ma_expansion_age", score.get("trend_age", 0))
        enriched["ma_break_state"] = score.get("ma_break_state", "Data Missing")
        enriched["ma_break_reason"] = score.get("ma_break_reason", "Data Missing")
        enriched["ma_break_date"] = score.get("ma_break_date", "")
        enriched["expma_state"] = score.get("expma_state", "Data Missing")
        enriched["expma_spread_pct"] = as_percent(score.get("expma_spread_pct"))
        enriched["expma_stack_age"] = score.get("expma_stack_age", 0)
        enriched["expma_start_date"] = score.get("expma_start_date", "")
        enriched["expma_break_state"] = score.get("expma_break_state", "Data Missing")
        enriched["expma_break_reason"] = score.get("expma_break_reason", "Data Missing")
        enriched["expma_break_date"] = score.get("expma_break_date", "")
        enriched["gain_expma_to_ma_pct"] = as_percent(score.get("gain_expma_to_ma_pct"))
        enriched["gain_ma_to_now_pct"] = as_percent(score.get("gain_ma_to_now_pct"))
        enriched["gain_expma_to_now_pct"] = as_percent(score.get("gain_expma_to_now_pct"))
        enriched["days_above_50ma"] = score.get("days_above_50ma", 0)
        enriched["ma_stack_age"] = score.get("ma_stack_age", 0)
        enriched["extension_20_pct"] = as_percent(score.get("extension_20_pct"))
        enriched["pivot_gap_pct"] = as_percent(score.get("pivot_gap_pct", enriched["distance_to_pivot"]))
        enriched["session_move_pct"] = as_percent(score.get("session_move_pct"))
        enriched["session_price_fmt"] = fmt_number(score.get("session_price"))
        enriched["session_label"] = score.get("session_label", "Data Missing")
        enriched["session_time"] = score.get("session_time", "Data Missing")
        enriched["session_context"] = score.get("session_context", "Data Missing")
        enriched["avg_volume_20_fmt"] = fmt_number(score.get("avg_volume_20"), 0)
        enriched["max_volume_20_fmt"] = fmt_number(score.get("max_volume_20"), 0)
        enriched["volume_vs_avg_20"] = score.get("volume_vs_avg_20")
        enriched["volume_vs_max_20"] = score.get("volume_vs_max_20")
        enriched["contraction_sequence"] = score.get("contraction_sequence", "Data Missing")
        enriched["pullback_volume_detail"] = score.get("pullback_volume_detail", "Data Missing")
        enriched["volume_state"] = score.get("volume_state", "Data Missing")
        enriched["tightness_state"] = score.get("tightness_state", "Data Missing")
        enriched["support_basis"] = score.get("support_basis", "20D low excluding latest bar")
        enriched["price_fmt"] = fmt_number(score.get("price"))
        enriched["pivot_fmt"] = fmt_number(score.get("pivot"))
        enriched["support_fmt"] = fmt_number(score.get("support"))
        scores.append(enriched)
    return {
        "id": stem,
        "date": stem[:10],
        "mode": snapshot.get("mode"),
        "generated_at_local": snapshot.get("generated_at_local"),
        "generated_at_new_york": snapshot.get("generated_at_new_york"),
        "core_attention": extract_section(markdown, "Today's Core Attention"),
        "classification": extract_section(markdown, "Classification"),
        "focus": extract_focus(markdown),
        "scores": scores,
    }


def load_price_history() -> dict[str, list[dict]]:
    histories = {}
    for path in sorted((DATA_DIR / "prices").glob("*.csv")):
        ticker = path.stem
        rows = []
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                try:
                    rows.append(
                        {
                            "date": row["Date"],
                            "open": float(row["Open"]),
                            "high": float(row["High"]),
                            "low": float(row["Low"]),
                            "close": float(row["Close"]),
                            "volume": float(row["Volume"]),
                        }
                    )
                except (KeyError, TypeError, ValueError):
                    continue
        for period in (5, 10, 20, 50, 150, 200):
            key = f"ma{period}"
            for idx, item in enumerate(rows):
                if idx + 1 < period:
                    item[key] = None
                    continue
                window = rows[idx + 1 - period : idx + 1]
                item[key] = sum(row["close"] for row in window) / period
        histories[ticker] = rows[-260:]
    return histories


def write_site_files(reports: list[dict]) -> None:
    SITE_DATA_DIR.mkdir(parents=True, exist_ok=True)
    reports = clean_legacy_value(reports)
    (SITE_DATA_DIR / "reports.json").write_text(json.dumps({"reports": reports}, indent=2), encoding="utf-8")
    (SITE_DATA_DIR / "price_history.json").write_text(json.dumps(load_price_history(), indent=2), encoding="utf-8")

    (SITE_DIR / "index.html").write_text(
        """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Momentum Trading Agent</title>
  <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <main class="shell">
    <header class="app-header">
      <div>
        <p class="eyebrow">Momentum Trading Agent</p>
        <h1>Daily Momentum Dashboard</h1>
      </div>
      <div class="timestamp" id="timestamp">Loading...</div>
    </header>

    <section class="toolbar" aria-label="Latest report context">
      <div class="latest-context" id="latestContext">Loading latest update...</div>
    </section>

    <nav class="view-switch" aria-label="Dashboard views">
      <button class="active" type="button" data-view="chartBoardView">Chart Board</button>
      <button type="button" data-view="homeView">Report</button>
    </nav>

    <div class="view" id="homeView" hidden>
      <section class="panel">
        <div class="panel-head">
          <h2>Core Attention</h2>
        </div>
        <ul class="attention-list" id="coreAttention"></ul>
      </section>

      <section class="panel">
        <div class="panel-head">
          <h2>Classification</h2>
        </div>
        <div class="classification-grid" id="classificationGrid"></div>
      </section>

      <section class="panel">
        <div class="panel-head">
          <h2>Focus Stocks</h2>
        </div>
        <div class="focus-grid" id="focusGrid"></div>
      </section>

      <section class="panel">
        <div class="panel-head">
          <h2>Report Assistant</h2>
        </div>
        <div class="chat-log" id="chatLog"></div>
        <form class="chat-form" id="chatForm">
          <input id="chatInput" type="text" autocomplete="off" placeholder="Ask about today's focus, INTC, breakout watch...">
          <button type="submit">Ask</button>
        </form>
      </section>
    </div>

    <div class="view chart-board" id="chartBoardView">
      <section class="panel">
        <div class="panel-head chart-head">
          <div>
            <h2>Trend Chart Board</h2>
            <p>MA5 &gt; MA10 &gt; MA20 &gt; MA30 &gt; MA60; EXPMA layer preserved, pivot/VCP metrics below each chart.</p>
          </div>
          <div class="chart-tools">
            <input id="boardSearch" type="search" placeholder="Search ticker..." aria-label="Search ticker">
            <label>Min days</label>
            <select id="minDaysFilter" aria-label="Minimum expansion days">
              <option value="0">All</option>
              <option value="3">≥ 3d</option>
              <option value="5">≥ 5d</option>
              <option value="10">≥ 10d</option>
              <option value="20">≥ 20d</option>
            </select>
            <button class="sort-btn active" id="btnSortDays" type="button">Days↓</button>
            <button class="sort-btn" id="btnSortPivot" type="button">Pivot↓</button>
            <button class="sort-btn" id="btnOnlyConfirmed" type="button">Trend Pass</button>
            <div class="count-badge">Show <span id="countDisplay">0</span></div>
          </div>
        </div>
        <div class="watchlist-grid" id="watchlistGrid"></div>
      </section>
    </div>
  </main>
  <script src="app.js"></script>
  <script src="extras.js"></script>
</body>
</html>
""",
        encoding="utf-8",
    )

    (SITE_DIR / "styles.css").write_text(
        """* {
  box-sizing: border-box;
}

:root {
  color-scheme: light;
  --bg: #f4f6f8;
  --surface: #ffffff;
  --surface-2: #eef3f7;
  --text: #17202a;
  --muted: #66717f;
  --line: #d9e0e7;
  --accent: #1f7a5b;
  --accent-2: #2f5f98;
  --warn: #a15c12;
  --danger: #b84242;
  --shadow: 0 8px 24px rgba(23, 32, 42, 0.08);
}

body {
  margin: 0;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  background: var(--bg);
  color: var(--text);
}

.shell {
  margin: 0 auto;
  padding: 0;
}

.app-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  padding: 20px 24px 16px;
}

.eyebrow {
  margin: 0 0 4px;
  color: var(--accent-2);
  font-size: 13px;
  font-weight: 700;
  text-transform: uppercase;
}

h1, h2, h3, p {
  margin-top: 0;
}

h1 {
  margin-bottom: 0;
  font-size: 30px;
  line-height: 1.1;
}

h2 {
  margin-bottom: 0;
  font-size: 18px;
}

h3 {
  margin-bottom: 8px;
  font-size: 16px;
}

.timestamp {
  color: var(--muted);
  font-size: 13px;
  text-align: right;
}

.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 0 24px 16px;
}

.view-switch {
  display: inline-flex;
  gap: 4px;
  padding: 4px;
  margin: 0 24px 16px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--surface);
}

.view-switch button {
  min-height: 34px;
  padding: 0 14px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--muted);
  font-weight: 800;
}

.view-switch button.active {
  background: var(--accent-2);
  color: #fff;
}

.view[hidden] {
  display: none;
}

#homeView {
  width: min(1120px, calc(100% - 40px));
  margin: 0 auto;
  padding-bottom: 20px;
}

#chartBoardView {
  width: 100%;
  min-height: calc(100vh - 160px);
  padding: 0 16px 20px;
  background: #0d1117;
}

.segmented {
  display: inline-flex;
  gap: 4px;
  padding: 4px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--surface);
}

.segmented button {
  min-height: 34px;
  padding: 0 14px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--muted);
  font-weight: 700;
}

.segmented button.active {
  background: var(--accent);
  color: white;
}

.select-label {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--muted);
  font-size: 13px;
  font-weight: 700;
}

.latest-context {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--surface);
  color: var(--muted);
  font-size: 13px;
  font-weight: 700;
}

select {
  min-height: 36px;
  max-width: 220px;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: var(--surface);
  color: var(--text);
  padding: 0 10px;
}

.regime {
  width: min(1120px, calc(100% - 40px));
  margin-right: auto;
  margin-left: auto;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 12px;
}

.metric-card, .panel {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 8px;
  box-shadow: var(--shadow);
}

.metric-card {
  padding: 14px;
}

.regime .metric-card {
  border-color: #30363d;
  background: #0d1117;
  box-shadow: none;
}

.regime .metric-value {
  color: #c9d1d9;
}

.regime .metric-label,
.regime .metric-note {
  color: #8b949e;
}

.metric-label {
  color: var(--muted);
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
}

.metric-value {
  margin-top: 8px;
  font-size: 22px;
  font-weight: 800;
}

.metric-note {
  margin-top: 5px;
  color: var(--muted);
  font-size: 12px;
}

.panel {
  margin-top: 12px;
  padding: 16px;
}

.chart-board .panel {
  background: #0d1117;
  border-color: #30363d;
  box-shadow: none;
  padding: 12px;
}

.chart-board .panel h2,
.chart-board .panel-head {
  color: #c9d1d9;
}

.chart-head {
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.chart-head p {
  margin: 4px 0 0;
  color: #8b949e;
  font-size: 12px;
}

.chart-tools {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
}

.chart-tools input,
.chart-tools select,
.sort-btn {
  min-height: 30px;
  border: 1px solid #30363d;
  border-radius: 6px;
  background: #0d1117;
  color: #c9d1d9;
  font: inherit;
  font-size: 12px;
}

.chart-tools input {
  width: 150px;
  padding: 0 9px;
}

.chart-tools select {
  padding: 0 7px;
}

.chart-tools label {
  color: #8b949e;
  font-size: 12px;
  font-weight: 800;
}

.sort-btn {
  padding: 0 9px;
  color: #8b949e;
  font-weight: 800;
}

.sort-btn.active {
  border-color: #58a6ff;
  color: #58a6ff;
}

.count-badge {
  padding: 7px 9px;
  border: 1px solid #30363d;
  border-radius: 6px;
  background: #0d1117;
  color: #8b949e;
  font-size: 12px;
  font-weight: 800;
}

.panel-head {
  display: flex;
  align-items: center;
  margin-bottom: 12px;
}

.panel-head.split {
  justify-content: space-between;
  gap: 10px;
}

.attention-list {
  display: grid;
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.attention-list li {
  padding: 10px 12px;
  border-left: 4px solid var(--accent-2);
  border-radius: 6px;
  background: var(--surface-2);
  line-height: 1.45;
}

.classification-grid, .focus-grid, .watchlist-grid {
  display: grid;
  gap: 10px;
}

.classification-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.classification-card, .focus-card, .stock-card {
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #fff;
  padding: 12px;
}

.classification-card p, .focus-card p, .stock-card p {
  margin: 0;
  color: var(--muted);
  line-height: 1.45;
}

.focus-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.focus-card ul {
  display: grid;
  gap: 7px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.focus-card li {
  color: var(--muted);
  line-height: 1.45;
}

.focus-card strong {
  color: var(--text);
}

.watchlist-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.chart-board .watchlist-grid {
  grid-template-columns: repeat(auto-fill, minmax(620px, 1fr));
  gap: 10px;
}

.chart-board .stock-card {
  border-color: #30363d;
  background: #05070a;
  color: #c9d1d9;
  padding: 0;
  overflow: hidden;
  transition: border-color .18s, box-shadow .18s;
}

.chart-board .stock-card:hover {
  border-color: #58a6ff;
  box-shadow: 0 0 0 1px rgba(88, 166, 255, 0.22);
}

.chart-board .stock-top {
  margin: 0;
  padding: 8px 10px;
  border-bottom: 1px solid #21262d;
  background: #0d1117;
}

.chart-board .card-badges {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: 6px;
}

.chart-board .badge {
  margin-top: 0;
  border: 1px solid #30363d;
  background: #161b22;
}

.chart-board .badge-days {
  border-color: #2ea043;
  color: #56d364;
}

.chart-board .badge-gap {
  border-color: #f0883e66;
  color: #f0883e;
}

.chart-board .badge-expma {
  border-color: #a371f7aa;
  color: #a371f7;
}

.chart-board .card-meta,
.chart-board .expma-info {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  padding: 5px 10px;
  border-bottom: 1px solid #21262d;
  background: #05070a;
  color: #8b949e;
  font-size: 11px;
}

.chart-board .card-meta .val,
.chart-board .expma-info b {
  color: #c9d1d9;
}

.chart-board .card-meta .up,
.chart-board .expma-info .gain-pos {
  color: #56d364;
}

.chart-board .card-meta .down,
.chart-board .expma-info .gain-neg {
  color: #f85149;
}

.chart-board .expma-info {
  background: #0d1117;
}

.chart-board .expma-info .lbl {
  color: #a371f7;
  font-weight: 800;
}

.chart-board .mini-chart-wrap {
  border-right: 0;
  border-left: 0;
  border-bottom: 0;
  border-radius: 0;
}

.chart-board .mini-chart {
  height: 430px;
}

.trend-chart-shell {
  min-height: 430px;
}

.chart-core {
  min-width: 0;
}

.chart-metric-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(132px, 1fr));
  gap: 6px;
  padding: 8px;
  border-top: 1px solid #21262d;
  background: #0d1117;
}

.chart-metric-row .metric-box {
  min-width: 0;
  padding: 8px 7px;
  border: 1px solid #21262d;
  border-radius: 4px;
  background: #05070a;
  min-height: 52px;
}

.chart-metric-row span {
  display: block;
  color: #6e7681;
  font-size: 10px;
  font-weight: 800;
  text-transform: uppercase;
  white-space: normal;
  overflow-wrap: anywhere;
}

.chart-metric-row b {
  display: block;
  margin-top: 3px;
  color: #c9d1d9;
  font-size: 12px;
  line-height: 1.35;
  white-space: normal;
  overflow-wrap: anywhere;
}

.chart-metric-row .metric-box.positive {
  border-color: #2ea04366;
  background: #07150d;
}

.chart-metric-row .metric-box.positive b {
  color: #3fb950;
}

.chart-metric-row .metric-box.warning {
  border-color: #d2992266;
  background: #171205;
}

.chart-metric-row .metric-box.warning b {
  color: #f2cc60;
}

.chart-metric-row .metric-box.danger {
  border-color: #f8514966;
  background: #190b0d;
}

.chart-metric-row .metric-box.danger b {
  color: #ff7b72;
}

.chart-metric-row .metric-box.hot-cell {
  border-color: #f0883e88;
}

.chart-metric-row .metric-box.hot-cell b {
  color: #ffa657;
}

.chart-metric-row .metric-box.danger-cell b {
  color: #ff7b72;
}

.chart-metric-row .metric-box.wide {
  grid-column: span 2;
}

.chart-metric-row .metric-box.extra-wide {
  grid-column: span 4;
}

.stock-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}

.ticker {
  font-size: 20px;
  font-weight: 850;
}

.score {
  min-width: 58px;
  text-align: right;
  font-size: 20px;
  font-weight: 850;
}

.badge {
  display: inline-block;
  margin-top: 7px;
  padding: 4px 7px;
  border-radius: 6px;
  background: var(--surface-2);
  color: var(--accent-2);
  font-size: 12px;
  font-weight: 800;
}

.badge.hot {
  color: #3fb950;
}

.badge.watch {
  color: #58a6ff;
}

.badge.base {
  color: #d2a8ff;
}

.badge.warn {
  color: var(--warn);
}

.badge.danger {
  color: var(--danger);
}

.stock-meta {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  margin-top: 12px;
}

.stock-meta div {
  padding: 8px;
  border-radius: 6px;
  background: var(--surface-2);
}

.stock-meta span {
  display: block;
  color: var(--muted);
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
}

.stock-meta b {
  display: block;
  margin-top: 3px;
  font-size: 14px;
}

.score-breakdown {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 6px;
  margin-top: 10px;
}

.score-breakdown span {
  padding: 7px 6px;
  border-radius: 6px;
  background: var(--surface-2);
  color: var(--muted);
  font-size: 11px;
  font-weight: 800;
  text-align: center;
}

.focus-card .score-breakdown {
  grid-template-columns: repeat(4, minmax(0, 1fr));
  margin-bottom: 10px;
}

.focus-title {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 10px;
}

.lifecycle-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 6px;
  margin-bottom: 10px;
}

.lifecycle-strip span {
  min-width: 0;
  overflow: hidden;
  padding: 7px 6px;
  border-radius: 6px;
  background: var(--surface-2);
  color: var(--muted);
  font-size: 11px;
  font-weight: 800;
  text-align: center;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chart-board .stock-meta div,
.chart-board .score-breakdown span {
  background: #0d1117;
  color: #8b949e;
}

.chart-board .stock-meta b,
.chart-board .ticker,
.chart-board .score {
  color: #c9d1d9;
}

.chart-board .stock-meta span,
.chart-board .comment {
  color: #8b949e;
}

.comment {
  margin-top: 10px;
  color: var(--muted);
  font-size: 13px;
  line-height: 1.45;
}

.mini-chart-wrap {
  margin-top: 12px;
  border: 1px solid #30363d;
  border-radius: 8px;
  background: #0d1117;
  overflow: hidden;
}

.mini-chart {
  width: 100%;
  height: 320px;
}

.mini-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 10px;
  padding: 7px 8px 8px;
  color: #8b949e;
  font-size: 11px;
  border-top: 1px solid #30363d;
}

.mini-legend span {
  align-items: center;
  display: inline-flex;
  gap: 4px;
  white-space: nowrap;
}

.mini-legend span::before {
  display: inline-block;
  width: 14px;
  height: 2px;
  border-radius: 99px;
  background: currentColor;
  content: "";
}

.mini-legend .legend-k::before {
  width: 8px;
  height: 8px;
  border-radius: 2px;
  background: #3fb950;
}

.mini-legend .legend-ma5 { color: #58a6ff; }
.mini-legend .legend-ma10 { color: #f0883e; }
.mini-legend .legend-ma20 { color: #d2a8ff; }
.mini-legend .legend-ma30 { color: #56d364; }
.mini-legend .legend-ma60 { color: #e3b341; }
.mini-legend .legend-ma50 { color: #d29922; }
.mini-legend .legend-ma150 { color: #a371f7; }
.mini-legend .legend-ma200 { color: #8b949e; }
.mini-legend .legend-pivot { color: #1f6feb; }
.mini-legend .legend-support { color: #bf8700; }

.mini-levels {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 6px;
  padding: 0 8px 8px;
  color: #8b949e;
  font-size: 11px;
}

.mini-levels span {
  min-width: 0;
  overflow: hidden;
  padding: 5px 6px;
  border-radius: 6px;
  background: #161b22;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.vcp-summary {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 6px;
  padding: 0 8px 8px;
  color: #8b949e;
  font-size: 11px;
}

.vcp-summary span {
  min-width: 0;
  overflow: hidden;
  padding: 5px 6px;
  border-radius: 6px;
  background: #161b22;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chart-wrap {
  width: 100%;
  overflow: hidden;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #fbfcfd;
}

#candleChart {
  width: 100%;
  height: 430px;
}

.chart-meta {
  margin-top: 10px;
  color: var(--muted);
  font-size: 13px;
}

.chat-log {
  display: grid;
  gap: 10px;
  max-height: 360px;
  overflow: auto;
  padding: 4px;
}

.chat-message {
  width: min(760px, 100%);
  padding: 10px 12px;
  border-radius: 8px;
  line-height: 1.45;
}

.chat-message.assistant {
  background: var(--surface-2);
  border: 1px solid var(--line);
}

.chat-message.user {
  justify-self: end;
  background: #dcebe4;
  border: 1px solid #b8d2c5;
}

.chat-message strong {
  display: block;
  margin-bottom: 4px;
  font-size: 12px;
  text-transform: uppercase;
  color: var(--muted);
}

.chat-form {
  display: flex;
  gap: 8px;
  margin-top: 12px;
}

.chat-form input {
  flex: 1;
  min-height: 40px;
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 0 12px;
  font: inherit;
}

.chat-form button {
  min-height: 40px;
  border: 0;
  border-radius: 6px;
  background: var(--accent);
  color: white;
  padding: 0 16px;
  font-weight: 800;
}

@media (max-width: 820px) {
  .shell {
    padding: 0;
  }

  .app-header {
    padding: 14px;
  }

  .app-header, .toolbar {
    align-items: stretch;
    flex-direction: column;
  }

  .toolbar {
    padding: 0 14px 14px;
  }

  .timestamp {
    text-align: left;
  }

  h1 {
    font-size: 25px;
  }

  .regime, .classification-grid, .focus-grid, .watchlist-grid {
    grid-template-columns: 1fr;
  }

  .regime, #homeView {
    width: calc(100% - 28px);
  }

  #chartBoardView {
    padding: 0 8px 14px;
  }

  .view-switch {
    display: flex;
  }

  .view-switch button {
    flex: 1;
  }

  .chart-board .watchlist-grid {
    grid-template-columns: 1fr;
  }

  .segmented {
    width: 100%;
  }

  .segmented button {
    flex: 1;
  }

  .select-label {
    align-items: stretch;
    flex-direction: column;
  }

  .mini-levels,
  .vcp-summary {
    grid-template-columns: 1fr;
  }

  .chart-metric-row .metric-box.wide,
  .chart-metric-row .metric-box.extra-wide {
    grid-column: span 1;
  }

  select {
    max-width: none;
    width: 100%;
  }

  #candleChart {
    height: 340px;
  }

  .chart-board .mini-chart {
    height: 300px;
  }

  .score-breakdown {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .chat-form {
    flex-direction: column;
  }
}
""",
        encoding="utf-8",
    )

    (SITE_DIR / "app.js").write_text(
        """const state = {
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
  const response = await fetch("data/reports.json");
  const payload = await response.json();
  state.reports = payload.reports.sort((a, b) => b.id.localeCompare(a.id));
  setInitialReport();
  render();
}

boot().catch((error) => {
  document.body.innerHTML = `<main class="shell"><h1>Unable to load dashboard</h1><p>${error.message}</p></main>`;
});
""",
        encoding="utf-8",
    )

    (SITE_DIR / "extras.js").write_text(
        """const extrasState = {
  reports: [],
  priceHistory: {},
  activeTicker: "",
};

function latestReport() {
  return [...extrasState.reports].sort((a, b) => new Date(b.generated_at_local) - new Date(a.generated_at_local))[0] || extrasState.reports[0];
}

function scoreFor(ticker) {
  const report = latestReport();
  return report?.scores?.find((item) => item.ticker === ticker);
}

function tickerList() {
  const report = latestReport();
  return report?.scores?.map((item) => item.ticker) || Object.keys(extrasState.priceHistory);
}

function money(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "Data Missing";
  return Number(value).toFixed(2);
}

function pct(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "Data Missing";
  return `${(Number(value) * 100).toFixed(1)}%`;
}

function initChartControl() {
  const select = document.querySelector("#chartTicker");
  const tickers = tickerList();
  extrasState.activeTicker = extrasState.activeTicker || tickers[0] || "";
  select.innerHTML = tickers.map((ticker) => `<option value="${ticker}">${ticker}</option>`).join("");
  select.value = extrasState.activeTicker;
  select.addEventListener("change", () => {
    extrasState.activeTicker = select.value;
    renderChart();
  });
}

function drawCandles(canvas, rows, score) {
  const ctx = canvas.getContext("2d");
  const ratio = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  canvas.width = Math.max(320, Math.floor(rect.width * ratio));
  canvas.height = Math.floor(rect.height * ratio);
  ctx.scale(ratio, ratio);

  const width = rect.width;
  const height = rect.height;
  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "#fbfcfd";
  ctx.fillRect(0, 0, width, height);

  if (!rows.length) {
    ctx.fillStyle = "#66717f";
    ctx.fillText("No chart data", 18, 32);
    return;
  }

  const pad = { left: 44, right: 14, top: 18, bottom: 34 };
  const chartWidth = width - pad.left - pad.right;
  const chartHeight = height - pad.top - pad.bottom;
  const highs = rows.map((row) => row.high);
  const lows = rows.map((row) => row.low);
  const maxPrice = Math.max(...highs);
  const minPrice = Math.min(...lows);
  const range = Math.max(1, maxPrice - minPrice);
  const y = (price) => pad.top + ((maxPrice - price) / range) * chartHeight;
  const movingAverage = (period) => rows.map((row, index) => {
    if (index + 1 < period) return null;
    const slice = rows.slice(index + 1 - period, index + 1);
    return { date: row.date, value: slice.reduce((sum, item) => sum + item.close, 0) / period };
  });
  const drawLine = (series, color, widthValue = 1.5) => {
    ctx.strokeStyle = color;
    ctx.lineWidth = widthValue;
    ctx.beginPath();
    let started = false;
    series.forEach((point, index) => {
      if (!point) return;
      const x = pad.left + (chartWidth / Math.max(1, rows.length - 1)) * index;
      const yy = y(point.value);
      if (!started) {
        ctx.moveTo(x, yy);
        started = true;
      } else {
        ctx.lineTo(x, yy);
      }
    });
    if (started) ctx.stroke();
  };

  ctx.strokeStyle = "#d9e0e7";
  ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i += 1) {
    const yy = pad.top + (chartHeight / 4) * i;
    ctx.beginPath();
    ctx.moveTo(pad.left, yy);
    ctx.lineTo(width - pad.right, yy);
    ctx.stroke();
    const label = maxPrice - (range / 4) * i;
    ctx.fillStyle = "#66717f";
    ctx.font = "11px system-ui";
    ctx.fillText(label.toFixed(0), 6, yy + 4);
  }

  const candleWidth = Math.max(3, chartWidth / rows.length * 0.58);
  rows.forEach((row, index) => {
    const x = pad.left + (chartWidth / Math.max(1, rows.length - 1)) * index;
    const up = row.close >= row.open;
    const color = up ? "#1f7a5b" : "#b84242";
    ctx.strokeStyle = color;
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.moveTo(x, y(row.high));
    ctx.lineTo(x, y(row.low));
    ctx.stroke();
    const top = y(Math.max(row.open, row.close));
    const bottom = y(Math.min(row.open, row.close));
    ctx.fillRect(x - candleWidth / 2, top, candleWidth, Math.max(1, bottom - top));
  });

  drawLine(movingAverage(20), "#2f5f98", 1.6);
  drawLine(movingAverage(50), "#a15c12", 1.4);
  drawLine(movingAverage(150), "#66717f", 1.2);

  if (score?.pivot) {
    const py = y(score.pivot);
    ctx.strokeStyle = "#2f5f98";
    ctx.setLineDash([6, 4]);
    ctx.beginPath();
    ctx.moveTo(pad.left, py);
    ctx.lineTo(width - pad.right, py);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = "#2f5f98";
    ctx.fillText(`Pivot ${money(score.pivot)}`, pad.left + 6, py - 6);
  }

  if (score?.support) {
    const sy = y(score.support);
    ctx.strokeStyle = "#a15c12";
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(pad.left, sy);
    ctx.lineTo(width - pad.right, sy);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = "#a15c12";
    ctx.fillText(`Support ${money(score.support)}`, pad.left + 6, sy - 6);
  }

  if (score?.high_52w) {
    const hy = y(score.high_52w);
    if (hy >= pad.top && hy <= height - pad.bottom) {
      ctx.strokeStyle = "#8a5fbf";
      ctx.setLineDash([2, 4]);
      ctx.beginPath();
      ctx.moveTo(pad.left, hy);
      ctx.lineTo(width - pad.right, hy);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = "#8a5fbf";
      ctx.fillText(`52W High ${money(score.high_52w)}`, pad.left + 6, hy + 14);
    }
  }
}

function drawMiniChart(canvas, rows, score) {
  const ctx = canvas.getContext("2d");
  const ratio = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  canvas.width = Math.max(260, Math.floor(rect.width * ratio));
  canvas.height = Math.floor(rect.height * ratio);
  ctx.scale(ratio, ratio);

  const width = rect.width;
  const height = rect.height;
  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "#fbfcfd";
  ctx.fillRect(0, 0, width, height);
  const data = rows.slice(-90);
  if (data.length < 2) {
    ctx.fillStyle = "#66717f";
    ctx.fillText("No data", 10, 20);
    return;
  }

  const ma = (period) => data.map((row, index) => {
    if (index + 1 < period) return null;
    const slice = data.slice(index + 1 - period, index + 1);
    return slice.reduce((sum, item) => sum + item.close, 0) / period;
  });
  const candidates = [
    ...data.flatMap((row) => [row.high, row.low, row.close]),
    score?.pivot,
    score?.support,
    score?.high_52w,
  ].filter((value) => value !== null && value !== undefined && Number.isFinite(Number(value)));
  const max = Math.max(...candidates);
  const min = Math.min(...candidates);
  const range = Math.max(1, max - min);
  const pad = { left: 6, right: 42, top: 10, bottom: 18 };
  const chartWidth = width - pad.left - pad.right;
  const chartHeight = height - pad.top - pad.bottom;
  const x = (index) => pad.left + (chartWidth / Math.max(1, data.length - 1)) * index;
  const y = (value) => pad.top + ((max - value) / range) * chartHeight;

  const horizontal = (value, color, label) => {
    if (value === null || value === undefined) return;
    const yy = y(Number(value));
    ctx.strokeStyle = color;
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(pad.left, yy);
    ctx.lineTo(width - pad.right, yy);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = color;
    ctx.font = "10px system-ui";
    ctx.fillText(label, width - pad.right + 4, Math.max(12, Math.min(height - 4, yy + 3)));
  };

  const line = (values, color, lineWidth = 1.4) => {
    ctx.strokeStyle = color;
    ctx.lineWidth = lineWidth;
    ctx.beginPath();
    let started = false;
    values.forEach((value, index) => {
      if (value === null || value === undefined) return;
      const xx = x(index);
      const yy = y(Number(value));
      if (!started) {
        ctx.moveTo(xx, yy);
        started = true;
      } else {
        ctx.lineTo(xx, yy);
      }
    });
    if (started) ctx.stroke();
  };

  horizontal(score?.high_52w, "#8a5fbf", "High");
  horizontal(score?.pivot, "#2f5f98", "Pivot");
  horizontal(score?.support, "#a15c12", "Sup");
  line(data.map((row) => row.close), "#17202a", 1.7);
  line(ma(20), "#2f5f98", 1.3);
  line(ma(50), "#a15c12", 1.2);

  const last = data[data.length - 1];
  const first = data[0];
  const up = last.close >= first.close;
  ctx.fillStyle = up ? "#1f7a5b" : "#b84242";
  ctx.font = "11px system-ui";
  ctx.fillText(`${up ? "+" : ""}${(((last.close / first.close) - 1) * 100).toFixed(1)}%`, pad.left, height - 5);
}

function renderChart() {
  const ticker = extrasState.activeTicker;
  const rows = extrasState.priceHistory[ticker] || [];
  const score = scoreFor(ticker);
  drawCandles(document.querySelector("#candleChart"), rows, score);
  const latest = rows[rows.length - 1];
  document.querySelector("#chartMeta").textContent = latest
    ? `${ticker}: ${latest.date} close ${money(latest.close)}. Status: ${score?.status || "Data Missing"}. Score: ${score?.momentum_score ?? "Data Missing"}/100.`
    : `${ticker}: Data Missing`;
}

function renderMiniCharts() {
  document.querySelectorAll(".mini-chart").forEach((canvas) => {
    const ticker = canvas.dataset.ticker;
    drawMiniChart(canvas, extrasState.priceHistory[ticker] || [], scoreFor(ticker));
  });
}

function addMessage(role, text) {
  const log = document.querySelector("#chatLog");
  const div = document.createElement("div");
  div.className = `chat-message ${role}`;
  div.innerHTML = `<strong>${role === "user" ? "You" : "Assistant"}</strong>${text}`;
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
}

function answerQuestion(raw) {
  const question = raw.toLowerCase();
  const report = latestReport();
  const scores = report?.scores || [];
  const ticker = tickerList().find((item) => question.includes(item.toLowerCase()));
  if (ticker) {
    const score = scoreFor(ticker);
    if (!score) return `${ticker}: Data Missing`;
    return `${ticker}: ${score.category}. Status ${score.status}. Timing ${score.timing_score ?? score.momentum_score}/100. Price ${money(score.price)}, pivot ${money(score.pivot)}, support ${money(score.support)}. ${score.comment}`;
  }
  if (question.includes("突破") || question.includes("breakout")) {
    const watch = scores.filter((item) => ["Actionable Now", "Breakout Watch"].includes(item.category));
    if (!watch.length) return "No actionable or breakout-watch names in the latest report. Confirmation still requires a clean pivot trigger and demand expansion.";
    return `Breakout focus: ${watch.map((item) => `${item.ticker} pivot ${money(item.pivot)}`).join("; ")}. No confirmed breakout unless the daily-close and volume rules are met.`;
  }
  if (question.includes("重点") || question.includes("focus") || question.includes("watch")) {
    const lines = report?.core_attention || [];
    return lines.length ? lines.join("<br>") : "No core attention items found.";
  }
  if (question.includes("avoid") || question.includes("回避")) {
    const avoid = scores.filter((item) => item.category === "Repair Needed");
    return avoid.length ? `Repair needed: ${avoid.map((item) => item.ticker).join(", ")}.` : "No Repair Needed names in the latest report.";
  }
  return "I can answer from the loaded report. Try asking: 'INTC 怎么看', '今天突破重点是什么', '哪些要回避', or 'focus list'.";
}

function initChat() {
  addMessage("assistant", "Local report assistant ready. This version answers from the loaded report data only; it is not connected to a live LLM yet.");
  document.querySelector("#chatForm").addEventListener("submit", (event) => {
    event.preventDefault();
    const input = document.querySelector("#chatInput");
    const value = input.value.trim();
    if (!value) return;
    addMessage("user", value);
    addMessage("assistant", answerQuestion(value));
    input.value = "";
  });
}

async function bootExtras() {
  const [reportsResponse, priceResponse] = await Promise.all([
    fetch("data/reports.json"),
    fetch("data/price_history.json"),
  ]);
  extrasState.reports = (await reportsResponse.json()).reports.sort((a, b) => b.id.localeCompare(a.id));
  extrasState.priceHistory = await priceResponse.json();
  initChartControl();
  renderChart();
  renderMiniCharts();
  initChat();
  window.addEventListener("dashboard:rendered", renderMiniCharts);
  window.addEventListener("resize", renderChart);
  window.addEventListener("resize", renderMiniCharts);
}

bootExtras().catch((error) => {
  console.error(error);
  const meta = document.querySelector("#chartMeta");
  if (meta) meta.textContent = `Unable to load extras: ${error.message}`;
});
""",
        encoding="utf-8",
    )

    extras_template = ROOT / "scripts" / "site_extras.js"
    if extras_template.exists():
        (SITE_DIR / "extras.js").write_text(extras_template.read_text(encoding="utf-8"), encoding="utf-8")


def main() -> None:
    snapshot_paths = sorted(DATA_DIR.glob("*_snapshot.json"))
    reports = [load_report(path) for path in snapshot_paths]
    reports.sort(key=lambda item: item["id"], reverse=True)
    write_site_files(reports)
    print(SITE_DIR / "index.html")


if __name__ == "__main__":
    main()

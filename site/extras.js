const extrasState = {
  reports: [],
  priceHistory: {},
  activeTicker: "",
  miniCharts: new Map(),
};

const CHART_COLORS = {
  up: "#2ea043",
  down: "#d73a49",
  ma5: "#58a6ff",
  ma10: "#f0883e",
  ma20: "#d2a8ff",
  ma30: "#56d364",
  ma60: "#e3b341",
  ma50: "#8b949e",
  ma150: "#8b5cf6",
  ma200: "#57606a",
  expma5: "#79c0ff",
  expma10: "#ffb347",
  expma20: "#e2b8ff",
  expma30: "#85e89d",
  expma60: "#ffd37e",
  pivot: "#1f6feb",
  support: "#bf8700",
  resistance: "#8250df",
  pullback: "#ff7b72",
  volumeUp: "rgba(46, 160, 67, 0.42)",
  volumeDown: "rgba(248, 81, 73, 0.42)",
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

function movingAverage(rows, period) {
  return rows.map((row, index) => {
    if (index + 1 < period) return null;
    const slice = rows.slice(index + 1 - period, index + 1);
    return slice.reduce((sum, item) => sum + item.close, 0) / period;
  });
}

function chartRows(ticker, limit = 120) {
  return (extrasState.priceHistory[ticker] || []).slice(-limit);
}

function maValues(rows, period) {
  const key = `ma${period}`;
  if (rows.some((row) => row[key] !== undefined)) {
    return rows.map((row) => row[key] ?? null);
  }
  return movingAverage(rows, period);
}

function expmaValues(rows, period) {
  const alpha = 2 / (period + 1);
  let prev = null;
  return rows.map((row) => {
    prev = prev === null ? row.close : row.close * alpha + prev * (1 - alpha);
    return prev;
  });
}

function avg(values) {
  const clean = values.filter((value) => Number.isFinite(value));
  if (!clean.length) return null;
  return clean.reduce((sum, value) => sum + value, 0) / clean.length;
}

function localExtreme(rows, index, field, compare) {
  const start = Math.max(0, index - 2);
  const end = Math.min(rows.length - 1, index + 2);
  const value = rows[index][field];
  for (let i = start; i <= end; i += 1) {
    if (i !== index && compare(rows[i][field], value)) return false;
  }
  return true;
}

function detectPullbacks(rows) {
  if (rows.length < 20) return { pullbacks: [], sequence: "Data Missing", volumeState: "Data Missing", tightness: "Data Missing" };
  const highs = [];
  for (let i = 2; i < rows.length - 2; i += 1) {
    if (localExtreme(rows, i, "high", (candidate, value) => candidate > value)) highs.push(i);
  }
  const pullbacks = [];
  highs.forEach((highIndex, highPosition) => {
    const nextHighIndex = highs[highPosition + 1] || rows.length - 1;
    if (nextHighIndex <= highIndex + 2) return;
    let lowIndex = highIndex + 1;
    for (let i = highIndex + 1; i <= nextHighIndex; i += 1) {
      if (rows[i].low < rows[lowIndex].low) lowIndex = i;
    }
    const high = rows[highIndex].high;
    const low = rows[lowIndex].low;
    if (!high || lowIndex <= highIndex) return;
    const depth = (low / high) - 1;
    if (depth > -0.025) return;
    const pullbackVolume = avg(rows.slice(highIndex, lowIndex + 1).map((row) => row.volume));
    const priorLowIndex = highPosition > 0 ? highs[highPosition - 1] : Math.max(0, highIndex - 12);
    const priorVolume = avg(rows.slice(priorLowIndex, highIndex + 1).map((row) => row.volume));
    pullbacks.push({
      highIndex,
      lowIndex,
      high,
      low,
      depth,
      pullbackVolume,
      priorVolume,
      label: `${(depth * 100).toFixed(1)}%`,
    });
  });
  const recent = pullbacks.slice(-4);
  const depths = recent.map((item) => Math.abs(item.depth));
  const improving = depths.length >= 2 && depths.slice(1).every((depth, index) => depth <= depths[index] * 1.15);
  const dryingCount = recent.filter((item) => item.pullbackVolume !== null && item.priorVolume !== null && item.pullbackVolume < item.priorVolume * 0.9).length;
  const sequence = recent.length ? recent.map((item) => item.label).join(" / ") : "None";
  const volumeState = recent.length
    ? dryingCount >= Math.ceil(recent.length / 2) ? "Drying" : "Mixed"
    : "None";
  const tightness = recent.length >= 2 ? (improving ? "Improving" : "Messy") : "Need More";
  return { pullbacks: recent, sequence, volumeState, tightness };
}

function buildPullbackMarks(rows, pullbacks) {
  return pullbacks.map((item) => ([
    {
      coord: [rows[item.highIndex].date, item.high],
      lineStyle: { color: CHART_COLORS.pullback, type: "dashed", width: 1 },
      label: {
        show: true,
        formatter: item.label,
        color: CHART_COLORS.pullback,
        fontSize: 10,
        position: "middle",
      },
    },
    {
      coord: [rows[item.lowIndex].date, item.low],
      lineStyle: { color: CHART_COLORS.pullback, type: "dashed", width: 1 },
    },
  ]));
}

function buildMarkLines(score, compact = false) {
  const lines = [];
  const addLine = (value, name, color, type = "dashed", position = "insideEndTop") => {
    if (value === null || value === undefined || Number.isNaN(Number(value))) return;
    lines.push({
      yAxis: Number(value),
      name,
      lineStyle: { color, type, width: compact ? 1 : 1.2 },
      label: {
        show: !compact,
        formatter: compact ? name : `${name} ${money(value)}`,
        color,
        fontSize: compact ? 9 : 10,
        position,
      },
    });
  };
  addLine(score?.high_52w, "Resistance", CHART_COLORS.resistance, "dotted", "insideStartTop");
  addLine(score?.pivot, "Pivot", CHART_COLORS.pivot, "dashed", "insideEndTop");
  addLine(score?.support, "Support", CHART_COLORS.support, "dotted", "insideEndBottom");
  return lines;
}

function buildChartOption(ticker, rows, score, compact = false) {
  const dates = rows.map((row) => row.date);
  const kline = rows.map((row) => [row.open, row.close, row.low, row.high]);
  const volume = rows.map((row) => ({
    value: row.volume,
    itemStyle: { color: row.close >= row.open ? CHART_COLORS.volumeUp : CHART_COLORS.volumeDown },
  }));
  const ma5 = maValues(rows, 5);
  const ma10 = maValues(rows, 10);
  const ma20 = maValues(rows, 20);
  const ma30 = maValues(rows, 30);
  const ma60 = maValues(rows, 60);
  const expma5 = expmaValues(rows, 5);
  const expma10 = expmaValues(rows, 10);
  const expma20 = expmaValues(rows, 20);
  const expma30 = expmaValues(rows, 30);
  const expma60 = expmaValues(rows, 60);
  const contraction = detectPullbacks(rows);
  const markLine = { silent: true, symbol: "none", data: buildMarkLines(score, compact) };
  const pullbackMarkLine = {
    silent: true,
    symbol: "none",
    data: buildPullbackMarks(rows, contraction.pullbacks),
  };
  const baseText = { color: "#8b949e", fontSize: compact ? 9 : 11 };
  const startValue = Math.max(0, rows.length - 30);

  return {
    backgroundColor: "#0d1117",
    animation: false,
    tooltip: {
      show: true,
      trigger: "axis",
      axisPointer: { type: "cross" },
      backgroundColor: "rgba(22,27,34,0.96)",
      borderColor: "#30363d",
      textStyle: { color: "#c9d1d9", fontSize: 12 },
      formatter(params) {
        const dt = params[0]?.axisValue || "";
        let html = `<strong>${ticker} ${dt}</strong><br>`;
        params.forEach((p) => {
          if (p.seriesType === "candlestick") {
            const [, open, close, low, high] = p.value;
            html += `O ${money(open)} H ${money(high)} L ${money(low)} C ${money(close)}<br>`;
          } else if (p.seriesName === "VOL") {
            html += `Volume ${Number(p.value).toLocaleString()}<br>`;
          } else if (p.value !== null && p.value !== undefined) {
            html += `${p.seriesName} ${money(p.value)}<br>`;
          }
        });
        return html;
      },
    },
    axisPointer: {
      link: compact ? undefined : [{ xAxisIndex: "all" }],
      label: { backgroundColor: "#2f5f98" },
    },
    legend: compact ? undefined : {
      top: 2,
      right: 8,
      data: ["K", "MA5", "MA10", "MA20", "MA30", "MA60", "EXPMA5", "EXPMA10", "EXPMA20", "EXPMA30", "EXPMA60"],
      textStyle: baseText,
      itemWidth: 12,
      itemHeight: 2,
      selected: {
        EXPMA5: false,
        EXPMA10: false,
        EXPMA20: false,
        EXPMA30: false,
        EXPMA60: false,
      },
    },
    grid: compact
      ? [
          { left: 50, right: 46, top: 16, bottom: 76 },
          { left: 50, right: 46, top: "82%", bottom: 42 },
        ]
      : [
          { left: 50, right: 16, top: 34, bottom: 78 },
          { left: 50, right: 16, top: "82%", bottom: 24 },
        ],
    xAxis: compact
      ? [
          {
            type: "category",
            data: dates,
            boundaryGap: true,
            axisLabel: { ...baseText, formatter: (value) => value.slice(5) },
            axisLine: { lineStyle: { color: "#30363d" } },
            splitLine: { show: false },
          },
          {
            type: "category",
            data: dates,
            gridIndex: 1,
            axisLabel: { show: false },
            axisLine: { lineStyle: { color: "#30363d" } },
            splitLine: { show: false },
          },
        ]
      : [
          {
            type: "category",
            data: dates,
            boundaryGap: true,
            axisLabel: { ...baseText, formatter: (value) => value.slice(5) },
            axisLine: { lineStyle: { color: "#30363d" } },
            splitLine: { show: false },
          },
          {
            type: "category",
            data: dates,
            gridIndex: 1,
            axisLabel: { show: false },
            axisLine: { lineStyle: { color: "#30363d" } },
            splitLine: { show: false },
          },
        ],
    yAxis: compact
      ? [
          {
            scale: true,
            position: "right",
            axisLabel: { ...baseText, formatter: (value) => Number(value).toFixed(0) },
            splitLine: { lineStyle: { color: "#21262d" } },
          },
          {
            scale: true,
            gridIndex: 1,
            axisLabel: { show: false },
            splitLine: { show: false },
          },
        ]
      : [
          {
            scale: true,
            axisLabel: baseText,
            splitLine: { lineStyle: { color: "#21262d" } },
          },
          {
            scale: true,
            gridIndex: 1,
            axisLabel: { show: false },
            splitLine: { show: false },
          },
        ],
    dataZoom: [
      { type: "inside", xAxisIndex: compact ? [0, 1] : [0, 1], startValue, endValue: rows.length - 1 },
      {
        type: "slider",
        xAxisIndex: compact ? [0, 1] : [0, 1],
        bottom: compact ? 8 : 4,
        height: compact ? 18 : 18,
        borderColor: "#30363d",
        textStyle: baseText,
        handleStyle: { color: CHART_COLORS.pivot },
        fillerColor: "rgba(88, 166, 255, 0.16)",
        dataBackground: {
          lineStyle: { color: "#30363d" },
          areaStyle: { color: "#161b22" },
        },
        selectedDataBackground: {
          lineStyle: { color: "#58a6ff" },
          areaStyle: { color: "rgba(88, 166, 255, 0.18)" },
        },
        startValue,
        endValue: rows.length - 1,
      },
    ],
    series: [
      {
        name: "K",
        type: "candlestick",
        data: kline,
        itemStyle: {
          color: CHART_COLORS.up,
          color0: CHART_COLORS.down,
          borderColor: CHART_COLORS.up,
          borderColor0: CHART_COLORS.down,
        },
        markLine,
      },
      {
        name: "Pullback",
        type: "line",
        data: dates.map(() => null),
        symbol: "none",
        lineStyle: { opacity: 0 },
        markLine: pullbackMarkLine,
      },
      {
        name: "MA5",
        type: "line",
        data: ma5,
        symbol: "none",
        lineStyle: { width: compact ? 1 : 1.4, color: CHART_COLORS.ma5 },
      },
      {
        name: "MA10",
        type: "line",
        data: ma10,
        symbol: "none",
        lineStyle: { width: compact ? 1 : 1.4, color: CHART_COLORS.ma10 },
      },
      {
        name: "MA20",
        type: "line",
        data: ma20,
        symbol: "none",
        lineStyle: { width: compact ? 1 : 1.4, color: CHART_COLORS.ma20 },
      },
      {
        name: "MA30",
        type: "line",
        data: ma30,
        symbol: "none",
        lineStyle: { width: compact ? 1 : 1.3, color: CHART_COLORS.ma30 },
      },
      {
        name: "MA60",
        type: "line",
        data: ma60,
        symbol: "none",
        lineStyle: { width: compact ? 1 : 1.2, color: CHART_COLORS.ma60 },
      },
      ...(compact ? [] : [
        {
          name: "EXPMA5",
          type: "line",
          data: expma5,
          symbol: "none",
          lineStyle: { width: 1.5, color: CHART_COLORS.expma5, type: "dashed" },
        },
        {
          name: "EXPMA10",
          type: "line",
          data: expma10,
          symbol: "none",
          lineStyle: { width: 1.5, color: CHART_COLORS.expma10, type: "dashed" },
        },
        {
          name: "EXPMA20",
          type: "line",
          data: expma20,
          symbol: "none",
          lineStyle: { width: 1.5, color: CHART_COLORS.expma20, type: "dashed" },
        },
        {
          name: "EXPMA30",
          type: "line",
          data: expma30,
          symbol: "none",
          lineStyle: { width: 1.5, color: CHART_COLORS.expma30, type: "dashed" },
        },
        {
          name: "EXPMA60",
          type: "line",
          data: expma60,
          symbol: "none",
          lineStyle: { width: 1.5, color: CHART_COLORS.expma60, type: "dashed" },
        },
      ]),
      {
        name: "VOL",
        type: "bar",
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: volume,
      },
    ],
  };
}

function renderMiniCharts() {
  if (!window.echarts) return;
  const visible = [...document.querySelectorAll(".mini-chart")];
  const visibleSet = new Set(visible);
  extrasState.miniCharts.forEach((chart, element) => {
    if (!visibleSet.has(element)) {
      chart.dispose();
      extrasState.miniCharts.delete(element);
    }
  });
  visible.forEach((element) => {
    const ticker = element.dataset.ticker;
    const rows = chartRows(ticker, 90);
    const score = scoreFor(ticker);
    const contraction = detectPullbacks(rows);
    const summary = document.querySelector(`.vcp-summary[data-vcp-ticker="${ticker}"]`);
    if (summary) {
      summary.innerHTML = `
        <span>Pullbacks ${contraction.sequence}</span>
        <span>Volume ${contraction.volumeState}</span>
        <span>Tightness ${contraction.tightness}</span>
      `;
    }
    let chart = extrasState.miniCharts.get(element);
    if (!chart) {
      chart = echarts.init(element, null, { renderer: "canvas" });
      extrasState.miniCharts.set(element, chart);
    }
    chart.setOption(buildChartOption(ticker, rows, score, true), true);
  });
}

function resizeCharts() {
  extrasState.miniCharts.forEach((chart) => chart.resize());
}

function initViewSwitch() {
  document.querySelectorAll(".view-switch button").forEach((button) => {
    button.addEventListener("click", () => {
      const targetId = button.dataset.view;
      document.querySelectorAll(".view-switch button").forEach((item) => {
        item.classList.toggle("active", item === button);
      });
      document.querySelectorAll(".view").forEach((view) => {
        view.hidden = view.id !== targetId;
      });
      if (targetId === "chartBoardView") {
        requestAnimationFrame(() => {
          renderMiniCharts();
          resizeCharts();
        });
      }
    });
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
    return `${ticker}: ${score.category}. Status ${score.status}. Timing ${score.timing_score ?? score.momentum_score}/100. Price ${money(score.price)}, session ${score.session_context || "Data Missing"}, pivot ${money(score.pivot)}, support ${money(score.support)}. ${score.comment}`;
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
  renderMiniCharts();
  initViewSwitch();
  initChat();
  window.addEventListener("dashboard:rendered", renderMiniCharts);
  window.addEventListener("resize", resizeCharts);
}

bootExtras().catch((error) => {
  console.error(error);
  document.querySelectorAll(".vcp-summary").forEach((item) => {
    item.innerHTML = `<span>Chart data unavailable</span>`;
  });
});

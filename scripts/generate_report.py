from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import yfinance as yf


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
PRICE_DIR = DATA_DIR / "prices"
REPORT_DIR = ROOT / "reports"

WATCHLIST = [
    "INTC",
    "STM",
    "AMD",
    "MU",
    "NVDA",
    "BE",
    "TTMI",
    "SNDK",
    "MXL",
    "LITE",
    "AVGO",
    "CIEN",
]

BENCHMARKS = ["QQQ", "SOXX", "SMH"]


@dataclass
class Analysis:
    ticker: str
    price: float | None
    volume: float | None
    avg_volume_20: float | None
    max_volume_20: float | None
    volume_vs_avg_20: float | None
    volume_vs_max_20: float | None
    ma5: float | None
    ma10: float | None
    ma20: float | None
    ma30: float | None
    ma50: float | None
    ma60: float | None
    ma150: float | None
    ma200: float | None
    high_52w: float | None
    pivot: float | None
    support: float | None
    support_basis: str
    session_price: float | None
    session_move_pct: float | None
    session_time: str
    session_label: str
    session_context: str
    trend_gate: bool
    trend_age: int
    trend_phase: str
    short_ma_state: str
    short_ma_spread_pct: float | None
    ma_expansion_state: str
    ma_expansion_start_date: str
    ma_expansion_age: int
    expma_state: str
    expma_spread_pct: float | None
    expma_stack_age: int
    expma_start_date: str
    gain_expma_to_ma_pct: float | None
    gain_ma_to_now_pct: float | None
    gain_expma_to_now_pct: float | None
    days_above_50ma: int
    ma_stack_age: int
    extension_20_pct: float | None
    pivot_gap_pct: float | None
    setup_quality_score: int
    breakout_readiness_score: int
    demand_score: int
    entry_risk_score: int
    timing_score: int
    setup_state: str
    contraction_sequence: str
    pullback_volume_detail: str
    volume_state: str
    tightness_state: str
    trend_signal: str
    trend_score: int
    rs_score: int
    setup_score: int
    volume_score: int
    risk_score: int
    momentum_score: int
    status: str
    key_level: str
    invalidation: str
    comment: str
    data_missing: bool


def ensure_dirs() -> None:
    PRICE_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)


def flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [col[0] if isinstance(col, tuple) else col for col in df.columns]
    return df


def fetch_history(ticker: str, period: str = "2y") -> pd.DataFrame:
    df = yf.download(ticker, period=period, interval="1d", auto_adjust=False, progress=False)
    df = flatten_columns(df)
    if df.empty:
        return df
    df.index = pd.to_datetime(df.index)
    df = df.dropna(subset=["Close"])
    df.to_csv(PRICE_DIR / f"{ticker}.csv")
    return df


def fetch_intraday_history(ticker: str) -> pd.DataFrame:
    df = yf.download(ticker, period="5d", interval="5m", prepost=True, auto_adjust=False, progress=False)
    df = flatten_columns(df)
    if df.empty:
        return df
    df.index = pd.to_datetime(df.index)
    return df.dropna(subset=["Close"])


def pct_return(df: pd.DataFrame, days: int) -> float | None:
    if len(df) <= days:
        return None
    start = df["Close"].iloc[-days - 1]
    end = df["Close"].iloc[-1]
    if not np.isfinite(start) or start == 0:
        return None
    return float((end / start) - 1)


def safe_float(value: object) -> float | None:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(value):
        return None
    return value


def fmt_money(value: float | None) -> str:
    return "Data Missing" if value is None else f"{value:.2f}"


def fmt_num(value: float | None) -> str:
    return "Data Missing" if value is None else f"{value:,.0f}"


def fmt_pct(value: float | None) -> str:
    return "Data Missing" if value is None else f"{value * 100:.1f}%"


def fmt_ratio(value: float | None) -> str:
    return "Data Missing" if value is None else f"{value:.2f}x"


def distance_pct(price: float | None, level: float | None) -> float | None:
    if price is None or level is None or level == 0:
        return None
    return (price / level) - 1


def moving_average(df: pd.DataFrame, days: int) -> float | None:
    if len(df) < days:
        return None
    return safe_float(df["Close"].rolling(days).mean().iloc[-1])


def exp_moving_average(df: pd.DataFrame, days: int) -> float | None:
    if len(df) < days:
        return None
    return safe_float(df["Close"].ewm(span=days, adjust=False).mean().iloc[-1])


def recent_pivot(df: pd.DataFrame) -> float | None:
    if len(df) < 21:
        return None
    lookback = df.iloc[-61:-1] if len(df) >= 61 else df.iloc[:-1]
    if lookback.empty:
        return None
    return safe_float(lookback["High"].max())


def recent_support(df: pd.DataFrame) -> float | None:
    if len(df) < 21:
        return None
    lookback = df.iloc[-21:-1]
    return safe_float(lookback["Low"].min())


def support_basis_text() -> str:
    return "20D low excluding latest bar"


def rolling_ma_series(df: pd.DataFrame, days: int) -> pd.Series:
    return df["Close"].rolling(days).mean()


def consecutive_true(mask: pd.Series) -> int:
    count = 0
    for value in reversed(mask.fillna(False).tolist()):
        if bool(value):
            count += 1
        else:
            break
    return count


def trend_phase(age: int) -> str:
    if age <= 0:
        return "No Trend"
    if age <= 2:
        return "Early Turn"
    if age <= 15:
        return "Fresh Trend"
    if age <= 45:
        return "Developing Trend"
    if age <= 90:
        return "Mature Trend"
    return "Late / Extended Trend"


def short_ma_state(price: float | None, ma5: float | None, ma10: float | None, ma20: float | None) -> tuple[str, float | None]:
    if price is None or ma5 is None or ma10 is None or ma20 is None or ma20 == 0:
        return "Data Missing", None
    spread = (ma5 / ma20) - 1
    if price >= ma5 and ma5 > ma10 > ma20:
        return "Bullish Expansion", spread
    if price >= ma10 and ma5 >= ma10 >= ma20:
        return "Constructive", spread
    if price < ma10 and ma5 >= ma10 >= ma20:
        return "Pullback Watch", spread
    if ma5 < ma10 and price < ma10:
        return "Short-Term Weakening", spread
    return "Neutral / Entangled", spread


def stacked_start_date(df: pd.DataFrame, age: int) -> str:
    if age <= 0 or len(df) < age:
        return ""
    return str(df.index[-age].date())


def pct_gain_between(df: pd.DataFrame, start_date: str, end_date: str | None = None) -> float | None:
    if not start_date:
        return None
    start_rows = df[df.index.date >= pd.to_datetime(start_date).date()]
    if start_rows.empty:
        return None
    start_close = safe_float(start_rows["Close"].iloc[0])
    if end_date:
        end_rows = df[df.index.date >= pd.to_datetime(end_date).date()]
        if end_rows.empty:
            return None
        end_close = safe_float(end_rows["Close"].iloc[0])
    else:
        end_close = safe_float(df["Close"].iloc[-1])
    if start_close is None or end_close is None or start_close == 0:
        return None
    return (end_close / start_close) - 1


def ma_expansion_lifecycle(df: pd.DataFrame) -> tuple[str, str, int]:
    if len(df) < 60:
        return "Data Missing", "", 0
    ma5 = rolling_ma_series(df, 5)
    ma10 = rolling_ma_series(df, 10)
    ma20 = rolling_ma_series(df, 20)
    ma30 = rolling_ma_series(df, 30)
    ma60 = rolling_ma_series(df, 60)
    stack = (ma5 > ma10) & (ma10 > ma20) & (ma20 > ma30) & (ma30 > ma60)
    age = consecutive_true(stack)
    return ("MA Bullish Expansion" if age > 0 else "MA Not Expanded"), stacked_start_date(df, age), age


def expma_lifecycle(df: pd.DataFrame) -> tuple[str, float | None, int, str]:
    if len(df) < 60:
        return "Data Missing", None, 0, ""
    ema5 = df["Close"].ewm(span=5, adjust=False).mean()
    ema10 = df["Close"].ewm(span=10, adjust=False).mean()
    ema20 = df["Close"].ewm(span=20, adjust=False).mean()
    ema30 = df["Close"].ewm(span=30, adjust=False).mean()
    ema60 = df["Close"].ewm(span=60, adjust=False).mean()
    stack = (ema5 > ema10) & (ema10 > ema20) & (ema20 > ema30) & (ema30 > ema60)
    age = consecutive_true(stack)
    latest_ema5 = safe_float(ema5.iloc[-1])
    latest_ema10 = safe_float(ema10.iloc[-1])
    latest_ema60 = safe_float(ema60.iloc[-1])
    price = safe_float(df["Close"].iloc[-1])
    spread = distance_pct(latest_ema5, latest_ema60)
    start_date = stacked_start_date(df, age)
    if price is None or latest_ema5 is None or latest_ema60 is None:
        return "Data Missing", spread, age, start_date
    if age > 0 and price >= latest_ema10:
        return "EXPMA Bullish Expansion", spread, age, start_date
    if age > 0:
        return "EXPMA Pullback Watch", spread, age, start_date
    return "EXPMA Not Expanded", spread, age, start_date


def trend_lifecycle(df: pd.DataFrame, high_52w: float | None) -> tuple[bool, int, str, int, int]:
    if len(df) < 200 or high_52w is None:
        return False, 0, "Data Missing", 0, 0
    ma50 = rolling_ma_series(df, 50)
    ma150 = rolling_ma_series(df, 150)
    ma200 = rolling_ma_series(df, 200)
    close = df["Close"]
    stack = (ma50 > ma150) & (ma150 > ma200)
    above50 = close > ma50
    gate = above50 & (close > ma150) & (close > ma200) & stack & (close >= high_52w * 0.75)
    age = consecutive_true(gate)
    days_above_50 = consecutive_true(above50)
    ma_stack = consecutive_true(stack)
    return bool(gate.iloc[-1]), age, trend_phase(age), days_above_50, ma_stack


def local_extreme(df: pd.DataFrame, index: int, column: str, mode: str) -> bool:
    start = max(0, index - 2)
    end = min(len(df) - 1, index + 2)
    value = df[column].iloc[index]
    window = df[column].iloc[start : end + 1]
    if mode == "high":
        return bool(value >= window.max())
    return bool(value <= window.min())


def contraction_metrics(df: pd.DataFrame, lookback: int = 90) -> dict[str, object]:
    window = df.tail(lookback).copy()
    if len(window) < 20:
        return {"sequence": "Data Missing", "volume_state": "Data Missing", "tightness_state": "Data Missing", "pullbacks": []}
    window = window.reset_index(drop=False)
    highs = [idx for idx in range(2, len(window) - 2) if local_extreme(window, idx, "High", "high")]
    pullbacks: list[dict[str, float | int | str | None]] = []
    for pos, high_idx in enumerate(highs):
        next_high = highs[pos + 1] if pos + 1 < len(highs) else len(window) - 1
        if next_high <= high_idx + 2:
            continue
        low_idx = int(window["Low"].iloc[high_idx : next_high + 1].idxmin())
        high = safe_float(window["High"].iloc[high_idx])
        low = safe_float(window["Low"].iloc[low_idx])
        if high is None or low is None or high == 0 or low_idx <= high_idx:
            continue
        depth = (low / high) - 1
        if depth > -0.025:
            continue
        pb_vol = safe_float(window["Volume"].iloc[high_idx : low_idx + 1].mean())
        prior_start = max(0, highs[pos - 1] if pos > 0 else high_idx - 12)
        prior_vol = safe_float(window["Volume"].iloc[prior_start : high_idx + 1].mean())
        pullbacks.append(
            {
                "high_idx": high_idx,
                "low_idx": low_idx,
                "depth": depth,
                "pullback_volume": pb_vol,
                "prior_volume": prior_vol,
            }
        )
    recent = pullbacks[-4:]
    depths = [abs(float(item["depth"])) for item in recent]
    improving = len(depths) >= 2 and all(depths[i] <= depths[i - 1] * 1.15 for i in range(1, len(depths)))
    drying = [
        item
        for item in recent
        if item["pullback_volume"] is not None
        and item["prior_volume"] is not None
        and float(item["pullback_volume"]) < float(item["prior_volume"]) * 0.9
    ]
    sequence = " / ".join(f"{float(item['depth']) * 100:.1f}%" for item in recent) if recent else "None"
    volume_state = "Drying" if recent and len(drying) >= max(1, len(recent) // 2) else "Mixed" if recent else "None"
    tightness_state = "Improving" if improving else "Messy" if len(recent) >= 2 else "Need More"
    return {"sequence": sequence, "volume_state": volume_state, "tightness_state": tightness_state, "pullbacks": recent}


def pullback_volume_detail(contraction: dict[str, object], avg_volume_20: float | None) -> str:
    pullbacks = contraction.get("pullbacks", [])
    if not isinstance(pullbacks, list) or not pullbacks:
        return "None"
    parts = []
    for item in pullbacks[-4:]:
        if not isinstance(item, dict):
            continue
        depth = safe_float(item.get("depth"))
        pb_vol = safe_float(item.get("pullback_volume"))
        prior_vol = safe_float(item.get("prior_volume"))
        prior_ratio = pb_vol / prior_vol if pb_vol is not None and prior_vol not in (None, 0) else None
        avg_ratio = pb_vol / avg_volume_20 if pb_vol is not None and avg_volume_20 not in (None, 0) else None
        depth_text = "Data Missing" if depth is None else f"{depth * 100:.1f}%"
        parts.append(f"{depth_text} vol {fmt_ratio(avg_ratio)} avg20 / {fmt_ratio(prior_ratio)} prior")
    return " | ".join(parts) if parts else "None"


def setup_quality_score(df: pd.DataFrame, price: float | None, pivot: float | None, ma20: float | None, ma50: float | None, contraction: dict[str, object]) -> int:
    score = 0
    gap = distance_pct(price, pivot)
    if gap is not None:
        if -0.05 <= gap <= 0.02:
            score += 12
        elif -0.10 <= gap < -0.05 or 0.02 < gap <= 0.05:
            score += 6
    if contraction["tightness_state"] == "Improving":
        score += 10
    elif contraction["tightness_state"] == "Need More":
        score += 4
    recent = df.tail(10)
    if not recent.empty:
        tight_range = (recent["High"].max() / recent["Low"].min()) - 1 if recent["Low"].min() else None
        if tight_range is not None and tight_range <= 0.08:
            score += 8
        elif tight_range is not None and tight_range <= 0.14:
            score += 4
    if price is not None and ((ma20 is not None and price >= ma20) or (ma50 is not None and price >= ma50)):
        score += 5
    return min(score, 35)


def breakout_readiness_score(price: float | None, pivot: float | None, volume: float | None, avg_volume_20: float | None, trend_gate: bool) -> int:
    score = 0
    gap = distance_pct(price, pivot)
    if trend_gate:
        score += 6
    if gap is not None:
        if -0.03 <= gap <= 0.01:
            score += 12
        elif -0.06 <= gap < -0.03 or 0.01 < gap <= 0.03:
            score += 7
        elif -0.10 <= gap < -0.06:
            score += 3
        if gap > 0:
            score += 4
    if volume is not None and avg_volume_20 is not None:
        if volume >= avg_volume_20 * 1.5:
            score += 8
        elif volume >= avg_volume_20:
            score += 4
    return min(score, 30)


def demand_score(df: pd.DataFrame, volume: float | None, avg_volume_20: float | None, contraction: dict[str, object]) -> int:
    score = 0
    if len(df) >= 21:
        recent = df.iloc[-20:].copy()
        up_volume = recent.loc[recent["Close"] > recent["Open"], "Volume"].mean()
        down_volume = recent.loc[recent["Close"] < recent["Open"], "Volume"].mean()
        if pd.notna(up_volume) and pd.notna(down_volume) and up_volume > down_volume:
            score += 7
        pullbacks = recent[recent["Close"].diff() < 0]
        if not pullbacks.empty and pullbacks["Volume"].mean() < recent["Volume"].mean():
            score += 5
    if contraction["volume_state"] == "Drying":
        score += 4
    if volume is not None and avg_volume_20 is not None and volume > avg_volume_20:
        score += 4
    return min(score, 20)


def entry_risk_score(price: float | None, pivot: float | None, support: float | None, ma20: float | None) -> int:
    score = 0
    gap = distance_pct(price, pivot)
    if gap is not None:
        if -0.05 <= gap <= 0.02:
            score += 6
        elif -0.10 <= gap < -0.05 or 0.02 < gap <= 0.05:
            score += 3
    anchor = support if support is not None else pivot
    if price is not None and anchor is not None and price > 0:
        risk = (price - anchor) / price
        if 0 <= risk <= 0.08:
            score += 5
        elif 0.08 < risk <= 0.12:
            score += 2
    if price is not None and ma20 is not None:
        extension = (price / ma20) - 1
        if extension <= 0.08:
            score += 4
        elif extension <= 0.15:
            score += 2
    return min(score, 15)


def trend_score(price: float | None, ma50: float | None, ma150: float | None, ma200: float | None, high_52w: float | None) -> int:
    score = 0
    score += 5 if price is not None and ma50 is not None and price > ma50 else 0
    score += 5 if price is not None and ma150 is not None and price > ma150 else 0
    score += 5 if price is not None and ma200 is not None and price > ma200 else 0
    score += 5 if ma50 is not None and ma150 is not None and ma50 > ma150 else 0
    score += 5 if ma150 is not None and ma200 is not None and ma150 > ma200 else 0
    score += 5 if price is not None and high_52w is not None and price >= high_52w * 0.75 else 0
    return score


def relative_strength_score(df: pd.DataFrame, qqq: pd.DataFrame, soxx: pd.DataFrame, watch_returns_3m: dict[str, float | None], ticker: str) -> int:
    score = 0
    periods = [(5, 5), (21, 8), (63, 8)]
    for days, points in periods:
        stock_ret = pct_return(df, days)
        qqq_ret = pct_return(qqq, days)
        soxx_ret = pct_return(soxx, days)
        if stock_ret is not None and qqq_ret is not None and soxx_ret is not None and stock_ret > qqq_ret and stock_ret > soxx_ret:
            score += points
    ranked = [v for v in watch_returns_3m.values() if v is not None]
    own = watch_returns_3m.get(ticker)
    if own is not None and ranked:
        threshold = np.quantile(ranked, 0.75)
        score += 4 if own >= threshold else 0
    return score


def setup_score(price: float | None, volume: float | None, avg_volume_20: float | None, pivot: float | None) -> int:
    score = 0
    if price is not None and pivot is not None:
        distance = (pivot - price) / pivot
        if -0.02 <= distance <= 0.05:
            score += 5
        if price > pivot:
            score += 5
    if volume is not None and avg_volume_20 is not None and volume > avg_volume_20 * 1.5:
        score += 5
    return score


def volume_score(df: pd.DataFrame, volume: float | None, avg_volume_20: float | None) -> int:
    score = 0
    if len(df) >= 21:
        recent = df.iloc[-20:].copy()
        up_volume = recent.loc[recent["Close"] > recent["Open"], "Volume"].mean()
        down_volume = recent.loc[recent["Close"] < recent["Open"], "Volume"].mean()
        if pd.notna(up_volume) and pd.notna(down_volume) and up_volume > down_volume:
            score += 5
        pullbacks = recent[recent["Close"].diff() < 0]
        if not pullbacks.empty and pullbacks["Volume"].mean() < recent["Volume"].mean():
            score += 5
    if volume is not None and avg_volume_20 is not None and volume > avg_volume_20:
        score += 5
    return score


def risk_score(price: float | None, pivot: float | None, support: float | None, ma20: float | None) -> int:
    score = 0
    anchor = support if support is not None else pivot
    if price is not None and anchor is not None and abs(price - anchor) / price <= 0.05:
        score += 4
    if price is not None and anchor is not None and price > anchor and (price - anchor) / price <= 0.08:
        score += 3
    if price is not None and ma20 is not None and price <= ma20 * 1.15:
        score += 3
    return score


def classify_status(price: float | None, pivot: float | None, support: float | None, ma20: float | None, ma50: float | None, trend_gate: bool, timing: int) -> str:
    if price is None:
        return "Data Missing"
    if support is not None and price < support:
        return "Structure Break"
    if ma50 is not None and price < ma50:
        return "Trend Break"
    if ma20 is not None and price < ma20:
        return "Early Warning"
    if not trend_gate:
        return "Repair Needed"
    gap = distance_pct(price, pivot)
    if gap is not None and 0 <= gap <= 0.03:
        if timing >= 80:
            return "Actionable Now"
        return "Breakout Confirmed / Manage"
    if gap is not None and gap > 0:
        return "Breakout Confirmed / Manage"
    if timing >= 90 or (gap is not None and -0.01 <= gap <= 0.01 and timing >= 80):
        return "Actionable Now"
    if timing >= 80:
        return "Breakout Watch"
    if timing >= 70:
        return "Constructive Base"
    if timing >= 60:
        return "Developing Setup"
    return "Developing Setup"


def completed_daily_history(raw_history: dict[str, pd.DataFrame], mode: str, now_ny: datetime) -> dict[str, pd.DataFrame]:
    if mode != "premarket":
        return raw_history
    completed = {}
    today = now_ny.date()
    for ticker, df in raw_history.items():
        if df.empty:
            completed[ticker] = df
            continue
        completed[ticker] = df[df.index.date < today].copy()
    return completed


def session_label(now_ny: datetime) -> str:
    minutes = now_ny.hour * 60 + now_ny.minute
    if 4 * 60 <= minutes < 9 * 60 + 30:
        return "Pre-market"
    if 9 * 60 + 30 <= minutes < 16 * 60:
        return "Regular session"
    if 16 * 60 <= minutes < 20 * 60:
        return "After-hours"
    return "Closed"


def session_snapshot(ticker: str, intraday_history: dict[str, pd.DataFrame], completed_history: dict[str, pd.DataFrame], now_ny: datetime) -> dict[str, object]:
    completed = completed_history.get(ticker, pd.DataFrame())
    intraday = intraday_history.get(ticker, pd.DataFrame())
    label = session_label(now_ny)
    if completed.empty:
        return {"price": None, "move_pct": None, "time": "Data Missing", "label": label, "context": "Data Missing"}
    prev_close = safe_float(completed.iloc[-1].get("Close"))
    if prev_close is None or prev_close == 0:
        return {"price": None, "move_pct": None, "time": "Data Missing", "label": label, "context": "Data Missing"}
    if intraday.empty:
        return {"price": None, "move_pct": None, "time": "Data Missing", "label": label, "context": "No extended-hours data"}
    idx = intraday.index
    if idx.tz is None:
        localized_idx = idx.tz_localize("UTC").tz_convert("America/New_York")
    else:
        localized_idx = idx.tz_convert("America/New_York")
    intraday = intraday.copy()
    intraday.index = localized_idx
    today_rows = intraday[intraday.index.date == now_ny.date()]
    if today_rows.empty:
        return {"price": None, "move_pct": None, "time": "Data Missing", "label": label, "context": "No current extended-hours data"}
    latest = today_rows.iloc[-1]
    price = safe_float(latest.get("Close"))
    if price is None:
        return {"price": None, "move_pct": None, "time": "Data Missing", "label": label, "context": "Data Missing"}
    move = (price / prev_close) - 1
    ts = today_rows.index[-1].strftime("%Y-%m-%d %H:%M %Z")
    return {
        "price": price,
        "move_pct": move,
        "time": ts,
        "label": label,
        "context": f"{label}: {fmt_money(price)} ({fmt_pct(move)} vs prior close) at {ts}",
    }


def gap_context(ticker: str, raw_history: dict[str, pd.DataFrame], completed_history: dict[str, pd.DataFrame]) -> str:
    raw = raw_history.get(ticker, pd.DataFrame())
    completed = completed_history.get(ticker, pd.DataFrame())
    if raw.empty or completed.empty:
        return "Data Missing"
    latest = raw.iloc[-1]
    last_completed = completed.iloc[-1]
    if raw.index[-1].date() == completed.index[-1].date():
        return "No current-session data"
    current = safe_float(latest.get("Close"))
    current_open = safe_float(latest.get("Open"))
    prev_close = safe_float(last_completed.get("Close"))
    if current is None or current_open is None or prev_close is None or prev_close == 0:
        return "Data Missing"
    gap = (current_open / prev_close) - 1
    move = (current / prev_close) - 1
    return f"Open gap {gap * 100:.1f}%; latest vs prior close {move * 100:.1f}%"


def latest_session_move(ticker: str, raw_history: dict[str, pd.DataFrame], completed_history: dict[str, pd.DataFrame]) -> float | None:
    raw = raw_history.get(ticker, pd.DataFrame())
    completed = completed_history.get(ticker, pd.DataFrame())
    if raw.empty or completed.empty or raw.index[-1].date() == completed.index[-1].date():
        return None
    current = safe_float(raw.iloc[-1].get("Close"))
    prev_close = safe_float(completed.iloc[-1].get("Close"))
    if current is None or prev_close is None or prev_close == 0:
        return None
    return (current / prev_close) - 1


def category(item: Analysis) -> str:
    if item.data_missing:
        return "Data Missing"
    if item.status == "Actionable Now":
        return "Actionable Now"
    if item.status == "Breakout Confirmed / Manage":
        return "Breakout Confirmed / Manage"
    if item.status == "Breakout Watch":
        return "Breakout Watch"
    if item.status == "Constructive Base":
        return "Constructive Base"
    if item.status == "Developing Setup":
        return "Developing Setup"
    return "Repair Needed"


def category_rank(name: str) -> int:
    order = {
        "Actionable Now": 0,
        "Breakout Confirmed / Manage": 1,
        "Breakout Watch": 2,
        "Constructive Base": 3,
        "Developing Setup": 4,
        "Repair Needed": 5,
        "Data Missing": 6,
    }
    return order.get(name, 99)


def attention_label(item: Analysis) -> str:
    if item.status == "Actionable Now":
        return "inside the actionable timing window"
    if item.status == "Breakout Confirmed / Manage":
        return "confirmed above pivot; manage around the breakout level instead of treating it as broken"
    if item.status == "Breakout Watch":
        return "near pivot; monitor for reclaim with volume"
    if item.status == "Constructive Base":
        return "base is constructive but not yet in the best trigger window"
    if item.status == "Developing Setup":
        return "setup is developing but still needs tighter price/volume action"
    if item.status in {"Trend Break", "Structure Break", "Early Warning"}:
        return "trend or structure needs repair before becoming actionable"
    return "not actionable under current timing rules"


def trigger_line(item: Analysis) -> str:
    if item.pivot is None or item.price is None:
        return "Data Missing"
    if item.status == "Breakout Confirmed / Manage":
        return f"Confirmed above pivot {fmt_money(item.pivot)}. Priority is whether price holds pivot while trend and volume remain healthy."
    if item.price < item.pivot:
        return f"Watch for a move through {fmt_money(item.pivot)}; confirmation still requires a daily close above pivot with volume > 1.5x 20D average."
    return f"Already above pivot {fmt_money(item.pivot)}; priority is whether price can hold that level without reversal."


def risk_line(item: Analysis) -> str:
    anchor = item.support if item.support is not None else item.ma50
    if anchor is None:
        return "Data Missing"
    if item.status == "Breakout Confirmed / Manage":
        return f"Breakout remains healthy while price holds pivot/near-term support; first warning is a failed hold above {fmt_money(item.pivot)}."
    return f"Invalidation/repair level: {fmt_money(anchor)}. A close below 50DMA or failed pivot reclaim reduces priority."


def focus_reason(item: Analysis, raw_history: dict[str, pd.DataFrame], completed_history: dict[str, pd.DataFrame]) -> str:
    dist = distance_pct(item.price, item.pivot)
    dist_text = "Data Missing" if dist is None else f"{dist * 100:.1f}% vs pivot"
    session_text = "" if item.session_move_pct is None else f" Current session context is {item.session_context}."
    return (
        f"{attention_label(item).capitalize()}. Timing {item.timing_score}/100, "
        f"{item.trend_phase}, trend age {item.trend_age} days, {dist_text}. "
        f"Pullbacks {item.contraction_sequence}; volume {item.volume_state}.{session_text}"
    )


def classify_report_groups(analyses: list[Analysis]) -> dict[str, list[Analysis]]:
    groups: dict[str, list[Analysis]] = {}
    for item in analyses:
        groups.setdefault(category(item), []).append(item)
    for items in groups.values():
        items.sort(key=lambda x: x.timing_score, reverse=True)
    return dict(sorted(groups.items(), key=lambda kv: category_rank(kv[0])))


def core_attention(analyses: list[Analysis], raw_history: dict[str, pd.DataFrame], completed_history: dict[str, pd.DataFrame]) -> list[str]:
    groups = classify_report_groups(analyses)
    actionable = groups.get("Actionable Now", [])
    confirmed = groups.get("Breakout Confirmed / Manage", [])
    watch = groups.get("Breakout Watch", [])
    constructive = groups.get("Constructive Base", [])
    broken = groups.get("Repair Needed", [])
    lines = []
    if actionable:
        names = ", ".join(item.ticker for item in actionable[:4])
        levels = "; ".join(f"{item.ticker} trigger {fmt_money(item.pivot)} / invalidation {item.invalidation}" for item in actionable[:4])
        lines.append(f"- Actionable timing window: {names}. {levels}.")
    if confirmed:
        names = ", ".join(item.ticker for item in confirmed[:4])
        levels = "; ".join(f"{item.ticker} hold pivot {fmt_money(item.pivot)}" for item in confirmed[:4])
        lines.append(f"- Breakout confirmed / manage: {names}. Key test: {levels}.")
    if watch:
        names = ", ".join(item.ticker for item in watch[:4])
        levels = "; ".join(f"{item.ticker} pivot {fmt_money(item.pivot)}" for item in watch[:4])
        lines.append(f"- Breakout watch: {names}. Key levels: {levels}.")
    if constructive:
        names = ", ".join(f"{item.ticker} {item.trend_phase}" for item in constructive[:4])
        lines.append(f"- Constructive bases: {names}. Need tighter action or a cleaner trigger.")
    strong_gap = [
        item
        for item in analyses
        if (item.session_move_pct or 0) >= 0.05
    ]
    if strong_gap:
        names = ", ".join(f"{item.ticker} {fmt_pct(item.session_move_pct)}" for item in strong_gap[:5])
        lines.append(f"- Gap/early strength to monitor, not automatically confirm: {names}.")
    if broken:
        names = ", ".join(item.ticker for item in broken[:4])
        lines.append(f"- Repair needed: {names}. Need trend/structure repair before becoming actionable.")
    if not lines:
        lines.append("- No high-quality action cluster today; preserve capital and wait for cleaner setups.")
    return lines


def analyze_ticker(
    ticker: str,
    history: dict[str, pd.DataFrame],
    intraday_history: dict[str, pd.DataFrame],
    watch_returns_3m: dict[str, float | None],
    now_ny: datetime,
) -> Analysis:
    df = history.get(ticker, pd.DataFrame())
    qqq = history.get("QQQ", pd.DataFrame())
    soxx = history.get("SOXX", pd.DataFrame())
    session = session_snapshot(ticker, intraday_history, history, now_ny)
    if df.empty or len(df) < 200:
        return Analysis(
            ticker=ticker,
            price=None,
            volume=None,
            avg_volume_20=None,
            max_volume_20=None,
            volume_vs_avg_20=None,
            volume_vs_max_20=None,
            ma5=None,
            ma10=None,
            ma20=None,
            ma30=None,
            ma50=None,
            ma60=None,
            ma150=None,
            ma200=None,
            high_52w=None,
            pivot=None,
            support=None,
            support_basis=support_basis_text(),
            session_price=safe_float(session.get("price")),
            session_move_pct=safe_float(session.get("move_pct")),
            session_time=str(session.get("time", "Data Missing")),
            session_label=str(session.get("label", "Data Missing")),
            session_context=str(session.get("context", "Data Missing")),
            trend_gate=False,
            trend_age=0,
            trend_phase="Data Missing",
            short_ma_state="Data Missing",
            short_ma_spread_pct=None,
            ma_expansion_state="Data Missing",
            ma_expansion_start_date="",
            ma_expansion_age=0,
            expma_state="Data Missing",
            expma_spread_pct=None,
            expma_stack_age=0,
            expma_start_date="",
            gain_expma_to_ma_pct=None,
            gain_ma_to_now_pct=None,
            gain_expma_to_now_pct=None,
            days_above_50ma=0,
            ma_stack_age=0,
            extension_20_pct=None,
            pivot_gap_pct=None,
            setup_quality_score=0,
            breakout_readiness_score=0,
            demand_score=0,
            entry_risk_score=0,
            timing_score=0,
            setup_state="Data Missing",
            contraction_sequence="Data Missing",
            pullback_volume_detail="Data Missing",
            volume_state="Data Missing",
            tightness_state="Data Missing",
            trend_signal="Data Missing",
            trend_score=0,
            rs_score=0,
            setup_score=0,
            volume_score=0,
            risk_score=0,
            momentum_score=0,
            status="Data Missing",
            key_level="Data Missing",
            invalidation="Data Missing",
            comment="Data Missing",
            data_missing=True,
        )

    price = safe_float(df["Close"].iloc[-1])
    volume = safe_float(df["Volume"].iloc[-1])
    avg_volume_20 = safe_float(df["Volume"].rolling(20).mean().iloc[-1])
    max_volume_20 = safe_float(df["Volume"].tail(20).max())
    volume_vs_avg_20 = volume / avg_volume_20 if volume is not None and avg_volume_20 not in (None, 0) else None
    volume_vs_max_20 = volume / max_volume_20 if volume is not None and max_volume_20 not in (None, 0) else None
    ma5 = moving_average(df, 5)
    ma10 = moving_average(df, 10)
    ma20 = moving_average(df, 20)
    ma30 = moving_average(df, 30)
    ma50 = moving_average(df, 50)
    ma60 = moving_average(df, 60)
    ma150 = moving_average(df, 150)
    ma200 = moving_average(df, 200)
    high_52w = safe_float(df["High"].tail(252).max())
    pivot = recent_pivot(df)
    support = recent_support(df)
    trend_gate, trend_age, phase, days_above_50, ma_stack = trend_lifecycle(df, high_52w)
    short_state, short_spread = short_ma_state(price, ma5, ma10, ma20)
    ma_expansion_state_value, ma_expansion_start, ma_expansion_age = ma_expansion_lifecycle(df)
    expma_state_value, expma_spread, expma_age, expma_start = expma_lifecycle(df)
    gain_expma_to_ma = pct_gain_between(df, expma_start, ma_expansion_start) if expma_start and ma_expansion_start else None
    gain_ma_to_now = pct_gain_between(df, ma_expansion_start)
    gain_expma_to_now = pct_gain_between(df, expma_start)
    contraction = contraction_metrics(df)
    pullback_volumes = pullback_volume_detail(contraction, avg_volume_20)

    trend = trend_score(price, ma50, ma150, ma200, high_52w)
    rs = relative_strength_score(df, qqq, soxx, watch_returns_3m, ticker)
    setup = setup_quality_score(df, price, pivot, ma20, ma50, contraction)
    breakout = breakout_readiness_score(price, pivot, volume, avg_volume_20, trend_gate)
    demand = demand_score(df, volume, avg_volume_20, contraction)
    entry_risk = entry_risk_score(price, pivot, support, ma20)
    total = setup + breakout + demand + entry_risk
    status = classify_status(price, pivot, support, ma20, ma50, trend_gate, total)
    extension_20 = distance_pct(price, ma20)
    pivot_gap = distance_pct(price, pivot)

    if pivot is not None and price is not None:
        if price < pivot:
            key = f"Pivot {pivot:.2f}; needs reclaim/hold above for confirmation"
        else:
            key = f"Hold above pivot {pivot:.2f}"
    else:
        key = "Data Missing"

    invalidation = fmt_money(support if support is not None else ma50)
    comment_parts = []
    comment_parts.append("Trend gate pass" if trend_gate else "Trend gate fail")
    comment_parts.append(phase)
    comment_parts.append(f"MA {ma_expansion_state_value}")
    comment_parts.append(f"short MA {short_state}")
    comment_parts.append(f"EXPMA {expma_state_value}")
    if pivot is not None and price is not None:
        comment_parts.append(f"{((price / pivot) - 1) * 100:.1f}% vs pivot")
    comment_parts.append(f"pullbacks {contraction['sequence']}")
    comment_parts.append(f"volume {contraction['volume_state']}")

    return Analysis(
        ticker=ticker,
        price=price,
        volume=volume,
        avg_volume_20=avg_volume_20,
        max_volume_20=max_volume_20,
        volume_vs_avg_20=volume_vs_avg_20,
        volume_vs_max_20=volume_vs_max_20,
        ma5=ma5,
        ma10=ma10,
        ma20=ma20,
        ma30=ma30,
        ma50=ma50,
        ma60=ma60,
        ma150=ma150,
        ma200=ma200,
        high_52w=high_52w,
        pivot=pivot,
        support=support,
        support_basis=support_basis_text(),
        session_price=safe_float(session.get("price")),
        session_move_pct=safe_float(session.get("move_pct")),
        session_time=str(session.get("time", "Data Missing")),
        session_label=str(session.get("label", "Data Missing")),
        session_context=str(session.get("context", "Data Missing")),
        trend_gate=trend_gate,
        trend_age=trend_age,
        trend_phase=phase,
        short_ma_state=short_state,
        short_ma_spread_pct=short_spread,
        ma_expansion_state=ma_expansion_state_value,
        ma_expansion_start_date=ma_expansion_start,
        ma_expansion_age=ma_expansion_age,
        expma_state=expma_state_value,
        expma_spread_pct=expma_spread,
        expma_stack_age=expma_age,
        expma_start_date=expma_start,
        gain_expma_to_ma_pct=gain_expma_to_ma,
        gain_ma_to_now_pct=gain_ma_to_now,
        gain_expma_to_now_pct=gain_expma_to_now,
        days_above_50ma=days_above_50,
        ma_stack_age=ma_stack,
        extension_20_pct=extension_20,
        pivot_gap_pct=pivot_gap,
        setup_quality_score=setup,
        breakout_readiness_score=breakout,
        demand_score=demand,
        entry_risk_score=entry_risk,
        timing_score=total,
        setup_state=status,
        contraction_sequence=str(contraction["sequence"]),
        pullback_volume_detail=pullback_volumes,
        volume_state=str(contraction["volume_state"]),
        tightness_state=str(contraction["tightness_state"]),
        trend_signal="Pass" if trend_gate else "Fail",
        trend_score=trend,
        rs_score=rs,
        setup_score=setup,
        volume_score=demand,
        risk_score=entry_risk,
        momentum_score=total,
        status=status,
        key_level=key,
        invalidation=invalidation,
        comment="; ".join(comment_parts),
        data_missing=False,
    )


def market_regime(history: dict[str, pd.DataFrame]) -> list[str]:
    lines = []
    for ticker in BENCHMARKS:
        df = history.get(ticker, pd.DataFrame())
        if df.empty or len(df) < 200:
            lines.append(f"- {ticker}: Data Missing")
            continue
        price = safe_float(df["Close"].iloc[-1])
        ma20 = moving_average(df, 20)
        ma50 = moving_average(df, 50)
        ma200 = moving_average(df, 200)
        state = []
        state.append("above 20DMA" if price is not None and ma20 is not None and price > ma20 else "below 20DMA")
        state.append("above 50DMA" if price is not None and ma50 is not None and price > ma50 else "below 50DMA")
        state.append("above 200DMA" if price is not None and ma200 is not None and price > ma200 else "below 200DMA")
        lines.append(f"- {ticker}: {fmt_money(price)} ({', '.join(state)})")
    return lines


def build_report(mode: str) -> Path:
    ensure_dirs()
    tickers = WATCHLIST + BENCHMARKS
    raw_history = {ticker: fetch_history(ticker) for ticker in tickers}
    intraday_history = {ticker: fetch_intraday_history(ticker) for ticker in tickers}
    now_ny = datetime.now(ZoneInfo("America/New_York"))
    now_local = datetime.now().astimezone()
    history = completed_daily_history(raw_history, mode, now_ny)
    watch_returns_3m = {ticker: pct_return(history[ticker], 63) for ticker in WATCHLIST}
    analyses = [analyze_ticker(ticker, history, intraday_history, watch_returns_3m, now_ny) for ticker in WATCHLIST]
    analyses.sort(key=lambda x: x.timing_score, reverse=True)

    available_dates = [df.index[-1].date() for df in history.values() if not df.empty]
    data_date = max(available_dates) if available_dates else now_ny.date()
    report_date = data_date.strftime("%Y-%m-%d")
    filename = REPORT_DIR / f"{report_date}_{mode}.md"

    opened_note = ""
    if mode == "premarket":
        market_open = now_ny.replace(hour=9, minute=30, second=0, microsecond=0)
        if now_ny >= market_open:
            opened_note = "\nNote: Generated after the regular-session open; treat this as a pre-market-format early-session report.\n"

    groups = classify_report_groups(analyses)
    focus_candidates = (
        groups.get("Actionable Now", [])
        + groups.get("Breakout Confirmed / Manage", [])
        + groups.get("Breakout Watch", [])
        + groups.get("Constructive Base", [])
        + groups.get("Developing Setup", [])
    )
    focus = sorted(focus_candidates, key=lambda x: x.timing_score, reverse=True)[:5]
    lines = [
        f"# {mode.title()} Timing Report - {report_date}",
        "",
        f"Generated: {now_local.strftime('%Y-%m-%d %H:%M %Z')} / {now_ny.strftime('%Y-%m-%d %H:%M %Z')}",
        "",
        "This is a research report only, not financial advice.",
        opened_note.strip(),
        "",
        "## Market Regime",
        *market_regime(history),
        "",
        "## Today's Core Attention",
        *core_attention(analyses, raw_history, history),
        "",
        "## Classification",
    ]
    for name, items in groups.items():
        summary = ", ".join(f"{item.ticker} ({item.timing_score}, {item.status})" for item in items)
        lines.append(f"- {name}: {summary if summary else 'None'}")

    lines.extend(["", "## Focus Stock Analysis"])
    for item in focus:
        lines.extend(
            [
                "",
                f"### {item.ticker} - {category(item)}",
                f"- Why it matters: {focus_reason(item, raw_history, history)}",
                f"- Today trigger: {trigger_line(item)}",
                f"- Risk / invalidation: {risk_line(item)}",
                f"- Key level: {item.key_level}",
                f"- Current session context: {item.session_context}",
            ]
        )

    lines.extend(["", "## Full Watchlist Detail"])
    for item in analyses:
        rel_1w = pct_return(history[item.ticker], 5) if item.ticker in history else None
        rel_1m = pct_return(history[item.ticker], 21) if item.ticker in history else None
        rel_3m = pct_return(history[item.ticker], 63) if item.ticker in history else None
        lines.extend(
            [
                "",
                f"### {item.ticker}",
                f"- Price: {fmt_money(item.price)}",
                f"- Session Price: {fmt_money(item.session_price)}",
                f"- Session Move: {fmt_pct(item.session_move_pct)}",
                f"- Session Context: {item.session_context}",
                f"- Volume: {fmt_num(item.volume)} vs 20D avg {fmt_num(item.avg_volume_20)}",
                f"- Volume vs 20D Avg: {fmt_ratio(item.volume_vs_avg_20)}",
                f"- 20D Max Volume: {fmt_num(item.max_volume_20)}",
                f"- Volume vs 20D Max: {fmt_ratio(item.volume_vs_max_20)}",
                f"- Relative Strength: 1W {fmt_pct(rel_1w)}, 1M {fmt_pct(rel_1m)}, 3M {fmt_pct(rel_3m)}",
                f"- Trend Gate: {item.trend_signal}",
                f"- Trend Age: {item.trend_age} trading days",
                f"- Trend Phase: {item.trend_phase}",
                f"- Short MA State: {item.short_ma_state}",
                f"- Short MA Spread: {fmt_pct(item.short_ma_spread_pct)}",
                f"- MA Expansion State: {item.ma_expansion_state}",
                f"- MA Expansion Start: {item.ma_expansion_start_date or 'Data Missing'}",
                f"- MA Expansion Age: {item.ma_expansion_age}",
                f"- EXPMA State: {item.expma_state}",
                f"- EXPMA Spread: {fmt_pct(item.expma_spread_pct)}",
                f"- EXPMA Stack Age: {item.expma_stack_age}",
                f"- EXPMA Start: {item.expma_start_date or 'Data Missing'}",
                f"- Gain EXPMA to MA: {fmt_pct(item.gain_expma_to_ma_pct)}",
                f"- Gain MA to Now: {fmt_pct(item.gain_ma_to_now_pct)}",
                f"- Gain EXPMA to Now: {fmt_pct(item.gain_expma_to_now_pct)}",
                f"- Days Above 50DMA: {item.days_above_50ma}",
                f"- MA Stack Age: {item.ma_stack_age}",
                f"- Extension from 20DMA: {fmt_pct(item.extension_20_pct)}",
                f"- Pivot Gap: {fmt_pct(item.pivot_gap_pct)}",
                f"- Timing Score: {item.timing_score}/100",
                f"- Setup Quality: {item.setup_quality_score}/35",
                f"- Breakout Readiness: {item.breakout_readiness_score}/30",
                f"- Volume / Demand: {item.demand_score}/20",
                f"- Entry Risk: {item.entry_risk_score}/15",
                f"- Pullback Sequence: {item.contraction_sequence}",
                f"- Pullback Volume Detail: {item.pullback_volume_detail}",
                f"- VCP Volume State: {item.volume_state}",
                f"- Tightness: {item.tightness_state}",
                f"- Pivot: {fmt_money(item.pivot)}",
                f"- Support: {fmt_money(item.support)}",
                f"- Support Basis: {item.support_basis}",
                f"- Status: {item.status}",
                f"- Classification: {category(item)}",
                f"- Current Session Context: {item.session_context}",
                f"- Key Level: {item.key_level}",
                f"- Invalidation Level: {item.invalidation}",
                f"- Comment: {item.comment}",
            ]
        )

    lines.extend(
        [
            "",
            f"## {'Pre-Market' if mode == 'premarket' else 'Post-Market'} Rules",
            "- Actionable Now requires timing quality plus a defined trigger; pre-market strength is context, not confirmation." if mode == "premarket" else "- Actionable Now is strongest when price closes near/above pivot with demand expansion and controlled entry risk.",
            "- Daily close and daily volume remain the source of truth for confirmed signals.",
            "- Missing data must be marked as Data Missing.",
        ]
    )
    filename.write_text("\n".join([line for line in lines if line is not None]) + "\n", encoding="utf-8")

    snapshot = {
        "generated_at_local": now_local.isoformat(),
        "generated_at_new_york": now_ny.isoformat(),
        "mode": mode,
        "watchlist": WATCHLIST,
        "benchmarks": BENCHMARKS,
        "scores": [item.__dict__ for item in analyses],
    }
    (DATA_DIR / f"{report_date}_{mode}_snapshot.json").write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    return filename


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["premarket", "postmarket"], default="premarket")
    args = parser.parse_args()
    path = build_report(args.mode)
    print(path)


if __name__ == "__main__":
    main()

"""Scoring helpers combining fundamentals and technical timing."""

from __future__ import annotations

from typing import Dict, Iterable, Mapping, Tuple

import numpy as np
import pandas as pd

from core.indicators import rsi, sma, vol_ma

__all__ = [
    "zscore_mad",
    "score_quality",
    "score_growth",
    "score_value",
    "score_finance",
    "score_dividend",
    "composite",
    "timing_modifier",
]


def zscore_mad(values: Iterable[float] | pd.Series) -> pd.Series:
    """Return the median-absolute-deviation based z-score of *values*."""

    series = pd.Series(list(values) if not isinstance(values, pd.Series) else values).astype(float)
    if series.empty:
        return series

    median = series.median(skipna=True)
    deviations = (series - median).abs()
    mad = deviations.median(skipna=True)

    if mad is None or np.isnan(mad) or mad == 0:
        std = series.std(ddof=0)
        if std == 0 or np.isnan(std):
            return pd.Series(np.zeros(len(series)), index=series.index, dtype=float)
        return ((series - median) / std).fillna(0.0)

    scale = 0.6744897501960817  # Approximation so that MAD matches standard deviation
    return ((series - median) * scale / mad).fillna(0.0)


def score_quality(fundamentals: Mapping[str, float]) -> float:
    metrics = [
        _score_linear(fundamentals.get("roe"), 0.1, 0.25),
        _score_linear(fundamentals.get("roa"), 0.05, 0.15),
        _score_linear(fundamentals.get("grossMargin"), 0.25, 0.55),
        _score_linear(fundamentals.get("operatingMargin"), 0.1, 0.3),
        _score_linear(fundamentals.get("ebitdaMargin"), 0.15, 0.35),
    ]
    return _aggregate_scores(metrics)


def score_growth(fundamentals: Mapping[str, float]) -> float:
    metrics = [
        _score_linear(fundamentals.get("revenueGrowth"), 0.0, 0.25),
        _score_linear(fundamentals.get("earningsGrowth"), 0.0, 0.3),
    ]
    return _aggregate_scores(metrics)


def score_value(fundamentals: Mapping[str, float]) -> float:
    metrics = [
        _score_linear(fundamentals.get("trailingPE"), 10.0, 40.0, reverse=True),
        _score_linear(fundamentals.get("forwardPE"), 10.0, 35.0, reverse=True),
        _score_linear(fundamentals.get("pb"), 1.0, 6.0, reverse=True),
        _score_linear(fundamentals.get("enterpriseToEbitda"), 6.0, 20.0, reverse=True),
    ]
    return _aggregate_scores(metrics)


def score_finance(fundamentals: Mapping[str, float]) -> float:
    debt_to_equity = fundamentals.get("debtToEquity")
    current_ratio = fundamentals.get("currentRatio")
    total_debt = fundamentals.get("totalDebt")
    total_cash = fundamentals.get("totalCash")

    coverage = None
    if _is_finite(total_debt) and total_debt > 0 and _is_finite(total_cash):
        coverage = total_cash / total_debt

    metrics = [
        _score_linear(debt_to_equity, 0.0, 2.0, reverse=True),
        _score_linear(current_ratio, 1.0, 3.0),
        _score_linear(coverage, 0.25, 1.5),
    ]
    return _aggregate_scores(metrics)


def score_dividend(fundamentals: Mapping[str, float]) -> float:
    yield_score = _score_linear(fundamentals.get("dividendYield"), 0.005, 0.06)
    payout = fundamentals.get("payoutRatio")
    payout_score = _score_band(payout, low=0.0, sweet_low=0.3, sweet_high=0.6, high=0.9)
    return _aggregate_scores([yield_score, payout_score])


def composite(weights: Mapping[str, float], parts: Mapping[str, float]) -> float:
    total_weight = sum(max(weight, 0.0) for weight in weights.values())
    if total_weight <= 0:
        return 0.0

    accum = 0.0
    for key, weight in weights.items():
        part_value = parts.get(key, 0.0)
        accum += max(weight, 0.0) * max(min(part_value, 100.0), 0.0)

    result = accum / total_weight
    return float(np.clip(result, 0.0, 100.0))


def timing_modifier(price_df: pd.DataFrame) -> Tuple[float, str]:
    if price_df is None or price_df.empty:
        return 0.0, "No price data"

    close_series = _column_case_insensitive(price_df, {"close", "adj close"})
    high_series = _column_case_insensitive(price_df, {"high"})
    volume_series = _column_case_insensitive(price_df, {"volume"})

    if close_series is None or high_series is None:
        return 0.0, "Incomplete OHLC data"

    closes = close_series.dropna()
    highs = high_series.loc[closes.index]

    if closes.shape[0] < 60:
        return 0.0, "Insufficient price history"

    sma50 = sma(closes, 50)
    sma200 = sma(closes, 200)
    rsi_series = rsi(closes, 14)

    last_close = closes.iloc[-1]
    last_sma50 = sma50.iloc[-1]
    last_sma200 = sma200.iloc[-1]
    last_rsi = rsi_series.iloc[-1]

    if np.isnan(last_sma200):
        return 0.0, "Insufficient long-term trend data"

    if last_close < last_sma200 * 0.995:
        return -20.0, "Price below SMA200 regime filter"

    modifier = 0.0
    reason = "Neutral setup"

    breakout_modifier, breakout_reason = _breakout_signal(closes, highs, volume_series)
    locked_signal = False
    if breakout_modifier is not None:
        modifier = breakout_modifier
        reason = breakout_reason
        locked_signal = True
    else:
        pullback_modifier, pullback_reason = _pullback_signal(closes, last_sma50, last_sma200, last_rsi)
        if pullback_modifier is not None:
            modifier = pullback_modifier
            reason = pullback_reason
            locked_signal = True
        else:
            trend_modifier, trend_reason = _trend_bias(last_close, last_sma50, last_sma200, last_rsi)
            modifier = trend_modifier
            reason = trend_reason

    if not locked_signal and last_rsi >= 75 and last_close > last_sma50 * 1.08:
        modifier = -10.0
        reason = "Extended and overbought"

    return float(np.clip(modifier, -20.0, 50.0)), reason


def _breakout_signal(
    closes: pd.Series, highs: pd.Series, volume_series: pd.Series | None
) -> Tuple[float | None, str]:
    if closes.shape[0] < 40 or volume_series is None or volume_series.empty:
        return None, ""

    aligned_volume = volume_series.reindex(closes.index).ffill()
    if aligned_volume.shape[0] < 20:
        return None, ""

    last_close = closes.iloc[-1]
    last_volume = aligned_volume.iloc[-1]
    recent_high = closes.rolling(window=20, min_periods=20).max().iloc[-1]
    volume_ma = vol_ma(aligned_volume, 20).iloc[-1]

    if np.isnan(recent_high) or np.isnan(volume_ma):
        return None, ""

    if last_close >= recent_high * 0.999 and last_volume >= volume_ma * 1.2:
        return 35.0, "Breakout above 20-day high with volume confirmation"

    return None, ""


def _pullback_signal(
    closes: pd.Series, last_sma50: float, last_sma200: float, last_rsi: float
) -> Tuple[float | None, str]:
    if np.isnan(last_sma50) or last_sma50 <= 0:
        return None, ""

    last_close = closes.iloc[-1]
    distance = abs(last_close - last_sma50) / last_sma50
    if distance <= 0.02 and 40 <= last_rsi <= 55 and last_close > last_sma200:
        return 20.0, "Pullback entry near SMA50 with balanced momentum"

    return None, ""


def _trend_bias(
    last_close: float, last_sma50: float, last_sma200: float, last_rsi: float
) -> Tuple[float, str]:
    if np.isnan(last_sma50):
        return 5.0, "Above long-term trend"

    if last_close > last_sma50 and 45 <= last_rsi <= 65:
        return 12.0, "Trending above SMA50 with supportive momentum"

    if last_close > last_sma200:
        return 6.0, "Above long-term trend"

    return 0.0, "Neutral setup"


def _score_linear(value: float | None, low: float, high: float, *, reverse: bool = False) -> float | None:
    if value is None or not _is_finite(value):
        return None

    if high <= low:
        return 50.0

    if reverse:
        if value <= low:
            return 100.0
        if value >= high:
            return 0.0
        ratio = 1 - (value - low) / (high - low)
    else:
        if value <= low:
            return 0.0
        if value >= high:
            return 100.0
        ratio = (value - low) / (high - low)

    return float(np.clip(ratio * 100.0, 0.0, 100.0))


def _score_band(
    value: float | None, *, low: float, sweet_low: float, sweet_high: float, high: float
) -> float | None:
    if value is None or not _is_finite(value):
        return None
    if value < low or value > high:
        return 0.0
    if sweet_low <= value <= sweet_high:
        return 100.0
    if value < sweet_low:
        ratio = (value - low) / (sweet_low - low) if sweet_low != low else 0.0
        return float(np.clip(ratio * 100.0, 0.0, 100.0))
    ratio = (high - value) / (high - sweet_high) if high != sweet_high else 0.0
    return float(np.clip(ratio * 100.0, 0.0, 100.0))


def _aggregate_scores(scores: Iterable[float | None]) -> float:
    valid = [score for score in scores if score is not None and _is_finite(score)]
    if not valid:
        return 0.0
    return float(np.clip(float(np.mean(valid)), 0.0, 100.0))


def _is_finite(value: float | None) -> bool:
    return value is not None and np.isfinite(value)


def _column_case_insensitive(df: pd.DataFrame, candidates: set[str]) -> pd.Series | None:
    lowercase_map: Dict[str, object] = {}
    for column in df.columns:
        if isinstance(column, tuple):
            name = str(column[-1]).lower()
        else:
            name = str(column).lower()
        lowercase_map[name] = column if not isinstance(column, tuple) else column

    for candidate in candidates:
        name = candidate.lower()
        if name in lowercase_map:
            column = lowercase_map[name]
            return df[column]
    return None

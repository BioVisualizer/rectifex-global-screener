import numpy as np
import pandas as pd

from core.scoring import (
    composite,
    score_dividend,
    score_finance,
    score_growth,
    score_quality,
    score_value,
    timing_modifier,
    zscore_mad,
)


def _price_frame(close_values: np.ndarray, volume_values: np.ndarray | None = None) -> pd.DataFrame:
    dates = pd.date_range(end=pd.Timestamp("2024-01-31"), periods=len(close_values), freq="B")
    close = pd.Series(close_values, index=dates)
    volume = (
        pd.Series(volume_values, index=dates)
        if volume_values is not None
        else pd.Series(np.full(len(close_values), 1_000_000), index=dates)
    )
    return pd.DataFrame(
        {
            "Open": close,
            "High": close * 1.01,
            "Low": close * 0.99,
            "Close": close,
            "Adj Close": close,
            "Volume": volume,
        }
    )


def test_zscore_mad_returns_zero_for_constant_series():
    series = pd.Series([5, 5, 5, 5, 5], dtype=float)
    result = zscore_mad(series)
    assert np.allclose(result, 0.0)


def test_score_blocks_distinguish_good_and_poor_fundamentals():
    good = {
        "roe": 0.28,
        "roa": 0.16,
        "grossMargin": 0.58,
        "operatingMargin": 0.24,
        "ebitdaMargin": 0.4,
        "revenueGrowth": 0.28,
        "earningsGrowth": 0.32,
        "trailingPE": 15.0,
        "forwardPE": 14.0,
        "pb": 2.0,
        "enterpriseToEbitda": 8.0,
        "debtToEquity": 0.4,
        "currentRatio": 2.1,
        "totalDebt": 5e9,
        "totalCash": 6.5e9,
        "dividendYield": 0.035,
        "payoutRatio": 0.45,
    }

    poor = {
        "roe": 0.03,
        "roa": 0.01,
        "grossMargin": 0.18,
        "operatingMargin": 0.05,
        "ebitdaMargin": 0.08,
        "revenueGrowth": -0.05,
        "earningsGrowth": -0.12,
        "trailingPE": 55.0,
        "forwardPE": 48.0,
        "pb": 9.0,
        "enterpriseToEbitda": 25.0,
        "debtToEquity": 3.5,
        "currentRatio": 0.9,
        "totalDebt": 8e9,
        "totalCash": 1.5e9,
        "dividendYield": 0.002,
        "payoutRatio": 0.95,
    }

    assert score_quality(good) > score_quality(poor)
    assert score_growth(good) > score_growth(poor)
    assert score_value(good) > score_value(poor)
    assert score_finance(good) > score_finance(poor)
    assert score_dividend(good) > score_dividend(poor)


def test_composite_respects_weights():
    weights = {"quality": 50, "growth": 30, "value": 20}
    parts = {"quality": 80, "growth": 60, "value": 40}
    result = composite(weights, parts)
    expected = (80 * 50 + 60 * 30 + 40 * 20) / sum(weights.values())
    assert np.isclose(result, expected)


def test_timing_modifier_flags_price_below_sma200():
    closes = np.linspace(100, 80, 240)
    df = _price_frame(closes)
    modifier, reason = timing_modifier(df)
    assert modifier == -20.0
    assert "SMA200" in reason


def test_timing_modifier_detects_breakout_with_volume_confirmation():
    closes = np.concatenate([
        np.linspace(80, 100, 220),
        np.linspace(101, 120, 40),
    ])
    volumes = np.concatenate([
        np.full(219, 900_000),
        np.full(40, 1_500_000),
        np.array([3_000_000]),
    ])
    df = _price_frame(closes, volumes)
    modifier, reason = timing_modifier(df)
    assert modifier >= 30.0
    assert "Breakout" in reason


def test_timing_modifier_requires_history():
    closes = np.linspace(90, 100, 40)
    df = _price_frame(closes)
    modifier, reason = timing_modifier(df)
    assert modifier == 0.0
    assert "history" in reason.lower()

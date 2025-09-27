from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd

from core.scans.contrarian import ClassicOversoldScenario
from core.scans.floor_consolidation import FloorConsolidationQualityScenario
from core.scans.lti_compounder import LTICompounderScenario
from core.scans.momentum import MomentumBreakoutScenario
from core.scans.squeeze import VolatilitySqueezeScenario


def _make_price_df(prices: np.ndarray, volume: np.ndarray | float) -> pd.DataFrame:
    dates = pd.date_range(end="2024-01-31", periods=len(prices), freq="B")
    volume_array = (
        np.full(len(prices), float(volume)) if np.isscalar(volume) else np.asarray(volume, dtype=float)
    )
    data = {
        "Open": prices,
        "High": prices + 0.5,
        "Low": prices - 0.5,
        "Close": prices,
        "Adj Close": prices,
        "Volume": volume_array,
    }
    df = pd.DataFrame(data, index=dates)
    df.attrs["symbol"] = "TEST"
    return df


def _make_fundamentals() -> Dict[str, float]:
    return {
        "roe": 0.22,
        "roa": 0.12,
        "grossMargin": 0.55,
        "operatingMargin": 0.24,
        "ebitdaMargin": 0.30,
        "revenueGrowth": 0.18,
        "earningsGrowth": 0.22,
        "trailingPE": 24.0,
        "forwardPE": 21.0,
        "pb": 4.0,
        "enterpriseToEbitda": 12.0,
        "debtToEquity": 0.6,
        "totalDebt": 5e9,
        "totalCash": 6e9,
        "currentRatio": 1.5,
        "dividendYield": 0.018,
        "payoutRatio": 0.45,
        "beta": 1.1,
        "marketCap": 150e9,
        "averageVolume": 2.5e6,
    }


def test_momentum_breakout_detects_buy_signal() -> None:
    prices = np.linspace(100.0, 150.0, 260)
    volume = np.full_like(prices, 1_000_000.0)
    volume[-1] = 1_600_000.0
    df = _make_price_df(prices, volume)

    scenario = MomentumBreakoutScenario()
    result, signals = scenario.evaluate(df, fundamentals=None)

    assert result is not None
    assert result.score >= scenario.default_params["threshold"]
    assert any(signal.side == "buy" for signal in signals)


def test_classic_oversold_detects_reversal() -> None:
    base = np.linspace(120.0, 90.0, 50)
    selloff = np.linspace(90.0, 70.0, 10, endpoint=False)
    recovery = np.array([72.0, 74.0, 79.0, 83.0])
    prices = np.concatenate([base, selloff, recovery])
    volume = np.full_like(prices, 750_000.0)
    df = _make_price_df(prices, volume)

    scenario = ClassicOversoldScenario()
    result, signals = scenario.evaluate(df, fundamentals=None)

    assert result is not None
    assert any(signal.side == "buy" for signal in signals)


def test_volatility_squeeze_breakout_generates_signal() -> None:
    flat = np.full(140, 100.0)
    small_noise = flat + np.sin(np.linspace(0, np.pi, 140)) * 0.4
    breakout = np.array([101.0, 103.0, 107.0, 110.0, 112.0, 115.0, 118.0, 120.0, 122.0, 125.0])
    prices = np.concatenate([small_noise, breakout])
    volume = np.full_like(prices, 400_000.0)
    volume[-1] = 700_000.0
    df = _make_price_df(prices, volume)

    scenario = VolatilitySqueezeScenario()
    result, signals = scenario.evaluate(df, fundamentals=None)

    assert result is not None
    assert any(signal.side == "buy" for signal in signals)


def test_floor_consolidation_quality_requires_fundamentals() -> None:
    base = np.concatenate([
        np.full(20, 100.0),
        np.linspace(100.0, 102.0, 10),
        np.linspace(102.0, 103.0, 10),
    ])
    breakout = np.array([104.0, 105.0, 107.0, 110.0, 112.0])
    prices = np.concatenate([base, breakout])
    volume = np.full_like(prices, 300_000.0)
    volume[-1] = 450_000.0
    df = _make_price_df(prices, volume)

    fundamentals = _make_fundamentals()
    scenario = FloorConsolidationQualityScenario()
    result, signals = scenario.evaluate(df, fundamentals=fundamentals)

    assert result is not None
    assert any(signal.side == "buy" for signal in signals)
    assert "Quality fundamentals confirmed" in result.reasons


def test_lti_compounder_generates_long_term_signal() -> None:
    prices = np.linspace(80.0, 160.0, 260)
    volume = np.full_like(prices, 1_200_000.0)
    df = _make_price_df(prices, volume)

    fundamentals = _make_fundamentals()
    scenario = LTICompounderScenario()
    result, signals = scenario.evaluate(df, fundamentals=fundamentals)

    assert result is not None
    assert result.metrics["final_score"] >= scenario.default_params["threshold"]
    assert any(signal.side == "buy" for signal in signals)


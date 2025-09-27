from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core import indicators


def test_sma_and_ema_basic():
    series = pd.Series([1, 2, 3, 4, 5], dtype=float)
    sma = indicators.sma(series, window=2)
    ema = indicators.ema(series, span=2)

    assert np.isnan(sma.iloc[0])
    assert sma.iloc[-1] == pytest.approx(4.5)
    assert ema.iloc[-1] > ema.iloc[-2]


def test_rsi_bounds():
    series = pd.Series(np.linspace(1, 10, 50), dtype=float)
    rsi_values = indicators.rsi(series, window=14)

    assert (rsi_values >= 0).all()
    assert (rsi_values <= 100).all()
    assert rsi_values.iloc[-1] > 70


def test_macd_components():
    series = pd.Series(np.linspace(1, 10, 30), dtype=float)
    macd = indicators.macd(series)

    assert set(macd.columns) == {"macd", "signal", "hist"}
    assert macd.iloc[-1, 0] == pytest.approx(macd.iloc[-1, 1] + macd.iloc[-1, 2])


def test_atr_monotonic_trend():
    high = pd.Series([10, 11, 12, 13, 14], dtype=float)
    low = high - 1
    close = high - 0.5

    atr_values = indicators.atr(high, low, close, window=3)
    valid = atr_values.dropna()
    assert not valid.empty
    assert valid.iloc[-1] > 0
    assert valid.iloc[-1] >= valid.iloc[0]


def test_bollinger_width_positive():
    series = pd.Series(np.linspace(1, 10, 30), dtype=float)
    bands = indicators.bollinger(series, window=5)

    valid = bands.dropna()
    assert (valid["upper"] >= valid["mid"]).all()
    assert (valid["mid"] >= valid["lower"]).all()
    assert (valid["width"] >= 0).all()


def test_stochastic_range():
    high = pd.Series([10, 11, 12, 13, 14], dtype=float)
    low = high - 2
    close = high - 1

    stoch = indicators.stoch(high, low, close, k_window=3, d_window=2, smooth_k=2)
    assert set(stoch.columns) == {"%K", "%D"}
    assert (stoch["%K"] >= 0).all()
    assert (stoch["%K"] <= 100).all()


def test_adx_trend_strength():
    high = pd.Series([10, 11, 12, 13, 14, 15], dtype=float)
    low = high - 1
    close = high - 0.5

    adx_values = indicators.adx(high, low, close, window=3)
    assert (adx_values >= 0).all()
    assert (adx_values <= 100).all()
    assert adx_values.iloc[-1] > adx_values.iloc[2]


def test_obv_accumulates_volume():
    close = pd.Series([10, 11, 10, 12, 11], dtype=float)
    volume = pd.Series([100, 100, 100, 100, 100], dtype=float)

    obv_series = indicators.obv(close, volume)
    assert obv_series.iloc[0] == 0
    assert obv_series.iloc[1] == 100
    assert obv_series.iloc[2] == 0


def test_volume_moving_average():
    volume = pd.Series([10, 20, 30, 40], dtype=float)
    vol_avg = indicators.vol_ma(volume, window=2)

    assert np.isnan(vol_avg.iloc[0])
    assert vol_avg.iloc[-1] == pytest.approx(35)


def test_keltner_channels_structure():
    high = pd.Series([10, 11, 12, 13, 14], dtype=float)
    low = high - 1
    close = high - 0.5

    keltner = indicators.keltner_channels(high, low, close, window=3, atr_window=2)
    assert set(keltner.columns) == {"mid", "upper", "lower"}
    valid = keltner.dropna()
    assert (valid["upper"] >= valid["mid"]).all()
    assert (valid["mid"] >= valid["lower"]).all()

"""Collection of pure indicator helper functions used by the screener."""

from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd

__all__ = [
    "sma",
    "ema",
    "rsi",
    "macd",
    "atr",
    "bollinger",
    "stoch",
    "adx",
    "obv",
    "vol_ma",
    "keltner_channels",
]


def _as_series(values: Iterable[float] | pd.Series) -> pd.Series:
    if isinstance(values, pd.Series):
        return values.astype(float)
    return pd.Series(pd.array(list(values), dtype="float64"))


def sma(series: Iterable[float] | pd.Series, window: int, *, min_periods: int | None = None) -> pd.Series:
    """Simple moving average."""

    if window <= 0:
        raise ValueError("window must be positive")

    data = _as_series(series)
    min_periods = min_periods if min_periods is not None else window
    return data.rolling(window=window, min_periods=min_periods).mean()


def ema(series: Iterable[float] | pd.Series, span: int) -> pd.Series:
    """Exponential moving average using an EMA span."""

    if span <= 0:
        raise ValueError("span must be positive")

    data = _as_series(series)
    return data.ewm(span=span, adjust=False).mean()


def rsi(series: Iterable[float] | pd.Series, window: int = 14) -> pd.Series:
    """Relative Strength Index (0-100)."""

    if window <= 0:
        raise ValueError("window must be positive")

    data = _as_series(series)
    delta = data.diff()
    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)

    avg_gain = gains.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    avg_loss = losses.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()

    loss_replaced = avg_loss.replace(0, np.nan)
    rs = avg_gain / loss_replaced
    rsi_values = 100 - (100 / (1 + rs))

    gain_zero = avg_gain <= 1e-12
    loss_zero = avg_loss <= 1e-12
    rsi_values = rsi_values.mask(loss_zero & ~gain_zero, 100)
    rsi_values = rsi_values.mask(gain_zero & ~loss_zero, 0)
    rsi_values = rsi_values.mask(gain_zero & loss_zero, 50)

    return rsi_values.fillna(50)


def macd(series: Iterable[float] | pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """Moving Average Convergence Divergence indicator."""

    if fast <= 0 or slow <= 0 or signal <= 0:
        raise ValueError("MACD periods must be positive")
    if fast >= slow:
        raise ValueError("fast period must be less than slow period")

    data = _as_series(series)
    ema_fast = ema(data, fast)
    ema_slow = ema(data, slow)
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return pd.DataFrame({"macd": macd_line, "signal": signal_line, "hist": histogram})


def atr(
    high: Iterable[float] | pd.Series,
    low: Iterable[float] | pd.Series,
    close: Iterable[float] | pd.Series,
    window: int = 14,
) -> pd.Series:
    """Average True Range (Wilder smoothing)."""

    if window <= 0:
        raise ValueError("window must be positive")

    high_s = _as_series(high)
    low_s = _as_series(low)
    close_s = _as_series(close)

    prev_close = close_s.shift(1)
    ranges = pd.concat(
        [
            high_s - low_s,
            (high_s - prev_close).abs(),
            (low_s - prev_close).abs(),
        ],
        axis=1,
    )
    true_range = ranges.max(axis=1, skipna=False)
    return true_range.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()


def bollinger(
    series: Iterable[float] | pd.Series,
    window: int = 20,
    num_std: float = 2.0,
) -> pd.DataFrame:
    """Bollinger Bands (mid, upper, lower, width)."""

    if window <= 0:
        raise ValueError("window must be positive")
    if num_std <= 0:
        raise ValueError("num_std must be positive")

    data = _as_series(series)
    mid = sma(data, window)
    std = data.rolling(window=window, min_periods=window).std(ddof=0)
    upper = mid + num_std * std
    lower = mid - num_std * std
    width = upper - lower
    return pd.DataFrame({"mid": mid, "upper": upper, "lower": lower, "width": width})


def stoch(
    high: Iterable[float] | pd.Series,
    low: Iterable[float] | pd.Series,
    close: Iterable[float] | pd.Series,
    k_window: int = 14,
    d_window: int = 3,
    smooth_k: int = 3,
) -> pd.DataFrame:
    """Stochastic Oscillator (percent K/D)."""

    if min(k_window, d_window, smooth_k) <= 0:
        raise ValueError("windows must be positive")

    high_s = _as_series(high)
    low_s = _as_series(low)
    close_s = _as_series(close)

    lowest_low = low_s.rolling(window=k_window, min_periods=k_window).min()
    highest_high = high_s.rolling(window=k_window, min_periods=k_window).max()
    denom = (highest_high - lowest_low).replace(0, np.nan)
    percent_k = ((close_s - lowest_low) / denom) * 100
    percent_k = percent_k.rolling(window=smooth_k, min_periods=smooth_k).mean()
    percent_d = percent_k.rolling(window=d_window, min_periods=d_window).mean()
    return pd.DataFrame({"%K": percent_k.fillna(0), "%D": percent_d.fillna(0)})


def adx(
    high: Iterable[float] | pd.Series,
    low: Iterable[float] | pd.Series,
    close: Iterable[float] | pd.Series,
    window: int = 14,
) -> pd.Series:
    """Average Directional Index."""

    if window <= 0:
        raise ValueError("window must be positive")

    high_s = _as_series(high)
    low_s = _as_series(low)
    close_s = _as_series(close)

    up_move = high_s.diff()
    down_move = low_s.shift(1) - low_s
    plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)

    prev_close = close_s.shift(1)
    ranges = pd.concat(
        [
            high_s - low_s,
            (high_s - prev_close).abs(),
            (low_s - prev_close).abs(),
        ],
        axis=1,
    )
    true_range = ranges.max(axis=1, skipna=False)

    atr_smoothed = true_range.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    plus_smoothed = pd.Series(plus_dm, index=high_s.index).ewm(
        alpha=1 / window, adjust=False, min_periods=window
    ).mean()
    minus_smoothed = pd.Series(minus_dm, index=high_s.index).ewm(
        alpha=1 / window, adjust=False, min_periods=window
    ).mean()

    plus_di = 100 * plus_smoothed / atr_smoothed.replace(0, np.nan)
    minus_di = 100 * minus_smoothed / atr_smoothed.replace(0, np.nan)
    dx = (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan) * 100
    return dx.ewm(alpha=1 / window, adjust=False, min_periods=window).mean().fillna(0)


def obv(close: Iterable[float] | pd.Series, volume: Iterable[float] | pd.Series) -> pd.Series:
    """On-Balance Volume."""

    close_s = _as_series(close)
    volume_s = _as_series(volume)

    direction = close_s.diff().fillna(0).apply(np.sign)
    obv_delta = direction * volume_s
    return obv_delta.cumsum().fillna(0)


def vol_ma(volume: Iterable[float] | pd.Series, window: int = 20) -> pd.Series:
    """Moving average of traded volume."""

    if window <= 0:
        raise ValueError("window must be positive")

    volume_s = _as_series(volume)
    return volume_s.rolling(window=window, min_periods=window).mean()


def keltner_channels(
    high: Iterable[float] | pd.Series,
    low: Iterable[float] | pd.Series,
    close: Iterable[float] | pd.Series,
    window: int = 20,
    atr_window: int = 10,
    multiplier: float = 2.0,
) -> pd.DataFrame:
    """Keltner Channels based on EMA midline and ATR bands."""

    if min(window, atr_window) <= 0:
        raise ValueError("windows must be positive")
    if multiplier <= 0:
        raise ValueError("multiplier must be positive")

    close_s = _as_series(close)
    mid = ema(close_s, window)
    atr_values = atr(high, low, close, atr_window)
    upper = mid + multiplier * atr_values
    lower = mid - multiplier * atr_values
    return pd.DataFrame({"mid": mid, "upper": upper, "lower": lower})

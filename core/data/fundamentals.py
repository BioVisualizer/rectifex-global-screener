"""Utilities for defensively extracting fundamental metrics from yfinance."""

from __future__ import annotations

from typing import Dict, Mapping, Sequence

import numpy as np
import pandas as pd

__all__ = ["read_fundamentals"]


_FUNDAMENTAL_KEYS = [
    "roe",
    "roa",
    "grossMargin",
    "operatingMargin",
    "ebitdaMargin",
    "revenueGrowth",
    "earningsGrowth",
    "trailingPE",
    "forwardPE",
    "pb",
    "enterpriseToEbitda",
    "debtToEquity",
    "totalDebt",
    "totalCash",
    "currentRatio",
    "dividendYield",
    "payoutRatio",
    "beta",
    "marketCap",
    "averageVolume",
]

_ALIAS_PATHS: Dict[str, Sequence[Sequence[str] | str]] = {
    "roe": ["returnOnEquity", ("financialData", "returnOnEquity")],
    "roa": ["returnOnAssets", ("financialData", "returnOnAssets")],
    "grossMargin": ["grossMargins", ("financialData", "grossMargins")],
    "operatingMargin": ["operatingMargins", ("financialData", "operatingMargins")],
    "ebitdaMargin": ["ebitdaMargins", ("financialData", "ebitdaMargins")],
    "revenueGrowth": [("financialData", "revenueGrowth")],
    "earningsGrowth": [("financialData", "earningsGrowth")],
    "trailingPE": [("summaryDetail", "trailingPE")],
    "forwardPE": [("summaryDetail", "forwardPE")],
    "pb": ["priceToBook", ("summaryDetail", "priceToBook")],
    "enterpriseToEbitda": [("summaryDetail", "enterpriseToEbitda")],
    "debtToEquity": [("financialData", "debtToEquity")],
    "totalDebt": [("balanceSheet", "Total Debt"), ("financialData", "totalDebt")],
    "totalCash": [("balanceSheet", "Cash And Cash Equivalents"), ("financialData", "totalCash")],
    "currentRatio": [("financialData", "currentRatio")],
    "dividendYield": [("summaryDetail", "dividendYield")],
    "payoutRatio": [("summaryDetail", "payoutRatio")],
    "beta": [("summaryDetail", "beta")],
    "marketCap": [("summaryDetail", "marketCap"), ("price", "marketCap")],
    "averageVolume": [("summaryDetail", "averageVolume"), ("price", "averageDailyVolume10Day")],
}


def read_fundamentals(info: Mapping[str, object] | None) -> Dict[str, float]:
    """Return a normalised dictionary of fundamental metrics.

    The function defensively coerces values to floats and replaces missing
    or invalid entries with ``numpy.nan``. Only a curated list of attributes
    is extracted to keep the downstream scoring logic deterministic.
    """

    normalised = _normalise_mapping(info)
    if normalised is None:
        return {key: np.nan for key in _FUNDAMENTAL_KEYS}

    result: Dict[str, float] = {}
    for key in _FUNDAMENTAL_KEYS:
        raw_value = _extract_value(normalised, key)
        result[key] = _coerce_numeric(raw_value)
    return result


def _normalise_mapping(info: object) -> Mapping[str, object] | None:
    if info is None:
        return None
    if isinstance(info, Mapping):
        return info
    if hasattr(info, "to_dict"):
        converted = info.to_dict()  # type: ignore[attr-defined]
        if isinstance(converted, Mapping):
            return converted
    return None


def _extract_value(info: Mapping[str, object], key: str) -> object:
    if key in info:
        return info[key]

    for alias in _ALIAS_PATHS.get(key, ()):  # type: ignore[arg-type]
        value = _value_from_alias(info, alias)
        if value is not None:
            return value
    return None


def _value_from_alias(info: Mapping[str, object], alias: Sequence[str] | str) -> object:
    if isinstance(alias, str):
        return info.get(alias)

    current: object = info
    for segment in alias:
        if isinstance(current, Mapping):
            current = current.get(segment)
        elif isinstance(current, pd.DataFrame):
            if segment in current.index:
                series = current.loc[segment]
                current = _first_scalar(series)
            else:
                return None
        elif isinstance(current, pd.Series):
            if segment in current.index:
                current = _coerce_series_value(current[segment])
            else:
                return None
        else:
            return None

        if current is None:
            return None

    if isinstance(current, Mapping):
        if len(current) == 1:
            return next(iter(current.values()))
    return current


def _coerce_numeric(value: object) -> float:
    """Best-effort conversion of *value* to a float.

    Numbers are returned as ``float``. Strings are parsed while supporting
    typical yfinance formatting quirks such as percentage suffixes and
    magnitude abbreviations (``1.2B``). Anything that cannot be safely
    interpreted is converted to ``numpy.nan``.
    """

    if value is None:
        return float("nan")

    if isinstance(value, bool):
        return float(value)

    if isinstance(value, (int, float, np.number)):
        if np.isnan(value):  # type: ignore[arg-type]
            return float("nan")
        return float(value)

    if isinstance(value, (list, tuple, set)):
        if not value:
            return float("nan")
        first = next(iter(value))
        return _coerce_numeric(first)

    if isinstance(value, pd.Series):
        return _coerce_numeric(_first_scalar(value))

    if isinstance(value, pd.DataFrame):
        return _coerce_numeric(_first_scalar(value.stack(dropna=False)))

    if isinstance(value, str):
        text = value.strip()
        if not text:
            return float("nan")

        lowered = text.lower()
        if lowered in {"nan", "n/a", "na", "none", "null", "-"}:
            return float("nan")

        multiplier = 1.0
        if text.endswith("%"):
            text = text[:-1]
            multiplier = 0.01

        unit_multipliers = {"k": 1e3, "m": 1e6, "b": 1e9, "t": 1e12}
        last_char = text[-1].lower()
        if last_char in unit_multipliers and _is_numeric_prefix(text[:-1]):
            multiplier *= unit_multipliers[last_char]
            text = text[:-1]

        cleaned = _clean_numeric_string(text)
        if cleaned is None:
            return float("nan")

        try:
            parsed = float(cleaned)
        except ValueError:
            return float("nan")
        return parsed * multiplier

    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return float("nan")


def _first_scalar(series: pd.Series) -> object:
    if series.empty:
        return float("nan")
    cleaned = series.dropna()
    if not cleaned.empty:
        return cleaned.iloc[0]
    return series.iloc[0]


def _coerce_series_value(value: object) -> object:
    if isinstance(value, pd.Series):
        return _first_scalar(value)
    return value


def _clean_numeric_string(text: str) -> str | None:
    allowed = set("0123456789+-.eE")
    cleaned_chars = [ch for ch in text if ch in allowed]
    if not cleaned_chars:
        return None

    cleaned = "".join(cleaned_chars)
    if cleaned.count(".") > 1:
        return None
    if cleaned.count("e") + cleaned.count("E") > 1:
        return None
    return cleaned


def _is_numeric_prefix(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    cleaned = _clean_numeric_string(stripped)
    if cleaned is None:
        return False
    try:
        float(cleaned)
    except ValueError:
        return False
    return True

"""Utilities to normalise fundamental data returned by yfinance."""

from __future__ import annotations

from typing import Dict, Mapping

import numpy as np

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


def read_fundamentals(info: Mapping[str, object] | None) -> Dict[str, float]:
    """Return a normalised dictionary of fundamental metrics.

    The function defensively coerces values to floats and replaces missing
    or invalid entries with ``numpy.nan``. Only a curated list of attributes
    is extracted to keep the downstream scoring logic deterministic.
    """

    if info is None:
        return {key: np.nan for key in _FUNDAMENTAL_KEYS}

    result: Dict[str, float] = {}
    for key in _FUNDAMENTAL_KEYS:
        raw_value = info.get(key) if isinstance(info, Mapping) else None
        result[key] = _coerce_numeric(raw_value)
    return result


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

    if isinstance(value, (list, tuple)):
        if not value:
            return float("nan")
        return _coerce_numeric(value[0])

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

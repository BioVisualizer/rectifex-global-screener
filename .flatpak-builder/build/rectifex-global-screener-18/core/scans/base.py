"""Base classes and helper utilities for scan implementations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd

from core.models import ScanResult, TradeSignal

__all__ = ["BaseScenario", "ScenarioContext", "PriceSeriesBundle"]


@dataclass(frozen=True)
class PriceSeriesBundle:
    """Convenience container bundling canonical OHLCV series."""

    open: pd.Series
    high: pd.Series
    low: pd.Series
    close: pd.Series
    volume: Optional[pd.Series]


@dataclass(frozen=True)
class ScenarioContext:
    """Runtime context passed to scans with the extracted data series."""

    price_df: pd.DataFrame
    symbol: str
    fundamentals: Optional[dict]
    series: PriceSeriesBundle

    @property
    def as_of(self) -> datetime:
        """Return the timestamp of the last available close."""

        if self.series.close.empty:
            return datetime.utcnow()
        last_index = self.series.close.index[-1]
        if isinstance(last_index, pd.Timestamp):
            return last_index.to_pydatetime(warn=False)
        return datetime.utcnow()


class BaseScenario(ABC):
    """Abstract base class for all scan scenarios."""

    id: str
    name: str
    description: str
    default_params: Dict[str, Any]

    def build_context(
        self, price_df: Optional[pd.DataFrame], fundamentals: Optional[dict]
    ) -> Optional[ScenarioContext]:
        """Return a :class:`ScenarioContext` or ``None`` when data is missing."""

        if price_df is None or price_df.empty:
            return None

        open_series = self._column(price_df, {"open"})
        high_series = self._column(price_df, {"high"})
        low_series = self._column(price_df, {"low"})
        close_series = self._column(price_df, {"close", "adj close"})

        if close_series is None or high_series is None or low_series is None or open_series is None:
            return None

        volume_series = self._column(price_df, {"volume"})

        bundle = PriceSeriesBundle(
            open=open_series.astype(float),
            high=high_series.astype(float),
            low=low_series.astype(float),
            close=close_series.astype(float),
            volume=volume_series.astype(float) if volume_series is not None else None,
        )

        symbol = ""
        if isinstance(price_df.attrs.get("symbol"), str):
            symbol = price_df.attrs["symbol"]

        return ScenarioContext(
            price_df=price_df,
            symbol=symbol,
            fundamentals=fundamentals,
            series=bundle,
        )

    @abstractmethod
    def evaluate(
        self,
        price_df: Optional[pd.DataFrame],
        fundamentals: Optional[dict],
        params: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Optional[ScanResult], List[TradeSignal]]:
        """Evaluate the scan returning a result and associated trade signals."""

    # ------------------------------------------------------------------
    # Helper utilities
    # ------------------------------------------------------------------
    @staticmethod
    def _column(df: pd.DataFrame, candidates: Iterable[str]) -> Optional[pd.Series]:
        """Return a case-insensitive column match from *df*.

        The helper also supports MultiIndex columns as produced by ``yf.download``.
        """

        lowered = {candidate.lower() for candidate in candidates}

        for column in df.columns:
            if isinstance(column, tuple):
                name = str(column[-1]).lower()
            else:
                name = str(column).lower()
            if name in lowered:
                series = df[column]
                return series
        return None

    @staticmethod
    def _append_reason(reasons: List[str], text: str) -> None:
        if text and text not in reasons:
            reasons.append(text)

    @staticmethod
    def _confidence_from_score(score: float, threshold: float) -> float:
        if threshold <= 0:
            return 0.0
        return float(np.clip(score / max(threshold, 1e-6), 0.0, 1.0))


"""Utility helpers for retrieving chart-ready price data."""

from __future__ import annotations

from typing import Optional

import pandas as pd

from core.cache import Cache
from core.data.fetcher import Fetcher

__all__ = ["ChartDataProvider"]


class ChartDataProvider:
    """Load price history for chart displays using cache-aware logic."""

    def __init__(
        self,
        *,
        cache: Cache | None = None,
        fetcher: Fetcher | None = None,
        ttl_days: int | None = None,
    ) -> None:
        self._cache = cache or Cache()
        self._fetcher = fetcher or Fetcher()
        self._ttl_days = ttl_days

    def load(self, symbol: str, period: str) -> Optional[pd.DataFrame]:
        """Return a DataFrame suitable for chart rendering.

        Cached data is preferred when still within the configured TTL. If the
        cache entry is stale (or missing) the provider fetches fresh data via
        :class:`Fetcher`. When the refresh fails the method falls back to the
        stale cache copy to ensure the UI can still show historical context.
        """

        cached = self._cache.get(symbol, period)
        if cached is not None and not cached.empty:
            cached = cached.copy()
            cached.attrs["symbol"] = symbol

        ttl = self._ttl_days
        if cached is not None and not cached.empty and not self._cache.is_stale(symbol, period, ttl_days=ttl):
            return cached

        fresh = self._fetcher.fetch_single(symbol, period=period)
        if fresh is not None and not fresh.empty:
            fresh = fresh.copy()
            fresh.attrs["symbol"] = symbol
            self._cache.set(symbol, period, fresh)
            return fresh

        return cached

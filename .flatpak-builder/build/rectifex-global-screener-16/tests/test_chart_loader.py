from __future__ import annotations

from datetime import datetime
from typing import Dict, Optional

import pandas as pd

from core.cache import Cache
from core.data.chart_loader import ChartDataProvider


class DummyFetcher:
    def __init__(self, responses: Dict[str, Optional[pd.DataFrame]]) -> None:
        self._responses = responses
        self.calls: list[tuple[str, str]] = []

    def fetch_single(self, symbol: str, period: str = "1y") -> Optional[pd.DataFrame]:
        self.calls.append((symbol, period))
        return self._responses.get(symbol)


def _sample_frame() -> pd.DataFrame:
    dates = pd.date_range(end=datetime.utcnow(), periods=5, freq="D")
    return pd.DataFrame(
        {
            "Open": [100, 101, 102, 103, 104],
            "High": [101, 102, 103, 104, 105],
            "Low": [99, 100, 101, 102, 103],
            "Close": [100.5, 101.2, 102.8, 103.6, 104.1],
            "Volume": [1_000_000] * 5,
        },
        index=dates,
    )


def test_chart_provider_returns_cached_when_fresh(tmp_path) -> None:
    cache = Cache(base_dir=tmp_path)
    frame = _sample_frame()
    cache.set("TEST", "1y", frame)

    fetcher = DummyFetcher({})
    provider = ChartDataProvider(cache=cache, fetcher=fetcher)

    loaded = provider.load("TEST", "1y")
    assert loaded is not None
    pd.testing.assert_frame_equal(loaded, frame)
    assert fetcher.calls == []


def test_chart_provider_refreshes_stale_cache(tmp_path) -> None:
    cache = Cache(base_dir=tmp_path)
    stale_frame = _sample_frame()
    cache.set("TEST", "1y", stale_frame)

    fresh_frame = stale_frame.copy()
    fresh_frame["Close"] += 1
    fetcher = DummyFetcher({"TEST": fresh_frame})

    provider = ChartDataProvider(cache=cache, fetcher=fetcher, ttl_days=-1)
    loaded = provider.load("TEST", "1y")
    assert loaded is not None
    pd.testing.assert_frame_equal(loaded, fresh_frame)
    assert fetcher.calls == [("TEST", "1y")]


def test_chart_provider_falls_back_to_stale_when_fetch_fails(tmp_path) -> None:
    cache = Cache(base_dir=tmp_path)
    stale_frame = _sample_frame()
    cache.set("TEST", "1y", stale_frame)

    fetcher = DummyFetcher({"TEST": None})
    provider = ChartDataProvider(cache=cache, fetcher=fetcher, ttl_days=-1)

    loaded = provider.load("TEST", "1y")
    assert loaded is not None
    pd.testing.assert_frame_equal(loaded, stale_frame)

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from core.cache import Cache


@pytest.fixture()
def sample_frame() -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=3, freq="D")
    return pd.DataFrame(
        {
            "Open": [1.0, 2.0, 3.0],
            "High": [1.5, 2.5, 3.5],
            "Low": [0.5, 1.5, 2.5],
            "Close": [1.2, 2.2, 3.2],
            "Adj Close": [1.1, 2.1, 3.1],
            "Volume": [100, 150, 200],
        },
        index=index,
    )


def test_cache_roundtrip(tmp_path, sample_frame):
    cache = Cache(base_dir=tmp_path)
    cache.set("AAPL", "1y", sample_frame)

    loaded = cache.get("AAPL", "1y")
    assert loaded is not None
    pd.testing.assert_frame_equal(loaded, sample_frame)


def test_cache_staleness(tmp_path, sample_frame):
    cache = Cache(base_dir=tmp_path)
    cache.set("AAPL", "1y", sample_frame)

    index_path = tmp_path / "index.db"
    stale_time = datetime.now(timezone.utc) - timedelta(days=10)
    with sqlite3.connect(index_path) as connection:
        connection.execute(
            "UPDATE cache_index SET updated_at=? WHERE symbol=? AND period=?",
            (stale_time.isoformat(), "AAPL", "1y"),
        )
        connection.commit()

    assert cache.is_stale("AAPL", "1y", ttl_days=7)


def test_cache_clear(tmp_path, sample_frame):
    cache = Cache(base_dir=tmp_path)
    cache.set("AAPL", "1y", sample_frame)
    cache.set("MSFT", "6mo", sample_frame)

    removed = cache.clear(symbol="AAPL")
    assert removed >= 1
    assert cache.get("AAPL", "1y") is None
    assert cache.get("MSFT", "6mo") is not None

    removed_old = cache.clear(older_than_days=0)
    assert removed_old >= 1
    assert cache.get("MSFT", "6mo") is None

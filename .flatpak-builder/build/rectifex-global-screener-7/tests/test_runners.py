from __future__ import annotations

from typing import Dict, List, Optional, Sequence

import pandas as pd

from core.models import ScanResult, TradeSignal
from core.runners import ScanRunner
from core.scans.base import BaseScenario


def _price_frame(symbol: str) -> pd.DataFrame:
    index = pd.date_range("2023-01-01", periods=30, freq="B")
    close = pd.Series(range(100, 130), index=index, dtype=float)
    frame = pd.DataFrame(
        {
            "Open": close - 1.0,
            "High": close + 1.5,
            "Low": close - 1.5,
            "Close": close,
            "Adj Close": close,
            "Volume": 1_000_000.0,
        },
        index=index,
    )
    frame.attrs["symbol"] = symbol
    return frame


class DummyFetcher:
    def __init__(self, data: Dict[str, pd.DataFrame]) -> None:
        self.data = data
        self.called_with: List[Sequence[str]] = []

    def fetch_batch(self, symbols: List[str], period: str = "1y", chunk_size: Optional[int] = None):
        self.called_with.append(list(symbols))
        return {symbol: self.data.get(symbol) for symbol in symbols}

    def fetch_single(self, symbol: str, period: str = "1y") -> Optional[pd.DataFrame]:  # pragma: no cover
        return self.data.get(symbol)


class DummyCache:
    def __init__(self) -> None:
        self.storage: Dict[tuple[str, str], pd.DataFrame] = {}
        self.stale: Dict[tuple[str, str], bool] = {}

    def get(self, symbol: str, period: str) -> Optional[pd.DataFrame]:
        return self.storage.get((symbol, period))

    def set(self, symbol: str, period: str, df: pd.DataFrame) -> None:
        self.storage[(symbol, period)] = df
        self.stale[(symbol, period)] = False

    def is_stale(self, symbol: str, period: str, ttl_days: int | None = None) -> bool:
        return self.stale.get((symbol, period), True)


class DummyScenario(BaseScenario):
    id = "dummy"
    name = "Dummy"
    description = ""
    default_params: Dict[str, object] = {}

    def evaluate(self, price_df, fundamentals, params):
        last_price = float(price_df.iloc[-1]["Close"])
        result = ScanResult(
            symbol=price_df.attrs.get("symbol", ""),
            score=75.0,
            metrics={"last_price": last_price},
            reasons=["Test"],
            last_price=last_price,
            as_of=price_df.index[-1].to_pydatetime(),
        )
        signals = [
            TradeSignal(
                symbol=result.symbol,
                timestamp=price_df.index[-1],
                side="buy",
                confidence=0.8,
                reason="Dummy",
                scenario_id=self.id,
            )
        ]
        return result, signals


def test_runner_streams_results_and_updates_cache() -> None:
    symbols = ["AAA", "BBB", "AAA"]  # Duplicate to test normalisation
    frames = {symbol: _price_frame(symbol) for symbol in {"AAA", "BBB"}}

    fetcher = DummyFetcher(frames)
    cache = DummyCache()

    runner = ScanRunner(fetcher=fetcher, cache=cache, max_workers=2)

    results: List[ScanResult] = []
    signals: List[TradeSignal] = []
    progresses: List[tuple[int, int, int, int]] = []

    def on_result(result: Optional[ScanResult], emitted_signals: List[TradeSignal]) -> None:
        if result is not None:
            results.append(result)
        signals.extend(emitted_signals)

    def on_progress(progress) -> None:
        progresses.append((progress.total, progress.processed, progress.skipped, progress.errors))

    future = runner.start(
        DummyScenario(),
        symbols,
        period="6mo",
        on_result=on_result,
        on_progress=on_progress,
    )

    summary = future.result(timeout=5)

    assert summary.total == 2
    assert summary.processed == 2
    assert summary.skipped == 0
    assert summary.errors == 0
    assert summary.cache_hits == 0
    assert summary.cache_misses == 2

    assert len(results) == 2
    assert len(signals) == 2

    assert cache.get("AAA", "6mo") is not None
    assert cache.get("BBB", "6mo") is not None

    assert progresses[0][0] == 2
    assert progresses[-1][1] == 2

    runner.shutdown()


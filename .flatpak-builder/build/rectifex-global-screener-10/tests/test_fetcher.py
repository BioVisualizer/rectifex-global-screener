from __future__ import annotations

from typing import Dict

import pandas as pd
import pytest

from core.data.fetcher import Fetcher


class DummyTicker:
    def __init__(self, symbol: str, responses: Dict[str, pd.DataFrame]) -> None:
        self.symbol = symbol
        self._responses = responses

    def history(self, period: str, auto_adjust: bool = False) -> pd.DataFrame:  # noqa: ARG002
        return self._responses.get(self.symbol, pd.DataFrame())


@pytest.fixture()
def dummy_data() -> Dict[str, pd.DataFrame]:
    index = pd.date_range("2024-01-01", periods=2, freq="D")
    base = pd.DataFrame(
        {
            "Open": [1.0, 2.0],
            "High": [1.1, 2.1],
            "Low": [0.9, 1.9],
            "Close": [1.05, 2.05],
            "Adj Close": [1.05, 2.05],
            "Volume": [100, 120],
        },
        index=index,
    )
    return {
        "AAPL": base,
        "MSFT": base * 2,
    }


def test_fetch_batch_with_fallback(monkeypatch: pytest.MonkeyPatch, dummy_data: Dict[str, pd.DataFrame]):
    download_calls = []

    def fake_download(*, tickers, period, group_by, threads, progress):  # noqa: ANN001
        download_calls.append((tuple(tickers), period, group_by, threads, progress))
        index = pd.date_range("2024-01-01", periods=2, freq="D")
        frame = dummy_data["AAPL"].copy()
        frame.index = index
        return pd.concat({tickers[0]: frame}, axis=1)

    monkeypatch.setattr("core.data.fetcher.yf.download", fake_download)

    def fake_ticker(symbol: str):
        return DummyTicker(symbol, dummy_data)

    monkeypatch.setattr("core.data.fetcher.yf.Ticker", fake_ticker)

    fetcher = Fetcher(max_retries=1, sleep_fn=lambda _: None)
    results = fetcher.fetch_batch(["AAPL", "MSFT"], period="6mo", chunk_size=10)

    assert download_calls, "Batch download should have been invoked"
    assert results["AAPL"] is not None
    pd.testing.assert_frame_equal(results["AAPL"], dummy_data["AAPL"])
    assert results["MSFT"] is not None
    pd.testing.assert_frame_equal(results["MSFT"], dummy_data["MSFT"])


def test_fetch_single_returns_none_for_empty(monkeypatch: pytest.MonkeyPatch):
    class EmptyTicker:
        def history(self, period: str, auto_adjust: bool = False) -> pd.DataFrame:  # noqa: ARG002
            return pd.DataFrame()

    monkeypatch.setattr("core.data.fetcher.yf.Ticker", lambda symbol: EmptyTicker())
    fetcher = Fetcher(max_retries=1, sleep_fn=lambda _: None)
    assert fetcher.fetch_single("EMPTY", period="1mo") is None

"""Data fetching utilities built around yfinance."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Optional

import pandas as pd
import yfinance as yf

from core.config import DEFAULT_CONFIG

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class FetchResult:
    symbol: str
    data: Optional[pd.DataFrame]


class Fetcher:
    """Retrieve price data from yfinance with defensive fallbacks."""

    def __init__(
        self,
        max_retries: Optional[int] = None,
        backoff_factor: Optional[float] = None,
        initial_backoff_seconds: Optional[float] = None,
        sleep_fn: Optional[Callable[[float], None]] = None,
    ) -> None:
        config = DEFAULT_CONFIG.fetcher
        self.max_retries = max_retries if max_retries is not None else config.max_retries
        self.backoff_factor = backoff_factor if backoff_factor is not None else config.backoff_factor
        self.initial_backoff_seconds = (
            initial_backoff_seconds if initial_backoff_seconds is not None else config.initial_backoff_seconds
        )
        self._sleep_fn = sleep_fn or time.sleep

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def fetch_single(self, symbol: str, period: str = "1y") -> Optional[pd.DataFrame]:
        """Fetch historical data for a single symbol using the ticker fallback."""

        def _operation() -> pd.DataFrame:
            ticker = yf.Ticker(symbol)
            return ticker.history(period=period, auto_adjust=False)

        try:
            df = self._execute_with_retries(_operation, symbol=symbol, period=period)
        except Exception as exc:  # pragma: no cover - last resort logging
            _LOGGER.error("Failed to fetch data for %s after retries: %s", symbol, exc)
            return None

        if df is None or df.empty:
            _LOGGER.info("No data returned for %s (%s) via ticker history", symbol, period)
            return None

        return self._prepare_frame(df)

    def fetch_batch(
        self,
        symbols: List[str],
        period: str = "1y",
        chunk_size: Optional[int] = None,
    ) -> Dict[str, Optional[pd.DataFrame]]:
        """Fetch data for *symbols* using batch download with fallbacks."""

        config_chunk = chunk_size if chunk_size is not None else DEFAULT_CONFIG.fetcher.batch_chunk_size
        results: Dict[str, Optional[pd.DataFrame]] = {symbol: None for symbol in symbols}

        for chunk in _chunked(symbols, config_chunk):
            batch_df = self._download_chunk(chunk, period)
            frames = self._split_batch_result(chunk, batch_df)

            for symbol in chunk:
                df = frames.get(symbol)
                if df is None or df.empty:
                    _LOGGER.debug("Falling back to single fetch for %s", symbol)
                    df = self.fetch_single(symbol, period)
                results[symbol] = df if df is not None and not df.empty else None

        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _download_chunk(self, symbols: Iterable[str], period: str) -> Optional[pd.DataFrame]:
        symbol_list = list(symbols)

        def _operation() -> pd.DataFrame:
            joined = " ".join(symbol_list)
            _LOGGER.info("Batch download for %s (%s)", joined, period)
            return yf.download(  # type: ignore[no-untyped-call]
                tickers=symbol_list,
                period=period,
                group_by="ticker",
                threads=False,
                progress=False,
            )

        try:
            return self._execute_with_retries(_operation, symbol=",".join(symbol_list), period=period)
        except Exception as exc:  # pragma: no cover - batch download fatal
            _LOGGER.error("Batch download failed for %s: %s", symbol_list, exc)
            return None

    def _split_batch_result(
        self, symbols: Iterable[str], batch_df: Optional[pd.DataFrame]
    ) -> Dict[str, Optional[pd.DataFrame]]:
        frames: Dict[str, Optional[pd.DataFrame]] = {symbol: None for symbol in symbols}
        if batch_df is None or batch_df.empty:
            return frames

        if isinstance(batch_df.columns, pd.MultiIndex):
            for symbol in symbols:
                try:
                    df = batch_df.xs(symbol, axis=1, level=0)
                except KeyError:
                    frames[symbol] = None
                    continue
                frames[symbol] = self._prepare_frame(df)
        else:
            symbol = next(iter(symbols))
            frames[symbol] = self._prepare_frame(batch_df)

        return frames

    def _prepare_frame(self, df: pd.DataFrame) -> pd.DataFrame:
        cleaned = df.copy()
        cleaned = cleaned.dropna(how="all")
        if cleaned.index.tzinfo is not None:
            cleaned.index = cleaned.index.tz_convert(None)
        cleaned.sort_index(inplace=True)
        return cleaned

    def _execute_with_retries(
        self,
        operation: Callable[[], pd.DataFrame],
        *,
        symbol: str,
        period: str,
    ) -> pd.DataFrame:
        delay = self.initial_backoff_seconds
        last_exception: Optional[Exception] = None

        for attempt in range(1, self.max_retries + 1):
            try:
                _LOGGER.debug("Attempt %s for %s (%s)", attempt, symbol, period)
                return operation()
            except Exception as exc:  # pragma: no cover - network errors
                last_exception = exc
                _LOGGER.warning(
                    "Attempt %s failed for %s (%s): %s", attempt, symbol, period, exc
                )
                if attempt >= self.max_retries:
                    break
                self._sleep_fn(delay)
                delay *= self.backoff_factor

        if last_exception is not None:
            raise last_exception
        raise RuntimeError("Operation failed without exception")


def _chunked(items: List[str], chunk_size: int) -> Iterable[List[str]]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    for index in range(0, len(items), chunk_size):
        yield items[index : index + chunk_size]

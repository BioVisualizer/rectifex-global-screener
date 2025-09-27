"""Threaded scan runner coordinating data retrieval and evaluation."""

from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

import pandas as pd

from core.cache import Cache
from core.data.fetcher import Fetcher
from core.models import ScanResult, TradeSignal
from core.scans import SCENARIO_REGISTRY, BaseScenario

_LOGGER = logging.getLogger(__name__)


ResultCallback = Callable[[Optional[ScanResult], List[TradeSignal]], None]
ProgressCallback = Callable[["ScanProgress"], None]
FundamentalsProvider = Callable[[str], Optional[dict]]


@dataclass(frozen=True)
class ScanProgress:
    """Progress information emitted while a scan is running."""

    total: int
    processed: int
    skipped: int
    errors: int

    @property
    def remaining(self) -> int:
        return max(self.total - self.processed, 0)


@dataclass(frozen=True)
class ScanSummary:
    """Final statistics returned after a scan completes."""

    total: int
    processed: int
    skipped: int
    errors: int
    cache_hits: int
    cache_misses: int
    duration_seconds: float


class ScanRunner:
    """Coordinate fetching, caching and evaluating scan scenarios."""

    def __init__(
        self,
        *,
        fetcher: Optional[Fetcher] = None,
        cache: Optional[Cache] = None,
        fundamentals_provider: Optional[FundamentalsProvider] = None,
        max_workers: int = 4,
    ) -> None:
        if max_workers <= 0:
            raise ValueError("max_workers must be positive")

        self._fetcher = fetcher or Fetcher()
        self._cache = cache or Cache()
        self._fundamentals_provider = fundamentals_provider or (lambda symbol: None)
        self._max_workers = max_workers

        self._manager_executor = ThreadPoolExecutor(max_workers=1)
        self._active_future: Optional[Future[ScanSummary]] = None
        self._cancel_event = threading.Event()
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def start(
        self,
        strategy: str | BaseScenario,
        symbols: Sequence[str],
        *,
        params: Optional[Dict[str, object]] = None,
        period: str = "1y",
        on_result: Optional[ResultCallback] = None,
        on_progress: Optional[ProgressCallback] = None,
    ) -> Future[ScanSummary]:
        """Start a scan in the background returning a :class:`Future`."""

        scenario = self._resolve_scenario(strategy)
        symbol_list = self._normalise_symbols(symbols)

        with self._lock:
            if self._active_future is not None and not self._active_future.done():
                raise RuntimeError("A scan is already running")
            self._cancel_event.clear()
            future = self._manager_executor.submit(
                self._run_scan,
                scenario,
                symbol_list,
                params or {},
                period,
                on_result,
                on_progress,
            )
            self._active_future = future

        def _clear_active(_future: Future[ScanSummary]) -> None:
            with self._lock:
                self._active_future = None

        future.add_done_callback(_clear_active)
        return future

    def stop(self) -> None:
        """Request cancellation of the active scan."""

        self._cancel_event.set()

    def shutdown(self) -> None:
        """Dispose the runner and release underlying executors."""

        with self._lock:
            future = self._active_future
        if future is not None:
            future.cancel()
        self._manager_executor.shutdown(wait=True)

    # ------------------------------------------------------------------
    # Internal implementation
    # ------------------------------------------------------------------
    def _run_scan(
        self,
        scenario: BaseScenario,
        symbols: List[str],
        params: Dict[str, object],
        period: str,
        on_result: Optional[ResultCallback],
        on_progress: Optional[ProgressCallback],
    ) -> ScanSummary:
        start_time = time.perf_counter()
        total = len(symbols)
        processed = skipped = errors = 0

        cache_hits = cache_misses = 0

        self._emit_progress(on_progress, ScanProgress(total, processed, skipped, errors))

        price_map, cache_hits, cache_misses = self._load_price_data(symbols, period)

        def _process(symbol: str) -> Tuple[str, Optional[ScanResult], List[TradeSignal], Optional[str]]:
            if self._cancel_event.is_set():
                return symbol, None, [], "cancelled"

            price_df = price_map.get(symbol)
            if price_df is None or price_df.empty:
                return symbol, None, [], "missing"

            fundamentals = self._fundamentals_provider(symbol)

            try:
                result, signals = scenario.evaluate(price_df, fundamentals, params)
                return symbol, result, signals, None
            except Exception as exc:  # pragma: no cover - defensive logging
                _LOGGER.exception("Scenario evaluation failed for %s", symbol)
                return symbol, None, [], str(exc)

        with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
            futures = {executor.submit(_process, symbol): symbol for symbol in symbols}
            for future in as_completed(futures):
                symbol, result, signals, error = future.result()

                if error is not None:
                    if error == "missing":
                        skipped += 1
                    elif error == "cancelled":
                        skipped += 1
                    else:
                        errors += 1
                else:
                    if result is None and not signals:
                        skipped += 1
                    else:
                        if on_result is not None:
                            on_result(result, signals)

                processed += 1
                self._emit_progress(
                    on_progress,
                    ScanProgress(total, processed, skipped, errors),
                )

                if self._cancel_event.is_set():
                    break

        duration = time.perf_counter() - start_time
        return ScanSummary(
            total=total,
            processed=processed,
            skipped=skipped,
            errors=errors,
            cache_hits=cache_hits,
            cache_misses=cache_misses,
            duration_seconds=duration,
        )

    def _load_price_data(
        self, symbols: Iterable[str], period: str
    ) -> Tuple[Dict[str, pd.DataFrame], int, int]:
        price_map: Dict[str, pd.DataFrame] = {}
        stale_cache: Dict[str, pd.DataFrame] = {}
        cache_hits = cache_misses = 0
        symbols_to_fetch: List[str] = []

        for symbol in symbols:
            cached_df = self._cache.get(symbol, period)
            if cached_df is not None and not cached_df.empty:
                cached_df = cached_df.copy()
                cached_df.attrs["symbol"] = symbol
                if not self._cache.is_stale(symbol, period):
                    price_map[symbol] = cached_df
                    cache_hits += 1
                    continue
                stale_cache[symbol] = cached_df
            symbols_to_fetch.append(symbol)

        if symbols_to_fetch:
            fetched = self._fetcher.fetch_batch(symbols_to_fetch, period=period)
            for symbol in symbols_to_fetch:
                df = fetched.get(symbol)
                if df is not None and not df.empty:
                    df = df.copy()
                    df.attrs["symbol"] = symbol
                    price_map[symbol] = df
                    self._cache.set(symbol, period, df)
                    cache_misses += 1
                elif symbol in stale_cache:
                    price_map[symbol] = stale_cache[symbol]

        return price_map, cache_hits, cache_misses

    @staticmethod
    def _emit_progress(callback: Optional[ProgressCallback], progress: ScanProgress) -> None:
        if callback is not None:
            try:
                callback(progress)
            except Exception:  # pragma: no cover - defensive logging
                _LOGGER.exception("Progress callback raised an exception")

    @staticmethod
    def _resolve_scenario(strategy: str | BaseScenario) -> BaseScenario:
        if isinstance(strategy, BaseScenario):
            return strategy

        try:
            scenario_cls = SCENARIO_REGISTRY[str(strategy)]
        except KeyError as exc:  # pragma: no cover - invalid configuration
            raise ValueError(f"Unknown strategy identifier: {strategy}") from exc
        return scenario_cls()

    @staticmethod
    def _normalise_symbols(symbols: Sequence[str]) -> List[str]:
        deduplicated: List[str] = []
        seen = set()
        for symbol in symbols:
            key = symbol.strip().upper()
            if not key or key in seen:
                continue
            seen.add(key)
            deduplicated.append(key)
        return deduplicated


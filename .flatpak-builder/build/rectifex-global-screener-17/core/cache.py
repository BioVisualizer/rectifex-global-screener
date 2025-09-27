"""Parquet-backed price cache with SQLite index metadata."""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import pandas as pd

from core.config import DEFAULT_CONFIG

_LOGGER = logging.getLogger(__name__)


def _sanitize_symbol(symbol: str) -> str:
    return symbol.replace("/", "-").upper()


@dataclass
class CacheMetadata:
    symbol: str
    period: str
    updated_at: datetime
    rows: int


class Cache:
    """Price cache using Parquet files and a SQLite metadata index."""

    def __init__(self, base_dir: Optional[Path | str] = None, ttl_days: Optional[int] = None) -> None:
        config = DEFAULT_CONFIG.cache
        self.base_dir = Path(base_dir) if base_dir is not None else Path(config.base_dir)
        self.prices_dir = self.base_dir / config.prices_subdir
        self.index_path = self.base_dir / config.index_name
        self.ttl_days = ttl_days if ttl_days is not None else config.ttl_days

        self.prices_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_index()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get(self, symbol: str, period: str) -> Optional[pd.DataFrame]:
        """Return cached price data if available and not stale."""

        path = self._path_for(symbol, period)
        if not path.exists():
            return None

        try:
            df = pd.read_parquet(path)
        except Exception as exc:  # pragma: no cover - unexpected IO errors
            _LOGGER.warning("Failed to load cache for %s (%s): %s", symbol, period, exc)
            return None

        if df is None or df.empty:
            return None

        return self._restore_index_frequency(df)

    def set(self, symbol: str, period: str, df: pd.DataFrame) -> None:
        """Persist price data for *symbol* and *period*."""

        if df is None or df.empty:
            _LOGGER.debug("Skipping cache store for %s (%s) due to empty dataframe", symbol, period)
            return

        path = self._path_for(symbol, period)
        to_store = df.copy()
        if isinstance(to_store.index, pd.DatetimeIndex):
            if to_store.index.tz is not None:
                to_store.index = to_store.index.tz_convert(None)
            # ``freq`` information is not preserved by Parquet, so normalise before writing.
            to_store.index = pd.DatetimeIndex(to_store.index)
        try:
            to_store.to_parquet(path)
        except Exception as exc:  # pragma: no cover - unexpected IO errors
            _LOGGER.error("Failed to write cache for %s (%s): %s", symbol, period, exc)
            return

        metadata = CacheMetadata(
            symbol=symbol,
            period=period,
            updated_at=datetime.now(timezone.utc),
            rows=len(df.index),
        )
        self._upsert_metadata(metadata)

    def is_stale(self, symbol: str, period: str, ttl_days: Optional[int] = None) -> bool:
        """Return ``True`` if cached data is older than the provided TTL."""

        ttl = ttl_days if ttl_days is not None else self.ttl_days
        metadata = self._read_metadata(symbol, period)
        if metadata is None:
            return True
        return metadata.updated_at < datetime.now(timezone.utc) - timedelta(days=ttl)

    def clear(
        self,
        symbol: Optional[str] = None,
        older_than_days: Optional[int] = None,
    ) -> int:
        """Remove cache entries based on *symbol* and/or age criteria."""

        if symbol is None and older_than_days is None:
            removed = self._remove_all()
        elif symbol is not None and older_than_days is None:
            removed = self._remove_symbol(symbol)
        elif symbol is None and older_than_days is not None:
            cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
            removed = self._remove_older_than(cutoff)
        else:
            cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days or 0)
            removed = self._remove_symbol(symbol, cutoff)

        return removed

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _ensure_index(self) -> None:
        connection = sqlite3.connect(self.index_path)
        try:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS cache_index (
                    symbol TEXT NOT NULL,
                    period TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    rows INTEGER NOT NULL,
                    PRIMARY KEY(symbol, period)
                )
                """
            )
            connection.commit()
        finally:
            connection.close()

    def _path_for(self, symbol: str, period: str) -> Path:
        sanitized = _sanitize_symbol(symbol)
        filename = f"{sanitized}__{period}.parquet"
        return self.prices_dir / filename

    def _upsert_metadata(self, metadata: CacheMetadata) -> None:
        connection = sqlite3.connect(self.index_path)
        try:
            connection.execute(
                """
                INSERT INTO cache_index (symbol, period, updated_at, rows)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(symbol, period) DO UPDATE SET
                    updated_at=excluded.updated_at,
                    rows=excluded.rows
                """,
                (
                    metadata.symbol,
                    metadata.period,
                    metadata.updated_at.isoformat(),
                    metadata.rows,
                ),
            )
            connection.commit()
        finally:
            connection.close()

    def _read_metadata(self, symbol: str, period: str) -> Optional[CacheMetadata]:
        connection = sqlite3.connect(self.index_path)
        try:
            cursor = connection.execute(
                "SELECT updated_at, rows FROM cache_index WHERE symbol=? AND period=?",
                (symbol, period),
            )
            row = cursor.fetchone()
        finally:
            connection.close()

        if row is None:
            return None

        updated_at_str, rows = row
        updated_at = datetime.fromisoformat(updated_at_str)
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)
        return CacheMetadata(symbol=symbol, period=period, updated_at=updated_at, rows=rows)

    def _remove_all(self) -> int:
        connection = sqlite3.connect(self.index_path)
        try:
            cursor = connection.execute("SELECT symbol, period FROM cache_index")
            entries = cursor.fetchall()
        finally:
            connection.close()

        removed = 0
        for symbol, period in entries:
            removed += self._remove_symbol(symbol, None)
        return removed

    def _remove_symbol(self, symbol: str, older_than: Optional[datetime] = None) -> int:
        connection = sqlite3.connect(self.index_path)
        try:
            if older_than is None:
                cursor = connection.execute(
                    "SELECT period FROM cache_index WHERE symbol=?",
                    (symbol,),
                )
            else:
                cursor = connection.execute(
                    """
                    SELECT period FROM cache_index
                    WHERE symbol=? AND updated_at < ?
                    """,
                    (symbol, older_than.isoformat()),
                )
            periods = [row[0] for row in cursor.fetchall()]
        finally:
            connection.close()

        removed = 0
        for period in periods:
            path = self._path_for(symbol, period)
            if path.exists():
                path.unlink()
                removed += 1

        connection = sqlite3.connect(self.index_path)
        try:
            if older_than is None:
                connection.execute("DELETE FROM cache_index WHERE symbol=?", (symbol,))
            else:
                connection.execute(
                    "DELETE FROM cache_index WHERE symbol=? AND updated_at < ?",
                    (symbol, older_than.isoformat()),
                )
            connection.commit()
        finally:
            connection.close()

        return removed

    def _remove_older_than(self, cutoff: datetime) -> int:
        connection = sqlite3.connect(self.index_path)
        try:
            cursor = connection.execute(
                "SELECT symbol, period FROM cache_index WHERE updated_at < ?",
                (cutoff.isoformat(),),
            )
            entries = cursor.fetchall()
        finally:
            connection.close()

        removed = 0
        for symbol, period in entries:
            removed += self._remove_symbol(symbol, cutoff)
        return removed

    def _restore_index_frequency(self, df: pd.DataFrame) -> pd.DataFrame:
        if not isinstance(df.index, pd.DatetimeIndex):
            return df

        if df.index.freq is not None:
            return df

        try:
            inferred = pd.infer_freq(df.index)
        except (ValueError, TypeError):
            inferred = None

        if inferred:
            df.index = pd.DatetimeIndex(df.index, freq=inferred)

        return df

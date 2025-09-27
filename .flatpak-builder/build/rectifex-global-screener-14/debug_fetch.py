"""Utility script used during development to validate data fetching and caching."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import List

import pandas as pd

from core.cache import Cache
from core.config import DEFAULT_CONFIG
from core.data.fetcher import Fetcher

_LOGGER = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tickers", nargs="*", help="Ticker symbols to download (e.g. AAPL MSFT)")
    parser.add_argument("--period", default=DEFAULT_CONFIG.fetcher.period_default, help="yfinance period argument")
    parser.add_argument(
        "--from-file",
        dest="from_file",
        type=Path,
        help="Optional text file containing tickers (one per line)",
    )
    parser.add_argument("--use-cache", action="store_true", help="Attempt to read/write through the cache")
    return parser.parse_args()


def read_tickers(args: argparse.Namespace) -> List[str]:
    tickers: List[str] = []
    if args.from_file:
        tickers.extend(line.strip() for line in args.from_file.read_text().splitlines() if line.strip())
    tickers.extend(args.tickers)
    return tickers


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    args = parse_args()
    tickers = read_tickers(args)

    if not tickers:
        raise SystemExit("No tickers provided")

    fetcher = Fetcher()
    cache = Cache()

    results = {}
    for symbol, df in fetcher.fetch_batch(tickers, period=args.period).items():
        if df is None or df.empty:
            _LOGGER.warning("No data for %s", symbol)
            continue
        _LOGGER.info("Fetched %s rows for %s", len(df), symbol)
        if args.use_cache:
            cache.set(symbol, args.period, df)
        summary = {
            "rows": len(df),
            "start": df.index.min().isoformat() if isinstance(df.index, pd.DatetimeIndex) else None,
            "end": df.index.max().isoformat() if isinstance(df.index, pd.DatetimeIndex) else None,
        }
        results[symbol] = summary

    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Command-line interface for executing Rectifex scans outside the UI."""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import pandas as pd
import yfinance as yf

from core.data.fundamentals import read_fundamentals
from core.models import ScanResult, TradeSignal
from core.runners import ScanRunner
from core.scans import SCENARIO_REGISTRY, BaseScenario

_LOGGER = logging.getLogger("rectifex.cli")


class FundamentalsService:
    """Lightweight fundamentals fetcher with retry handling."""

    def __init__(self, max_retries: int = 3, initial_delay: float = 1.0, backoff: float = 2.0) -> None:
        self._max_retries = max_retries
        self._initial_delay = initial_delay
        self._backoff = backoff
        self._cache: Dict[str, Dict[str, float]] = {}

    def get(self, symbol: str) -> Dict[str, float]:
        if symbol in self._cache:
            return self._cache[symbol]

        delay = self._initial_delay
        for attempt in range(1, self._max_retries + 1):
            try:
                ticker = yf.Ticker(symbol)
                info = ticker.info
                fundamentals = read_fundamentals(info)
                self._cache[symbol] = fundamentals
                return fundamentals
            except Exception as exc:  # pragma: no cover - network variability
                _LOGGER.warning("Fundamentals fetch failed for %s (attempt %s): %s", symbol, attempt, exc)
                if attempt >= self._max_retries:
                    break
                time.sleep(delay)
                delay *= self._backoff

        _LOGGER.error("Falling back to empty fundamentals for %s", symbol)
        fundamentals = read_fundamentals(None)
        self._cache[symbol] = fundamentals
        return fundamentals


def _parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="rectifex", description="Rectifex Global Screener CLI")
    parser.add_argument("command", choices=["scan"], help="Command to execute")
    parser.add_argument("--version", action="version", version="Rectifex CLI 1.0")

    parser.add_argument("--strategy", required=True, help="Identifier of the scan strategy")
    parser.add_argument("--tickers", required=True, help="Path to a text file with tickers (one per line)")
    parser.add_argument("--period", default="1y", help="History period to request from yfinance")
    parser.add_argument("--out", required=True, help="Destination JSON file for results")
    parser.add_argument("--profile", help="Optional profile (e.g. for LTI Compounder)")
    parser.add_argument(
        "--params",
        nargs="*",
        default=[],
        metavar="KEY=VALUE",
        help="Override scenario parameters using key=value notation",
    )
    parser.add_argument(
        "--include-signals",
        action="store_true",
        help="Include trade signal history in the exported JSON",
    )
    parser.add_argument("--workers", type=int, default=4, help="Thread pool size for scenario evaluation")

    return parser.parse_args(argv)


def _load_tickers(path: Path) -> List[str]:
    if not path.exists():
        raise FileNotFoundError(f"Ticker file not found: {path}")

    symbols: List[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        symbols.append(stripped.upper())

    return symbols


def _parse_param_value(value: str):  # type: ignore[no-untyped-def]
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value


def _build_params(scenario: BaseScenario, overrides: Iterable[str], profile: Optional[str]) -> Dict[str, object]:
    params: Dict[str, object] = dict(getattr(scenario, "default_params", {}))
    if profile:
        params["profile"] = profile
    for override in overrides:
        if "=" not in override:
            _LOGGER.warning("Ignoring invalid parameter override: %s", override)
            continue
        key, raw_value = override.split("=", 1)
        params[key.strip()] = _parse_param_value(raw_value.strip())
    return params


def _results_to_dict(result: ScanResult) -> Dict[str, object]:
    payload: Dict[str, object] = {
        "symbol": result.symbol,
        "score": result.score,
        "last_price": result.last_price,
        "as_of": result.as_of.isoformat(),
        "metrics": result.metrics,
        "reasons": result.reasons,
    }
    if result.meta is not None:
        payload["meta"] = asdict(result.meta)
    return payload


def _signals_to_list(signals: Iterable[TradeSignal]) -> List[Dict[str, object]]:
    entries: List[Dict[str, object]] = []
    for signal in signals:
        entries.append(
            {
                "symbol": signal.symbol,
                "timestamp": pd.Timestamp(signal.timestamp).isoformat(),
                "side": signal.side,
                "confidence": signal.confidence,
                "reason": signal.reason,
                "scenario_id": signal.scenario_id,
            }
        )
    return entries


def main(argv: Optional[Iterable[str]] = None) -> int:
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    args = _parse_args(argv)

    if args.command != "scan":
        _LOGGER.error("Unsupported command: %s", args.command)
        return 1

    strategy_id = args.strategy
    try:
        scenario_cls = SCENARIO_REGISTRY[strategy_id]
    except KeyError:
        _LOGGER.error("Unknown strategy identifier: %s", strategy_id)
        return 1

    scenario = scenario_cls()
    params = _build_params(scenario, args.params, args.profile)

    tickers_path = Path(args.tickers)
    try:
        tickers = _load_tickers(tickers_path)
    except FileNotFoundError as exc:
        _LOGGER.error(str(exc))
        return 1

    if not tickers:
        _LOGGER.error("Ticker list is empty: %s", tickers_path)
        return 1

    fundamentals = FundamentalsService()
    results: Dict[str, ScanResult] = {}
    signals: Dict[str, List[TradeSignal]] = {}

    runner = ScanRunner(max_workers=args.workers, fundamentals_provider=fundamentals.get)

    def _on_result(result: Optional[ScanResult], emitted: List[TradeSignal]) -> None:
        if result is not None:
            results[result.symbol] = result
        for signal in emitted:
            signals.setdefault(signal.symbol, []).append(signal)

    future = runner.start(
        scenario,
        tickers,
        params=params,
        period=args.period,
        on_result=_on_result,
        on_progress=None,
    )

    try:
        summary = future.result()
    finally:
        runner.shutdown()

    output = {
        "strategy": strategy_id,
        "period": args.period,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": summary.__dict__ if summary is not None else None,
        "results": [_results_to_dict(result) for result in results.values()],
    }

    if args.include_signals:
        all_signals: List[TradeSignal] = []
        for bucket in signals.values():
            all_signals.extend(bucket)
        output["signals"] = _signals_to_list(all_signals)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    _LOGGER.info("Results written to %s", out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Golden cross / death cross detection."""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from core.indicators import rsi, sma
from core.models import ScanResult, TradeSignal
from core.scans.base import BaseScenario

__all__ = ["GoldenCrossScenario"]


class GoldenCrossScenario(BaseScenario):
    id = "golden_cross"
    name = "Golden Cross"
    description = "SMA50 crossing above SMA200 (buy) and below (sell)."
    default_params: Dict[str, float] = {"threshold": 45.0}

    def evaluate(
        self,
        price_df: Optional[pd.DataFrame],
        fundamentals: Optional[dict],
        params: Optional[Dict[str, float]] = None,
    ) -> Tuple[Optional[ScanResult], List[TradeSignal]]:
        context = self.build_context(price_df, fundamentals)
        if context is None:
            return None, []

        arguments = {**self.default_params, **(params or {})}
        threshold = float(arguments.get("threshold", 45.0))

        closes = context.series.close.dropna()
        if closes.shape[0] < 210:
            return None, []

        sma50 = sma(closes, 50)
        sma200 = sma(closes, 200)
        last_close = closes.iloc[-1]
        last_sma50 = sma50.iloc[-1]
        last_sma200 = sma200.iloc[-1]
        prev_sma50 = sma50.iloc[-2]
        prev_sma200 = sma200.iloc[-2]

        if np.isnan(last_sma200) or np.isnan(prev_sma200):
            return None, []

        golden_cross = prev_sma50 <= prev_sma200 and last_sma50 > last_sma200
        death_cross = prev_sma50 >= prev_sma200 and last_sma50 < last_sma200

        rsi_series = rsi(closes, 14)
        last_rsi = float(rsi_series.iloc[-1])

        score = 25.0
        if golden_cross:
            score += 25.0
        if death_cross:
            score += 15.0
        score += np.clip((last_sma50 / last_sma200 - 1.0) * 100.0, -20.0, 20.0)
        score += np.clip((last_rsi - 50.0) / 50.0 * 15.0, -15.0, 15.0)
        score = float(np.clip(score, 0.0, 100.0))

        reasons: List[str] = []
        if golden_cross:
            self._append_reason(reasons, "SMA50 crossed above SMA200")
        if death_cross:
            self._append_reason(reasons, "SMA50 crossed below SMA200")
        if last_rsi >= 55:
            self._append_reason(reasons, "Momentum supportive (RSI ≥ 55)")
        if last_rsi <= 45:
            self._append_reason(reasons, "Momentum weakening (RSI ≤ 45)")

        metrics = {
            "sma50": float(last_sma50),
            "sma200": float(last_sma200),
            "last_rsi": last_rsi,
            "golden_cross": float(bool(golden_cross)),
            "death_cross": float(bool(death_cross)),
            "score": score,
        }

        signals: List[TradeSignal] = []
        if golden_cross:
            confidence = self._confidence_from_score(score, threshold)
            signals.append(
                TradeSignal(
                    symbol=context.symbol,
                    timestamp=closes.index[-1],
                    side="buy",
                    confidence=confidence,
                    reason="Golden cross triggered",
                    scenario_id=self.id,
                )
            )
        if death_cross:
            confidence = self._confidence_from_score(score, threshold)
            signals.append(
                TradeSignal(
                    symbol=context.symbol,
                    timestamp=closes.index[-1],
                    side="sell",
                    confidence=confidence,
                    reason="Death cross triggered",
                    scenario_id=self.id,
                )
            )

        result = None
        if score >= threshold:
            result = ScanResult(
                symbol=context.symbol,
                score=score,
                metrics=metrics,
                reasons=reasons[:3],
                last_price=float(last_close),
                as_of=context.as_of,
                meta=None,
            )

        return result, signals


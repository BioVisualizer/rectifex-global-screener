"""Long-term compounder strategy combining fundamentals and timing."""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from core.config import DEFAULT_CONFIG
from core.indicators import rsi, sma
from core.models import ScanResult, TradeSignal
from core.scans.base import BaseScenario
from core.scoring import (
    composite,
    score_dividend,
    score_finance,
    score_growth,
    score_quality,
    score_value,
    timing_modifier,
)

__all__ = ["LTICompounderScenario"]


class LTICompounderScenario(BaseScenario):
    id = "lti_compounder"
    name = "LTI Compounder"
    description = "Fundamental compounder profile with technical timing overlays."
    default_params: Dict[str, object] = {
        "profile": "balanced",
        "threshold": 60.0,
    }

    def evaluate(
        self,
        price_df: Optional[pd.DataFrame],
        fundamentals: Optional[dict],
        params: Optional[Dict[str, object]] = None,
    ) -> Tuple[Optional[ScanResult], List[TradeSignal]]:
        context = self.build_context(price_df, fundamentals)
        if context is None or fundamentals is None:
            return None, []

        arguments = {**self.default_params, **(params or {})}
        profile = str(arguments.get("profile", "balanced")).lower()
        threshold = float(arguments.get("threshold", 60.0))

        weights = DEFAULT_CONFIG.profiles.lti_profiles.get(profile)
        if weights is None:
            weights = DEFAULT_CONFIG.profiles.lti_profiles["balanced"]

        parts = {
            "quality": score_quality(fundamentals),
            "growth": score_growth(fundamentals),
            "value": score_value(fundamentals),
            "finance": score_finance(fundamentals),
            "dividend": score_dividend(fundamentals),
        }
        base_score = composite(weights, parts)

        timing, timing_reason = timing_modifier(context.price_df)
        final_score = float(np.clip(base_score + timing, 0.0, 100.0))

        closes = context.series.close.dropna()
        if closes.empty:
            return None, []

        sma50 = sma(closes, 50)
        sma200 = sma(closes, 200)
        last_close = float(closes.iloc[-1])
        last_sma200 = float(sma200.iloc[-1]) if sma200.iloc[-1] == sma200.iloc[-1] else np.nan
        last_sma50 = float(sma50.iloc[-1]) if sma50.iloc[-1] == sma50.iloc[-1] else np.nan
        rsi_series = rsi(closes, 14)
        last_rsi = float(rsi_series.iloc[-1])

        reasons: List[str] = []
        sorted_parts = sorted(parts.items(), key=lambda item: item[1], reverse=True)
        for key, value in sorted_parts[:2]:
            self._append_reason(reasons, f"{key.title()} score {value:.0f}")
        if timing_reason:
            self._append_reason(reasons, timing_reason)

        metrics = {
            "base_score": float(base_score),
            "timing_modifier": float(timing),
            "final_score": final_score,
            "last_close": last_close,
            "last_sma50": float(last_sma50),
            "last_sma200": float(last_sma200),
            "last_rsi": last_rsi,
        }
        metrics.update({f"score_{key}": float(value) for key, value in parts.items()})

        signals: List[TradeSignal] = []
        buy_trigger = final_score >= threshold and timing >= 0 and (
            np.isnan(last_sma200) or last_close >= last_sma200 * 0.99
        )

        prev_close = float(closes.iloc[-2]) if closes.shape[0] >= 2 else last_close
        sell_trigger = False
        if not np.isnan(last_sma200) and last_close < last_sma200 * 0.98:
            sell_trigger = True
        elif last_rsi >= 75 and last_close < prev_close:
            sell_trigger = True

        confidence = self._confidence_from_score(final_score, threshold)
        if buy_trigger:
            signals.append(
                TradeSignal(
                    symbol=context.symbol,
                    timestamp=closes.index[-1],
                    side="buy",
                    confidence=confidence,
                    reason="Compounder profile aligned with timing",
                    scenario_id=self.id,
                )
            )
        if sell_trigger:
            sell_confidence = max(confidence, 0.4)
            signals.append(
                TradeSignal(
                    symbol=context.symbol,
                    timestamp=closes.index[-1],
                    side="sell",
                    confidence=sell_confidence,
                    reason="Trend deterioration for compounder",
                    scenario_id=self.id,
                )
            )

        result = None
        if final_score >= threshold:
            result = ScanResult(
                symbol=context.symbol,
                score=final_score,
                metrics=metrics,
                reasons=reasons[:3],
                last_price=last_close,
                as_of=context.as_of,
                meta=None,
            )

        return result, signals


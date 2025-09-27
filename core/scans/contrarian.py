"""Contrarian and mean-reversion scans."""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np

from core.indicators import bollinger, rsi, stoch
from core.models import ScanResult, TradeSignal
from core.scans.base import BaseScenario

__all__ = [
    "ClassicOversoldScenario",
    "MeanReversionBollingerScenario",
    "StochasticOversoldScenario",
]


class ClassicOversoldScenario(BaseScenario):
    id = "classic_oversold"
    name = "Classic Oversold"
    description = "RSI capitulation followed by a bounce above the lower Bollinger Band."
    default_params: Dict[str, float] = {
        "rsi_threshold": 30.0,
        "threshold": 50.0,
    }

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
        rsi_threshold = float(arguments.get("rsi_threshold", 30.0))
        threshold = float(arguments.get("threshold", 50.0))

        closes = context.series.close.dropna()
        lows = context.series.low.reindex(closes.index)
        highs = context.series.high.reindex(closes.index)

        if closes.shape[0] < 40:
            return None, []

        rsi_series = rsi(closes, 14)
        bb = bollinger(closes, window=20)
        last_close = closes.iloc[-1]
        last_rsi = float(rsi_series.iloc[-1])
        recent_rsi = rsi_series.tail(3)
        recent_min_rsi = float(recent_rsi.min())
        oversold_recent = recent_min_rsi <= rsi_threshold
        last_lower = float(bb["lower"].iloc[-1])
        prev_close = closes.iloc[-2] if closes.shape[0] >= 2 else np.nan
        candle_reversal = last_close > prev_close and last_close > last_lower

        rsi_reference = min(last_rsi, recent_min_rsi)
        rsi_score = np.clip((rsi_threshold - rsi_reference) / max(rsi_threshold, 1e-3), 0.0, 1.5)
        bounce_score = 1.0 if candle_reversal else 0.0
        score = float(np.clip(20.0 + rsi_score * 40.0 + bounce_score * 30.0, 0.0, 100.0))

        reasons: List[str] = []
        if oversold_recent:
            if last_rsi <= rsi_threshold:
                rsi_text = f"RSI oversold ({last_rsi:.1f})"
            else:
                rsi_text = f"RSI rebounded from {recent_min_rsi:.1f}"
            self._append_reason(reasons, rsi_text)
        if candle_reversal:
            self._append_reason(reasons, "Reversal candle above lower Bollinger Band")

        signals: List[TradeSignal] = []
        if oversold_recent and candle_reversal:
            confidence = self._confidence_from_score(score, threshold)
            signals.append(
                TradeSignal(
                    symbol=context.symbol,
                    timestamp=closes.index[-1],
                    side="buy",
                    confidence=confidence,
                    reason="Oversold reversal setup",
                    scenario_id=self.id,
                )
            )

        metrics = {
            "last_close": float(last_close),
            "lower_band": float(last_lower),
            "last_rsi": last_rsi,
            "recent_min_rsi": recent_min_rsi,
            "score": score,
        }

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


class MeanReversionBollingerScenario(BaseScenario):
    id = "mean_reversion_bb"
    name = "Mean Reversion (Bollinger)"
    description = "Price pierces the lower Bollinger Band and reclaims it on a bounce."
    default_params: Dict[str, float] = {
        "threshold": 48.0,
        "band_window": 20,
    }

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
        threshold = float(arguments.get("threshold", 48.0))
        band_window = int(arguments.get("band_window", 20))

        closes = context.series.close.dropna()
        lows = context.series.low.reindex(closes.index)

        if closes.shape[0] < band_window + 5:
            return None, []

        bb = bollinger(closes, window=band_window)
        last_close = closes.iloc[-1]
        last_low = lows.iloc[-1]
        lower_band = bb["lower"].iloc[-1]
        prev_close = closes.iloc[-2] if closes.shape[0] >= 2 else last_close

        tagged_band = last_low < lower_band
        reclaim = last_close > lower_band and prev_close < lower_band

        score_components = [
            25.0 if tagged_band else 0.0,
            35.0 if reclaim else 0.0,
        ]
        score = float(np.clip(sum(score_components) + 20.0, 0.0, 100.0))

        reasons: List[str] = []
        if tagged_band:
            self._append_reason(reasons, "Price flushed below lower band")
        if reclaim:
            self._append_reason(reasons, "Close reclaimed lower band")

        signals: List[TradeSignal] = []
        if tagged_band and reclaim:
            confidence = self._confidence_from_score(score, threshold)
            signals.append(
                TradeSignal(
                    symbol=context.symbol,
                    timestamp=closes.index[-1],
                    side="buy",
                    confidence=confidence,
                    reason="Bollinger mean reversion trigger",
                    scenario_id=self.id,
                )
            )

        metrics = {
            "last_close": float(last_close),
            "lower_band": float(lower_band),
            "tagged_band": float(bool(tagged_band)),
            "reclaim": float(bool(reclaim)),
            "score": score,
        }

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


class StochasticOversoldScenario(BaseScenario):
    id = "stochastic_oversold"
    name = "Stochastic Oversold"
    description = "%K crossing above %D in the oversold zone (<20)."
    default_params: Dict[str, float] = {
        "threshold": 45.0,
    }

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
        highs = context.series.high.reindex(closes.index)
        lows = context.series.low.reindex(closes.index)

        if closes.shape[0] < 20:
            return None, []

        stoch_df = stoch(highs, lows, closes)
        percent_k = stoch_df["%K"].iloc[-1]
        percent_d = stoch_df["%D"].iloc[-1]
        prev_k = stoch_df["%K"].iloc[-2] if stoch_df.shape[0] >= 2 else percent_k
        prev_d = stoch_df["%D"].iloc[-2] if stoch_df.shape[0] >= 2 else percent_d

        oversold = max(percent_k, percent_d) < 20
        bullish_cross = prev_k < prev_d and percent_k > percent_d

        score = float(np.clip(15.0 + (1 if oversold else 0) * 35.0 + (1 if bullish_cross else 0) * 35.0, 0, 100))

        reasons: List[str] = []
        if oversold:
            self._append_reason(reasons, "Stochastic deeply oversold")
        if bullish_cross:
            self._append_reason(reasons, "%K bullish cross over %D")

        signals: List[TradeSignal] = []
        if oversold and bullish_cross:
            confidence = self._confidence_from_score(score, threshold)
            signals.append(
                TradeSignal(
                    symbol=context.symbol,
                    timestamp=closes.index[-1],
                    side="buy",
                    confidence=confidence,
                    reason="Stochastic oversold reversal",
                    scenario_id=self.id,
                )
            )

        metrics = {
            "%K": float(percent_k),
            "%D": float(percent_d),
            "score": score,
        }

        result = None
        if score >= threshold:
            result = ScanResult(
                symbol=context.symbol,
                score=score,
                metrics=metrics,
                reasons=reasons[:3],
                last_price=float(closes.iloc[-1]),
                as_of=context.as_of,
                meta=None,
            )

        return result, signals


"""Volatility squeeze detection and breakout handling."""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np

from core.indicators import bollinger, keltner_channels, vol_ma
from core.models import ScanResult, TradeSignal
from core.scans.base import BaseScenario

__all__ = ["VolatilitySqueezeScenario"]


class VolatilitySqueezeScenario(BaseScenario):
    id = "volatility_squeeze"
    name = "Volatility Squeeze"
    description = "Compression of Bollinger width within Keltner channels followed by a break."
    default_params: Dict[str, float] = {
        "threshold": 60.0,
        "lookback": 120,
        "width_percentile": 0.25,
        "volume_multiplier": 1.2,
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
        threshold = float(arguments.get("threshold", 60.0))
        lookback = int(arguments.get("lookback", 120))
        width_percentile = float(arguments.get("width_percentile", 0.25))
        volume_multiplier = float(arguments.get("volume_multiplier", 1.2))

        closes = context.series.close.dropna()
        highs = context.series.high.reindex(closes.index)
        lows = context.series.low.reindex(closes.index)
        volume = context.series.volume.reindex(closes.index) if context.series.volume is not None else None

        if closes.shape[0] < max(lookback, 40) or volume is None or volume.isna().all():
            return None, []

        bb = bollinger(closes, window=20)
        kc = keltner_channels(highs, lows, closes, window=20, atr_window=10, multiplier=1.5)

        width = bb["width"]
        if width.isna().all():
            return None, []

        recent_width = width.iloc[-lookback:]
        width_floor = np.nanpercentile(recent_width.dropna(), width_percentile * 100)

        last_close = closes.iloc[-1]
        last_upper = bb["upper"].iloc[-1]
        last_lower = bb["lower"].iloc[-1]
        last_kc_upper = kc["upper"].iloc[-1]
        last_kc_lower = kc["lower"].iloc[-1]
        last_width = width.iloc[-1]

        squeeze_active = last_width <= width_floor and last_upper <= last_kc_upper and last_lower >= last_kc_lower

        volume_ma_series = vol_ma(volume, 20)
        last_volume_ma = volume_ma_series.iloc[-1]
        last_volume = volume.iloc[-1]
        volume_confirm = last_volume_ma > 0 and last_volume >= last_volume_ma * volume_multiplier

        breakout_up = last_close > max(last_upper, last_kc_upper)
        breakout_down = last_close < min(last_lower, last_kc_lower)

        score = 35.0
        if squeeze_active:
            score += 25.0
        if breakout_up or breakout_down:
            score += 20.0
        if volume_confirm:
            score += 15.0
        score = float(np.clip(score, 0.0, 100.0))

        reasons: List[str] = []
        if squeeze_active:
            self._append_reason(reasons, "Bollinger width compressed inside Keltner channels")
        if breakout_up:
            self._append_reason(reasons, "Breakout above squeeze range")
        if breakout_down:
            self._append_reason(reasons, "Breakdown below squeeze range")
        if volume_confirm:
            self._append_reason(reasons, "Volume expansion on break")

        metrics = {
            "last_width": float(last_width),
            "width_floor": float(width_floor),
            "breakout_up": float(bool(breakout_up)),
            "breakout_down": float(bool(breakout_down)),
            "volume_ratio": float((last_volume / last_volume_ma) if last_volume_ma else np.nan),
            "score": score,
        }

        signals: List[TradeSignal] = []
        if breakout_up and volume_confirm:
            confidence = self._confidence_from_score(score, threshold)
            signals.append(
                TradeSignal(
                    symbol=context.symbol,
                    timestamp=closes.index[-1],
                    side="buy",
                    confidence=confidence,
                    reason="Squeeze breakout to the upside",
                    scenario_id=self.id,
                )
            )
        if breakout_down and volume_confirm:
            confidence = self._confidence_from_score(score, threshold)
            signals.append(
                TradeSignal(
                    symbol=context.symbol,
                    timestamp=closes.index[-1],
                    side="sell",
                    confidence=confidence,
                    reason="Squeeze breakdown to the downside",
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


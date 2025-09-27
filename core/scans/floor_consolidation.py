"""Floor consolidation setups identifying tight ranges before breakouts."""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np

from core.indicators import rsi, vol_ma
from core.models import ScanResult, TradeSignal
from core.scans.base import BaseScenario
from core.scoring import score_finance, score_quality

__all__ = [
    "FloorConsolidationUniversalScenario",
    "FloorConsolidationQualityScenario",
]


class _BaseFloorScenario(BaseScenario):
    range_window: int = 30
    breakout_buffer: float = 0.005
    max_range_pct: float = 0.12
    volume_multiplier: float = 1.25

    def _evaluate_common(self, context: object) -> Optional[dict]:
        if context is None:  # type: ignore[redundant-expr]
            return None
        assert hasattr(context, "series")
        series = context.series  # type: ignore[attr-defined]

        closes = series.close.dropna()
        highs = series.high.reindex(closes.index)
        lows = series.low.reindex(closes.index)
        volume = series.volume.reindex(closes.index) if series.volume is not None else None

        if closes.shape[0] < max(self.range_window + 5, 40) or volume is None or volume.isna().all():
            return None

        recent_high = highs.rolling(window=self.range_window, min_periods=self.range_window).max()
        recent_low = lows.rolling(window=self.range_window, min_periods=self.range_window).min()
        last_high = float(recent_high.iloc[-1])
        last_low = float(recent_low.iloc[-1])
        last_close = float(closes.iloc[-1])
        range_pct = (last_high - last_low) / last_close if last_close else np.nan

        higher_lows = lows.iloc[-3:].is_monotonic_increasing if lows.shape[0] >= 3 else False
        volume_ma_series = vol_ma(volume, 20)
        last_volume = float(volume.iloc[-1])
        last_volume_ma = float(volume_ma_series.iloc[-1])
        breakout_trigger = last_high * (1 - self.breakout_buffer)
        breakout = last_close >= breakout_trigger
        volume_confirm = last_volume_ma > 0 and last_volume >= last_volume_ma * self.volume_multiplier
        rsi_series = rsi(closes, 14)
        last_rsi = float(rsi_series.iloc[-1])

        return {
            "closes": closes,
            "last_close": last_close,
            "last_high": last_high,
            "last_low": last_low,
            "range_pct": range_pct,
            "higher_lows": bool(higher_lows),
            "breakout": bool(breakout),
            "volume_confirm": bool(volume_confirm),
            "volume_ratio": (last_volume / last_volume_ma) if last_volume_ma else np.nan,
            "last_rsi": last_rsi,
        }


class FloorConsolidationUniversalScenario(_BaseFloorScenario):
    id = "floor_consolidation_universal"
    name = "Floor Consolidation (Universal)"
    description = "Tight base with rising lows and breakout on volume."
    default_params: Dict[str, float] = {"threshold": 55.0}

    def evaluate(
        self,
        price_df: Optional[pd.DataFrame],
        fundamentals: Optional[dict],
        params: Optional[Dict[str, float]] = None,
    ) -> Tuple[Optional[ScanResult], List[TradeSignal]]:
        context = self.build_context(price_df, fundamentals)
        if context is None:
            return None, []

        snapshot = self._evaluate_common(context)
        if snapshot is None:
            return None, []

        threshold = float({**self.default_params, **(params or {})}.get("threshold", 55.0))
        score = 25.0
        if snapshot["range_pct"] <= self.max_range_pct:
            score += 20.0
        if snapshot["higher_lows"]:
            score += 15.0
        if snapshot["breakout"]:
            score += 20.0
        if snapshot["volume_confirm"]:
            score += 10.0
        score = float(np.clip(score, 0.0, 100.0))

        reasons: List[str] = []
        if snapshot["range_pct"] <= self.max_range_pct:
            self._append_reason(reasons, "Range contracted near lows")
        if snapshot["higher_lows"]:
            self._append_reason(reasons, "Higher lows across the base")
        if snapshot["breakout"]:
            self._append_reason(reasons, "Breakout above base resistance")
        if snapshot["volume_confirm"]:
            self._append_reason(reasons, "Volume expansion on breakout")

        signals: List[TradeSignal] = []
        if snapshot["breakout"] and snapshot["volume_confirm"]:
            confidence = self._confidence_from_score(score, threshold)
            signals.append(
                TradeSignal(
                    symbol=context.symbol,
                    timestamp=snapshot["closes"].index[-1],
                    side="buy",
                    confidence=confidence,
                    reason="Floor breakout with volume",
                    scenario_id=self.id,
                )
            )

        metrics = {
            "range_pct": float(snapshot["range_pct"]),
            "volume_ratio": float(snapshot["volume_ratio"]),
            "last_rsi": float(snapshot["last_rsi"]),
            "score": score,
        }

        result = None
        if score >= threshold:
            result = ScanResult(
                symbol=context.symbol,
                score=score,
                metrics=metrics,
                reasons=reasons[:3],
                last_price=float(snapshot["last_close"]),
                as_of=context.as_of,
                meta=None,
            )

        return result, signals


class FloorConsolidationQualityScenario(_BaseFloorScenario):
    id = "floor_consolidation_quality"
    name = "Floor Consolidation (Quality)"
    description = "Floor consolidation with additional fundamental quality filter."
    default_params: Dict[str, float] = {"threshold": 60.0, "quality_floor": 60.0, "finance_floor": 55.0}

    def evaluate(
        self,
        price_df: Optional[pd.DataFrame],
        fundamentals: Optional[dict],
        params: Optional[Dict[str, float]] = None,
    ) -> Tuple[Optional[ScanResult], List[TradeSignal]]:
        context = self.build_context(price_df, fundamentals)
        if context is None:
            return None, []

        snapshot = self._evaluate_common(context)
        if snapshot is None or fundamentals is None:
            return None, []

        arguments = {**self.default_params, **(params or {})}
        threshold = float(arguments.get("threshold", 60.0))
        quality_floor = float(arguments.get("quality_floor", 60.0))
        finance_floor = float(arguments.get("finance_floor", 55.0))

        quality_score = score_quality(fundamentals)
        finance_score = score_finance(fundamentals)
        fundamentals_ok = quality_score >= quality_floor and finance_score >= finance_floor

        base_result, signals = FloorConsolidationUniversalScenario.evaluate(  # type: ignore[misc]
            self,
            price_df,
            fundamentals,
            {"threshold": threshold},
        )

        if base_result is None:
            return None, []

        if not fundamentals_ok:
            return None, []

        base_result.metrics.update({"quality_score": quality_score, "finance_score": finance_score})
        self._append_reason(base_result.reasons, "Quality fundamentals confirmed")

        return base_result, signals


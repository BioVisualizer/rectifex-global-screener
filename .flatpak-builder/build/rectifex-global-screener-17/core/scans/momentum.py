"""Momentum oriented scan implementations."""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from core.indicators import rsi, sma, vol_ma
from core.models import ScanResult, TradeSignal
from core.scans.base import BaseScenario

__all__ = ["MomentumBreakoutScenario", "VolumeConfirmedBreakoutScenario"]


class MomentumBreakoutScenario(BaseScenario):
    id = "momentum_breakout"
    name = "Momentum Breakout"
    description = (
        "52-week high breakout confirmed by trend filters and volume expansion."
    )
    default_params: Dict[str, float] = {
        "lookback": 252,
        "volume_multiplier": 1.3,
        "threshold": 65.0,
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
        lookback = int(arguments.get("lookback", 252))
        volume_multiplier = float(arguments.get("volume_multiplier", 1.3))
        threshold = float(arguments.get("threshold", 65.0))

        closes = context.series.close.dropna()
        highs = context.series.high.reindex(closes.index)
        volume = context.series.volume.reindex(closes.index) if context.series.volume is not None else None

        if closes.shape[0] < max(lookback, 220) or volume is None or volume.isna().all():
            return None, []

        sma50 = sma(closes, 50)
        sma200 = sma(closes, 200)
        last_close = closes.iloc[-1]
        last_sma50 = sma50.iloc[-1]
        last_sma200 = sma200.iloc[-1]

        if np.isnan(last_sma200) or np.isnan(last_sma50):
            return None, []

        recent_high = highs.rolling(window=lookback, min_periods=lookback).max().iloc[-1]
        if np.isnan(recent_high):
            return None, []

        volume_ma_series = vol_ma(volume, 20)
        last_volume_ma = volume_ma_series.iloc[-1]
        last_volume = volume.iloc[-1]

        if np.isnan(last_volume_ma) or last_volume_ma == 0:
            return None, []

        trend_filter = last_sma50 > last_sma200 * 1.01
        near_high = last_close >= recent_high * 0.995
        volume_confirm = last_volume >= last_volume_ma * volume_multiplier

        breakout_strength = np.clip((last_close / recent_high - 1.0) * 400.0, 0.0, 20.0)
        trend_strength = np.clip((last_sma50 / last_sma200 - 1.0) * 500.0, 0.0, 25.0)
        volume_strength = np.clip((last_volume / last_volume_ma - 1.0) * 30.0, 0.0, 20.0)
        base_score = 40.0 + breakout_strength + trend_strength + volume_strength
        rsi_series = rsi(closes, 14)
        last_rsi = float(rsi_series.iloc[-1])
        momentum_bias = np.clip(last_rsi - 50.0, 0.0, 15.0)
        score = float(np.clip(base_score + momentum_bias, 0.0, 100.0))

        metrics = {
            "last_close": float(last_close),
            "recent_high": float(recent_high),
            "volume_ratio": float(last_volume / last_volume_ma),
            "sma50_sma200_ratio": float(last_sma50 / last_sma200),
            "rsi": last_rsi,
            "score": score,
        }

        reasons: List[str] = []
        if trend_filter:
            self._append_reason(reasons, "Uptrend confirmed (SMA50 > SMA200)")
        if near_high:
            self._append_reason(reasons, "Price pushing 52-week highs")
        if volume_confirm:
            self._append_reason(reasons, "Volume expansion above average")
        if last_rsi >= 60:
            self._append_reason(reasons, "Momentum supportive (RSI ≥ 60)")

        signals: List[TradeSignal] = []
        if trend_filter and near_high and volume_confirm:
            confidence = self._confidence_from_score(score, threshold)
            signals.append(
                TradeSignal(
                    symbol=context.symbol,
                    timestamp=closes.index[-1],
                    side="buy",
                    confidence=confidence,
                    reason="Breakout with trend and volume confirmation",
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


class VolumeConfirmedBreakoutScenario(BaseScenario):
    id = "volume_confirmed_breakout"
    name = "Volume Confirmed Breakout"
    description = "Near-high setup backed by strong volume acceleration."
    default_params: Dict[str, float] = {
        "lookback": 252,
        "proximity": 0.02,
        "volume_multiplier": 1.5,
        "threshold": 55.0,
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
        lookback = int(arguments.get("lookback", 252))
        proximity = float(arguments.get("proximity", 0.02))
        volume_multiplier = float(arguments.get("volume_multiplier", 1.5))
        threshold = float(arguments.get("threshold", 55.0))

        closes = context.series.close.dropna()
        highs = context.series.high.reindex(closes.index)
        volume = context.series.volume.reindex(closes.index) if context.series.volume is not None else None

        if closes.shape[0] < lookback or volume is None or volume.isna().all():
            return None, []

        recent_high = highs.rolling(window=lookback, min_periods=lookback).max().iloc[-1]
        if np.isnan(recent_high) or recent_high == 0:
            return None, []

        last_close = closes.iloc[-1]
        distance = (recent_high - last_close) / recent_high
        volume_ma_series = vol_ma(volume, 20)
        last_volume_ma = volume_ma_series.iloc[-1]
        last_volume = volume.iloc[-1]

        if np.isnan(last_volume_ma) or last_volume_ma == 0:
            return None, []

        volume_ratio = last_volume / last_volume_ma
        proximity_score = np.clip((proximity - max(distance, 0.0)) / proximity, 0.0, 1.0)
        volume_score = np.clip(volume_ratio / volume_multiplier, 0.0, 2.0)

        score = float(np.clip(30.0 + proximity_score * 40.0 + volume_score * 30.0, 0.0, 100.0))

        reasons: List[str] = []
        if distance <= proximity:
            self._append_reason(reasons, f"Price within {proximity * 100:.1f}% of 52-week high")
        if volume_ratio >= volume_multiplier:
            self._append_reason(reasons, "Volume surge vs. 20-day average")

        signals: List[TradeSignal] = []
        if distance <= proximity and volume_ratio >= volume_multiplier:
            confidence = self._confidence_from_score(score, threshold)
            signals.append(
                TradeSignal(
                    symbol=context.symbol,
                    timestamp=closes.index[-1],
                    side="buy",
                    confidence=confidence,
                    reason="Volume-backed breakout continuation",
                    scenario_id=self.id,
                )
            )

        metrics = {
            "last_close": float(last_close),
            "recent_high": float(recent_high),
            "distance_to_high": float(distance),
            "volume_ratio": float(volume_ratio),
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


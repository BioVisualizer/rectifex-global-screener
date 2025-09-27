"""Core dataclasses shared across the application."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Literal, Optional

import pandas as pd


@dataclass
class TickerMeta:
    symbol: str
    name: Optional[str] = None
    exchange: Optional[str] = None
    currency: Optional[str] = None
    market_cap: Optional[float] = None


@dataclass
class ScanResult:
    symbol: str
    score: float
    metrics: Dict[str, float]
    reasons: List[str]
    last_price: float
    as_of: datetime
    meta: Optional[TickerMeta] = None


@dataclass
class TradeSignal:
    symbol: str
    timestamp: pd.Timestamp
    side: Literal["buy", "sell"]
    confidence: float
    reason: str
    scenario_id: str

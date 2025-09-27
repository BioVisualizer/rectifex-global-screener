"""Scan registry exporting available strategies."""

from __future__ import annotations

from typing import Dict, Type

from core.scans.base import BaseScenario
from core.scans.contrarian import (
    ClassicOversoldScenario,
    MeanReversionBollingerScenario,
    StochasticOversoldScenario,
)
from core.scans.floor_consolidation import (
    FloorConsolidationQualityScenario,
    FloorConsolidationUniversalScenario,
)
from core.scans.golden_cross import GoldenCrossScenario
from core.scans.lti_compounder import LTICompounderScenario
from core.scans.momentum import MomentumBreakoutScenario, VolumeConfirmedBreakoutScenario
from core.scans.squeeze import VolatilitySqueezeScenario

__all__ = [
    "BaseScenario",
    "ClassicOversoldScenario",
    "MeanReversionBollingerScenario",
    "StochasticOversoldScenario",
    "FloorConsolidationUniversalScenario",
    "FloorConsolidationQualityScenario",
    "MomentumBreakoutScenario",
    "VolumeConfirmedBreakoutScenario",
    "GoldenCrossScenario",
    "VolatilitySqueezeScenario",
    "LTICompounderScenario",
    "SCENARIO_REGISTRY",
]


SCENARIO_REGISTRY: Dict[str, Type[BaseScenario]] = {
    cls.id: cls
    for cls in [
        ClassicOversoldScenario,
        MeanReversionBollingerScenario,
        StochasticOversoldScenario,
        FloorConsolidationUniversalScenario,
        FloorConsolidationQualityScenario,
        MomentumBreakoutScenario,
        VolumeConfirmedBreakoutScenario,
        GoldenCrossScenario,
        VolatilitySqueezeScenario,
        LTICompounderScenario,
    ]
}


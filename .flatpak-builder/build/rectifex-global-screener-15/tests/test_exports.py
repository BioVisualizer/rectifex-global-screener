from __future__ import annotations

from datetime import datetime

import pandas as pd
import pytest

try:
    import PyQt6.QtWidgets  # noqa: F401
except Exception:  # pragma: no cover - environment without Qt libraries
    pytest.skip("PyQt6 is required for export tests", allow_module_level=True)

from app.ui.components.results_table import ResultRow
from app.ui.main_window import MainWindow
from core.models import ScanResult, TickerMeta, TradeSignal


def _result() -> ScanResult:
    return ScanResult(
        symbol="TEST",
        score=87.5,
        metrics={"score_quality": 82.0, "alpha": 1.2},
        reasons=["Momentum confirmed", "Volume expansion"],
        last_price=123.45,
        as_of=datetime(2024, 5, 1, 15, 30),
        meta=TickerMeta(symbol="TEST", name="Test Corp", exchange="NYSE", currency="USD", market_cap=1.5e10),
    )


def _signal() -> TradeSignal:
    return TradeSignal(
        symbol="TEST",
        timestamp=pd.Timestamp("2024-05-01T15:30:00Z"),
        side="buy",
        confidence=0.85,
        reason="LTI compounder profile triggered",
        scenario_id="lti_compounder",
    )


def test_prepare_export_frames_structures_results_and_signals() -> None:
    row = ResultRow(result=_result(), signals=[_signal()])
    results_df, signals_df = MainWindow._prepare_export_frames([row], {"TEST": [_signal()]})

    assert "Symbol" in results_df.columns
    assert "metric_score_quality" in results_df.columns
    assert results_df.loc[0, "Symbol"] == "TEST"
    assert results_df.loc[0, "Top Reasons"] == "Momentum confirmed | Volume expansion"

    assert not signals_df.empty
    assert signals_df.loc[0, "Symbol"] == "TEST"
    assert signals_df.loc[0, "Scenario"] == "lti_compounder"

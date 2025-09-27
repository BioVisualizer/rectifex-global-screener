from __future__ import annotations

from concurrent.futures import Future
from datetime import datetime

import pandas as pd
import pytest

try:
    import PyQt6.QtWidgets  # noqa: F401
except Exception:  # pragma: no cover - environment without Qt libraries
    pytest.skip("PyQt6 is required for UI tests", allow_module_level=True)

from PyQt6 import QtCore

from app.ui.main_window import MainWindow
from core.models import ScanResult, TradeSignal
from core.runners import ScanProgress, ScanSummary


class DummyRunner:
    def __init__(self) -> None:
        # Bypass parent initialisation to avoid threads
        self.started = False
        self.stopped = False
        self.shutdown_called = False
        self._tickers: list[str] = []

    def start(
        self,
        strategy,
        symbols,
        *,
        params=None,
        period="1y",
        on_result=None,
        on_progress=None,
    ):
        self.started = True
        self._tickers = list(symbols)

        future: Future[ScanSummary] = Future()

        def _emit() -> None:
            progress = ScanProgress(total=len(self._tickers), processed=1, skipped=0, errors=0)
            if on_progress is not None:
                on_progress(progress)

            if on_result is not None:
                result = ScanResult(
                    symbol=self._tickers[0],
                    score=72.5,
                    metrics={"final_score": 72.5},
                    reasons=["Momentum breakout"],
                    last_price=123.45,
                    as_of=datetime.utcnow(),
                )
                signal = TradeSignal(
                    symbol=self._tickers[0],
                    timestamp=pd.Timestamp.utcnow(),
                    side="buy",
                    confidence=0.85,
                    reason="Dummy trigger",
                    scenario_id="dummy",
                )
                on_result(result, [signal])

            future.set_result(
                ScanSummary(
                    total=len(self._tickers),
                    processed=len(self._tickers),
                    skipped=0,
                    errors=0,
                    cache_hits=0,
                    cache_misses=len(self._tickers),
                    duration_seconds=0.1,
                )
            )

        QtCore.QTimer.singleShot(0, _emit)
        return future

    def stop(self) -> None:
        self.stopped = True

    def shutdown(self) -> None:
        self.shutdown_called = True


@pytest.mark.usefixtures("qtbot")
def test_main_window_streams_results(qtbot) -> None:
    runner = DummyRunner()
    window = MainWindow(runner=runner)
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)

    window._tickers_edit.setText("AAA, BBB")
    qtbot.mouseClick(window._run_button, QtCore.Qt.MouseButton.LeftButton)

    qtbot.waitUntil(lambda: window._results_model.rowCount() > 0, timeout=2000)
    assert window._results_model.rowCount() == 1
    row = window._results_model.row_at(0)
    assert row is not None
    assert row.result.symbol == "AAA"

    qtbot.waitUntil(lambda: "Completed" in window._progress_label.text(), timeout=2000)
    assert "Cache hits" in window._cache_label.text()

    window.close()
    assert runner.shutdown_called is False  # Runner owned externally


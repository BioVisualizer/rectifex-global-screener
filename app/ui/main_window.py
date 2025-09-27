"""Main window implementation for the Rectifex Global Screener UI."""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

from PyQt6 import QtCore, QtGui, QtWidgets

from core.models import ScanResult, TradeSignal
from core.runners import ScanRunner, ScanSummary
from core.scans import SCENARIO_REGISTRY, BaseScenario

from .components import (
    ChartWidget,
    FiltersDock,
    InsightPanel,
    ResultsTableModel,
    ResultsTableView,
    StrategyListWidget,
)

__all__ = ["MainWindow"]


class _ScanBridge(QtCore.QObject):
    resultReceived = QtCore.pyqtSignal(object, object)  # ScanResult | None, List[TradeSignal]
    progressUpdated = QtCore.pyqtSignal(object)  # ScanProgress
    scanFinished = QtCore.pyqtSignal(object, object)  # ScanSummary | None, Exception | None


class MainWindow(QtWidgets.QMainWindow):
    """Interactive desktop front-end coordinating scans and UI updates."""

    def __init__(self, runner: Optional[ScanRunner] = None, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Rectifex Global Screener")
        self.resize(1280, 840)

        self._runner = runner or ScanRunner(max_workers=4)
        self._owns_runner = runner is None
        self._bridge = _ScanBridge(self)
        self._signal_store: Dict[str, List[TradeSignal]] = {}

        self._bridge.resultReceived.connect(self._handle_stream_result)
        self._bridge.progressUpdated.connect(self._update_progress)
        self._bridge.scanFinished.connect(self._scan_finished)

        self._results_model = ResultsTableModel(self)
        self._results_view = ResultsTableView(self)
        self._results_view.setModel(self._results_model)
        header = self._results_view.horizontalHeader()
        header.setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(True)

        self._chart_widget = ChartWidget(self)
        self._insight_panel = InsightPanel(self)

        self._strategy_sidebar = StrategyListWidget(self)
        self._strategy_sidebar.strategySelected.connect(self._on_sidebar_strategy)

        self._filters_dock = FiltersDock(self)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, self._filters_dock)

        self._progress_label = QtWidgets.QLabel("Idle")
        self._cache_label = QtWidgets.QLabel("Cache: n/a")
        status_bar = self.statusBar()
        status_bar.addPermanentWidget(self._progress_label)
        status_bar.addPermanentWidget(self._cache_label)

        self._setup_toolbar()
        self.setCentralWidget(self._build_layout())

        selection_model = self._results_view.selectionModel()
        if selection_model is not None:
            selection_model.currentChanged.connect(self._on_selection_changed)

        self._populate_strategy_controls()
        self._set_controls_enabled(True)

    # ------------------------------------------------------------------
    # UI construction helpers
    # ------------------------------------------------------------------
    def _setup_toolbar(self) -> None:
        toolbar = QtWidgets.QToolBar("Controls", self)
        toolbar.setMovable(False)
        toolbar.setIconSize(QtCore.QSize(16, 16))
        self.addToolBar(QtCore.Qt.ToolBarArea.TopToolBarArea, toolbar)

        self._strategy_combo = QtWidgets.QComboBox(self)
        self._strategy_combo.currentIndexChanged.connect(self._on_strategy_combo_changed)

        self._period_combo = QtWidgets.QComboBox(self)
        for label, value in self._period_options():
            self._period_combo.addItem(label, value)
        self._period_combo.setCurrentIndex(1)

        self._tickers_edit = QtWidgets.QLineEdit(self)
        self._tickers_edit.setPlaceholderText("Enter comma separated tickers e.g. AAPL, MSFT, GOOGL")
        self._tickers_edit.returnPressed.connect(self._start_scan)

        self._run_button = QtWidgets.QPushButton("Run", self)
        self._run_button.setShortcut(QtGui.QKeySequence("Ctrl+R"))
        self._run_button.clicked.connect(self._start_scan)

        self._stop_button = QtWidgets.QPushButton("Stop", self)
        self._stop_button.setShortcut(QtGui.QKeySequence("Escape"))
        self._stop_button.clicked.connect(self._stop_scan)
        self._stop_button.setEnabled(False)

        toolbar.addWidget(QtWidgets.QLabel("Strategy", self))
        toolbar.addWidget(self._strategy_combo)
        toolbar.addSeparator()
        toolbar.addWidget(QtWidgets.QLabel("Period", self))
        toolbar.addWidget(self._period_combo)
        toolbar.addSeparator()
        toolbar.addWidget(QtWidgets.QLabel("Universe", self))
        toolbar.addWidget(self._tickers_edit)
        toolbar.addSeparator()
        toolbar.addWidget(self._run_button)
        toolbar.addWidget(self._stop_button)

    def _build_layout(self) -> QtWidgets.QWidget:
        central = QtWidgets.QWidget(self)
        layout = QtWidgets.QVBoxLayout(central)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal, central)
        splitter.addWidget(self._strategy_sidebar)

        results_container = QtWidgets.QWidget(splitter)
        results_layout = QtWidgets.QVBoxLayout(results_container)
        results_layout.setContentsMargins(0, 0, 0, 0)
        results_layout.addWidget(self._results_view)
        splitter.addWidget(results_container)

        right_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical, splitter)
        right_splitter.addWidget(self._insight_panel)
        right_splitter.addWidget(self._chart_widget)
        splitter.addWidget(right_splitter)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        layout.addWidget(splitter)

        return central

    def _populate_strategy_controls(self) -> None:
        self._strategy_combo.blockSignals(True)
        self._strategy_combo.clear()
        entries: List[Tuple[str, BaseScenario]] = []
        for identifier, scenario_cls in SCENARIO_REGISTRY.items():
            scenario = scenario_cls()
            entries.append((identifier, scenario))
        entries.sort(key=lambda pair: pair[1].name.lower())

        for identifier, scenario in entries:
            self._strategy_combo.addItem(scenario.name, identifier)

        self._strategy_combo.blockSignals(False)
        if self._strategy_combo.count() > 0:
            self._strategy_combo.setCurrentIndex(0)
            self._strategy_sidebar.select_strategy(self._current_strategy())
            self._filters_dock.set_strategy(self._current_strategy())

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------
    def _on_strategy_combo_changed(self, index: int) -> None:
        identifier = self._current_strategy()
        if identifier is None:
            return
        self._strategy_sidebar.select_strategy(identifier)
        self._filters_dock.set_strategy(identifier)

    def _on_sidebar_strategy(self, identifier: str) -> None:
        combo_index = self._strategy_combo.findData(identifier)
        if combo_index >= 0:
            self._strategy_combo.setCurrentIndex(combo_index)

    def _on_selection_changed(
        self, current: QtCore.QModelIndex, previous: QtCore.QModelIndex
    ) -> None:  # pragma: no cover - trivial glue
        self._update_insight_from_index(current)

    def _start_scan(self) -> None:
        strategy_id = self._current_strategy()
        if strategy_id is None:
            QtWidgets.QMessageBox.warning(self, "Strategy", "Please select a strategy to run.")
            return

        tickers = self._parse_tickers(self._tickers_edit.text())
        if not tickers:
            QtWidgets.QMessageBox.information(
                self,
                "Tickers required",
                "Provide at least one ticker (comma separated) before starting a scan.",
            )
            return

        params = self._filters_dock.parameters()
        period = self._period_combo.currentData()

        self._signal_store.clear()
        self._results_model.clear()
        self._progress_label.setText("Starting…")
        self._cache_label.setText("Cache: pending")
        self._set_controls_enabled(False)
        self._stop_button.setEnabled(True)

        scenario = SCENARIO_REGISTRY[strategy_id]()

        def _on_result(result: Optional[ScanResult], signals: List[TradeSignal]) -> None:
            self._bridge.resultReceived.emit(result, signals)

        def _on_progress(progress) -> None:
            self._bridge.progressUpdated.emit(progress)

        future = self._runner.start(
            scenario,
            tickers,
            params=params,
            period=str(period),
            on_result=_on_result,
            on_progress=_on_progress,
        )

        def _on_done(fut) -> None:
            summary: Optional[ScanSummary] = None
            error: Optional[Exception] = None
            try:
                summary = fut.result()
            except Exception as exc:  # pragma: no cover - defensive
                error = exc
            self._bridge.scanFinished.emit(summary, error)

        future.add_done_callback(_on_done)

    def _stop_scan(self) -> None:
        self._runner.stop()
        self._stop_button.setEnabled(False)
        self._progress_label.setText("Stopping…")

    def _handle_stream_result(self, result: Optional[ScanResult], signals: List[TradeSignal]) -> None:
        if result is not None:
            self._signal_store[result.symbol] = list(signals)
            self._results_model.upsert_row(result, list(signals))
            if self._results_model.rowCount() == 1:
                index = self._results_model.index(0, 0)
                self._results_view.selectRow(0)
                self._update_insight_from_index(index)
        elif signals:
            # Assign signals to their symbol when result omitted (e.g. watch alerts)
            for signal in signals:
                bucket = self._signal_store.setdefault(signal.symbol, [])
                bucket.append(signal)
        self._update_selected_signals()

    def _update_progress(self, progress) -> None:
        self._progress_label.setText(
            f"Processed {progress.processed}/{progress.total} · Skipped {progress.skipped} · Errors {progress.errors}"
        )

    def _scan_finished(self, summary: Optional[ScanSummary], error: Optional[Exception]) -> None:
        self._set_controls_enabled(True)
        self._stop_button.setEnabled(False)
        if error is not None:
            self._progress_label.setText("Scan failed")
            QtWidgets.QMessageBox.critical(self, "Scan failed", str(error))
            return
        if summary is None:
            self._progress_label.setText("Scan cancelled")
            return
        self._progress_label.setText(
            f"Completed in {summary.duration_seconds:.1f}s · Processed {summary.processed}/{summary.total}"
        )
        self._cache_label.setText(
            f"Cache hits {summary.cache_hits} · misses {summary.cache_misses}"
        )

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------
    def _current_strategy(self) -> Optional[str]:
        return self._strategy_combo.currentData()

    @staticmethod
    def _parse_tickers(text: str) -> List[str]:
        entries = [entry.strip().upper() for entry in text.replace("\n", ",").split(",")]
        return [entry for entry in entries if entry]

    def _update_insight_from_index(self, index: QtCore.QModelIndex) -> None:
        if not index.isValid():
            self._insight_panel.show_result(None, [])
            self._chart_widget.set_symbol(None)
            self._chart_widget.display_signals([])
            return

        row = index.row()
        row_data = self._results_model.row_at(row)
        if row_data is None:
            self._insight_panel.show_result(None, [])
            return

        signals = self._signal_store.get(row_data.result.symbol, row_data.signals)
        self._insight_panel.show_result(row_data.result, signals)
        self._chart_widget.set_symbol(row_data.result.symbol)
        self._chart_widget.display_signals(signals)

    def _update_selected_signals(self) -> None:
        index = self._results_view.currentIndex()
        if index.isValid():
            self._update_insight_from_index(index)

    def _set_controls_enabled(self, enabled: bool) -> None:
        self._run_button.setEnabled(enabled)
        self._strategy_combo.setEnabled(enabled)
        self._period_combo.setEnabled(enabled)
        self._tickers_edit.setEnabled(enabled)

    @staticmethod
    def _period_options() -> Sequence[Tuple[str, str]]:
        return (
            ("3 Months", "3mo"),
            ("6 Months", "6mo"),
            ("1 Year", "1y"),
            ("2 Years", "2y"),
            ("5 Years", "5y"),
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def closeEvent(self, event: QtGui.QCloseEvent) -> None:  # pragma: no cover - Qt callback
        try:
            self._runner.stop()
            if self._owns_runner:
                self._runner.shutdown()
        finally:
            super().closeEvent(event)


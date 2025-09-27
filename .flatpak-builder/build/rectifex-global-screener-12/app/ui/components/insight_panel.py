"""Insight panel showing metrics and narrative for the selected result."""

from __future__ import annotations

from typing import Iterable

from PyQt6 import QtCore, QtWidgets

from core.models import ScanResult, TradeSignal

__all__ = ["InsightPanel"]


class InsightPanel(QtWidgets.QWidget):
    """Contextual details about the selected scan result."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._title = QtWidgets.QLabel("Insights")
        self._title.setObjectName("insightTitle")
        self._title.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)

        self._badges = QtWidgets.QLabel()
        self._badges.setWordWrap(True)

        self._reasons = QtWidgets.QTextBrowser()
        self._reasons.setReadOnly(True)
        self._reasons.setPlaceholderText("Select a row to inspect the top reasons and signals.")

        self._signals = QtWidgets.QTextBrowser()
        self._signals.setReadOnly(True)
        self._signals.setPlaceholderText("Trade signals emitted by the selected strategy will appear here.")

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        layout.addWidget(self._title)
        layout.addWidget(self._badges)

        layout.addWidget(QtWidgets.QLabel("Top reasons"))
        layout.addWidget(self._reasons, 1)
        layout.addWidget(QtWidgets.QLabel("Signal history"))
        layout.addWidget(self._signals, 1)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def show_result(self, result: ScanResult | None, signals: Iterable[TradeSignal]) -> None:
        if result is None:
            self._title.setText("Insights")
            self._badges.setText("Select a result to view details.")
            self._reasons.clear()
            self._signals.clear()
            return

        self._title.setText(f"{result.symbol} · {result.score:.1f}")
        self._badges.setText(self._format_badges(result))
        self._reasons.setHtml("<br/>".join(result.reasons) or "No reasons available.")
        self._signals.setHtml(self._format_signals(signals))

    # ------------------------------------------------------------------
    # Formatting helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _format_badges(result: ScanResult) -> str:
        metrics = result.metrics or {}
        tags = []
        for key in ("score_quality", "score_growth", "score_value", "score_finance", "score_dividend"):
            value = metrics.get(key)
            if value is None:
                continue
            tags.append(f"<b>{key.split('_')[-1].title()}</b>: {value:.0f}")
        if not tags:
            return ""
        return " · ".join(tags)

    @staticmethod
    def _format_signals(signals: Iterable[TradeSignal]) -> str:
        lines = []
        for signal in signals:
            timestamp = signal.timestamp.strftime("%Y-%m-%d %H:%M")
            lines.append(
                f"<b>{signal.side.title()}</b> — {timestamp} — Confidence {signal.confidence:.0%}<br/>{signal.reason}"
            )
        if not lines:
            return "No signals for this entry."
        return "<hr/>".join(lines)


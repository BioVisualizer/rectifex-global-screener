"""Placeholder chart widget displaying contextual information."""

from __future__ import annotations

from typing import Iterable, List

from PyQt6 import QtCore, QtWidgets

from core.models import TradeSignal

__all__ = ["ChartWidget"]


class ChartWidget(QtWidgets.QWidget):
    """A lightweight placeholder until the full charting stack is implemented."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._title = QtWidgets.QLabel("Chart preview")
        self._title.setObjectName("chartTitle")
        self._title.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)

        self._summary = QtWidgets.QTextBrowser(self)
        self._summary.setOpenExternalLinks(False)
        self._summary.setReadOnly(True)
        self._summary.setPlaceholderText("Select a result to preview price action and signals.")

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._title)
        layout.addWidget(self._summary)

        self._symbol: str | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def set_symbol(self, symbol: str | None) -> None:
        self._symbol = symbol
        if symbol:
            self._title.setText(f"{symbol} · Chart preview")
        else:
            self._title.setText("Chart preview")

    def display_signals(self, signals: Iterable[TradeSignal]) -> None:
        lines: List[str] = []
        for signal in signals:
            timestamp = signal.timestamp.strftime("%Y-%m-%d %H:%M")
            lines.append(
                f"<b>{signal.side.title()}</b> · {timestamp} · "
                f"Confidence {signal.confidence:.0%} · {signal.reason}"
            )
        if not lines:
            lines = ["No signals generated for the selected entry yet."]
        content = "<br/>".join(lines)
        self._summary.setHtml(content)


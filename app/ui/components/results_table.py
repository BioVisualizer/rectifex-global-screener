"""Streaming results table for displaying scan outputs."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Sequence

from PyQt6 import QtCore, QtGui, QtWidgets

from core.models import ScanResult, TradeSignal

__all__ = ["ResultsTableModel", "ResultsTableView", "ResultRow"]


@dataclass
class ResultRow:
    result: ScanResult
    signals: List[TradeSignal]


class ResultsTableModel(QtCore.QAbstractTableModel):
    """Model storing :class:`ScanResult` entries as they stream in."""

    HEADERS: Sequence[str] = (
        "Symbol",
        "Score",
        "Last Price",
        "Signals",
        "Top Reasons",
        "As of",
    )

    def __init__(self, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self._rows: List[ResultRow] = []
        self._index: Dict[str, int] = {}

    # ------------------------------------------------------------------
    # Qt Model interface
    # ------------------------------------------------------------------
    def rowCount(self, parent: QtCore.QModelIndex | QtCore.QPersistentModelIndex = QtCore.QModelIndex()) -> int:  # type: ignore[override]
        if parent.isValid():
            return 0
        return len(self._rows)

    def columnCount(self, parent: QtCore.QModelIndex | QtCore.QPersistentModelIndex = QtCore.QModelIndex()) -> int:  # type: ignore[override]
        if parent.isValid():
            return 0
        return len(self.HEADERS)

    def headerData(self, section: int, orientation: QtCore.Qt.Orientation, role: int = QtCore.Qt.ItemDataRole.DisplayRole):  # type: ignore[override]
        if role != QtCore.Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == QtCore.Qt.Orientation.Horizontal:
            try:
                return self.HEADERS[section]
            except IndexError:
                return None
        return str(section + 1)

    def data(self, index: QtCore.QModelIndex, role: int = QtCore.Qt.ItemDataRole.DisplayRole):  # type: ignore[override]
        if not index.isValid():
            return None

        row = index.row()
        if row < 0 or row >= len(self._rows):
            return None

        result_row = self._rows[row]
        result = result_row.result

        if role == QtCore.Qt.ItemDataRole.DisplayRole:
            column = index.column()
            if column == 0:
                return result.symbol
            if column == 1:
                return f"{result.score:.1f}"
            if column == 2:
                return f"{result.last_price:.2f}"
            if column == 3:
                counts = _signal_counts(result_row.signals)
                return ", ".join(
                    f"{side.title()}: {count}"
                    for side, count in counts.items()
                    if count > 0
                ) or "—"
            if column == 4:
                return "; ".join(result.reasons)
            if column == 5:
                return result.as_of.strftime("%Y-%m-%d %H:%M")

        if role == QtCore.Qt.ItemDataRole.ToolTipRole:
            return "\n".join(result.reasons)

        if role == QtCore.Qt.ItemDataRole.TextAlignmentRole:
            if index.column() in {1, 2, 3}:
                return int(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)

        if role == QtCore.Qt.ItemDataRole.FontRole and index.column() == 0:
            font = QtGui.QFont()
            font.setBold(True)
            return font

        return None

    # ------------------------------------------------------------------
    # Custom API
    # ------------------------------------------------------------------
    def clear(self) -> None:
        if not self._rows:
            return
        self.beginResetModel()
        self._rows.clear()
        self._index.clear()
        self.endResetModel()

    def upsert_row(self, result: ScanResult, signals: List[TradeSignal]) -> None:
        """Insert or update the row matching *result.symbol*."""

        row_index = self._index.get(result.symbol)
        if row_index is None:
            row_index = len(self._rows)
            self.beginInsertRows(QtCore.QModelIndex(), row_index, row_index)
            self._rows.append(ResultRow(result=result, signals=signals))
            self._index[result.symbol] = row_index
            self.endInsertRows()
            return

        self._rows[row_index] = ResultRow(result=result, signals=signals)
        top_left = self.index(row_index, 0)
        bottom_right = self.index(row_index, self.columnCount() - 1)
        self.dataChanged.emit(top_left, bottom_right, [])

    def row_at(self, row: int) -> ResultRow | None:
        if 0 <= row < len(self._rows):
            return self._rows[row]
        return None

    def rows(self) -> List[ResultRow]:
        return list(self._rows)


class ResultsTableView(QtWidgets.QTableView):
    """Configured table view for presenting scan results."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.setAlternatingRowColors(True)
        self.setSortingEnabled(True)
        self.horizontalHeader().setStretchLastSection(True)
        self.verticalHeader().setVisible(False)
        self.setWordWrap(False)


def _signal_counts(signals: Sequence[TradeSignal]) -> Dict[str, int]:
    counts: Dict[str, int] = defaultdict(int)
    for signal in signals:
        counts[signal.side] += 1
    return counts


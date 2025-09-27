"""Strategy browser widget used to explore available scan scenarios."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

from PyQt6 import QtCore, QtWidgets

from core.scans import SCENARIO_REGISTRY, BaseScenario

__all__ = ["StrategyListWidget", "StrategyInfo"]


@dataclass(frozen=True)
class StrategyInfo:
    """Presentation data describing a scan strategy."""

    identifier: str
    name: str
    description: str


class StrategyListWidget(QtWidgets.QWidget):
    """Sidebar widget listing the registered scan strategies."""

    strategySelected = QtCore.pyqtSignal(str)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._items: Dict[str, StrategyInfo] = self._load_strategies()

        self._search = QtWidgets.QLineEdit(self)
        self._search.setPlaceholderText("Search strategies…")
        self._search.textChanged.connect(self._apply_filter)

        self._list = QtWidgets.QListWidget(self)
        self._list.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self._list.itemSelectionChanged.connect(self._on_selection_changed)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._search)
        layout.addWidget(self._list)

        self._populate()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def select_strategy(self, identifier: str) -> None:
        """Select the strategy matching *identifier* if present."""

        for index in range(self._list.count()):
            item = self._list.item(index)
            if item.data(QtCore.Qt.ItemDataRole.UserRole) == identifier:
                self._list.setCurrentRow(index)
                self._ensure_visible(index)
                return

    def current_strategy(self) -> str | None:
        item = self._list.currentItem()
        if item is None:
            return None
        return item.data(QtCore.Qt.ItemDataRole.UserRole)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _populate(self) -> None:
        self._list.clear()
        for info in self._items.values():
            item = QtWidgets.QListWidgetItem(info.name)
            item.setData(QtCore.Qt.ItemDataRole.UserRole, info.identifier)
            item.setToolTip(info.description)
            item.setData(QtCore.Qt.ItemDataRole.StatusTipRole, info.description)
            self._list.addItem(item)
        if self._list.count() > 0:
            self._list.setCurrentRow(0)

    def _apply_filter(self, query: str) -> None:
        query_normalised = query.strip().lower()
        for index in range(self._list.count()):
            item = self._list.item(index)
            info = self._items[item.data(QtCore.Qt.ItemDataRole.UserRole)]
            visible = True
            if query_normalised:
                haystack = f"{info.name} {info.description}".lower()
                visible = query_normalised in haystack
            item.setHidden(not visible)

    def _on_selection_changed(self) -> None:
        identifier = self.current_strategy()
        if identifier is not None:
            self.strategySelected.emit(identifier)

    def _ensure_visible(self, index: int) -> None:
        item = self._list.item(index)
        if item is not None:
            self._list.scrollToItem(item)

    @staticmethod
    def _load_strategies() -> Dict[str, StrategyInfo]:
        strategies: List[Tuple[str, StrategyInfo]] = []
        for identifier, scenario_cls in SCENARIO_REGISTRY.items():
            scenario: BaseScenario = scenario_cls()
            strategies.append(
                (
                    identifier,
                    StrategyInfo(
                        identifier=identifier,
                        name=getattr(scenario, "name", identifier.title()),
                        description=getattr(scenario, "description", ""),
                    ),
                )
            )
        strategies.sort(key=lambda item: item[1].name.lower())
        return dict(strategies)


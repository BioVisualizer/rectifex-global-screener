"""Dockable filters and parameter configuration panel."""

from __future__ import annotations

from typing import Dict

from PyQt6 import QtCore, QtWidgets

from core.config import DEFAULT_CONFIG

__all__ = ["FiltersDock"]


class FiltersDock(QtWidgets.QDockWidget):
    """Provides parameter forms for the currently selected scan strategy."""

    parametersChanged = QtCore.pyqtSignal(dict)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__("Filters", parent)
        self.setObjectName("FiltersDock")
        self.setAllowedAreas(
            QtCore.Qt.DockWidgetArea.RightDockWidgetArea | QtCore.Qt.DockWidgetArea.LeftDockWidgetArea
        )

        self._stack = QtWidgets.QStackedWidget(self)
        self.setWidget(self._stack)

        self._forms: Dict[str, QtWidgets.QWidget] = {}
        self._build_default_form()
        self._build_lti_form()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def set_strategy(self, identifier: str) -> None:
        widget = self._forms.get(identifier)
        if widget is None:
            widget = self._forms["default"]
        self._stack.setCurrentWidget(widget)

    def parameters(self) -> Dict[str, object]:
        current = self._stack.currentWidget()
        if current is None:
            return {}
        getter = getattr(current, "parameters", None)
        if callable(getter):
            return getter()
        return {}

    # ------------------------------------------------------------------
    # Form builders
    # ------------------------------------------------------------------
    def _build_default_form(self) -> None:
        widget = _FormContainer("No additional parameters for this strategy.")
        self._forms["default"] = widget
        self._stack.addWidget(widget)

    def _build_lti_form(self) -> None:
        widget = _LTICompounderForm(self)
        self._forms["lti_compounder"] = widget
        self._stack.addWidget(widget)


class _FormContainer(QtWidgets.QWidget):
    def __init__(self, message: str, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        label = QtWidgets.QLabel(message, self)
        label.setWordWrap(True)
        layout.addWidget(label)
        layout.addStretch(1)

    def parameters(self) -> Dict[str, object]:
        return {}


class _LTICompounderForm(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QtWidgets.QFormLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self._profile_combo = QtWidgets.QComboBox(self)
        profiles = sorted(DEFAULT_CONFIG.profiles.lti_profiles.keys())
        for profile in profiles:
            self._profile_combo.addItem(profile.title(), profile)

        self._threshold_spin = QtWidgets.QDoubleSpinBox(self)
        self._threshold_spin.setRange(0.0, 100.0)
        self._threshold_spin.setDecimals(1)
        self._threshold_spin.setSingleStep(1.0)
        self._threshold_spin.setValue(60.0)

        layout.addRow("Profile", self._profile_combo)
        layout.addRow("Score threshold", self._threshold_spin)
        layout.addItem(QtWidgets.QSpacerItem(0, 0, QtWidgets.QSizePolicy.Policy.Minimum, QtWidgets.QSizePolicy.Policy.Expanding))

    def parameters(self) -> Dict[str, object]:
        return {
            "profile": self._profile_combo.currentData(),
            "threshold": float(self._threshold_spin.value()),
        }


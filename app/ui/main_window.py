"""Initial placeholder implementation of the main application window."""

from __future__ import annotations

from PyQt6 import QtCore, QtWidgets


class MainWindow(QtWidgets.QMainWindow):
    """Skeleton main window used during early development stages."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Rectifex Global Screener")
        self.resize(1024, 768)

        label = QtWidgets.QLabel(
            "Rectifex Global Screener\nUI implementation is in progress.", self
        )
        label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        central = QtWidgets.QWidget(self)
        layout = QtWidgets.QVBoxLayout(central)
        layout.addWidget(label)
        self.setCentralWidget(central)

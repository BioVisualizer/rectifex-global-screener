"""Entry point for the Rectifex Global Screener application."""

from __future__ import annotations

import logging
import sys

try:
    from PyQt6 import QtWidgets
except ImportError as exc:  # pragma: no cover - executed only when PyQt6 missing
    raise SystemExit(
        "PyQt6 is required to launch the Rectifex Global Screener UI. "
        "Install the dependencies listed in requirements.txt and try again."
    ) from exc

from app.ui.main_window import MainWindow


logging.basicConfig(level=logging.INFO)


def main() -> int:
    """Launch the Qt application."""
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

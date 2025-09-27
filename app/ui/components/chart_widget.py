"""Matplotlib-powered chart widget visualising price action and signals."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional

import numpy as np
import pandas as pd
from matplotlib import dates as mdates
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from mplfinance.original_flavor import candlestick_ohlc
from PyQt6 import QtCore, QtWidgets

from core.indicators import macd, rsi, sma
from core.models import TradeSignal

__all__ = ["ChartWidget"]


@dataclass(frozen=True)
class _ArrowConfig:
    color: str
    marker: str
    offset: float


class ChartWidget(QtWidgets.QWidget):
    """Embed a candlestick chart with indicator overlays and signal arrows."""

    _ARROWS = {
        "buy": _ArrowConfig(color="#10B981", marker="^", offset=-0.0125),
        "sell": _ArrowConfig(color="#EF4444", marker="v", offset=0.0125),
    }

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._title = QtWidgets.QLabel("Chart preview")
        self._title.setObjectName("chartTitle")
        self._title.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)

        self._message = QtWidgets.QLabel("Select a result to preview price action and signals.")
        self._message.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._message.setWordWrap(True)

        self._figure = Figure(figsize=(7.2, 5.0))
        self._canvas = FigureCanvasQTAgg(self._figure)

        self._stack = QtWidgets.QStackedLayout()
        self._stack.addWidget(self._message)
        self._stack.addWidget(self._canvas)

        container = QtWidgets.QWidget(self)
        container.setLayout(self._stack)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._title)
        layout.addWidget(container, 1)

        self._symbol: Optional[str] = None
        self._price_data: Optional[pd.DataFrame] = None
        self._signals: List[TradeSignal] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def set_symbol(self, symbol: str | None) -> None:
        self._symbol = symbol
        if symbol:
            self._title.setText(f"{symbol} · Chart preview")
        else:
            self._title.setText("Chart preview")
            self.clear()

    def set_loading(self, message: str = "Loading chart…") -> None:
        self._stack.setCurrentWidget(self._message)
        self._message.setText(message)

    def set_error(self, message: str) -> None:
        self._stack.setCurrentWidget(self._message)
        self._message.setText(message)

    def set_price_data(self, price_df: Optional[pd.DataFrame]) -> None:
        if price_df is None or price_df.empty:
            self._price_data = None
            self._stack.setCurrentWidget(self._message)
            self._message.setText("No price data available for the selected symbol.")
            return
        cleaned = price_df.copy()
        cleaned = cleaned.dropna(subset=["Open", "High", "Low", "Close"])
        if cleaned.empty:
            self._price_data = None
            self._stack.setCurrentWidget(self._message)
            self._message.setText("Price history is incomplete for chart rendering.")
            return
        if not isinstance(cleaned.index, pd.DatetimeIndex):
            cleaned.index = pd.DatetimeIndex(cleaned.index)
        cleaned.index = cleaned.index.tz_localize(None)
        self._price_data = cleaned
        self._render_chart()

    def display_signals(self, signals: Iterable[TradeSignal]) -> None:
        self._signals = list(signals)
        if self._price_data is not None:
            self._render_chart()

    def clear(self) -> None:
        self._price_data = None
        self._signals.clear()
        self._figure.clear()
        self._stack.setCurrentWidget(self._message)
        self._message.setText("Select a result to preview price action and signals.")
        self._canvas.draw_idle()

    # ------------------------------------------------------------------
    # Internal rendering helpers
    # ------------------------------------------------------------------
    def _render_chart(self) -> None:
        if self._price_data is None or self._price_data.empty:
            self._stack.setCurrentWidget(self._message)
            return

        price_df = self._price_data
        dates = mdates.date2num(price_df.index.to_pydatetime())

        self._figure.clear()
        grid = self._figure.add_gridspec(7, 1, hspace=0.05)
        ax_price = self._figure.add_subplot(grid[:3, 0])
        ax_volume = self._figure.add_subplot(grid[3, 0], sharex=ax_price)
        ax_rsi = self._figure.add_subplot(grid[4, 0], sharex=ax_price)
        ax_macd = self._figure.add_subplot(grid[5:, 0], sharex=ax_price)

        self._draw_price(ax_price, price_df, dates)
        self._draw_volume(ax_volume, price_df, dates)
        self._draw_rsi(ax_rsi, price_df["Close"], dates)
        self._draw_macd(ax_macd, price_df["Close"], dates)
        self._overlay_signals(ax_price, price_df, dates)

        ax_macd.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
        for label in ax_macd.get_xticklabels():
            label.setRotation(40)
            label.setHorizontalAlignment("right")

        for axis in (ax_price, ax_volume, ax_rsi, ax_macd):
            axis.grid(True, which="major", linestyle="--", alpha=0.25)

        self._stack.setCurrentWidget(self._canvas)
        self._figure.tight_layout()
        self._canvas.draw_idle()

    def _draw_price(self, axis, price_df: pd.DataFrame, dates: np.ndarray) -> None:
        ohlc = np.column_stack(
            [
                dates,
                price_df["Open"].to_numpy(),
                price_df["High"].to_numpy(),
                price_df["Low"].to_numpy(),
                price_df["Close"].to_numpy(),
            ]
        )
        candlestick_ohlc(
            axis,
            ohlc,
            width=0.6,
            colorup="#10B981",
            colordown="#EF4444",
            alpha=0.9,
        )
        close = price_df["Close"]
        sma50 = sma(close, 50)
        sma200 = sma(close, 200)
        axis.plot(dates, sma50, label="SMA 50", color="#60A5FA", linewidth=1.2)
        axis.plot(dates, sma200, label="SMA 200", color="#A855F7", linewidth=1.2)
        axis.set_ylabel("Price")
        axis.legend(loc="upper left", fontsize=8)

    def _draw_volume(self, axis, price_df: pd.DataFrame, dates: np.ndarray) -> None:
        colors = np.where(price_df["Close"] >= price_df["Open"], "#10B981", "#EF4444")
        axis.bar(dates, price_df["Volume"].to_numpy(), color=colors, width=0.6, alpha=0.6)
        axis.set_ylabel("Volume")

    def _draw_rsi(self, axis, close: pd.Series, dates: np.ndarray) -> None:
        rsi_values = rsi(close, 14)
        axis.plot(dates, rsi_values, color="#6366F1", linewidth=1.0)
        axis.axhline(70, color="#F97316", linestyle="--", linewidth=0.8)
        axis.axhline(30, color="#F97316", linestyle="--", linewidth=0.8)
        axis.set_ylim(0, 100)
        axis.set_ylabel("RSI")

    def _draw_macd(self, axis, close: pd.Series, dates: np.ndarray) -> None:
        macd_df = macd(close)
        axis.plot(dates, macd_df["macd"], color="#F59E0B", linewidth=1.0, label="MACD")
        axis.plot(dates, macd_df["signal"], color="#2563EB", linewidth=1.0, label="Signal")
        hist_colors = np.where(macd_df["hist"] >= 0, "#10B981", "#EF4444")
        axis.bar(dates, macd_df["hist"], color=hist_colors, alpha=0.3, width=0.6)
        axis.set_ylabel("MACD")
        axis.legend(loc="upper left", fontsize=8)

    def _overlay_signals(self, axis, price_df: pd.DataFrame, dates: np.ndarray) -> None:
        if not self._signals:
            return

        index = price_df.index
        for signal in self._signals:
            config = self._ARROWS.get(signal.side)
            if config is None:
                continue
            try:
                loc = index.get_loc(signal.timestamp)
                if isinstance(loc, slice):
                    idx = loc.start
                else:
                    idx = loc
            except KeyError:
                locator = index.get_indexer([signal.timestamp], method="nearest")
                idx = locator[0] if locator.size and locator[0] >= 0 else None
            if idx is None or idx < 0 or idx >= len(index):
                continue
            row = price_df.iloc[idx]
            base_price = row["Low"] if signal.side == "buy" else row["High"]
            y_value = base_price * (1 + config.offset)
            size = 80 * (0.6 + 0.4 * float(signal.confidence))
            axis.scatter(
                [dates[idx]],
                [y_value],
                marker=config.marker,
                color=config.color,
                s=size,
                alpha=0.75 if signal.confidence >= 0.7 else 0.5,
                edgecolors="none",
                zorder=5,
            )


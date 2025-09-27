# Rectifex Global Screener

Rectifex Global Screener is a Linux-first desktop application that blends systematic
technical signals with fundamentals sourced from Yahoo Finance to surface
long-term compounders, breakout candidates, squeezes, and contrarian rebounds.
The PyQt6 interface streams results from background scan workers, shows
contextual insights, renders interactive candlestick charts with timing signals,
and exports findings for further analysis.

![Rectifex Global Screener main window placeholder](docs/images/screenshot-placeholder.png)
*Figure: Placeholder illustration of the three-pane screener layout.*

## Feature Highlights

- **Strategy catalog** covering momentum, contrarian, volatility squeeze, floor
  consolidation, golden cross, and the bespoke LTI Compounder (profiled
  Quality/Growth/Income blends).
- **Resilient market data pipeline** that caches price history to Parquet,
  indexes metadata in SQLite, retries yfinance downloads with exponential
  backoff, and transparently falls back to stale cache entries when necessary.
- **Universe loader & cache** that pulls NASDAQ/NYSE/S&P500 lists on demand,
  stores them as CSV under `~/.cache/com.rectifex.GlobalScreener/universe`, and
  automatically runs scans against `us-all` when no manual tickers are
  provided.
- **Streaming UI** backed by a thread-pooled `ScanRunner`. Results arrive in a
  virtualized table while insights, signal history, and chart overlays update
  instantly without blocking the main event loop.
- **Rich charting widget** powered by Matplotlib. Candlesticks include SMA50/200,
  volume bars, RSI, MACD histogram, and color-coded buy/sell arrows whose size
  and opacity respect signal confidence.
- **Exports** to CSV or Excel (with an optional `Signals` sheet) that flatten
  the result metrics, textual reasons, and generated trade signals.
- **Command-line interface** mirroring the UI scans for batch workflows:
  `rectifex-cli --strategy lti_compounder --profile balanced --tickers tickers.txt --period 5y --out results.json --include-signals`.

## Repository Layout

```
rectifex-global-screener/
├─ app/                    # PyQt6 application entry points and widgets
├─ core/                   # Business logic (data fetchers, scoring, scans)
├─ cli/                    # CLI entry point
├─ packaging/flatpak/      # Flatpak manifest and launch scripts
├─ tests/                  # Pytest suite for core modules and UI smoke tests
└─ requirements.txt        # Pinned dependency versions
```

## Development Setup

1. **Clone the repository and create a virtual environment**

   ```bash
   git clone https://github.com/your-org/rectifex-global-screener.git
   cd rectifex-global-screener
   python3.11 -m venv .venv
   source .venv/bin/activate
   ```

2. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

3. **Run the desktop UI**

   ```bash
   python -m app
   ```

4. **Execute the CLI**

   You can provide a ticker file or let the CLI load a universe automatically:

   ```bash
   python -m cli.rectifex_cli scan \
     --strategy lti_compounder \
     --profile balanced \
     --universe us-all \
     --max-tickers 250 \
     --refresh-days 7 \
     --period 5y \
     --out results.json \
     --include-signals
   ```

   When `--tickers` is omitted the selected universe (default `us-all`) is
   cached locally and reused until the refresh window expires.

5. **Run tests and linters**

   ```bash
   pytest
   ruff check .
   ```

## Flatpak Packaging

The Flatpak manifest installs pinned dependencies, copies the project into the
application prefix, and exposes launch scripts for both the UI and CLI.

```bash
flatpak-builder --user --install --force-clean build-dir packaging/flatpak/manifest.json
flatpak run com.rectifex.GlobalScreener           # Launch GUI
flatpak run --command=rectifex-cli com.rectifex.GlobalScreener --help  # Invoke CLI
```

## Data Source & Reliability Notes

- All market data originates from `yfinance`. Batch downloads run first, with
  per-symbol fallbacks when Yahoo throttles requests.
- Cached Parquet files persist for seven days by default. The TTL is
  configurable through `core/config.py`.
- When a ticker lacks fundamentals or price history, the scan logs the issue,
  marks the symbol as skipped, and continues processing the rest of the
  universe.

## Ticker Universes & Custom Lists

- Leaving the ticker field empty in the UI automatically loads the selected
  universe (default: `us-all`) and displays a status hint before the scan
  starts.
- The toolbar exposes dropdowns for the universe, a maximum ticker cap, and the
  refresh interval in days. The same options are available via CLI flags.
- Cached universes are written to
  `~/.cache/com.rectifex.GlobalScreener/universe/<name>.csv`. Populate
  `custom.csv` in that directory to maintain your own set of symbols.

## Disclaimer

Rectifex Global Screener is provided for educational and informational purposes
only. It does not constitute financial, investment, tax, or legal advice.
Perform independent research and consult licensed professionals before making
investment decisions.

## License

This project is released under the [MIT License](LICENSE).

# Rectifex Global Screener

This repository contains the in-progress implementation of the Rectifex Global Screener
application. The project targets Linux desktop environments (with Flatpak packaging) and
provides a configurable stock screening experience built on top of **yfinance**.

## Project Status

The implementation now includes the complete scan catalogue for the screener. Momentum,
contrarian, squeeze, floor consolidation, golden cross, and the new LTI Compounder strategies are
available with deterministic signal generation and scoring. Each scan operates on the shared data
fetching/caching infrastructure and is covered by unit tests exercising representative scenarios.
UI components remain placeholders that will be fleshed out in subsequent milestones.

## Getting Started

1. Create and activate a Python 3.11 virtual environment.
2. Install the pinned dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. (Optional) Launch the placeholder UI to verify the environment:

   ```bash
   python -m app
   ```

   A minimal PyQt6 window should appear noting that the full UI is under construction.

## Development Utilities

A `debug_fetch.py` helper is included to validate batch fetching logic without touching the main
application:

```bash
python debug_fetch.py AAPL MSFT --period 6mo --use-cache
```

The script prints a JSON summary of the downloads and optionally writes to the on-disk cache.

## Testing

Pytest-based unit tests are located in the `tests/` directory. Run them with:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest
```

The environment flag disables optional Qt-related plugins that require system GUI libraries.
The current suite exercises the caching layer, batch fetcher (with network access mocked), and
technical indicator implementations.

## Project Structure

```
rectifex-global-screener/
├─ app/                    # PyQt6 application entry point and UI modules
├─ core/                   # Business logic (config, cache, data access, etc.)
├─ tests/                  # Unit and integration tests
├─ debug_fetch.py          # Development helper for manual data checks
└─ requirements.txt        # Pinned dependency list
```

Further directories (e.g. CLI, packaging, additional scans) will be added as the roadmap
progresses.

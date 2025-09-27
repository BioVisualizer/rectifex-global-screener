# Rectifex Global Screener

## Project Overview
Rectifex Global Screener is a desktop research companion that helps investors and analysts surface potential equity opportunities across global markets. The application blends technical indicators with fundamental ratios to filter large universes of stocks and highlight candidates worth deeper due diligence. Built with Python and PyQt6, the interface is packaged as a Flatpak for seamless deployment on modern Linux distributions.

## Screenshot Placeholder
![Rectifex Global Screener main window placeholder](docs/images/screenshot-placeholder.png)
*Figure: Placeholder for the Rectifex Global Screener dashboard.*

## Key Features
- **Modern three-pane layout** that dedicates space for strategy controls, live scan results, and detailed instrument drill-downs.
- **Strategy selection** enabling users to mix-and-match technical and fundamental criteria on demand.
- **Data caching** that persists recent downloads to minimize redundant network calls and accelerate repeated scans.
- **Exportable results table** supporting CSV export for archival, presentation, or advanced spreadsheet analysis.

## Scanning Scenarios
### Momentum & Trend Continuation
- **RSI Breakout**: Flags tickers where the Relative Strength Index crosses above 55, signaling renewed bullish momentum.
- **Golden Cross Radar**: Identifies securities whose 50-day simple moving average has crossed above the 200-day average within the last 10 sessions.
- **ADX Strength Filter**: Highlights assets with Average Directional Index readings above 25, confirming trend persistence.

### Mean Reversion
- **Bollinger Band Squeeze**: Detects instruments trading outside the lower band following a squeeze event, suggesting a rebound setup.
- **Stochastic Reset**: Surfaces equities with %K rising through %D from oversold conditions.

### Value & Quality
- **Low P/E Outliers**: Screens for companies with price-to-earnings ratios below industry medians and positive earnings-per-share trends.
- **High ROE Leaders**: Targets firms delivering above 15% return on equity while maintaining manageable debt-to-equity ratios.
- **Dividend Durability**: Filters for businesses with five-year dividend growth streaks and payout ratios under 70%.

### Risk Management & Liquidity
- **ATR Volatility Guard**: Flags tickers whose Average True Range exceeds 4% of price, indicating elevated risk conditions.
- **Volume Confirmation**: Requires 20-day average volume above 1M shares to ensure adequate liquidity for position sizing.

## Installation Instructions
The application ships as a Flatpak for Debian-based systems. Follow the steps below to set up and launch the screener.

1. **Install prerequisites**:
   ```bash
   sudo apt update
   sudo apt install flatpak flatpak-builder python3 python3-pip git
   ```
2. **Enable Flathub (if not already configured)**:
   ```bash
   sudo flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
   ```
3. **Clone the repository and enter the project directory**:
   ```bash
   git clone https://github.com/your-org/rectifex-global-screener.git
   cd rectifex-global-screener
   ```
4. **Build the Flatpak bundle**:
   ```bash
   flatpak-builder --user --install --force-clean build-dir packaging/io.rectifex.GlobalScreener.json
   ```
5. **Install the application locally**:
   ```bash
   flatpak install --user io.rectifex.GlobalScreener
   ```
6. **Launch the screener**:
   ```bash
   flatpak run io.rectifex.GlobalScreener
   ```

## Ticker Management
Create customized watchlists by adding tickers into the Watchlist Manager panel. Lists can be organized by sector, geography, or strategy. Enter tickers using their full exchange-qualified symbols, such as `AAPL` for NASDAQ listings, `SAP.DE` for Xetra, or `6758.T` for the Tokyo Stock Exchange. Multiple watchlists can be saved, renamed, or deleted, allowing quick pivots between regional or thematic universes.

## Data Availability Notice
Rectifex Global Screener sources quotes, fundamentals, and historical prices from Yahoo Finance. While coverage is broad, some thinly traded small-cap or frontier-market listings may lack intraday updates, delisted history, or complete financial statements. For unsupported instruments, the scan will omit those entries and log a warning in the activity console.

## Explanation of Scan Results
Each row in the results table includes key financial and technical metrics to aid interpretation:
- **ROE (Return on Equity)**: Net income divided by shareholder equity, measuring capital efficiency.
- **P/E (Price-to-Earnings Ratio)**: Share price relative to earnings per share, indicating valuation versus profitability.
- **EPS Growth**: Compound annual growth rate of earnings per share across the last three fiscal years.
- **Debt-to-Equity**: Total liabilities divided by shareholder equity, assessing leverage risk.
- **Dividend Yield**: Annual dividend per share compared to current price.
- **RSI**: Momentum oscillator showing the speed and change of price movements.
- **ATR**: Average True Range, quantifying recent volatility.

## Disclaimer
Rectifex Global Screener is provided for educational and informational purposes only. It does not constitute financial, investment, tax, or legal advice. Users should conduct independent research and consult licensed professionals before making investment decisions.

## License
This project is released under the [MIT License](LICENSE).

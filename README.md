# Binance API Consumer & Market Terminal

A modular, production-ready cryptocurrency market terminal and consumer in Python. It features an interactive CLI menu with preset crypto pairs, intervals, modern multi-panel Plotly browser charts, terminal market dashboards, live WebSocket trade streams, and safe order execution.

---

## Key Features

- **Interactive CLI User Menu**: Interactive navigation with quick preset selections for popular cryptocurrencies (`BTCUSDT`, `ETHUSDT`, `SOLUSDT`, `BNBUSDT`, etc.), timeframes (`1m`, `5m`, `15m`, `1h`, `4h`, `1d`), and candle history counts.
- **Modern Multi-Panel Interactive Charts**: Professional dark-themed financial charts generated with Plotly:
  - **Panel 1**: Candlesticks + Bollinger Bands (20,2) + SMA 7 / 25 / 99.
  - **Panel 2**: Volume bars colored by bullish/bearish candle direction + 20-period Volume MA.
  - **Panel 3**: Relative Strength Index (RSI 14) oscillator with overbought (70) and oversold (30) bands.
- **Terminal Market Dashboard**: High-density snapshot with 24h high/low, volatility, volume, SMA trend signal, RSI status, recent candle table, and ASCII price curve.
- **Real-Time Trade Streaming**: High-performance asynchronous WebSocket stream using `BinanceSocketManager`.
- **Safe Order Validation**: Place test limit orders without risking capital using Binance's `create_test_order`.
- **Safe Environment & Secrets Management**: Configured via `.env` with automatic testnet switching and `.gitignore` safeguards.
- **Powered by `uv`**: Ultra-fast environment and dependency management.

---

## Quick Start

### 1. Set Up Environment & Dependencies

```powershell
# Create virtual environment with uv
uv venv .venv

# Install dependencies into .venv
uv pip install -r requirements.txt
```

*(Alternatively, standard `python -m venv .venv` and `pip install -r requirements.txt` work as well)*

---

### 2. Configure API Credentials (Optional)
If you want to interact with private account endpoints or the Binance Testnet:

1. Copy `.env.example` to `.env`:
   ```powershell
   Copy-Item .env.example .env
   ```
2. Edit `.env` with your API credentials:
   ```ini
   BINANCE_API_KEY=your_api_key_here
   BINANCE_API_SECRET=your_api_secret_here
   BINANCE_TESTNET=false
   BINANCE_TLD=com
   ```

> [!NOTE]
> Public market data, charting, and WebSocket streaming work out-of-the-box without API keys.

---

## Usage

### Interactive CLI Menu Mode (Default)
Launch the interactive terminal menu:
```powershell
uv run python binance_consumer.py
```

You will be presented with an interactive menu:
```
⚡ BINANCE API CONSUMER & MARKET TERMINAL ⚡
Network: Mainnet | TLD: com | Auth: Public Mode

Select an action:
  1) 📊 Interactive Browser Chart (Plotly HTML + RSI + Bollinger)
  2) 📈 Terminal Market Summary & ASCII Price Action
  3) ⚡ Live WebSocket Real-Time Trade Stream
  4) 🔍 Quick Spot Ticker Price Lookup
  5) 💰 Account Balances & Portfolio Summary
  6) 🧪 Place Safe Test Limit Order
  7) 🚪 Exit
```

---

### Direct CLI Commands (Batch & Automation Mode)

You can also run specific actions directly via command line arguments:

#### 1. Generate & Open Interactive Chart
```powershell
uv run python binance_consumer.py --chart -s BTCUSDT -i 1h -l 60
uv run python binance_consumer.py --chart -s SOLUSDT -i 15m -l 100
```

#### 2. Print Terminal Market Dashboard
```powershell
uv run python binance_consumer.py --summary -s ETHUSDT -i 1h -l 40
```

#### 3. Stream Live Trades in Real-Time
```powershell
uv run python binance_consumer.py --stream -s SOLUSDT
```

#### 4. Quick Ticker Price Lookup
```powershell
uv run python binance_consumer.py --ticker -s BNBUSDT
```

#### 5. Check Account Balances
```powershell
uv run python binance_consumer.py --balances
```

---

## Supported Presets & Custom Values

| Option | Popular Presets | Custom Support |
| :--- | :--- | :--- |
| **Pairs** | `BTCUSDT`, `ETHUSDT`, `SOLUSDT`, `BNBUSDT`, `XRPUSDT`, `DOGEUSDT`, `ADAUSDT` | Any valid Binance pair (e.g. `AVAXUSDT`, `PEPEUSDT`, `NEARUSDT`) |
| **Intervals** | `1m` (Scalp), `5m`, `15m` (Intraday), `1h` (Standard), `4h` (Swing), `1d` (Macro) | `3m`, `30m`, `2h`, `6h`, `8h`, `12h`, `3d`, `1w`, `1M` |
| **History Limits** | `30`, `60`, `100`, `200` candles | 1 to 1000 candles |

---

## File Structure

```
.
├── .env.example          # Environment configuration template
├── .gitignore            # Git exclusion rules (.env, .venv, *.html)
├── binance_charts.py     # Technical indicators & Plotly / Terminal visualizers
├── binance_consumer.py   # Interactive CLI terminal & consumer script
├── requirements.txt      # Python dependencies (python-binance, rich, plotly, etc.)
└── README.md             # Documentation & usage guide
```

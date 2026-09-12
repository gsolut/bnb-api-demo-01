"""
Binance API Consumer & Interactive Market Terminal
Provides an interactive CLI menu with preset symbols, intervals, modern Plotly charts,
terminal market dashboards, live WebSocket trade streaming, and private REST endpoints.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from typing import Any

# Ensure UTF-8 console output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from binance import AsyncClient, BinanceSocketManager, Client
from binance.enums import (
    ORDER_TYPE_LIMIT,
    SIDE_BUY,
    TIME_IN_FORCE_GTC,
)
from binance.exceptions import BinanceAPIException, BinanceRequestException
from dotenv import load_dotenv
from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

import binance_charts

console = Console(safe_box=True)

# ---------------------------------------------------------------
# 1) Configuration & Client Initialization
# ---------------------------------------------------------------
load_dotenv()

API_KEY = os.getenv("BINANCE_API_KEY", "").strip() or None
API_SECRET = os.getenv("BINANCE_API_SECRET", "").strip() or None
USE_TESTNET = os.getenv("BINANCE_TESTNET", "false").strip().lower() in {"1", "true", "yes"}
TLD = os.getenv("BINANCE_TLD", "com").strip() or "com"

# Initialize Client
client = Client(api_key=API_KEY, api_secret=API_SECRET, tld=TLD, testnet=USE_TESTNET)

# Preset Values for Quick Selection
POPULAR_SYMBOLS = [
    ("BTCUSDT", "Bitcoin / Tether"),
    ("ETHUSDT", "Ethereum / Tether"),
    ("SOLUSDT", "Solana / Tether"),
    ("BNBUSDT", "BNB / Tether"),
    ("XRPUSDT", "Ripple / Tether"),
    ("DOGEUSDT", "Dogecoin / Tether"),
    ("ADAUSDT", "Cardano / Tether"),
]

POPULAR_INTERVALS = [
    ("1m", "1 Minute (Scalping)"),
    ("5m", "5 Minutes (Short-term)"),
    ("15m", "15 Minutes (Intraday)"),
    ("1h", "1 Hour (Standard Hourly)"),
    ("4h", "4 Hours (Swing Trend)"),
    ("1d", "1 Day (Macro Trend)"),
]

POPULAR_LIMITS = [
    (30, "30 Candles (Fast)"),
    (60, "60 Candles (Recommended)"),
    (100, "100 Candles (In-depth)"),
    (200, "200 Candles (Extended History)"),
]


# ---------------------------------------------------------------
# 2) Helper Selection Prompts
# ---------------------------------------------------------------
def select_symbol(default: str = "BTCUSDT") -> str:
    """Prompts user to select from popular symbols or enter a custom pair."""
    console.print("\n[bold cyan]Select a Cryptocurrency Pair:[/bold cyan]")
    for idx, (sym, name) in enumerate(POPULAR_SYMBOLS, start=1):
        console.print(f"  [bold yellow]{idx}[/bold yellow]) [bold white]{sym:<10}[/bold white] - {name}")
    console.print(f"  [bold yellow]{len(POPULAR_SYMBOLS)+1}[/bold yellow]) Custom Symbol (e.g. AVAXUSDT, PEPEUSDT)")

    choice = Prompt.ask(
        "\nEnter choice number or symbol name",
        default=default,
        show_default=True,
    ).strip().upper()

    if choice.isdigit():
        choice_idx = int(choice)
        if 1 <= choice_idx <= len(POPULAR_SYMBOLS):
            return POPULAR_SYMBOLS[choice_idx - 1][0]
        elif choice_idx == len(POPULAR_SYMBOLS) + 1:
            custom = Prompt.ask("Enter custom pair").strip().upper()
            return custom or default

    return choice if choice else default


def select_interval(default: str = "1h") -> str:
    """Prompts user to select from popular intervals or enter a custom one."""
    console.print("\n[bold cyan]Select Time Interval:[/bold cyan]")
    for idx, (inv, desc) in enumerate(POPULAR_INTERVALS, start=1):
        console.print(f"  [bold yellow]{idx}[/bold yellow]) [bold white]{inv:<6}[/bold white] - {desc}")
    console.print(f"  [bold yellow]{len(POPULAR_INTERVALS)+1}[/bold yellow]) Custom Interval (e.g. 3m, 2h, 1w)")

    choice = Prompt.ask(
        "\nEnter choice number or interval",
        default=default,
        show_default=True,
    ).strip().lower()

    if choice.isdigit():
        choice_idx = int(choice)
        if 1 <= choice_idx <= len(POPULAR_INTERVALS):
            return POPULAR_INTERVALS[choice_idx - 1][0]
        elif choice_idx == len(POPULAR_INTERVALS) + 1:
            custom = Prompt.ask("Enter custom interval").strip().lower()
            return custom or default

    return choice if choice else default


def select_limit(default: int = 60) -> int:
    """Prompts user to select candle history limit."""
    console.print("\n[bold cyan]Select History Length (Candles):[/bold cyan]")
    for idx, (lim, desc) in enumerate(POPULAR_LIMITS, start=1):
        console.print(f"  [bold yellow]{idx}[/bold yellow]) [bold white]{lim} candles[/bold white] - {desc}")
    console.print(f"  [bold yellow]{len(POPULAR_LIMITS)+1}[/bold yellow]) Custom Limit")

    choice = Prompt.ask(
        "\nEnter choice number or candle count",
        default=str(default),
        show_default=True,
    ).strip()

    if choice.isdigit():
        choice_val = int(choice)
        if 1 <= choice_val <= len(POPULAR_LIMITS):
            return POPULAR_LIMITS[choice_val - 1][0]
        elif choice_val == len(POPULAR_LIMITS) + 1:
            custom = Prompt.ask("Enter number of candles (1-500)", default="60").strip()
            return int(custom) if custom.isdigit() else default
        elif choice_val > len(POPULAR_LIMITS):
            return choice_val

    return default


# ---------------------------------------------------------------
# 3) REST & Streaming Core Functions
# ---------------------------------------------------------------
def get_ticker(symbol: str = "BTCUSDT") -> dict[str, Any] | None:
    """Fetches the latest ticker price for a given symbol."""
    symbol_clean = symbol.strip().upper()
    try:
        ticker = client.get_symbol_ticker(symbol=symbol_clean)
        console.print(f"[bold green]✓ {ticker['symbol']} Latest Price:[/bold green] [bold white]{ticker['price']}[/bold white]")
        return ticker
    except (BinanceAPIException, BinanceRequestException) as err:
        console.print(f"[bold red]✗ Failed to fetch ticker for {symbol_clean}:[/bold red] {err}")
        return None


def get_balances(asset_filter: str | None = None) -> list[dict[str, str]]:
    """Fetches account balances for assets with non-zero quantities."""
    if not (API_KEY and API_SECRET):
        console.print("[bold yellow]! Skipping: No API key/secret configured in .env.[/bold yellow]")
        return []

    try:
        info = client.get_account()
        balances = [
            b for b in info.get("balances", [])
            if float(b.get("free", 0)) > 0 or float(b.get("locked", 0)) > 0
        ]
        if asset_filter:
            balances = [b for b in balances if b.get("asset") == asset_filter.upper()]

        table = Table(title=f"Account Balances ({len(balances)} non-zero assets)", show_header=True, header_style="bold magenta", expand=True)
        table.add_column("Asset", justify="center")
        table.add_column("Free", justify="right")
        table.add_column("Locked", justify="right")
        table.add_column("Total", justify="right")

        for b in balances:
            free = float(b["free"])
            locked = float(b["locked"])
            table.add_row(b["asset"], f"{free:,.6f}", f"{locked:,.6f}", f"{free + locked:,.6f}")

        console.print(table)
        return balances
    except (BinanceAPIException, BinanceRequestException) as err:
        console.print(f"[bold red]✗ Failed to fetch balances:[/bold red] {err}")
        return []


def place_test_limit_buy(
    symbol: str = "BTCUSDT",
    qty: float = 0.001,
    price: float = 20000.0,
) -> dict[str, Any] | None:
    """Places a safe test order against Binance endpoint."""
    if not (API_KEY and API_SECRET):
        console.print("[bold yellow]! Skipping: No API key/secret configured in .env.[/bold yellow]")
        return None

    symbol_clean = symbol.strip().upper()
    try:
        response = client.create_test_order(
            symbol=symbol_clean,
            side=SIDE_BUY,
            type=ORDER_TYPE_LIMIT,
            timeInForce=TIME_IN_FORCE_GTC,
            quantity=qty,
            price=f"{price:.2f}",
        )
        console.print(f"[bold green]✓ Test Limit Buy Order OK for {symbol_clean}:[/bold green] Qty={qty}, Price={price:.2f}")
        return response
    except (BinanceAPIException, BinanceRequestException) as err:
        console.print(f"[bold red]✗ Test order failed for {symbol_clean}:[/bold red] {err}")
        return None


async def stream_trades(symbol: str = "btcusdt", max_messages: int | None = None) -> None:
    """Streams real-time trades via WebSocket."""
    async_client = await AsyncClient.create(
        api_key=API_KEY,
        api_secret=API_SECRET,
        tld=TLD,
        testnet=USE_TESTNET,
    )
    bm = BinanceSocketManager(async_client)
    symbol_lower = symbol.strip().lower()

    console.print(f"\n[bold cyan]Connecting to live trade stream for {symbol.upper()} (Press Ctrl+C to stop)...[/bold cyan]")
    try:
        async with bm.trade_socket(symbol=symbol_lower) as trade_socket:
            msg_count = 0
            while True:
                message = await trade_socket.recv()
                if not message:
                    continue

                price = message.get("p", "0")
                qty = message.get("q", "0")
                is_buyer_mm = message.get("m", False)
                side = "SELL" if is_buyer_mm else "BUY"
                side_color = "red" if is_buyer_mm else "green"
                timestamp = time.strftime("%X")

                console.print(f"[{timestamp}] [{side_color}]{side:<4}[/{side_color}] | Qty: {qty:<12} @ {price}")
                msg_count += 1
                if max_messages and msg_count >= max_messages:
                    break
    except asyncio.CancelledError:
        console.print("\n[yellow]Stream task cancelled.[/yellow]")
    except Exception as err:
        console.print(f"[bold red]WebSocket error:[/bold red] {err}")
    finally:
        await async_client.close_connection()


# ---------------------------------------------------------------
# 4) Interactive CLI Menu Loop
# ---------------------------------------------------------------
def interactive_menu() -> None:
    """Main interactive menu offering presets, charting, streams, and API tools."""
    while True:
        banner = Text()
        banner.append("⚡ BINANCE API CONSUMER & MARKET TERMINAL ⚡\n", style="bold yellow")
        banner.append(f"Network: {'Testnet' if USE_TESTNET else 'Mainnet'} | TLD: {TLD} | Auth: {'Enabled' if API_KEY else 'Public Mode'}", style="dim cyan")
        console.print(Panel(Align.center(banner), border_style="yellow"))

        console.print("[bold]Select an action:[/bold]")
        console.print("  [bold cyan]1[/bold cyan]) 📊 [bold white]Interactive Browser Chart (Plotly HTML + RSI + Bollinger)[/bold white]")
        console.print("  [bold cyan]2[/bold cyan]) 📈 [bold white]Terminal Market Summary & ASCII Price Action[/bold white]")
        console.print("  [bold cyan]3[/bold cyan]) ⚡ [bold white]Live WebSocket Real-Time Trade Stream[/bold white]")
        console.print("  [bold cyan]4[/bold cyan]) 🔍 [bold white]Quick Spot Ticker Price Lookup[/bold white]")
        console.print("  [bold cyan]5[/bold cyan]) 💰 [bold white]Account Balances & Portfolio Summary[/bold white]")
        console.print("  [bold cyan]6[/bold cyan]) 🧪 [bold white]Place Safe Test Limit Order[/bold white]")
        console.print("  [bold cyan]7[/bold cyan]) 🚪 [bold red]Exit[/bold red]")

        choice = Prompt.ask("\nChoose an option", choices=["1", "2", "3", "4", "5", "6", "7"], default="1")

        if choice == "1":
            # Interactive Chart
            symbol = select_symbol("BTCUSDT")
            interval = select_interval("1h")
            limit = select_limit(60)
            console.print(f"\n[cyan]Fetching {limit} candles for {symbol} ({interval})...[/cyan]")
            df = binance_charts.fetch_ohlcv_dataframe(client, symbol=symbol, interval=interval, limit=limit)
            if not df.empty:
                binance_charts.create_modern_plotly_chart(df, symbol=symbol, interval=interval, auto_open=True)

        elif choice == "2":
            # Terminal Summary
            symbol = select_symbol("BTCUSDT")
            interval = select_interval("1h")
            limit = select_limit(40)
            console.print(f"\n[cyan]Fetching market snapshot for {symbol} ({interval})...[/cyan]")
            df = binance_charts.fetch_ohlcv_dataframe(client, symbol=symbol, interval=interval, limit=limit)
            if not df.empty:
                binance_charts.render_terminal_summary_table(df, symbol=symbol, interval=interval)

        elif choice == "3":
            # WebSocket Stream
            symbol = select_symbol("BTCUSDT")
            try:
                asyncio.run(stream_trades(symbol=symbol))
            except KeyboardInterrupt:
                console.print("\n[yellow]Trade stream stopped.[/yellow]")

        elif choice == "4":
            # Quick Ticker
            symbol = select_symbol("BTCUSDT")
            get_ticker(symbol)

        elif choice == "5":
            # Account Balances
            asset = Prompt.ask("Filter by asset symbol (leave empty for all)", default="").strip()
            get_balances(asset_filter=asset if asset else None)

        elif choice == "6":
            # Place Test Order
            symbol = select_symbol("BTCUSDT")
            qty_str = Prompt.ask("Quantity (in base asset)", default="0.001")
            price_str = Prompt.ask("Limit Price (USDT)", default="20000.0")
            try:
                place_test_limit_buy(symbol=symbol, qty=float(qty_str), price=float(price_str))
            except ValueError:
                console.print("[bold red]Invalid quantity or price.[/bold red]")

        elif choice == "7":
            console.print("[bold green]Goodbye![/bold green]")
            break

        console.print()
        Prompt.ask("[dim]Press Enter to return to main menu...[/dim]")
        console.print()


# ---------------------------------------------------------------
# 5) Main Entrypoint & CLI Argument Parser
# ---------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Binance API Consumer & Market Terminal")
    parser.add_argument("--symbol", "-s", type=str, default="BTCUSDT", help="Trading symbol (e.g. BTCUSDT, ETHUSDT)")
    parser.add_argument("--interval", "-i", type=str, default="1h", help="Candle interval (1m, 5m, 15m, 1h, 4h, 1d)")
    parser.add_argument("--limit", "-l", type=int, default=60, help="Candle count limit")
    parser.add_argument("--chart", action="store_true", help="Generate and open interactive Plotly HTML chart")
    parser.add_argument("--summary", action="store_true", help="Display terminal market summary and ASCII curve")
    parser.add_argument("--stream", action="store_true", help="Stream live WebSocket trades")
    parser.add_argument("--ticker", action="store_true", help="Fetch latest ticker price")
    parser.add_argument("--balances", action="store_true", help="Fetch account balances")
    parser.add_argument("--no-menu", action="store_true", help="Do not launch interactive menu")

    args = parser.parse_args()

    # If specific action flags were passed, execute them directly without opening menu
    if args.chart:
        df = binance_charts.fetch_ohlcv_dataframe(client, symbol=args.symbol, interval=args.interval, limit=args.limit)
        if not df.empty:
            binance_charts.create_modern_plotly_chart(df, symbol=args.symbol, interval=args.interval, auto_open=True)
        return

    if args.summary:
        df = binance_charts.fetch_ohlcv_dataframe(client, symbol=args.symbol, interval=args.interval, limit=args.limit)
        if not df.empty:
            binance_charts.render_terminal_summary_table(df, symbol=args.symbol, interval=args.interval)
        return

    if args.stream:
        try:
            asyncio.run(stream_trades(symbol=args.symbol))
        except KeyboardInterrupt:
            console.print("\n[yellow]Stream stopped.[/yellow]")
        return

    if args.ticker:
        get_ticker(symbol=args.symbol)
        return

    if args.balances:
        get_balances()
        return

    # Default to interactive menu if no specific CLI flags provided
    interactive_menu()


if __name__ == "__main__":
    main()

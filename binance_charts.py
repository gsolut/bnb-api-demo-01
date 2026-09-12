"""
Binance Market Data Charting & Visualization Module
Provides technical analysis calculations, interactive multi-panel Plotly charts,
and rich terminal summaries with ASCII price action charts.
"""

from __future__ import annotations

import os
import sys
import webbrowser
from typing import Any

# Ensure UTF-8 output on Windows consoles if supported
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceRequestException
from plotly.subplots import make_subplots
from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console(safe_box=True)


# ---------------------------------------------------------------
# 1) Technical Indicators Calculation
# ---------------------------------------------------------------
def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Calculates SMA, EMA, Bollinger Bands, Volume MA, and RSI."""
    df = df.copy()

    # Moving Averages
    df["sma_7"] = df["close"].rolling(window=7).mean()
    df["sma_25"] = df["close"].rolling(window=25).mean()
    df["sma_99"] = df["close"].rolling(window=99).mean()
    df["ema_12"] = df["close"].ewm(span=12, adjust=False).mean()
    df["ema_26"] = df["close"].ewm(span=26, adjust=False).mean()

    # Bollinger Bands (20 periods, 2 std)
    bb_period = 20
    df["bb_middle"] = df["close"].rolling(window=bb_period).mean()
    bb_std = df["close"].rolling(window=bb_period).std()
    df["bb_upper"] = df["bb_middle"] + (2 * bb_std)
    df["bb_lower"] = df["bb_middle"] - (2 * bb_std)

    # Volume MA
    df["vol_ma_20"] = df["volume"].rolling(window=20).mean()

    # Relative Strength Index (RSI - 14)
    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -1 * delta.clip(upper=0)
    avg_gain = gain.rolling(window=14, min_periods=14).mean()
    avg_loss = loss.rolling(window=14, min_periods=14).mean()

    # Exponential smoothing for RSI
    for i in range(14, len(df)):
        avg_gain.iloc[i] = (avg_gain.iloc[i - 1] * 13 + gain.iloc[i]) / 14
        avg_loss.iloc[i] = (avg_loss.iloc[i - 1] * 13 + loss.iloc[i]) / 14

    rs = avg_gain / avg_loss.replace(0, np.nan)
    df["rsi_14"] = 100 - (100 / (1 + rs))
    df["rsi_14"] = df["rsi_14"].fillna(50.0)

    # Direction flag for candles
    df["is_bullish"] = df["close"] >= df["open"]
    df["pct_change"] = df["close"].pct_change() * 100.0

    return df


# ---------------------------------------------------------------
# 2) Data Fetching from Binance REST API
# ---------------------------------------------------------------
def fetch_ohlcv_dataframe(
    client: Client,
    symbol: str = "BTCUSDT",
    interval: str = "1h",
    limit: int = 100,
) -> pd.DataFrame:
    """
    Fetches candlestick (kline) data from Binance and returns an indicator-enriched DataFrame.
    """
    symbol_clean = symbol.strip().upper()
    try:
        klines = client.get_klines(symbol=symbol_clean, interval=interval, limit=limit)
    except (BinanceAPIException, BinanceRequestException) as err:
        console.print(f"[bold red]Failed to fetch klines for {symbol_clean}:[/bold red] {err}")
        return pd.DataFrame()

    if not klines:
        console.print(f"[bold yellow]No kline data returned for {symbol_clean}.[/bold yellow]")
        return pd.DataFrame()

    columns = [
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_asset_volume", "number_of_trades",
        "taker_buy_base_asset_volume", "taker_buy_quote_asset_volume", "ignore"
    ]
    df = pd.DataFrame(klines, columns=columns)

    # Format timestamps
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
    df["close_time"] = pd.to_datetime(df["close_time"], unit="ms")

    # Cast numeric columns
    numeric_cols = ["open", "high", "low", "close", "volume", "quote_asset_volume", "number_of_trades"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Compute technical indicators
    df = calculate_indicators(df)
    return df


# ---------------------------------------------------------------
# 3) Modern Interactive Multi-Panel Plotly Chart
# ---------------------------------------------------------------
def create_modern_plotly_chart(
    df: pd.DataFrame,
    symbol: str = "BTCUSDT",
    interval: str = "1h",
    output_file: str | None = None,
    auto_open: bool = True,
) -> str:
    """
    Creates an interactive, professional dark-theme financial chart with 3 panels:
    - Main Panel: Candlestick, Bollinger Bands, SMA 7/25/99
    - Middle Panel: Volume bar chart with 20-period Volume MA
    - Lower Panel: RSI(14) oscillator with overbought/oversold levels
    """
    if df.empty:
        console.print("[bold red]Cannot create chart: DataFrame is empty.[/bold red]")
        return ""

    symbol_clean = symbol.strip().upper()
    if not output_file:
        output_file = f"{symbol_clean}_{interval}_chart.html"

    # 3-row layout
    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        row_heights=[0.60, 0.20, 0.20],
        subplot_titles=(
            f"<b>{symbol_clean} ({interval.upper()}) Price & Technical Indicators</b>",
            "<b>Volume</b>",
            "<b>Relative Strength Index (RSI 14)</b>"
        ),
    )

    # 1. Bollinger Bands Fill & Lines
    if "bb_upper" in df.columns and not df["bb_upper"].isna().all():
        fig.add_trace(
            go.Scatter(
                x=df["open_time"],
                y=df["bb_upper"],
                line=dict(color="rgba(128, 128, 128, 0.4)", width=1, dash="dot"),
                name="BB Upper (20,2)",
                hoverinfo="skip",
            ),
            row=1, col=1
        )
        fig.add_trace(
            go.Scatter(
                x=df["open_time"],
                y=df["bb_lower"],
                line=dict(color="rgba(128, 128, 128, 0.4)", width=1, dash="dot"),
                fill="tonexty",
                fillcolor="rgba(128, 128, 128, 0.05)",
                name="BB Lower (20,2)",
                hoverinfo="skip",
            ),
            row=1, col=1
        )

    # 2. Main Candlesticks
    fig.add_trace(
        go.Candlestick(
            x=df["open_time"],
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            name="OHLC",
            increasing_line_color="#00c087",  # Modern crypto green
            decreasing_line_color="#ff3b69",  # Modern crypto red
            increasing_fillcolor="#00c087",
            decreasing_fillcolor="#ff3b69",
        ),
        row=1, col=1
    )

    # 3. Moving Averages
    if "sma_7" in df.columns and not df["sma_7"].isna().all():
        fig.add_trace(
            go.Scatter(x=df["open_time"], y=df["sma_7"], line=dict(color="#f3ba2f", width=1.5), name="SMA 7"),
            row=1, col=1
        )
    if "sma_25" in df.columns and not df["sma_25"].isna().all():
        fig.add_trace(
            go.Scatter(x=df["open_time"], y=df["sma_25"], line=dict(color="#00b4d8", width=1.5), name="SMA 25"),
            row=1, col=1
        )
    if "sma_99" in df.columns and not df["sma_99"].isna().all():
        fig.add_trace(
            go.Scatter(x=df["open_time"], y=df["sma_99"], line=dict(color="#9b5de5", width=1.5), name="SMA 99"),
            row=1, col=1
        )

    # 4. Volume Subplot
    vol_colors = ["#00c087" if b else "#ff3b69" for b in df["is_bullish"]]
    fig.add_trace(
        go.Bar(
            x=df["open_time"],
            y=df["volume"],
            marker_color=vol_colors,
            name="Volume",
            opacity=0.85,
        ),
        row=2, col=1
    )
    if "vol_ma_20" in df.columns and not df["vol_ma_20"].isna().all():
        fig.add_trace(
            go.Scatter(
                x=df["open_time"],
                y=df["vol_ma_20"],
                line=dict(color="#ffa200", width=1.2),
                name="Vol MA (20)",
            ),
            row=2, col=1
        )

    # 5. RSI Subplot
    if "rsi_14" in df.columns and not df["rsi_14"].isna().all():
        fig.add_trace(
            go.Scatter(
                x=df["open_time"],
                y=df["rsi_14"],
                line=dict(color="#a06cd5", width=2),
                name="RSI (14)",
            ),
            row=3, col=1
        )
        # Overbought (70) & Oversold (30) Reference Lines
        fig.add_hline(y=70, line_dash="dash", line_color="#ff3b69", line_width=1, row=3, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="#00c087", line_width=1, row=3, col=1)
        fig.add_hline(y=50, line_dash="dot", line_color="#6c757d", line_width=0.8, row=3, col=1)

    # Dark Theme Layout Configuration
    latest_close = df["close"].iloc[-1]
    first_close = df["close"].iloc[0]
    period_change = ((latest_close - first_close) / first_close) * 100.0
    change_color = "#00c087" if period_change >= 0 else "#ff3b69"
    change_sign = "+" if period_change >= 0 else ""

    fig.update_layout(
        template="plotly_dark",
        title=dict(
            text=(
                f"<b>{symbol_clean} | Binance Market Analysis</b> "
                f"<span style='font-size:16px; color:{change_color};'>"
                f"Price: {latest_close:,.2f} ({change_sign}{period_change:.2f}%)</span>"
            ),
            x=0.03,
            y=0.98,
        ),
        xaxis_rangeslider_visible=False,
        hovermode="x unified",
        paper_bgcolor="#131722",
        plot_bgcolor="#181c27",
        font=dict(family="Segoe UI, Helvetica, Arial", size=12, color="#d1d4dc"),
        margin=dict(l=50, r=50, t=70, b=40),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            bgcolor="rgba(0,0,0,0.5)",
        ),
        height=850,
    )

    # Configure axes grids
    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor="#2a2e39")
    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor="#2a2e39")
    fig.update_yaxes(title_text="Price (USDT)", row=1, col=1)
    fig.update_yaxes(title_text="Volume", row=2, col=1)
    fig.update_yaxes(title_text="RSI", range=[0, 100], row=3, col=1)

    # Save to HTML
    fig.write_html(output_file)
    abs_path = os.path.abspath(output_file)
    console.print(f"[bold green]✓ Interactive chart generated successfully:[/bold green] [cyan]{abs_path}[/cyan]")

    if auto_open:
        try:
            webbrowser.open(f"file://{abs_path}")
        except Exception:
            pass

    return abs_path


# ---------------------------------------------------------------
# 4) ASCII Sparkline / Line Chart Generator (Cross-platform Safe)
# ---------------------------------------------------------------
def generate_ascii_chart(values: list[float], height: int = 8, width: int = 50) -> str:
    """Generates an ASCII text price chart safe for all terminal encodings."""
    if not values or len(values) < 2:
        return "Not enough data points for chart."

    # Resample / interpolate to target width if needed
    if len(values) > width:
        indices = np.linspace(0, len(values) - 1, width).astype(int)
        sampled = [values[i] for i in indices]
    else:
        sampled = values

    min_val = min(sampled)
    max_val = max(sampled)
    val_range = max_val - min_val if max_val != min_val else 1.0

    # Grid buffer
    grid = [[" " for _ in range(len(sampled))] for _ in range(height)]

    # Normalized row placement
    for col_idx, val in enumerate(sampled):
        norm = (val - min_val) / val_range
        row_idx = int(norm * (height - 1))
        row_idx = max(0, min(height - 1, row_idx))
        grid[height - 1 - row_idx][col_idx] = "*"

    # Add vertical filler connecting points
    for c in range(len(sampled) - 1):
        r1 = next(r for r in range(height) if grid[r][c] == "*")
        r2 = next(r for r in range(height) if grid[r][c + 1] == "*")
        step = 1 if r2 > r1 else -1
        for r in range(r1 + step, r2, step):
            if grid[r][c] == " ":
                grid[r][c] = "|"

    chart_lines = []
    for r in range(height):
        if r == 0:
            label = f"{max_val:>10.2f} |"
        elif r == height // 2:
            label = f"{(min_val + max_val)/2:>10.2f} |"
        elif r == height - 1:
            label = f"{min_val:>10.2f} |"
        else:
            label = " " * 10 + " |"
        chart_lines.append(label + "".join(grid[r]))

    chart_lines.append(" " * 11 + "+" + "-" * len(sampled))
    return "\n".join(chart_lines)


# ---------------------------------------------------------------
# 5) Terminal Summary & High-Density Dashboard
# ---------------------------------------------------------------
def render_terminal_summary_table(
    df: pd.DataFrame,
    symbol: str = "BTCUSDT",
    interval: str = "1h",
) -> None:
    """Renders a formatted terminal dashboard with indicators, candles, and ASCII price curve."""
    if df.empty:
        console.print("[bold red]No data to display.[/bold red]")
        return

    symbol_clean = symbol.strip().upper()
    latest = df.iloc[-1]

    latest_close = latest["close"]
    latest_open = latest["open"]
    latest_vol = latest["volume"]
    latest_rsi = latest.get("rsi_14", 50.0)
    sma7 = latest.get("sma_7", latest_close)
    sma25 = latest.get("sma_25", latest_close)

    period_change = ((latest_close - df["close"].iloc[0]) / df["close"].iloc[0]) * 100.0
    candle_change = ((latest_close - latest_open) / latest_open) * 100.0

    # Trend & Signal evaluation
    trend_color = "green" if latest_close >= sma25 else "red"
    trend_desc = "Bullish (Above SMA 25)" if latest_close >= sma25 else "Bearish (Below SMA 25)"

    rsi_color = "red" if latest_rsi >= 70 else ("green" if latest_rsi <= 30 else "yellow")
    rsi_desc = "Overbought (>70)" if latest_rsi >= 70 else ("Oversold (<30)" if latest_rsi <= 30 else "Neutral (30-70)")

    # 1. Header Panel
    header_text = Text()
    header_text.append(f"{symbol_clean} ", style="bold cyan")
    header_text.append(f"[{interval.upper()}]  ", style="bold yellow")
    header_text.append(f"Current: {latest_close:,.2f}  ", style="bold white")

    change_style = "bold green" if candle_change >= 0 else "bold red"
    change_sign = "+" if candle_change >= 0 else ""
    header_text.append(f"Candle: {change_sign}{candle_change:.2f}%  ", style=change_style)

    p_change_style = "bold green" if period_change >= 0 else "bold red"
    p_change_sign = "+" if period_change >= 0 else ""
    header_text.append(f"Range ({len(df)} candles): {p_change_sign}{period_change:.2f}%", style=p_change_style)

    console.print(Panel(Align.center(header_text), title="[bold]Market Snapshot[/bold]", border_style="cyan"))

    # 2. Key Metrics Table
    metrics_table = Table(show_header=True, header_style="bold magenta", expand=True)
    metrics_table.add_column("24h/Period High", justify="center")
    metrics_table.add_column("24h/Period Low", justify="center")
    metrics_table.add_column("Volume", justify="center")
    metrics_table.add_column("SMA 7 / 25", justify="center")
    metrics_table.add_column("RSI (14)", justify="center")
    metrics_table.add_column("Trend Status", justify="center")

    metrics_table.add_row(
        f"{df['high'].max():,.2f}",
        f"{df['low'].min():,.2f}",
        f"{latest_vol:,.2f}",
        f"{sma7:,.2f} / {sma25:,.2f}",
        f"[{rsi_color}]{latest_rsi:.1f} ({rsi_desc})[/{rsi_color}]",
        f"[{trend_color}]{trend_desc}[/{trend_color}]",
    )
    console.print(metrics_table)

    # 3. ASCII Price Chart
    console.print("\n[bold cyan]Price Action Curve (Closing Prices):[/bold cyan]")
    ascii_chart = generate_ascii_chart(df["close"].tolist(), height=8, width=54)
    console.print(f"[green]{ascii_chart}[/green]\n")

    # 4. Recent Candles Table
    candles_table = Table(title=f"Recent {symbol_clean} Candles (Last 5)", show_header=True, header_style="bold blue", expand=True)
    candles_table.add_column("Time (UTC)", justify="center")
    candles_table.add_column("Open", justify="right")
    candles_table.add_column("High", justify="right")
    candles_table.add_column("Low", justify="right")
    candles_table.add_column("Close", justify="right")
    candles_table.add_column("Change %", justify="right")
    candles_table.add_column("Volume", justify="right")

    for _, row in df.tail(5).iterrows():
        c_change = ((row["close"] - row["open"]) / row["open"]) * 100.0
        c_style = "green" if c_change >= 0 else "red"
        c_sign = "+" if c_change >= 0 else ""
        time_str = row["open_time"].strftime("%m-%d %H:%M")

        candles_table.add_row(
            time_str,
            f"{row['open']:,.2f}",
            f"{row['high']:,.2f}",
            f"{row['low']:,.2f}",
            f"{row['close']:,.2f}",
            f"[{c_style}]{c_sign}{c_change:.2f}%[/{c_style}]",
            f"{row['volume']:,.2f}",
        )

    console.print(candles_table)

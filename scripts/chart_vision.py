#!/usr/bin/env python3
"""
Chart Vision module for generating AI-optimized trading charts.

Creates 4-panel PNG charts (Price+SMA, RSI, Volume, CMF/OBV) for Gemini Vision analysis.
Adapted from LLM_trader/src/analyzer/pattern_engine/chart_generator.py
"""

import io
from datetime import datetime
from typing import Optional, Dict, Tuple

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


# AI-optimized colors for pattern recognition
AI_COLORS = {
    'background': '#000000',
    'grid': '#555555',
    'text': '#ffffff',
    'candle_up': '#00ff00',
    'candle_down': '#ff0000',
    'volume_up': '#00aa00',
    'volume_down': '#aa0000',
    'rsi': '#ffff00',
    'sma_50': '#ff8c00',
    'sma_200': '#9932cc',
    'cmf': '#00ffff',
    'obv': '#ff00ff',
    'rsi_oversold': '#00ff00',
    'rsi_overbought': '#ff0000',
}

# Chart settings
AI_CANDLE_LIMIT = 200


def fetch_ohlcv_for_chart(symbol: str, period: str = "1y") -> Optional[np.ndarray]:
    """
    Fetch OHLCV data from yfinance for chart generation.

    Args:
        symbol: Stock ticker (e.g., "AAPL", "MSFT")
        period: Time period (e.g., "1y", "6mo", "3mo")

    Returns:
        NumPy array with columns [timestamp_ms, open, high, low, close, volume]
        or None if fetch fails
    """
    try:
        import yfinance as yf

        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period, interval="1d")

        if df.empty:
            # Try common suffixes for non-US stocks
            for suffix in [".DE", ".L", ".PA", ".AS", ".MI", ".SW"]:
                ticker = yf.Ticker(f"{symbol}{suffix}")
                df = ticker.history(period=period, interval="1d")
                if not df.empty:
                    break

        if df.empty:
            print(f"  [Chart] No yfinance data for {symbol}")
            return None

        # Convert to numpy array: [timestamp_ms, open, high, low, close, volume]
        ohlcv = np.column_stack([
            df.index.astype(np.int64) // 10**6,  # timestamp in ms
            df['Open'].values,
            df['High'].values,
            df['Low'].values,
            df['Close'].values,
            df['Volume'].values,
        ])

        print(f"  [Chart] Fetched {len(ohlcv)} candles for {symbol}")
        return ohlcv

    except Exception as e:
        print(f"  [Chart] Error fetching OHLCV for {symbol}: {e}")
        return None


def calculate_chart_indicators(ohlcv: np.ndarray) -> Dict[str, np.ndarray]:
    """
    Calculate technical indicators for chart overlay.

    Args:
        ohlcv: OHLCV array with columns [timestamp, open, high, low, close, volume]

    Returns:
        Dict with indicator arrays: rsi, sma_50, sma_200, cmf, obv
    """
    closes = ohlcv[:, 4].astype(float)
    highs = ohlcv[:, 2].astype(float)
    lows = ohlcv[:, 3].astype(float)
    volumes = ohlcv[:, 5].astype(float)

    indicators = {}

    # SMA 50 and SMA 200
    indicators['sma_50'] = _calculate_sma(closes, 50)
    indicators['sma_200'] = _calculate_sma(closes, 200)

    # RSI (14-period)
    indicators['rsi'] = _calculate_rsi(closes, 14)

    # CMF (Chaikin Money Flow, 20-period)
    indicators['cmf'] = _calculate_cmf(highs, lows, closes, volumes, 20)

    # OBV (On-Balance Volume)
    indicators['obv'] = _calculate_obv(closes, volumes)

    return indicators


def _calculate_sma(data: np.ndarray, period: int) -> np.ndarray:
    """Calculate Simple Moving Average."""
    sma = np.full(len(data), np.nan)
    if len(data) >= period:
        for i in range(period - 1, len(data)):
            sma[i] = np.mean(data[i - period + 1:i + 1])
    return sma


def _calculate_rsi(closes: np.ndarray, period: int = 14) -> np.ndarray:
    """Calculate Relative Strength Index."""
    rsi = np.full(len(closes), np.nan)
    if len(closes) < period + 1:
        return rsi

    deltas = np.diff(closes)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)

    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])

    for i in range(period, len(closes)):
        if avg_loss == 0:
            rsi[i] = 100
        else:
            rs = avg_gain / avg_loss
            rsi[i] = 100 - (100 / (1 + rs))

        if i < len(deltas):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    return rsi


def _calculate_cmf(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray,
                   volumes: np.ndarray, period: int = 20) -> np.ndarray:
    """Calculate Chaikin Money Flow."""
    cmf = np.full(len(closes), np.nan)
    if len(closes) < period:
        return cmf

    # Money Flow Multiplier
    hl_range = highs - lows
    hl_range = np.where(hl_range == 0, 1, hl_range)  # Avoid division by zero
    mfm = ((closes - lows) - (highs - closes)) / hl_range

    # Money Flow Volume
    mfv = mfm * volumes

    for i in range(period - 1, len(closes)):
        vol_sum = np.sum(volumes[i - period + 1:i + 1])
        if vol_sum > 0:
            cmf[i] = np.sum(mfv[i - period + 1:i + 1]) / vol_sum

    return cmf


def _calculate_obv(closes: np.ndarray, volumes: np.ndarray) -> np.ndarray:
    """Calculate On-Balance Volume."""
    obv = np.zeros(len(closes))
    for i in range(1, len(closes)):
        if closes[i] > closes[i - 1]:
            obv[i] = obv[i - 1] + volumes[i]
        elif closes[i] < closes[i - 1]:
            obv[i] = obv[i - 1] - volumes[i]
        else:
            obv[i] = obv[i - 1]
    return obv


def _format_price(val: float) -> str:
    """Format price value for display."""
    if isinstance(val, (int, float)) and not np.isnan(val):
        if abs(val) < 0.01:
            return f"{val:.6f}"
        elif abs(val) < 10:
            return f"{val:.4f}"
        else:
            return f"{val:.2f}"
    return "N/A"


def generate_trading_chart(
    symbol: str,
    ohlcv: np.ndarray,
    indicators: Optional[Dict[str, np.ndarray]] = None,
    width: int = 1920,
    height: int = 1080,
) -> Optional[io.BytesIO]:
    """
    Generate a 4-panel trading chart optimized for AI vision analysis.

    Args:
        symbol: Asset symbol for title
        ohlcv: OHLCV array [timestamp_ms, open, high, low, close, volume]
        indicators: Pre-calculated indicators (rsi, sma_50, sma_200, cmf, obv)
        width: Image width in pixels
        height: Image height in pixels

    Returns:
        BytesIO containing PNG image, or None on error
    """
    try:
        # Limit candles for readability
        if len(ohlcv) > AI_CANDLE_LIMIT:
            ohlcv = ohlcv[-AI_CANDLE_LIMIT:]
            if indicators:
                indicators = {k: v[-AI_CANDLE_LIMIT:] if v is not None else None
                              for k, v in indicators.items()}

        # Parse data
        timestamps = pd.to_datetime(ohlcv[:, 0], unit='ms').to_pydatetime().tolist()
        opens = ohlcv[:, 1].astype(float)
        highs = ohlcv[:, 2].astype(float)
        lows = ohlcv[:, 3].astype(float)
        closes = ohlcv[:, 4].astype(float)
        volumes = ohlcv[:, 5].astype(float)

        # Extract indicators
        rsi_data = indicators.get('rsi') if indicators else None
        sma_50 = indicators.get('sma_50') if indicators else None
        sma_200 = indicators.get('sma_200') if indicators else None
        cmf_data = indicators.get('cmf') if indicators else None
        obv_data = indicators.get('obv') if indicators else None

        # Create 4-row subplot
        fig = make_subplots(
            rows=4, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.03,
            row_heights=[0.55, 0.15, 0.15, 0.15],
            specs=[
                [{"secondary_y": False}],
                [{"secondary_y": False}],
                [{"secondary_y": False}],
                [{"secondary_y": True}]
            ]
        )

        # ROW 1: Candlestick + SMA
        fig.add_trace(go.Candlestick(
            x=timestamps,
            open=opens, high=highs, low=lows, close=closes,
            name="Price",
            increasing_line_color=AI_COLORS['candle_up'],
            decreasing_line_color=AI_COLORS['candle_down'],
        ), row=1, col=1)

        # Add SMA 50
        if sma_50 is not None and len(sma_50) == len(timestamps):
            fig.add_trace(go.Scatter(
                x=timestamps, y=sma_50,
                mode='lines', name='SMA 50',
                line=dict(color=AI_COLORS['sma_50'], width=1.5),
            ), row=1, col=1)

        # Add SMA 200
        if sma_200 is not None and len(sma_200) == len(timestamps):
            fig.add_trace(go.Scatter(
                x=timestamps, y=sma_200,
                mode='lines', name='SMA 200',
                line=dict(color=AI_COLORS['sma_200'], width=1.5),
            ), row=1, col=1)

        # ROW 2: RSI
        if rsi_data is not None and len(rsi_data) == len(timestamps):
            fig.add_trace(go.Scatter(
                x=timestamps, y=rsi_data,
                mode='lines', name='RSI (14)',
                line=dict(color=AI_COLORS['rsi'], width=1.5),
            ), row=2, col=1)
            fig.add_hline(y=70, row=2, col=1,
                          line=dict(color=AI_COLORS['rsi_overbought'], width=1, dash='dash'))
            fig.add_hline(y=30, row=2, col=1,
                          line=dict(color=AI_COLORS['rsi_oversold'], width=1, dash='dash'))
            fig.add_hline(y=50, row=2, col=1,
                          line=dict(color='#666666', width=0.5, dash='dot'))

        # ROW 3: Volume
        volume_colors = [AI_COLORS['volume_up'] if closes[i] >= opens[i]
                         else AI_COLORS['volume_down'] for i in range(len(closes))]
        fig.add_trace(go.Bar(
            x=timestamps, y=volumes,
            name='Volume',
            marker_color=volume_colors,
            opacity=0.7
        ), row=3, col=1)

        # ROW 4: CMF + OBV
        if cmf_data is not None and len(cmf_data) == len(timestamps):
            fig.add_trace(go.Scatter(
                x=timestamps, y=cmf_data,
                mode='lines', name='CMF (20)',
                fill='tozeroy',
                line=dict(color=AI_COLORS['cmf'], width=1),
                fillcolor='rgba(0, 255, 255, 0.3)',
            ), row=4, col=1, secondary_y=False)
            fig.add_hline(y=0, row=4, col=1,
                          line=dict(color='#888888', width=1, dash='dash'))

        if obv_data is not None and len(obv_data) == len(timestamps):
            fig.add_trace(go.Scatter(
                x=timestamps, y=obv_data,
                mode='lines', name='OBV',
                line=dict(color=AI_COLORS['obv'], width=1.5),
            ), row=4, col=1, secondary_y=True)

        # Layout
        current_price = float(closes[-1])
        fig.update_layout(
            title=dict(
                text=f"{symbol} - Daily (Last {len(ohlcv)} Candles) | Price: ${_format_price(current_price)}",
                font=dict(size=24)
            ),
            template="plotly_dark",
            height=height,
            width=width,
            font=dict(family="Arial", size=16, color=AI_COLORS['text']),
            paper_bgcolor=AI_COLORS['background'],
            plot_bgcolor=AI_COLORS['background'],
            margin=dict(l=60, r=100, t=60, b=60),
            showlegend=True,
            legend=dict(
                orientation="h", yanchor="bottom", y=1.01, xanchor="right", x=1,
                font=dict(size=14), bgcolor='rgba(0,0,0,0.7)'
            ),
            xaxis_rangeslider_visible=False
        )

        # Configure axes
        for row in range(1, 5):
            fig.update_xaxes(
                showgrid=True, gridwidth=1, gridcolor=AI_COLORS['grid'],
                row=row, col=1
            )
            fig.update_yaxes(
                showgrid=True, gridwidth=1, gridcolor=AI_COLORS['grid'],
                side="right", row=row, col=1
            )

        fig.update_yaxes(title_text="Price", row=1, col=1)
        fig.update_yaxes(title_text="RSI", range=[0, 100], row=2, col=1)
        fig.update_yaxes(title_text="Vol", row=3, col=1)
        fig.update_yaxes(title_text="CMF", row=4, col=1, secondary_y=False)
        fig.update_yaxes(title_text="OBV", row=4, col=1, secondary_y=True)

        # Add price annotations
        idx_high = int(np.argmax(highs))
        idx_low = int(np.argmin(lows))

        fig.add_annotation(
            x=timestamps[idx_high], y=float(highs[idx_high]),
            text=f"MAX: ${_format_price(highs[idx_high])}",
            showarrow=True, arrowhead=2, ax=0, ay=-40,
            font=dict(size=14, color='white'),
            bgcolor='rgba(0,0,0,0.5)', bordercolor=AI_COLORS['candle_up'],
            row=1, col=1
        )
        fig.add_annotation(
            x=timestamps[idx_low], y=float(lows[idx_low]),
            text=f"MIN: ${_format_price(lows[idx_low])}",
            showarrow=True, arrowhead=2, ax=0, ay=40,
            font=dict(size=14, color='white'),
            bgcolor='rgba(0,0,0,0.5)', bordercolor=AI_COLORS['candle_down'],
            row=1, col=1
        )

        # Current price line
        fig.add_hline(y=current_price, row=1, col=1,
                      line=dict(color='#666666', width=1, dash='dot'))

        # Export to PNG
        img_bytes = fig.to_image(format="png", width=width, height=height, scale=1)

        img_buffer = io.BytesIO(img_bytes)
        img_buffer.seek(0)

        print(f"  [Chart] Generated {len(img_bytes)} bytes for {symbol}")
        return img_buffer

    except Exception as e:
        print(f"  [Chart] Error generating chart for {symbol}: {e}")
        return None


def create_chart_for_analysis(symbol: str) -> Optional[io.BytesIO]:
    """
    Convenience function to create a chart ready for Gemini Vision.

    Args:
        symbol: Stock ticker

    Returns:
        BytesIO with PNG chart, or None if generation fails
    """
    ohlcv = fetch_ohlcv_for_chart(symbol)
    if ohlcv is None:
        return None

    indicators = calculate_chart_indicators(ohlcv)
    return generate_trading_chart(symbol, ohlcv, indicators)


if __name__ == "__main__":
    import sys

    symbol = sys.argv[1] if len(sys.argv) > 1 else "AAPL"

    print(f"Generating chart for {symbol}...")
    chart = create_chart_for_analysis(symbol)

    if chart:
        # Save to disk for testing
        filename = f"{symbol}_chart.png"
        with open(filename, 'wb') as f:
            f.write(chart.read())
        print(f"Saved to {filename}")
    else:
        print("Chart generation failed")

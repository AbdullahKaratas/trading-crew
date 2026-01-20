#!/usr/bin/env python3
"""
Telegram Worker Script for GitHub Actions.

This script is triggered by the telegram_analysis GitHub Action when a user
sends a command via Telegram. It runs the analysis and sends the result back.
"""

import json
import os
import re
import sys
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "TradingAgents"))

import requests
import yfinance as yf
from datetime import date

from tradingagents.graph.trading_graph import TradingAgentsGraph
from gemini_utils import (
    call_gemini_flash,
    extract_price_from_text,
    parse_json_response,
)

# Commodities that need Gemini + Search (yfinance doesn't work for these)
COMMODITIES = {"silver", "gold"}


def send_telegram_photo(chat_id: str, photo_bytes: bytes, caption: str = None) -> bool:
    """Send a photo to Telegram.

    Args:
        chat_id: Telegram chat ID
        photo_bytes: Image data as bytes (PNG/JPEG)
        caption: Optional caption (max 1024 chars)

    Returns:
        True if successful
    """
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    url = f"https://api.telegram.org/bot{token}/sendPhoto"

    files = {"photo": ("chart.png", photo_bytes, "image/png")}
    data = {"chat_id": chat_id}

    if caption:
        data["caption"] = caption[:1024]  # Telegram limit
        data["parse_mode"] = "Markdown"

    try:
        response = requests.post(url, data=data, files=files)
        if response.ok:
            return True
        print(f"Telegram sendPhoto error: {response.status_code} - {response.text[:200]}")
        return False
    except Exception as e:
        print(f"Error sending photo: {e}")
        return False


def send_telegram_message(chat_id: str, text: str) -> bool:
    """Send a message to Telegram. Splits long messages automatically."""
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    url = f"https://api.telegram.org/bot{token}/sendMessage"

    # Telegram has a 4096 character limit - split if needed
    max_len = 4000
    messages = []

    if len(text) <= max_len:
        messages = [text]
    else:
        # Split at newlines to avoid cutting words
        parts = text.split('\n')
        current = ""
        for part in parts:
            if len(current) + len(part) + 1 <= max_len:
                current += part + '\n'
            else:
                if current:
                    messages.append(current.strip())
                current = part + '\n'
        if current:
            messages.append(current.strip())

    success = True
    for i, msg in enumerate(messages):
        response = requests.post(url, json={
            "chat_id": chat_id,
            "text": msg,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        })
        if not response.ok:
            print(f"Telegram API error: {response.status_code}")
            print(f"Response: {response.text[:500]}")
            # Retry without Markdown if it fails
            response = requests.post(url, json={
                "chat_id": chat_id,
                "text": msg,
                "disable_web_page_preview": True,
            })
            if not response.ok:
                print(f"Retry without Markdown also failed: {response.text[:200]}")
        success = success and response.ok
        if len(messages) > 1 and i < len(messages) - 1:
            time.sleep(0.5)  # Small delay between messages

    return success


def is_commodity(symbol: str) -> bool:
    """Check if symbol is a commodity (silver, gold, etc.)."""
    return symbol.lower() in COMMODITIES


def resolve_symbol(user_input: str) -> tuple[str, str]:
    """
    Resolve company name, ticker, or commodity to valid yfinance symbol using Gemini + Search.

    Args:
        user_input: Company name (e.g., "E.ON"), ticker (e.g., "AAPL"), or commodity (e.g., "Silver")

    Returns:
        Tuple of (symbol, display_name) - e.g., ("EOAN.DE", "E.ON SE") or ("SI=F", "Silver Futures")
    """
    prompt = f"""Find the yfinance (Yahoo Finance) ticker symbol for "{user_input}".

Return ONLY JSON (no markdown):
{{"symbol": "<yfinance symbol>", "name": "<full name>"}}

Use the exact symbol format that works with the yfinance Python library."""

    response = call_gemini_flash(prompt, use_search=True)
    data = parse_json_response(response)

    if data and data.get("symbol"):
        symbol = data["symbol"].upper()
        name = data.get("name", user_input)
        print(f"  Resolved '{user_input}' → {symbol} ({name})")
        return symbol, name

    # Fallback: return as-is (uppercase)
    print(f"  Could not resolve '{user_input}', using as-is")
    return user_input.upper(), user_input


def get_commodity_spot_price(commodity: str) -> dict:
    """Get current spot price for a commodity using Gemini + Google Search.

    Returns dict with price_usd, source, and commodity name.
    """
    commodity_name = commodity.lower().capitalize()

    prompt = f"""Search for the current {commodity_name} spot price in USD per ounce.
Return ONLY a JSON object with the exact current price (no markdown, no explanation):
{{"price_usd": 80.15, "source": "kitco.com"}}"""

    response_text = call_gemini_flash(prompt, use_search=True)

    # Parse JSON from response
    data = parse_json_response(response_text)
    if data:
        return {
            "price": data.get("price_usd", 0),
            "source": data.get("source", "unknown"),
            "name": commodity_name,
        }

    # Fallback: extract price from text
    price = extract_price_from_text(response_text)
    if price:
        return {"price": price, "source": "extracted", "name": commodity_name}

    raise ValueError(f"Could not parse commodity price from response")


def get_stock_data(symbol: str) -> dict:
    """Get current stock/commodity data with support/resistance levels.

    For commodities (silver, gold), uses Gemini + Search for spot price.
    For stocks, uses yfinance.
    """
    # Check if this is a commodity - use Gemini + Search instead of yfinance
    if is_commodity(symbol):
        commodity_data = get_commodity_spot_price(symbol)
        current_price = commodity_data["price"]

        # For commodities, we don't have historical data from yfinance
        # Support/resistance will come from the LLM analysis
        return {
            "name": commodity_data["name"],
            "price": current_price,
            "currency": "USD",
            "recent_low": current_price * 0.95,  # Placeholder
            "recent_high": current_price * 1.05,  # Placeholder
            "support_1": current_price * 0.95,
            "support_2": current_price * 0.90,
            "resistance_1": current_price * 1.05,
            "resistance_2": current_price * 1.10,
            "entry_zone_low": current_price * 0.98,
            "entry_zone_high": current_price,
            "week_52_low": current_price * 0.80,  # Placeholder
            "week_52_high": current_price * 1.20,  # Placeholder
            "sector": "Commodities",
            "is_commodity": True,
            "price_source": commodity_data["source"],
        }

    # Regular stock - use yfinance
    ticker = yf.Ticker(symbol)
    info = ticker.info
    hist = ticker.history(period="3mo")

    # If yfinance fails, try with common suffixes or fall back to Gemini
    if hist.empty:
        # Try common European suffixes
        for suffix in [".DE", ".L", ".PA", ".AS", ".MI", ".SW"]:
            alt_symbol = symbol + suffix
            ticker = yf.Ticker(alt_symbol)
            hist = ticker.history(period="3mo")
            if not hist.empty:
                info = ticker.info
                print(f"  Found {symbol} as {alt_symbol}")
                break

    # If still empty, fall back to Gemini + Search
    if hist.empty:
        print(f"  yfinance failed for {symbol}, using Gemini fallback")
        prompt = f"""Search for the current stock price of {symbol} in USD.
Return ONLY a JSON object: {{"price_usd": 123.45, "name": "Company Name", "source": "finance.yahoo.com"}}"""
        response_text = call_gemini_flash(prompt, use_search=True)
        data = parse_json_response(response_text)

        if data and data.get("price_usd"):
            price = data["price_usd"]
            return {
                "name": data.get("name", symbol),
                "price": price,
                "currency": "USD",
                "recent_low": price * 0.95,
                "recent_high": price * 1.05,
                "support_1": price * 0.95,
                "support_2": price * 0.90,
                "resistance_1": price * 1.05,
                "resistance_2": price * 1.10,
                "entry_zone_low": price * 0.98,
                "entry_zone_high": price,
                "week_52_low": price * 0.80,
                "week_52_high": price * 1.20,
                "sector": "Unknown",
                "price_source": "gemini_search",
            }

        raise ValueError(f"No data found for {symbol}")

    current_price = hist["Close"].iloc[-1]
    recent_low = hist["Low"].tail(20).min()
    recent_high = hist["High"].tail(20).max()

    # Calculate support and resistance levels
    support_1 = hist["Low"].tail(10).min()  # Recent support
    support_2 = hist["Low"].tail(30).min()  # Stronger support
    resistance_1 = hist["High"].tail(10).max()  # Recent resistance
    resistance_2 = hist["High"].tail(30).max()  # Stronger resistance

    # Entry zone (between current and support)
    entry_zone_low = support_1 * 1.01  # Just above support
    entry_zone_high = current_price * 0.98  # Slightly below current

    # 52 week data
    hist_1y = ticker.history(period="1y")
    week_52_low = hist_1y["Low"].min() if not hist_1y.empty else support_2
    week_52_high = hist_1y["High"].max() if not hist_1y.empty else resistance_2

    return {
        "name": info.get("shortName", symbol),
        "price": current_price,
        "currency": info.get("currency", "USD"),
        "recent_low": recent_low,
        "recent_high": recent_high,
        "support_1": support_1,
        "support_2": support_2,
        "resistance_1": resistance_1,
        "resistance_2": resistance_2,
        "entry_zone_low": entry_zone_low,
        "entry_zone_high": entry_zone_high,
        "week_52_low": week_52_low,
        "week_52_high": week_52_high,
        "sector": info.get("sector", "Unknown"),
    }


def _format_strategies(strategies: dict, risk_labels: dict, labels: dict) -> str:
    """Format knockout strategies as text lines."""
    lines = ""
    strategy_configs = [
        ("conservative", labels["conservative"], "🟢"),
        ("moderate", labels["moderate"], "🟡"),
        ("aggressive", labels["aggressive"], "🔴"),
    ]
    for strat_key, strat_name, strat_emoji in strategy_configs:
        strat = strategies.get(strat_key, {})
        ko = strat.get("ko_level_usd", 0)
        dist = strat.get("distance_pct", 0)
        risk = risk_labels.get(strat.get("risk", "medium"), labels["medium"])
        lines += f"{strat_emoji} *{strat_name}:* KO ${ko:,.0f} ({dist:.1f}%) - {risk}\n"
    return lines


def format_analyze_result(symbol: str, result: dict, stock_data: dict, budget: float = None, lang: str = "de") -> str:
    """Format analysis result for Telegram with new table-based format."""
    trade = result.get("trade_decision") or {}
    is_de = lang == "de"

    # Get all values from structured LLM response - NO FALLBACKS
    # If trade_decision is empty, risk_manager already raised an error
    signal_raw = trade.get("signal", "—").upper()
    confidence = trade.get("confidence")  # None if missing
    unable_to_assess = trade.get("unable_to_assess", False)
    price_usd = trade.get("price_usd")  # None if missing
    price_eur = trade.get("price_eur")  # None if missing
    strategies = trade.get("strategies") or {}
    hold_alternative = trade.get("hold_alternative")
    support_zones = trade.get("support_zones") or []
    resistance_zones = trade.get("resistance_zones") or []
    detailed_analysis = trade.get("detailed_analysis") or ""

    # Signal mapping with emojis
    signal_map = {
        "LONG": ("🟢", "LONG"),
        "SHORT": ("🔴", "SHORT"),
        "HOLD": ("🟡", "HOLD"),
        "IGNORE": ("⚫", "IGNORE"),
    }
    emoji, signal = signal_map.get(signal_raw, ("🟡", "HOLD"))

    # Labels
    labels = {
        "price": "Price" if not is_de else "Kurs",
        "confidence": "Confidence" if not is_de else "Konfidenz",
        "strategies": "Knockout Strategies" if not is_de else "Knockout-Strategien",
        "strategy": "Strategy" if not is_de else "Strategie",
        "ko_level": "KO-Level",
        "distance": "Distance" if not is_de else "Abstand",
        "risk": "Risk" if not is_de else "Risiko",
        "conservative": "Conservative" if not is_de else "Konservativ",
        "moderate": "Moderate" if not is_de else "Moderat",
        "aggressive": "Aggressive" if not is_de else "Aggressiv",
        "support": "Support Zones" if not is_de else "Unterstützungszonen",
        "resistance": "Resistance Zones" if not is_de else "Widerstandszonen",
        "analysis": "Analysis" if not is_de else "Analyse",
        "alternative": "Alternative (for those who want to enter)" if not is_de else "Alternative (für Einstieg trotz HOLD)",
        "low": "Low" if not is_de else "Niedrig",
        "medium": "Medium" if not is_de else "Mittel",
        "high": "High" if not is_de else "Hoch",
        "no_assessment": "Assessment not possible" if not is_de else "Keine Einschätzung möglich",
    }

    # Risk label translation
    risk_labels = {"low": labels["low"], "medium": labels["medium"], "high": labels["high"]}

    # Confidence bar visualization
    if confidence is not None:
        conf_bars = int(confidence * 10)
        conf_display = "█" * conf_bars + "░" * (10 - conf_bars)
        conf_text = f"{conf_display} {confidence:.0%}"
    else:
        conf_text = "—"

    # Price display
    if price_usd is not None and price_eur is not None:
        price_text = f"${price_usd:,.2f} / €{price_eur:,.2f}"
    elif price_usd is not None:
        price_text = f"${price_usd:,.2f}"
    else:
        price_text = "—"

    # Build response
    response = f"""
{emoji} *{signal}: {symbol}*
_{stock_data['name']}_

💵 *{labels['price']}:* {price_text}
📊 *{labels['confidence']}:* {conf_text}
"""

    # Handle unable to assess
    if unable_to_assess:
        response += f"\n⚠️ *{labels['no_assessment']}*\n"

    # Strategies section
    if strategies and signal_raw in ["LONG", "SHORT"]:
        response += f"\n🎯 *{labels['strategies']} ({signal}):*\n"
        response += _format_strategies(strategies, risk_labels, labels)

    # HOLD with alternative
    if signal_raw == "HOLD" and hold_alternative:
        alt_dir = hold_alternative.get("direction", "LONG")
        alt_strategies = hold_alternative.get("strategies", {})
        alt_emoji = "📈" if alt_dir == "LONG" else "📉"
        response += f"\n{alt_emoji} *{labels['alternative']} ({alt_dir}):*\n"
        response += _format_strategies(alt_strategies, risk_labels, labels)

    # Support zones
    if support_zones:
        response += f"""

📉 *{labels['support']}:*"""
        for zone in support_zones[:4]:  # Max 4 zones
            level = zone.get("level_usd", 0)
            desc = zone.get("description", "")
            response += f"""
├── ${level:,.2f} - {desc}"""

    # Resistance zones
    if resistance_zones:
        response += f"""

📈 *{labels['resistance']}:*"""
        for zone in resistance_zones[:4]:  # Max 4 zones
            level = zone.get("level_usd", 0)
            desc = zone.get("description", "")
            response += f"""
├── ${level:,.2f} - {desc}"""

    # Detailed analysis
    if detailed_analysis:
        # Allow longer analysis for full debate summary (up to 2500 chars)
        analysis_preview = detailed_analysis[:2500]
        if len(detailed_analysis) > 2500:
            analysis_preview += "..."
        response += f"""

💡 *{labels['analysis']}:*
{analysis_preview}"""

    # Timeframes section
    timeframes = trade.get("timeframes") or {}
    if timeframes:
        tf_label = "Zeithorizonte" if is_de else "Timeframes"
        tf_names = {
            "short_term": "Kurzfristig (Tage-Wochen)" if is_de else "Short-term (days-weeks)",
            "medium_term": "Mittelfristig (Wochen-Monate)" if is_de else "Medium-term (weeks-months)",
            "long_term": "Langfristig (Monate-Jahre)" if is_de else "Long-term (months-years)",
        }
        tf_emojis = {"LONG": "🟢", "SHORT": "🔴", "HOLD": "🟡"}

        response += f"""

⏱️ *{tf_label}:*"""
        for tf_key, tf_name in tf_names.items():
            tf_signal = str(timeframes.get(tf_key, "HOLD")).upper()
            emoji = tf_emojis.get(tf_signal, "🟡")
            response += f"""
├── {emoji} {tf_name}: {tf_signal}"""

    response += f"""

📈 [Chart](https://www.tradingview.com/chart/?symbol={symbol})"""

    return response.strip()


def run_analysis(symbol: str, lang: str = "en", forced_direction: str = None, current_price: float = None) -> dict:
    """Run analysis using Universal Multi-Agent System (Gemini + Search).

    All assets (stocks, commodities, ETFs) now use the same Gemini-based system
    for real-time data via Google Search. No more yfinance/API issues.

    Args:
        symbol: Any asset (e.g., "AAPL", "Silver", "Gold", "SPY")
        lang: Output language ("en" or "de")
        forced_direction: Optional forced direction ("long" or "short"). If None, LLM decides.
        current_price: Optional price hint (Gemini will verify via search)
    """
    from universal_agents import run_universal_analysis

    today = date.today().isoformat()
    print(f"Using Universal Multi-Agent System (Gemini + Search) for {symbol}")

    return run_universal_analysis(symbol, trade_date=today, lang=lang)


def main():
    """Main entry point."""
    # Get environment variables
    command = os.environ.get("COMMAND", "analyze")
    user_input = os.environ.get("SYMBOL", "").strip()  # Keep original for resolution
    direction = os.environ.get("DIRECTION", "").lower() or None  # "long", "short", or None
    budget_str = os.environ.get("BUDGET", "")
    chat_id = os.environ.get("CHAT_ID")
    username = os.environ.get("USERNAME", "User")
    lang = os.environ.get("LANG", "de").lower()

    # Validate language
    if lang not in ["de", "en"]:
        lang = "de"

    # Validate direction
    if direction and direction not in ["long", "short"]:
        direction = None

    if not user_input:
        msg = "❌ No symbol provided." if lang == "en" else "❌ Kein Symbol angegeben."
        send_telegram_message(chat_id, msg)
        return 1

    if not chat_id:
        print("Error: No CHAT_ID provided")
        return 1

    # Resolve company name to symbol (e.g., "E.ON" → "EOAN.DE", "Apple" → "AAPL")
    print(f"Resolving symbol for: {user_input}")
    symbol, display_name = resolve_symbol(user_input)

    budget = float(budget_str) if budget_str and budget_str != "null" else None

    direction_str = f" ({direction.upper()})" if direction else ""
    print(f"Running analysis for {symbol} ({display_name}){direction_str} (budget: {budget}, lang: {lang})")

    try:
        # Get stock data
        stock_data = get_stock_data(symbol)
        print(f"Stock: {stock_data['name']} @ {stock_data['price']:.2f}")

        # Run analysis with optional forced direction and current price
        result = run_analysis(symbol, lang, forced_direction=direction, current_price=stock_data['price'])
        print("Analysis complete")

        # Send chart image first (if available)
        chart_image = result.get("chart_image")
        if chart_image:
            try:
                chart_image.seek(0)
                chart_bytes = chart_image.read()
                caption = f"📊 {symbol} Chart" if lang == "en" else f"📊 {symbol} Chart"
                if send_telegram_photo(chat_id, chart_bytes, caption):
                    print("Chart sent to Telegram")
                else:
                    print("Failed to send chart, continuing with text")
            except Exception as e:
                print(f"Error sending chart: {e}")

        # Format and send result (always use format_analyze_result now)
        message = format_analyze_result(symbol, result, stock_data, budget, lang)

        success = send_telegram_message(chat_id, message)

        if success:
            print(f"Result sent to chat {chat_id}")
            return 0
        else:
            print("Failed to send message")
            return 1

    except Exception as e:
        error_msg = f"❌ Error analyzing *{symbol}*:\n\n`{str(e)[:200]}`" if lang == "en" else f"❌ Fehler bei Analyse von *{symbol}*:\n\n`{str(e)[:200]}`"
        send_telegram_message(chat_id, error_msg)
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

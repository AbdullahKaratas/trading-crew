#!/usr/bin/env python3
"""
Telegram Worker Script for GitHub Actions.

This script is triggered by the telegram_analysis GitHub Action when a user
sends a command via Telegram. It runs the analysis and sends the result back.
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "TradingAgents"))

import requests
import yfinance as yf
from datetime import date

from tradingagents.graph.trading_graph import TradingAgentsGraph


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
        success = success and response.ok
        if len(messages) > 1 and i < len(messages) - 1:
            import time
            time.sleep(0.5)  # Small delay between messages

    return success


def get_stock_data(symbol: str) -> dict:
    """Get current stock data with support/resistance levels."""
    ticker = yf.Ticker(symbol)
    info = ticker.info
    hist = ticker.history(period="3mo")

    if hist.empty:
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


def format_analyze_result(symbol: str, result: dict, stock_data: dict, budget: float = None, lang: str = "de") -> str:
    """Format analysis result for Telegram with new table-based format."""
    trade = result.get("trade_decision") or {}  # Structured data from JSON
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
        response += f"""
🎯 *{labels['strategies']} ({signal}):*
"""
        for strat_key, strat_name, strat_emoji in [("conservative", labels["conservative"], "🟢"), ("moderate", labels["moderate"], "🟡"), ("aggressive", labels["aggressive"], "🔴")]:
            strat = strategies.get(strat_key, {})
            ko = strat.get("ko_level_usd", 0)
            dist = strat.get("distance_pct", 0)
            risk = risk_labels.get(strat.get("risk", "medium"), labels["medium"])
            response += f"""{strat_emoji} *{strat_name}:* KO ${ko:,.0f} ({dist:.1f}%) - {risk}
"""

    # HOLD with alternative
    if signal_raw == "HOLD" and hold_alternative:
        alt_dir = hold_alternative.get("direction", "LONG")
        alt_strategies = hold_alternative.get("strategies", {})
        alt_emoji = "📈" if alt_dir == "LONG" else "📉"

        response += f"""
{alt_emoji} *{labels['alternative']} ({alt_dir}):*
"""
        for strat_key, strat_name, strat_emoji in [("conservative", labels["conservative"], "🟢"), ("moderate", labels["moderate"], "🟡"), ("aggressive", labels["aggressive"], "🔴")]:
            strat = alt_strategies.get(strat_key, {})
            ko = strat.get("ko_level_usd", 0)
            dist = strat.get("distance_pct", 0)
            risk = risk_labels.get(strat.get("risk", "medium"), labels["medium"])
            response += f"""{strat_emoji} *{strat_name}:* KO ${ko:,.0f} ({dist:.1f}%) - {risk}
"""

    # Support zones
    if support_zones:
        response += f"""

📉 *{labels['support']}:*"""
        for zone in support_zones[:4]:  # Max 4 zones
            level = zone.get("level_usd", 0)
            desc = zone.get("description", "")[:40]
            response += f"""
├── ${level:,.2f} - {desc}"""

    # Resistance zones
    if resistance_zones:
        response += f"""

📈 *{labels['resistance']}:*"""
        for zone in resistance_zones[:4]:  # Max 4 zones
            level = zone.get("level_usd", 0)
            desc = zone.get("description", "")[:40]
            response += f"""
├── ${level:,.2f} - {desc}"""

    # Detailed analysis
    if detailed_analysis:
        # Truncate if too long
        analysis_preview = detailed_analysis[:800]
        if len(detailed_analysis) > 800:
            analysis_preview += "..."
        response += f"""

📊 *{labels['analysis']}:*
{analysis_preview}"""

    response += f"""

📈 [Chart](https://www.tradingview.com/chart/?symbol={symbol})"""

    return response.strip()


def is_commodity(symbol: str) -> bool:
    """Check if symbol is a commodity/futures (ends with =F)."""
    return symbol.endswith("=F")


def get_commodity_name(symbol: str) -> str:
    """Get human-readable commodity name."""
    commodity_map = {
        "SI=F": "Silver",
        "GC=F": "Gold",
        "CL=F": "Crude Oil WTI",
        "BZ=F": "Brent Crude Oil",
        "NG=F": "Natural Gas",
        "HG=F": "Copper",
        "PL=F": "Platinum",
        "PA=F": "Palladium",
        "ZC=F": "Corn",
        "ZW=F": "Wheat",
        "ZS=F": "Soybeans",
    }
    return commodity_map.get(symbol, symbol.replace("=F", " Futures"))


def run_commodity_analysis(symbol: str, lang: str = "en") -> dict:
    """Run commodity analysis using Gemini with Google Search grounding."""
    import google.generativeai as genai

    genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))

    commodity_name = get_commodity_name(symbol)
    today = date.today().isoformat()

    # Language output instruction
    lang_name = "German" if lang == "de" else "English"

    prompt = f"""You are an experienced commodity analyst. Analyze {commodity_name} ({symbol}) for today ({today}).

IMPORTANT: Use Google Search to find current information!

Research and analyze:

1. **Current Market Situation**
   - Current price and daily movement
   - Key price levels (Support/Resistance)
   - Technical indicators (Trend, RSI, Moving Averages)

2. **Fundamental Factors**
   - Supply & Demand situation
   - Inventories / Stockpiles
   - Production data from relevant countries
   - Seasonal factors

3. **Market-Moving News**
   - Geopolitical developments
   - Central bank policy (Fed, ECB)
   - Economic data
   - Weather/Natural disasters (if relevant)

4. **Sentiment & Positioning**
   - COT Report (Commercials vs Speculators)
   - ETF Flows
   - Analyst opinions

Based on your analysis, provide a clear recommendation:

📋 ACTION BOX
━━━━━━━━━━━━━━━━━━━━
Signal: [BUY/SELL/HOLD]
Entry: $XX.XX (ideal entry price)
Stop-Loss: $XX.XX (-X.X%)
Target 1: $XX.XX (+X.X%)
Target 2: $XX.XX (+X.X%)
Risk/Reward: X.X:1
━━━━━━━━━━━━━━━━━━━━

IMPORTANT: Write your ENTIRE response in {lang_name}."""

    # Use Gemini 3 with Google Search grounding
    model = genai.GenerativeModel(
        "gemini-3-flash-preview",
        tools="google_search_retrieval"
    )

    response = model.generate_content(prompt)

    return {
        "final_trade_decision": response.text,
        "commodity_mode": True
    }


def run_analysis(symbol: str, lang: str = "en", forced_direction: str = None) -> dict:
    """Run analysis - uses commodity analyzer for futures, TradingAgents for stocks.

    Args:
        symbol: Stock ticker or commodity symbol
        lang: Output language ("en" or "de")
        forced_direction: Optional forced direction ("long" or "short"). If None, LLM decides.
    """

    # Check if this is a commodity/futures symbol
    if is_commodity(symbol):
        print(f"Detected commodity: {get_commodity_name(symbol)}")
        return run_commodity_analysis(symbol, lang)

    # Regular stock analysis with TradingAgents
    from tradingagents.default_config import DEFAULT_CONFIG

    # Start with defaults and override LLM settings
    config = DEFAULT_CONFIG.copy()
    config.update({
        "llm_provider": "mixed",
        "quick_think_llm": "gemini-3-flash-preview",
        "deep_think_llm": "claude-opus-4-5-20251101",
        "deep_think_fallback": "gemini-3-pro-preview",
        "max_debate_rounds": 2,
        "max_risk_discuss_rounds": 1,
        "output_language": lang,  # Pass language to generate output directly in target language
        "forced_direction": forced_direction,  # Pass forced direction to risk manager
    })

    ta = TradingAgentsGraph(debug=False, config=config)
    today = date.today().isoformat()

    # Pass language and forced direction to propagate
    final_state, decision = ta.propagate(symbol, today, output_language=lang, forced_direction=forced_direction)

    return final_state


def main():
    """Main entry point."""
    # Get environment variables
    command = os.environ.get("COMMAND", "analyze")
    symbol = os.environ.get("SYMBOL", "").upper()
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

    if not symbol:
        msg = "❌ No symbol provided." if lang == "en" else "❌ Kein Symbol angegeben."
        send_telegram_message(chat_id, msg)
        return 1

    if not chat_id:
        print("Error: No CHAT_ID provided")
        return 1

    budget = float(budget_str) if budget_str and budget_str != "null" else None

    direction_str = f" ({direction.upper()})" if direction else ""
    print(f"Running analysis for {symbol}{direction_str} (budget: {budget}, lang: {lang})")

    try:
        # Get stock data
        stock_data = get_stock_data(symbol)
        print(f"Stock: {stock_data['name']} @ {stock_data['price']:.2f}")

        # Run analysis with optional forced direction
        result = run_analysis(symbol, lang, forced_direction=direction)
        print("Analysis complete")

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

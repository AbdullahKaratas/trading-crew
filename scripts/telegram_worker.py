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
    """Format analysis result for Telegram with language support."""
    decision = result.get("final_trade_decision", "")
    currency = stock_data['currency']
    price = stock_data['price']

    # Detect signal type
    decision_upper = decision.upper()[:200]
    if "BUY" in decision_upper:
        signal = "BUY" if lang == "en" else "KAUFEN"
        emoji = "🟢"
    elif "SELL" in decision_upper or "SHORT" in decision_upper:
        signal = "SELL" if lang == "en" else "VERKAUFEN"
        emoji = "🔴"
    else:
        signal = "HOLD" if lang == "en" else "HALTEN"
        emoji = "🟡"

    # No truncation - send_telegram_message handles long texts automatically

    # Language-specific labels
    if lang == "en":
        labels = {
            "price": "Price",
            "levels": "Key Levels",
            "support": "Support",
            "resistance": "Resistance",
            "entry_zone": "Entry Zone",
            "week52": "52W Range",
            "analysis": "Analysis",
            "position": "Position",
            "recommended": "Recommended",
            "max_risk": "Max Risk",
            "stop_loss": "Stop-Loss",
        }
    else:
        labels = {
            "price": "Kurs",
            "levels": "Wichtige Levels",
            "support": "Support",
            "resistance": "Widerstand",
            "entry_zone": "Einstiegszone",
            "week52": "52W Bereich",
            "analysis": "Analyse",
            "position": "Position",
            "recommended": "Empfohlen",
            "max_risk": "Max Risiko",
            "stop_loss": "Stop-Loss",
        }

    response = f"""
{emoji} *{signal}: {symbol}*
_{stock_data['name']}_

💵 *{labels['price']}:* {currency} {price:,.2f}

📍 *{labels['levels']}:*
├── {labels['support']} 1: {currency} {stock_data['support_1']:,.2f}
├── {labels['support']} 2: {currency} {stock_data['support_2']:,.2f}
├── {labels['resistance']} 1: {currency} {stock_data['resistance_1']:,.2f}
├── {labels['resistance']} 2: {currency} {stock_data['resistance_2']:,.2f}
├── 🎯 {labels['entry_zone']}: {currency} {stock_data['entry_zone_low']:,.2f} - {stock_data['entry_zone_high']:,.2f}
└── {labels['week52']}: {currency} {stock_data['week_52_low']:,.2f} - {stock_data['week_52_high']:,.2f}

📊 *{labels['analysis']}:*
{decision}
"""

    if budget:
        stop_loss_price = stock_data['support_1'] * 0.98  # 2% below support
        stop_loss_pct = ((price - stop_loss_price) / price) * 100
        position_size = budget * 0.4
        max_risk = position_size * (stop_loss_pct / 100)

        response += f"""
💰 *{labels['position']} (Budget: €{budget:,.0f}):*
├── {labels['recommended']}: €{budget * 0.3:,.0f} - €{budget * 0.5:,.0f}
├── {labels['stop_loss']}: {currency} {stop_loss_price:,.2f} (-{stop_loss_pct:.1f}%)
└── {labels['max_risk']}: €{max_risk:,.0f}
"""

    response += f"\n📈 [Chart](https://www.tradingview.com/chart/?symbol={symbol})"
    return response.strip()


def format_knockout_result(symbol: str, direction: str, result: dict, stock_data: dict, budget: float = None, lang: str = "de") -> str:
    """Format knockout analysis for Telegram with language support."""
    decision = result.get("final_trade_decision", "")

    price = stock_data["price"]

    if direction == "long":
        emoji = "📈"
        ko_level = stock_data["recent_low"] * 0.95  # 5% below support
        distance = ((price - ko_level) / price) * 100
        target1 = price * 1.05
        target2 = price * 1.10
    else:
        emoji = "📉"
        ko_level = stock_data["recent_high"] * 1.05  # 5% above resistance
        distance = ((ko_level - price) / price) * 100
        target1 = price * 0.95
        target2 = price * 0.90

    leverage = min(10, max(2, int(100 / distance)))

    # Detect recommendation from analysis
    decision_upper = decision.upper()[:500]
    is_de = lang == "de"

    if direction == "long":
        # For LONG: BUY = ✅ empfohlen, SELL = ❌ nicht empfohlen
        if "BUY" in decision_upper or "KAUFEN" in decision_upper:
            signal_emoji = "✅"
            signal_text = "EMPFOHLEN" if is_de else "RECOMMENDED"
        elif "SELL" in decision_upper or "VERKAUFEN" in decision_upper:
            signal_emoji = "❌"
            signal_text = "NICHT EMPFOHLEN" if is_de else "NOT RECOMMENDED"
        else:
            signal_emoji = "⚠️"
            signal_text = "NEUTRAL" if is_de else "NEUTRAL"
    else:
        # For SHORT: SELL = ✅ empfohlen, BUY = ❌ nicht empfohlen
        if "SELL" in decision_upper or "VERKAUFEN" in decision_upper or "SHORT" in decision_upper:
            signal_emoji = "✅"
            signal_text = "EMPFOHLEN" if is_de else "RECOMMENDED"
        elif "BUY" in decision_upper or "KAUFEN" in decision_upper:
            signal_emoji = "❌"
            signal_text = "NICHT EMPFOHLEN" if is_de else "NOT RECOMMENDED"
        else:
            signal_emoji = "⚠️"
            signal_text = "NEUTRAL" if is_de else "NEUTRAL"

    # No truncation - send_telegram_message handles long texts automatically

    response = f"""
{emoji} *{direction.upper()} KNOCKOUT: {symbol}*
_{stock_data['name']}_

{signal_emoji} *TL;DR: {direction.upper()} {signal_text}*

💵 *Kurs:* {stock_data['currency']} {price:,.2f}

🎯 *Knockout-Empfehlung:*
├── KO-Level: {stock_data['currency']} {ko_level:,.2f}
├── Abstand: {distance:.1f}%
├── Empf. Hebel: {leverage}x
└── Support: {stock_data['currency']} {stock_data['recent_low']:,.2f}

📊 *Kursziele:*
├── Target 1: {stock_data['currency']} {target1:,.2f}
└── Target 2: {stock_data['currency']} {target2:,.2f}
"""

    if budget:
        response += f"""
💰 *Position (Budget: €{budget:,.0f}):*
├── Empf. Einsatz: €{budget * 0.2:,.0f}
└── Max Verlust (KO): €{budget * 0.2:,.0f}
"""

    response += f"""
💡 *Analyse:*
{decision}

⚠️ *Risiko:* Bei KO = Totalverlust!

📈 [Chart](https://www.tradingview.com/chart/?symbol={symbol})
"""
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

    # Language-specific prompt
    if lang == "de":
        prompt = f"""Du bist ein erfahrener Rohstoff-Analyst. Analysiere {commodity_name} ({symbol}) für heute ({today}).

WICHTIG: Nutze Google Search um aktuelle Informationen zu finden!

Recherchiere und analysiere:

1. **Aktuelle Marktsituation**
   - Aktueller Preis und Tagesentwicklung
   - Wichtige Preislevel (Support/Resistance)
   - Technische Indikatoren (Trend, RSI, Moving Averages)

2. **Fundamentale Faktoren**
   - Angebot & Nachfrage Situation
   - Lagerbestände / Inventories
   - Produktionszahlen relevanter Länder
   - Saisonale Faktoren

3. **Marktbewegende News**
   - Geopolitische Entwicklungen
   - Zentralbank-Politik (Fed, EZB)
   - Wirtschaftsdaten
   - Wetter/Naturkatastrophen (falls relevant)

4. **Sentiment & Positioning**
   - COT Report (Commercials vs Speculators)
   - ETF Flows
   - Analystenmeinungen

Basierend auf deiner Analyse, gib eine klare Empfehlung:

📋 ACTION BOX
━━━━━━━━━━━━━━━━━━━━
Signal: [BUY/SELL/HOLD]
Entry: $XX.XX (idealer Einstiegspreis)
Stop-Loss: $XX.XX (-X.X%)
Target 1: $XX.XX (+X.X%)
Target 2: $XX.XX (+X.X%)
Risk/Reward: X.X:1
━━━━━━━━━━━━━━━━━━━━

Schreibe die GESAMTE Analyse auf Deutsch."""
    else:
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
━━━━━━━━━━━━━━━━━━━━"""

    # Use Gemini with Google Search grounding
    model = genai.GenerativeModel(
        "gemini-2.0-flash",  # 2.0-flash supports Google Search grounding
        tools="google_search_retrieval"
    )

    response = model.generate_content(prompt)

    return {
        "final_trade_decision": response.text,
        "commodity_mode": True
    }


def run_analysis(symbol: str, lang: str = "en") -> dict:
    """Run analysis - uses commodity analyzer for futures, TradingAgents for stocks."""

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
    })

    ta = TradingAgentsGraph(debug=False, config=config)
    today = date.today().isoformat()

    # Pass language to propagate - model will generate in target language directly
    final_state, decision = ta.propagate(symbol, today, output_language=lang)

    return final_state


def main():
    """Main entry point."""
    # Get environment variables
    command = os.environ.get("COMMAND", "analyze")
    symbol = os.environ.get("SYMBOL", "").upper()
    budget_str = os.environ.get("BUDGET", "")
    chat_id = os.environ.get("CHAT_ID")
    username = os.environ.get("USERNAME", "User")
    lang = os.environ.get("LANG", "de").lower()

    # Validate language
    if lang not in ["de", "en"]:
        lang = "de"

    if not symbol:
        msg = "❌ No symbol provided." if lang == "en" else "❌ Kein Symbol angegeben."
        send_telegram_message(chat_id, msg)
        return 1

    if not chat_id:
        print("Error: No CHAT_ID provided")
        return 1

    budget = float(budget_str) if budget_str and budget_str != "null" else None

    print(f"Running {command} analysis for {symbol} (budget: {budget}, lang: {lang})")

    try:
        # Get stock data
        stock_data = get_stock_data(symbol)
        print(f"Stock: {stock_data['name']} @ {stock_data['price']:.2f}")

        # Run analysis
        result = run_analysis(symbol, lang)
        print("Analysis complete")

        # Format and send result
        if command in ["long", "short"]:
            message = format_knockout_result(symbol, command, result, stock_data, budget, lang)
        else:
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

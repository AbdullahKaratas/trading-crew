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
    """Send a message to Telegram."""
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    url = f"https://api.telegram.org/bot{token}/sendMessage"

    # Telegram has a 4096 character limit
    if len(text) > 4000:
        text = text[:3997] + "..."

    response = requests.post(url, json={
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    })
    return response.ok


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

    # Truncate decision
    if len(decision) > 900:
        decision = decision[:900] + "..."

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

    # Truncate decision
    if len(decision) > 800:
        decision = decision[:800] + "..."

    response = f"""
{emoji} *{direction.upper()} KNOCKOUT: {symbol}*
_{stock_data['name']}_

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
{decision[:500]}...

⚠️ *Risiko:* Bei KO = Totalverlust!

📈 [Chart](https://www.tradingview.com/chart/?symbol={symbol})
"""
    return response.strip()


def run_analysis(symbol: str) -> dict:
    """Run TradingAgents analysis."""
    from tradingagents.default_config import DEFAULT_CONFIG

    # Start with defaults and override LLM settings
    config = DEFAULT_CONFIG.copy()
    config.update({
        "llm_provider": "mixed",
        "quick_think_llm": "gemini-2.0-flash",
        "deep_think_llm": "claude-opus-4-5-20251101",
        "deep_think_fallback": "gemini-2.5-pro",
        "max_debate_rounds": 2,
        "max_risk_discuss_rounds": 1,
    })

    ta = TradingAgentsGraph(debug=False, config=config)
    today = date.today().isoformat()
    final_state, decision = ta.propagate(symbol, today)

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
        result = run_analysis(symbol)
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

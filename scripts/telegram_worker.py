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
    """Get current stock data."""
    ticker = yf.Ticker(symbol)
    info = ticker.info
    hist = ticker.history(period="3mo")

    if hist.empty:
        raise ValueError(f"No data found for {symbol}")

    current_price = hist["Close"].iloc[-1]
    recent_low = hist["Low"].tail(20).min()
    recent_high = hist["High"].tail(20).max()

    return {
        "name": info.get("shortName", symbol),
        "price": current_price,
        "currency": info.get("currency", "USD"),
        "recent_low": recent_low,
        "recent_high": recent_high,
        "sector": info.get("sector", "Unknown"),
    }


def format_analyze_result(symbol: str, result: dict, stock_data: dict, budget: float = None) -> str:
    """Format analysis result for Telegram."""
    decision = result.get("final_trade_decision", "")

    # Detect signal type
    decision_upper = decision.upper()[:200]
    if "BUY" in decision_upper:
        signal = "BUY"
        emoji = "🟢"
    elif "SELL" in decision_upper or "SHORT" in decision_upper:
        signal = "SELL"
        emoji = "🔴"
    else:
        signal = "HOLD"
        emoji = "🟡"

    # Truncate decision
    if len(decision) > 1200:
        decision = decision[:1200] + "..."

    response = f"""
{emoji} *{signal}: {symbol}*
_{stock_data['name']}_

💵 *Kurs:* {stock_data['currency']} {stock_data['price']:,.2f}

📊 *Analyse:*
{decision}
"""

    if budget:
        response += f"""
💰 *Position (Budget: €{budget:,.0f}):*
├── Empf. Position: €{budget * 0.3:,.0f} - €{budget * 0.5:,.0f}
└── Max Risiko (8% SL): €{budget * 0.5 * 0.08:,.0f}
"""

    response += f"\n📈 [Chart](https://www.tradingview.com/chart/?symbol={symbol})"
    return response.strip()


def format_knockout_result(symbol: str, direction: str, result: dict, stock_data: dict, budget: float = None) -> str:
    """Format knockout analysis for Telegram."""
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

    if not symbol:
        send_telegram_message(chat_id, "❌ Kein Symbol angegeben.")
        return 1

    if not chat_id:
        print("Error: No CHAT_ID provided")
        return 1

    budget = float(budget_str) if budget_str and budget_str != "null" else None

    print(f"Running {command} analysis for {symbol} (budget: {budget})")

    try:
        # Get stock data
        stock_data = get_stock_data(symbol)
        print(f"Stock: {stock_data['name']} @ {stock_data['price']:.2f}")

        # Run analysis
        result = run_analysis(symbol)
        print("Analysis complete")

        # Format and send result
        if command in ["long", "short"]:
            message = format_knockout_result(symbol, command, result, stock_data, budget)
        else:
            message = format_analyze_result(symbol, result, stock_data, budget)

        success = send_telegram_message(chat_id, message)

        if success:
            print(f"Result sent to chat {chat_id}")
            return 0
        else:
            print("Failed to send message")
            return 1

    except Exception as e:
        error_msg = f"❌ Fehler bei Analyse von *{symbol}*:\n\n`{str(e)[:200]}`"
        send_telegram_message(chat_id, error_msg)
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

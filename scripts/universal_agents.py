#!/usr/bin/env python3
"""
Universal Multi-Agent Analysis System using Gemini + Google Search.

Works for ALL assets: Stocks, Commodities, ETFs, Crypto, etc.
Replaces yfinance/Alpha Vantage with real-time Google Search data.

Architecture:
1. Data Gatherer - Price, Technicals, News, Fundamentals via Search
2. Investment Debate - Bull vs Bear (2 rounds)
3. Investment Judge - LONG/SHORT/HOLD
4. Risk Debate - Risky vs Safe vs Neutral
5. Risk Judge - Structured JSON output
"""

import os
import json
import re
from datetime import date
from typing import TypedDict

from google import genai
from google.genai import types


# Same JSON schema as TradingAgents
TRADE_DECISION_SCHEMA = {
    "signal": "LONG | SHORT | HOLD | IGNORE",
    "confidence": 0.75,
    "unable_to_assess": False,
    "price_usd": 0.0,
    "price_eur": 0.0,
    "strategies": {
        "conservative": {"ko_level_usd": 0.0, "distance_pct": 0.0, "risk": "low"},
        "moderate": {"ko_level_usd": 0.0, "distance_pct": 0.0, "risk": "medium"},
        "aggressive": {"ko_level_usd": 0.0, "distance_pct": 0.0, "risk": "high"},
    },
    "hold_alternative": None,
    "support_zones": [{"level_usd": 0.0, "description": ""}],
    "resistance_zones": [{"level_usd": 0.0, "description": ""}],
    "detailed_analysis": "",
}


class UniversalDebateState(TypedDict):
    """State for the universal multi-agent debate."""
    symbol: str
    asset_name: str
    asset_type: str  # "stock", "commodity", "etf", "crypto"
    current_price: float
    price_source: str
    today: str
    lang: str

    # Data from gatherer
    price_data: str
    technical_data: str
    news_data: str
    fundamental_data: str

    # Investment debate
    bull_arguments: str
    bear_arguments: str
    investment_debate_history: str
    investment_decision: str

    # Risk debate
    risky_arguments: str
    safe_arguments: str
    neutral_arguments: str
    risk_debate_history: str

    # Final output
    final_decision: dict


def get_gemini_client():
    """Get configured Gemini client."""
    return genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))


def call_gemini_with_search(prompt: str, max_retries: int = 3) -> str:
    """Call Gemini 3 Flash with Google Search grounding."""
    import time
    client = get_gemini_client()

    config = types.GenerateContentConfig(
        tools=[types.Tool(google_search=types.GoogleSearch())]
    )

    response = None
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model="gemini-3-flash-preview",
                contents=prompt,
                config=config
            )
            if response and response.text:
                return response.text
        except Exception as e:
            if "429" in str(e) and attempt < max_retries - 1:
                time.sleep(5 * (attempt + 1))  # Exponential backoff
                continue
            raise

    return (response.text if response and response.text else "") or ""


def call_gemini_deep_think(prompt: str, max_retries: int = 3) -> str:
    """Call Gemini Pro for deep thinking (judges)."""
    import time
    client = get_gemini_client()

    response = None
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model="gemini-3-pro-preview",
                contents=prompt
            )
            if response and response.text:
                return response.text
        except Exception as e:
            if "429" in str(e) and attempt < max_retries - 1:
                time.sleep(5 * (attempt + 1))
                continue
            raise

    return (response.text if response and response.text else "") or ""


def call_gemini_pro_with_search(prompt: str, max_retries: int = 3) -> str:
    """Call Gemini Pro with Google Search for final judge."""
    import time
    client = get_gemini_client()

    config = types.GenerateContentConfig(
        tools=[types.Tool(google_search=types.GoogleSearch())]
    )

    response = None
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model="gemini-3-pro-preview",
                contents=prompt,
                config=config
            )
            if response and response.text:
                return response.text
        except Exception as e:
            if "429" in str(e) and attempt < max_retries - 1:
                time.sleep(5 * (attempt + 1))
                continue
            raise

    return (response.text if response and response.text else "") or ""


def detect_asset_type(symbol: str) -> str:
    """Detect asset type from symbol."""
    symbol_lower = symbol.lower()

    # Commodities
    if symbol_lower in ["silver", "gold", "oil", "copper", "platinum", "palladium"]:
        return "commodity"
    if symbol.endswith("=F"):
        return "commodity"

    # Crypto
    if symbol_lower in ["btc", "eth", "bitcoin", "ethereum"] or symbol.endswith("-USD"):
        return "crypto"

    # ETFs (common ones)
    etfs = ["spy", "qqq", "iwm", "dia", "voo", "vti", "arkk", "xlf", "xle"]
    if symbol_lower in etfs:
        return "etf"

    # Default to stock
    return "stock"


# =============================================================================
# PHASE 1: DATA GATHERING (All via Gemini + Search)
# =============================================================================

def data_gatherer(symbol: str, trade_date: str, lang: str = "en") -> dict:
    """
    Gather comprehensive data using Gemini + Google Search.
    Works for any asset type.
    """
    asset_type = detect_asset_type(symbol)
    lang_instruction = "Respond in German." if lang == "de" else "Respond in English."

    # 1. Get current price
    price_prompt = f"""Search for the current price of {symbol} as of {trade_date}.
Return ONLY a JSON object (no markdown):
{{"price_usd": 100.00, "asset_name": "Company Name", "source": "yahoo.com"}}"""

    price_response = call_gemini_with_search(price_prompt) or ""

    # Parse price
    try:
        text = price_response.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
        price_data = json.loads(text)
        current_price = price_data.get("price_usd", 0)
        asset_name = price_data.get("asset_name", symbol)
        price_source = price_data.get("source", "unknown")
    except (json.JSONDecodeError, ValueError, AttributeError):
        match = re.search(r'\$?([\d,]+\.?\d*)', price_response or "")
        current_price = float(match.group(1).replace(",", "")) if match else 0
        asset_name = symbol
        price_source = "extracted"

    # 2. Get technical analysis data
    technical_prompt = f"""Search for technical analysis of {symbol} as of {trade_date}.

Provide:
- Current price and recent price action
- 50-day and 200-day Moving Averages (if available)
- RSI (Relative Strength Index)
- MACD status
- Key support levels (2-3)
- Key resistance levels (2-3)
- Overall trend (bullish/bearish/neutral)
- Volume analysis

{lang_instruction}
Keep response under 500 words."""

    technical_data = call_gemini_with_search(technical_prompt) or "No technical data available."

    # 3. Get news and events
    news_prompt = f"""Search for latest news about {symbol} from {trade_date}.

Focus on:
- Recent earnings/financial reports
- Analyst ratings and price targets
- Major announcements
- Sector/industry news
- Market-moving events

{lang_instruction}
Keep response under 400 words."""

    news_data = call_gemini_with_search(news_prompt) or "No recent news available."

    # 4. Get fundamentals (for stocks) or market context (for commodities)
    if asset_type == "stock":
        fundamental_prompt = f"""Search for fundamental data of {symbol} as of {trade_date}.

Provide:
- Market Cap
- P/E Ratio
- Revenue growth
- Profit margins
- Debt levels
- Competitive position
- Recent insider activity

{lang_instruction}
Keep response under 400 words."""
    else:
        fundamental_prompt = f"""Search for market context of {symbol} as of {trade_date}.

Provide:
- Supply and demand factors
- Seasonal patterns
- Macro economic factors
- COT positioning (if applicable)
- ETF flows
- Central bank policy impact

{lang_instruction}
Keep response under 400 words."""

    fundamental_data = call_gemini_with_search(fundamental_prompt) or "No fundamental data available."

    return {
        "current_price": current_price,
        "asset_name": asset_name,
        "asset_type": asset_type,
        "price_source": price_source,
        "price_data": f"Current Price: ${current_price:.2f} (Source: {price_source})",
        "technical_data": technical_data,
        "news_data": news_data,
        "fundamental_data": fundamental_data,
    }


# =============================================================================
# PHASE 2: INVESTMENT DEBATE (Bull vs Bear)
# =============================================================================

def bull_analyst(state: UniversalDebateState) -> str:
    """Bull analyst makes the case FOR going LONG."""
    lang_instruction = "Respond entirely in German." if state["lang"] == "de" else "Respond entirely in English."

    bear_args = state.get("bear_arguments", "")
    counter_section = f"\n## Bear's Arguments to Counter:\n{bear_args}\n\nDirectly address and counter each point." if bear_args else ""

    prompt = f"""You are a BULLISH Analyst advocating for a LONG position in {state['symbol']}.

## Current Data (as of {state['today']})
- **Asset**: {state['asset_name']} ({state['asset_type']})
- **Price**: ${state['current_price']:.2f}

## Technical Analysis
{state['technical_data']}

## News & Events
{state['news_data']}

## Fundamentals/Context
{state['fundamental_data']}
{counter_section}

## Your Task
Build a strong case for why {state['symbol']} will RISE. Focus on:
1. Bullish technical signals
2. Positive catalysts
3. Strong fundamentals or market tailwinds
4. Why bears are wrong

Be specific with price targets. {lang_instruction}
Keep response under 500 words."""

    return call_gemini_with_search(prompt, max_retries=2)


def bear_analyst(state: UniversalDebateState) -> str:
    """Bear analyst makes the case AGAINST going long."""
    lang_instruction = "Respond entirely in German." if state["lang"] == "de" else "Respond entirely in English."

    bull_args = state.get("bull_arguments", "")
    counter_section = f"\n## Bull's Arguments to Counter:\n{bull_args}\n\nDirectly address and counter each point." if bull_args else ""

    prompt = f"""You are a BEARISH Analyst arguing AGAINST a long position in {state['symbol']}.

## Current Data (as of {state['today']})
- **Asset**: {state['asset_name']} ({state['asset_type']})
- **Price**: ${state['current_price']:.2f}

## Technical Analysis
{state['technical_data']}

## News & Events
{state['news_data']}

## Fundamentals/Context
{state['fundamental_data']}
{counter_section}

## Your Task
Build a strong case for why {state['symbol']} will FALL. Focus on:
1. Bearish technical signals
2. Negative catalysts or risks
3. Weak fundamentals or headwinds
4. Why bulls are wrong

Be specific with downside targets. {lang_instruction}
Keep response under 500 words."""

    return call_gemini_with_search(prompt, max_retries=2)


def investment_judge(state: UniversalDebateState) -> str:
    """Investment Judge decides LONG/SHORT/HOLD."""
    lang_instruction = "Respond entirely in German." if state["lang"] == "de" else "Respond entirely in English."

    prompt = f"""You are the INVESTMENT JUDGE for {state['symbol']} analysis.

## Current Price: ${state['current_price']:.2f}
## Date: {state['today']}

## Full Debate History
{state['investment_debate_history']}

## Your Task
1. Evaluate which side presented stronger evidence
2. Identify the 2-3 most important factors
3. Acknowledge main risks
4. Make a decision: **LONG**, **SHORT**, or **HOLD**

End with exactly one of:
- RECOMMENDATION: **LONG**
- RECOMMENDATION: **SHORT**
- RECOMMENDATION: **HOLD**

{lang_instruction}
Keep response under 400 words."""

    return call_gemini_deep_think(prompt)


# =============================================================================
# PHASE 3: RISK DEBATE (Risky vs Safe vs Neutral)
# =============================================================================

def risky_analyst(state: UniversalDebateState) -> str:
    """Risky analyst advocates for aggressive strategies."""
    lang_instruction = "Respond entirely in German." if state["lang"] == "de" else "Respond entirely in English."

    prompt = f"""You are the AGGRESSIVE Risk Analyst for {state['symbol']}.

## Investment Decision: **{state['investment_decision']}**
## Current Price: ${state['current_price']:.2f}

Advocate for HIGH-REWARD strategies:
- Tight stop-losses (5-8% from price)
- Maximize upside potential
- Why waiting is wrong

Propose aggressive knockout levels. {lang_instruction}
Keep response under 300 words."""

    return call_gemini_with_search(prompt, max_retries=2)


def safe_analyst(state: UniversalDebateState) -> str:
    """Safe analyst prioritizes capital preservation."""
    lang_instruction = "Respond entirely in German." if state["lang"] == "de" else "Respond entirely in English."

    prompt = f"""You are the CONSERVATIVE Risk Analyst for {state['symbol']}.

## Investment Decision: **{state['investment_decision']}**
## Current Price: ${state['current_price']:.2f}
## Risky Analyst's Position:
{state.get('risky_arguments', '')}

Advocate for CAPITAL PRESERVATION:
- Wide stop-losses (15-25% from price)
- Why aggressive approach is dangerous
- Wait for better entries

Propose conservative knockout levels. {lang_instruction}
Keep response under 300 words."""

    return call_gemini_with_search(prompt, max_retries=2)


def neutral_analyst(state: UniversalDebateState) -> str:
    """Neutral analyst provides balanced perspective."""
    lang_instruction = "Respond entirely in German." if state["lang"] == "de" else "Respond entirely in English."

    prompt = f"""You are the NEUTRAL Risk Analyst for {state['symbol']}.

## Investment Decision: **{state['investment_decision']}**
## Current Price: ${state['current_price']:.2f}

## Risky Position:
{state.get('risky_arguments', '')}

## Safe Position:
{state.get('safe_arguments', '')}

Provide BALANCE:
- Where is Risky too aggressive?
- Where is Safe too cautious?
- What's the practical middle ground?

Propose moderate knockout levels. {lang_instruction}
Keep response under 300 words."""

    return call_gemini_with_search(prompt, max_retries=2)


# =============================================================================
# PHASE 4: FINAL RISK JUDGE
# =============================================================================

def risk_judge(state: UniversalDebateState) -> dict:
    """Risk Judge outputs structured JSON decision."""
    lang_instruction = "Respond entirely in German for detailed_analysis." if state["lang"] == "de" else "Respond entirely in English for detailed_analysis."

    eur_rate = 0.95
    price_eur = state['current_price'] * eur_rate

    prompt = f"""You are the FINAL RISK JUDGE for {state['symbol']}.

## TODAY'S DATE: {state['today']}
## AUTHORITATIVE PRICE: ${state['current_price']:.2f} USD / €{price_eur:.2f} EUR

Use Google Search to verify latest news and price for {state['symbol']} today.

## Investment Decision: {state['investment_decision']}

## Risk Debate Summary:
### Risky: {state['risky_arguments'][:500]}
### Safe: {state['safe_arguments'][:500]}
### Neutral: {state['neutral_arguments'][:500]}

## Output Requirements
Return ONLY valid JSON (no markdown):

{{
    "signal": "LONG or SHORT or HOLD",
    "confidence": 0.75,
    "unable_to_assess": false,
    "price_usd": {state['current_price']:.2f},
    "price_eur": {price_eur:.2f},
    "strategies": {{
        "conservative": {{"ko_level_usd": <15-25% from price>, "distance_pct": <15-25>, "risk": "low"}},
        "moderate": {{"ko_level_usd": <10-15% from price>, "distance_pct": <10-15>, "risk": "medium"}},
        "aggressive": {{"ko_level_usd": <5-10% from price>, "distance_pct": <5-10>, "risk": "high"}}
    }},
    "hold_alternative": null,
    "support_zones": [
        {{"level_usd": <price>, "description": "<reason>"}},
        {{"level_usd": <price>, "description": "<reason>"}}
    ],
    "resistance_zones": [
        {{"level_usd": <price>, "description": "<reason>"}},
        {{"level_usd": <price>, "description": "<reason>"}}
    ],
    "detailed_analysis": "<300-500 word analysis. {lang_instruction}>"
}}

For LONG: KO levels BELOW current price
For SHORT: KO levels ABOVE current price"""

    response = call_gemini_pro_with_search(prompt) or ""

    # Parse JSON
    try:
        text = response.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
        if text.endswith("```"):
            text = text[:-3].strip()

        return json.loads(text)
    except (json.JSONDecodeError, AttributeError) as e:
        return {
            "signal": "IGNORE",
            "confidence": 0.0,
            "unable_to_assess": True,
            "price_usd": state['current_price'],
            "price_eur": price_eur,
            "strategies": {},
            "support_zones": [],
            "resistance_zones": [],
            "detailed_analysis": f"Error parsing: {str(e)}\n\nRaw: {(response or '')[:500]}",
        }


# =============================================================================
# MAIN ORCHESTRATOR
# =============================================================================

def run_universal_analysis(symbol: str, trade_date: str = None, lang: str = "en") -> dict:
    """
    Run full multi-agent analysis using only Gemini + Google Search.

    Works for: Stocks, Commodities, ETFs, Crypto

    Args:
        symbol: Any ticker/asset (AAPL, Silver, BTC, SPY, etc.)
        trade_date: Analysis date (default: today)
        lang: Output language ("en" or "de")
    """
    if trade_date is None:
        trade_date = date.today().isoformat()

    print(f"\n{'='*60}")
    print(f"UNIVERSAL MULTI-AGENT ANALYSIS: {symbol}")
    print(f"Date: {trade_date}")
    print(f"{'='*60}")

    # Phase 1: Data Gathering
    print("\n[1/5] Gathering data via Google Search...")
    gathered_data = data_gatherer(symbol, trade_date, lang)

    print(f"  - Asset: {gathered_data['asset_name']} ({gathered_data['asset_type']})")
    print(f"  - Price: ${gathered_data['current_price']:.2f} (source: {gathered_data['price_source']})")

    # Initialize state
    state: UniversalDebateState = {
        "symbol": symbol.upper(),
        "asset_name": gathered_data["asset_name"],
        "asset_type": gathered_data["asset_type"],
        "current_price": gathered_data["current_price"],
        "price_source": gathered_data["price_source"],
        "today": trade_date,
        "lang": lang,
        "price_data": gathered_data["price_data"],
        "technical_data": gathered_data["technical_data"],
        "news_data": gathered_data["news_data"],
        "fundamental_data": gathered_data["fundamental_data"],
        "bull_arguments": "",
        "bear_arguments": "",
        "investment_debate_history": "",
        "investment_decision": "",
        "risky_arguments": "",
        "safe_arguments": "",
        "neutral_arguments": "",
        "risk_debate_history": "",
        "final_decision": {},
    }

    # Phase 2: Investment Debate (2 rounds)
    print("\n[2/5] Investment Debate: Bull vs Bear...")
    debate_history = ""

    for round_num in range(2):
        print(f"  Round {round_num + 1}/2:")

        print("    - Bull Analyst...")
        bull_response = bull_analyst(state)
        state["bull_arguments"] = bull_response
        debate_history += f"\n\n### BULL (Round {round_num + 1}):\n{bull_response}"

        print("    - Bear Analyst...")
        bear_response = bear_analyst(state)
        state["bear_arguments"] = bear_response
        debate_history += f"\n\n### BEAR (Round {round_num + 1}):\n{bear_response}"

        state["investment_debate_history"] = debate_history

    # Phase 3: Investment Judge
    print("\n[3/5] Investment Judge deciding...")
    judge_response = investment_judge(state)
    state["investment_debate_history"] += f"\n\n### JUDGE:\n{judge_response}"

    if "**LONG**" in judge_response:
        state["investment_decision"] = "LONG"
    elif "**SHORT**" in judge_response:
        state["investment_decision"] = "SHORT"
    else:
        state["investment_decision"] = "HOLD"

    print(f"  Decision: {state['investment_decision']}")

    # Phase 4: Risk Debate
    print("\n[4/5] Risk Debate: Risky vs Safe vs Neutral...")

    print("    - Risky Analyst...")
    state["risky_arguments"] = risky_analyst(state)

    print("    - Safe Analyst...")
    state["safe_arguments"] = safe_analyst(state)

    print("    - Neutral Analyst...")
    state["neutral_arguments"] = neutral_analyst(state)

    # Phase 5: Final Risk Judge
    print("\n[5/5] Risk Judge creating final decision...")
    final_decision = risk_judge(state)
    state["final_decision"] = final_decision

    print(f"  Signal: {final_decision.get('signal', 'UNKNOWN')}")
    print(f"  Confidence: {final_decision.get('confidence', 0):.0%}")

    print(f"\n{'='*60}")
    print("ANALYSIS COMPLETE")
    print(f"{'='*60}\n")

    return {
        "trade_decision": final_decision,
        "final_trade_decision": final_decision.get("detailed_analysis", ""),
        "universal_mode": True,
    }


if __name__ == "__main__":
    import sys
    symbol = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    lang = sys.argv[2] if len(sys.argv) > 2 else "de"

    result = run_universal_analysis(symbol, lang=lang)
    print(json.dumps(result["trade_decision"], indent=2, ensure_ascii=False))

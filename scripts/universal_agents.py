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

import json
from datetime import date
from typing import TypedDict

from gemini_utils import (
    call_gemini_flash,
    call_gemini_pro,
    call_gemini_json,
    extract_price_from_text,
    get_language_instruction,
    parse_json_response,
    TradeDecisionSchema,
)


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


# Asset type detection constants
COMMODITIES = {"silver", "gold", "oil", "copper", "platinum", "palladium"}
CRYPTO_SYMBOLS = {"btc", "eth", "bitcoin", "ethereum"}
ETFS = {"spy", "qqq", "iwm", "dia", "voo", "vti", "arkk", "xlf", "xle"}


def detect_asset_type(symbol: str) -> str:
    """Detect asset type from symbol."""
    symbol_lower = symbol.lower()

    if symbol_lower in COMMODITIES or symbol.endswith("=F"):
        return "commodity"

    if symbol_lower in CRYPTO_SYMBOLS or symbol.endswith("-USD"):
        return "crypto"

    if symbol_lower in ETFS:
        return "etf"

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
    lang_instruction = get_language_instruction(lang, "Respond")

    # 1. Get current price
    price_prompt = f"""Search for the current price of {symbol} as of {trade_date}.
Return ONLY a JSON object (no markdown):
{{"price_usd": 100.00, "asset_name": "Company Name", "source": "yahoo.com"}}"""

    price_response = call_gemini_flash(price_prompt, use_search=True) or ""

    # Parse price from response
    price_data = parse_json_response(price_response)
    if price_data:
        current_price = price_data.get("price_usd", 0)
        asset_name = price_data.get("asset_name", symbol)
        price_source = price_data.get("source", "unknown")
    else:
        # Fallback: extract price from text
        current_price = extract_price_from_text(price_response) or 0
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

    technical_data = call_gemini_flash(technical_prompt, use_search=True) or "No technical data available."

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

    news_data = call_gemini_flash(news_prompt, use_search=True) or "No recent news available."

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

    fundamental_data = call_gemini_flash(fundamental_prompt, use_search=True) or "No fundamental data available."

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
    lang_instruction = get_language_instruction(state["lang"])

    bear_args = state.get("bear_arguments", "")
    counter_section = ""
    if bear_args:
        counter_section = f"\n## Bear's Arguments to Counter:\n{bear_args}\n\nDirectly address and counter each point."

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

    return call_gemini_flash(prompt, use_search=True, max_retries=2)


def bear_analyst(state: UniversalDebateState) -> str:
    """Bear analyst makes the case AGAINST going long."""
    lang_instruction = get_language_instruction(state["lang"])

    bull_args = state.get("bull_arguments", "")
    counter_section = ""
    if bull_args:
        counter_section = f"\n## Bull's Arguments to Counter:\n{bull_args}\n\nDirectly address and counter each point."

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

    return call_gemini_flash(prompt, use_search=True, max_retries=2)


def investment_judge(state: UniversalDebateState) -> str:
    """Investment Judge decides LONG/SHORT/HOLD."""
    lang_instruction = get_language_instruction(state["lang"])

    prompt = f"""You are the INVESTMENT JUDGE for {state['symbol']} analysis.

## Current Price: ${state['current_price']:.2f}
## Date: {state['today']}

Use Google Search to verify the latest news and current situation for {state['symbol']}.

## Full Debate History
{state['investment_debate_history']}

## Your Task
1. Verify current market conditions via Google Search
2. Evaluate which side presented stronger evidence
3. Identify the 2-3 most important factors
4. Acknowledge main risks
5. Make a decision: **LONG**, **SHORT**, or **HOLD**

End with exactly one of:
- RECOMMENDATION: **LONG**
- RECOMMENDATION: **SHORT**
- RECOMMENDATION: **HOLD**

{lang_instruction}
Keep response under 400 words."""

    return call_gemini_pro(prompt, use_search=True)


# =============================================================================
# PHASE 3: RISK DEBATE (Risky vs Safe vs Neutral)
# =============================================================================

def risky_analyst(state: UniversalDebateState) -> str:
    """Risky analyst advocates for aggressive strategies."""
    lang_instruction = get_language_instruction(state["lang"])

    prompt = f"""You are the AGGRESSIVE Risk Analyst for {state['symbol']}.

## Investment Decision: **{state['investment_decision']}**
## Current Price: ${state['current_price']:.2f}

Advocate for HIGH-REWARD strategies:
- Tight stop-losses (5-8% from price)
- Maximize upside potential
- Why waiting is wrong

Propose aggressive knockout levels. {lang_instruction}
Keep response under 300 words."""

    return call_gemini_flash(prompt, use_search=True, max_retries=2)


def safe_analyst(state: UniversalDebateState) -> str:
    """Safe analyst prioritizes capital preservation."""
    lang_instruction = get_language_instruction(state["lang"])

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

    return call_gemini_flash(prompt, use_search=True, max_retries=2)


def neutral_analyst(state: UniversalDebateState) -> str:
    """Neutral analyst provides balanced perspective."""
    lang_instruction = get_language_instruction(state["lang"])

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

    return call_gemini_flash(prompt, use_search=True, max_retries=2)


# =============================================================================
# PHASE 4: FINAL RISK JUDGE
# =============================================================================

def risk_judge(state: UniversalDebateState) -> dict:
    """Risk Judge outputs structured JSON decision."""
    lang_instruction = get_language_instruction(state["lang"], "Write")

    eur_rate = 0.95
    price_eur = state['current_price'] * eur_rate

    prompt = f"""You are the FINAL RISK JUDGE for {state['symbol']}.

## TODAY'S DATE: {state['today']}
## AUTHORITATIVE PRICE: ${state['current_price']:.2f} USD / {price_eur:.2f} EUR

Use Google Search to verify latest news and price for {state['symbol']} today.

## Investment Decision: {state['investment_decision']}

## Investment Debate (Why this decision was made):
{state['investment_debate_history']}

## Risk Debate Summary:
### Risky Analyst: {state['risky_arguments']}
### Safe Analyst: {state['safe_arguments']}
### Neutral Analyst: {state['neutral_arguments']}

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
    "detailed_analysis": "<300-500 word analysis including timeframe reasoning. {lang_instruction}>",
    "timeframes": {{
        "short_term": "LONG or SHORT or HOLD",
        "medium_term": "LONG or SHORT or HOLD",
        "long_term": "LONG or SHORT or HOLD"
    }}
}}

**Timeframe Guidelines:**
- **short_term** (days-weeks): Based on RSI, MACD, immediate momentum
- **medium_term** (weeks-months): Based on trend, support/resistance, earnings
- **long_term** (months-years): Based on fundamentals, macro trends, industry position

Timeframes CAN differ (e.g., SHORT short_term due to overbought, LONG long_term for strong fundamentals).
The main "signal" should match your PRIMARY recommendation.

For LONG: KO levels BELOW current price
For SHORT: KO levels ABOVE current price"""

    # Use call_gemini_json with structured output schema
    # The schema guarantees valid JSON format - retries only for API errors
    result = call_gemini_json(
        prompt,
        model="gemini-3-pro-preview",
        use_search=True,
        max_retries=3,
        schema=TradeDecisionSchema,
    )

    if result:
        return result

    # Return error state if all retries failed
    return {
        "signal": "IGNORE",
        "confidence": 0.0,
        "unable_to_assess": True,
        "price_usd": state['current_price'],
        "price_eur": price_eur,
        "strategies": {},
        "support_zones": [],
        "resistance_zones": [],
        "detailed_analysis": "Error: Could not get valid JSON after 3 attempts.",
        "timeframes": {"short_term": "HOLD", "medium_term": "HOLD", "long_term": "HOLD"},
    }


def _extract_decision(judge_response: str) -> str:
    """Extract investment decision from judge response text."""
    if "**LONG**" in judge_response:
        return "LONG"
    if "**SHORT**" in judge_response:
        return "SHORT"
    return "HOLD"


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

    # Extract decision from judge response
    state["investment_decision"] = _extract_decision(judge_response)
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

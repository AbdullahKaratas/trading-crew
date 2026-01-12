#!/usr/bin/env python3
"""
Commodity Multi-Agent Debate System.

Mirrors the TradingAgents architecture but adapted for commodities (Silver, Gold, etc.).
Uses Gemini 3 + Google Search for real-time data instead of yfinance.

Architecture:
1. Data Gatherer - Collects current price, news, COT data, supply/demand via Search
2. Investment Debate - Bull vs Bear analysts debate the commodity
3. Investment Judge - Decides LONG/SHORT/HOLD
4. Risk Debate - Risky vs Safe vs Neutral analysts discuss risk levels
5. Risk Judge - Outputs structured JSON with knockout strategies
"""

import os
import json
import re
from datetime import date
from typing import TypedDict, Optional

from google import genai
from google.genai import types


# Commodity-specific JSON schema (same as TradingAgents)
TRADE_DECISION_SCHEMA = {
    "signal": "LONG | SHORT | HOLD | IGNORE",
    "confidence": 0.75,
    "unable_to_assess": False,
    "price_usd": 80.00,
    "price_eur": 76.00,
    "strategies": {
        "conservative": {"ko_level_usd": 70.0, "distance_pct": 12.5, "risk": "low"},
        "moderate": {"ko_level_usd": 74.0, "distance_pct": 7.5, "risk": "medium"},
        "aggressive": {"ko_level_usd": 77.0, "distance_pct": 3.75, "risk": "high"},
    },
    "hold_alternative": None,
    "support_zones": [{"level_usd": 75.0, "description": "Recent swing low"}],
    "resistance_zones": [{"level_usd": 85.0, "description": "Recent high"}],
    "detailed_analysis": "Full analysis text...",
}


class CommodityDebateState(TypedDict):
    """State for the commodity multi-agent debate."""
    commodity: str                    # e.g., "Silver"
    commodity_symbol: str             # e.g., "SILVER"
    current_price: float              # Spot price in USD
    price_source: str                 # Where price came from
    today: str                        # ISO date
    lang: str                         # "en" or "de"

    # Data from gatherer
    market_data: str                  # Price, technicals, trends
    news_data: str                    # Recent news and events
    cot_data: str                     # COT positioning data
    supply_demand_data: str           # Supply/demand factors

    # Investment debate
    bull_arguments: str
    bear_arguments: str
    investment_debate_history: str
    investment_decision: str          # LONG/SHORT/HOLD from judge

    # Risk debate
    risky_arguments: str
    safe_arguments: str
    neutral_arguments: str
    risk_debate_history: str

    # Final output
    final_decision: dict              # Structured JSON


def get_gemini_client():
    """Get configured Gemini client."""
    return genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))


def call_gemini_with_search(prompt: str, use_search: bool = True) -> str:
    """Call Gemini 3 Flash with optional Google Search grounding."""
    client = get_gemini_client()

    config = types.GenerateContentConfig(
        tools=[types.Tool(google_search=types.GoogleSearch())] if use_search else None
    )

    response = client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=prompt,
        config=config
    )

    return response.text or ""


def call_gemini_deep_think(prompt: str) -> str:
    """Call Gemini 3 Flash for deep thinking (judges)."""
    client = get_gemini_client()

    response = client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=prompt
    )

    return response.text or ""


# =============================================================================
# PHASE 1: DATA GATHERING
# =============================================================================

def data_gatherer(commodity: str, lang: str = "en") -> dict:
    """
    Gather comprehensive commodity data using Gemini + Google Search.

    Returns dict with: current_price, market_data, news_data, cot_data, supply_demand_data
    """
    today = date.today().isoformat()
    lang_instruction = "Respond in German." if lang == "de" else "Respond in English."

    # 1. Get current spot price (structured)
    price_prompt = f"""Search for the current {commodity} spot price in USD per ounce.
Return ONLY a JSON object with the exact price (no markdown):
{{"price_usd": 80.15, "source": "kitco.com"}}"""

    price_response = call_gemini_with_search(price_prompt)

    # Parse price
    try:
        # Remove markdown if present
        text = price_response.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
        price_data = json.loads(text)
        current_price = price_data.get("price_usd", 0)
        price_source = price_data.get("source", "unknown")
    except (json.JSONDecodeError, ValueError):
        # Fallback: extract number
        match = re.search(r'\$?([\d,]+\.?\d*)', price_response)
        current_price = float(match.group(1).replace(",", "")) if match else 0
        price_source = "extracted"

    # 2. Get market/technical data
    market_prompt = f"""Search for current {commodity} market analysis for {today}.

Provide a concise summary of:
- Current price trend (bullish/bearish/neutral)
- Key technical levels (support/resistance)
- Recent price action and momentum
- Moving average analysis (50-day, 200-day SMA)
- RSI and other momentum indicators if available

{lang_instruction}
Keep response under 400 words."""

    market_data = call_gemini_with_search(market_prompt)

    # 3. Get news and events
    news_prompt = f"""Search for latest {commodity} news and market-moving events for {today}.

Focus on:
- Central bank policy (Fed, ECB) impact on {commodity}
- Geopolitical developments affecting {commodity}
- Economic data releases (inflation, jobs, GDP)
- Any {commodity}-specific news (mining, production, demand)

{lang_instruction}
Keep response under 400 words."""

    news_data = call_gemini_with_search(news_prompt)

    # 4. Get COT (Commitment of Traders) data
    cot_prompt = f"""Search for latest {commodity} COT report and positioning data.

Provide:
- Commercial hedgers positioning (net long/short)
- Speculators (managed money) positioning
- Recent changes in positioning
- What this suggests about market sentiment

{lang_instruction}
Keep response under 300 words."""

    cot_data = call_gemini_with_search(cot_prompt)

    # 5. Get supply/demand fundamentals
    supply_prompt = f"""Search for {commodity} supply and demand fundamentals for 2025/2026.

Cover:
- Global production trends
- Industrial demand drivers
- Investment demand (ETFs, coins, bars)
- Inventory levels
- Seasonal factors

{lang_instruction}
Keep response under 300 words."""

    supply_demand_data = call_gemini_with_search(supply_prompt)

    return {
        "current_price": current_price,
        "price_source": price_source,
        "market_data": market_data,
        "news_data": news_data,
        "cot_data": cot_data,
        "supply_demand_data": supply_demand_data,
    }


# =============================================================================
# PHASE 2: INVESTMENT DEBATE (Bull vs Bear)
# =============================================================================

def bull_analyst(state: CommodityDebateState) -> str:
    """
    Bull analyst makes the case FOR going LONG on the commodity.
    Adapted from TradingAgents' bull_researcher.py
    """
    lang_instruction = "Respond entirely in German." if state["lang"] == "de" else "Respond entirely in English."

    bear_args = state.get("bear_arguments", "")
    counter_section = ""
    if bear_args:
        counter_section = f"""
## Bear's Arguments to Counter:
{bear_args}

You MUST directly address and counter each of the Bear's points with specific data and reasoning.
"""

    prompt = f"""You are a BULLISH {state['commodity']} Analyst advocating for a LONG position.

## Current Data
- **Commodity**: {state['commodity']}
- **Current Spot Price**: ${state['current_price']:.2f} per ounce
- **Date**: {state['today']}

## Market Analysis
{state['market_data']}

## News & Events
{state['news_data']}

## COT Positioning
{state['cot_data']}

## Supply & Demand
{state['supply_demand_data']}
{counter_section}
## Your Task

Build a strong, evidence-based case for why {state['commodity']} will RISE. Focus on:

1. **Bullish Technical Signals**: Uptrend confirmation, breakout patterns, support holding
2. **Macro Tailwinds**: Fed policy, inflation hedge demand, currency weakness
3. **Supply Constraints**: Production issues, declining inventories
4. **Demand Catalysts**: Industrial demand, investment demand, central bank buying
5. **COT Positioning**: If speculators are underweight, there's room to run

Be specific with price targets and timeframes. Use the data provided.

{lang_instruction}
Keep response under 500 words but make every word count."""

    return call_gemini_with_search(prompt, use_search=False)


def bear_analyst(state: CommodityDebateState) -> str:
    """
    Bear analyst makes the case AGAINST going long / FOR going SHORT.
    Adapted from TradingAgents' bear_researcher.py
    """
    lang_instruction = "Respond entirely in German." if state["lang"] == "de" else "Respond entirely in English."

    bull_args = state.get("bull_arguments", "")
    counter_section = ""
    if bull_args:
        counter_section = f"""
## Bull's Arguments to Counter:
{bull_args}

You MUST directly address and counter each of the Bull's points with specific data and reasoning.
"""

    prompt = f"""You are a BEARISH {state['commodity']} Analyst arguing AGAINST a long position.

## Current Data
- **Commodity**: {state['commodity']}
- **Current Spot Price**: ${state['current_price']:.2f} per ounce
- **Date**: {state['today']}

## Market Analysis
{state['market_data']}

## News & Events
{state['news_data']}

## COT Positioning
{state['cot_data']}

## Supply & Demand
{state['supply_demand_data']}
{counter_section}
## Your Task

Build a strong, evidence-based case for why {state['commodity']} will FALL or underperform. Focus on:

1. **Bearish Technical Signals**: Overbought conditions, resistance overhead, trend exhaustion
2. **Macro Headwinds**: Strong dollar, rising real rates, risk-on sentiment
3. **Supply Glut Risks**: Increased production, inventory builds
4. **Demand Weakness**: Industrial slowdown, reduced investment demand
5. **COT Positioning**: If speculators are extremely long, reversal risk is high

Be specific about downside targets and risk factors. Use the data provided.

{lang_instruction}
Keep response under 500 words but make every word count."""

    return call_gemini_with_search(prompt, use_search=False)


def investment_judge(state: CommodityDebateState) -> str:
    """
    Investment Judge synthesizes Bull vs Bear debate and decides LONG/SHORT/HOLD.
    Adapted from TradingAgents' research_manager.py
    """
    lang_instruction = "Respond entirely in German." if state["lang"] == "de" else "Respond entirely in English."

    prompt = f"""You are the INVESTMENT JUDGE for {state['commodity']} analysis.

## Current Price
${state['current_price']:.2f} per ounce

## Full Debate History
{state['investment_debate_history']}

## Bull's Final Position
{state['bull_arguments']}

## Bear's Final Position
{state['bear_arguments']}

## Your Task

As the impartial judge, you must:

1. **Evaluate Arguments**: Which side presented stronger evidence-based arguments?
2. **Identify Key Factors**: What are the 2-3 most important factors driving your decision?
3. **Acknowledge Weaknesses**: What are the main risks to your recommendation?
4. **Make a Decision**: You MUST choose one: **LONG**, **SHORT**, or **HOLD**

Do NOT choose HOLD unless the arguments are genuinely balanced with no clear edge.
Commodities are volatile - there's usually a directional bias.

End your response with exactly one of:
- RECOMMENDATION: **LONG**
- RECOMMENDATION: **SHORT**
- RECOMMENDATION: **HOLD**

{lang_instruction}
Keep response under 400 words."""

    return call_gemini_deep_think(prompt)


# =============================================================================
# PHASE 3: RISK DEBATE (Risky vs Safe vs Neutral)
# =============================================================================

def risky_analyst(state: CommodityDebateState) -> str:
    """
    Risky/Aggressive analyst advocates for bold, high-reward strategies.
    Adapted from TradingAgents' risky_analyst.py
    """
    lang_instruction = "Respond entirely in German." if state["lang"] == "de" else "Respond entirely in English."

    prompt = f"""You are the AGGRESSIVE/RISKY Risk Analyst for {state['commodity']}.

## Investment Decision
The Investment Judge has decided: **{state['investment_decision']}**

## Current Price
${state['current_price']:.2f} per ounce

## Investment Debate Summary
{state['investment_debate_history'][:1500]}

## Your Role

As the Risky Analyst, you champion HIGH-REWARD opportunities:

1. **Maximize Upside**: Argue for aggressive position sizing and tight stop-losses
2. **Momentum Play**: If the trend is strong, ride it with leverage
3. **Entry Now**: Waiting for pullbacks means missing the move
4. **Tight Knockouts**: Higher leverage = higher returns (accept the risk)

Counter the conservative approach - why is waiting or being cautious a mistake HERE?

Propose specific knockout levels for an AGGRESSIVE strategy:
- For LONG: Stop-loss 5-8% below current price
- For SHORT: Stop-loss 5-8% above current price

{lang_instruction}
Keep response under 300 words."""

    return call_gemini_with_search(prompt, use_search=False)


def safe_analyst(state: CommodityDebateState) -> str:
    """
    Safe/Conservative analyst prioritizes capital preservation.
    Adapted from TradingAgents' safe_analyst.py
    """
    lang_instruction = "Respond entirely in German." if state["lang"] == "de" else "Respond entirely in English."

    risky_args = state.get("risky_arguments", "")

    prompt = f"""You are the CONSERVATIVE/SAFE Risk Analyst for {state['commodity']}.

## Investment Decision
The Investment Judge has decided: **{state['investment_decision']}**

## Current Price
${state['current_price']:.2f} per ounce

## Risky Analyst's Position
{risky_args}

## Your Role

As the Safe Analyst, you prioritize CAPITAL PRESERVATION:

1. **Protect Downside**: Wide stop-losses to avoid whipsaws
2. **Wait for Confirmation**: Better entry points reduce risk
3. **Position Sizing**: Smaller positions survive volatility
4. **Wide Knockouts**: 15-25% distance gives room to breathe

Counter the aggressive approach - why is being too risky dangerous HERE?

Propose specific knockout levels for a CONSERVATIVE strategy:
- For LONG: Stop-loss 15-25% below current price (at key support)
- For SHORT: Stop-loss 15-25% above current price (at key resistance)

{lang_instruction}
Keep response under 300 words."""

    return call_gemini_with_search(prompt, use_search=False)


def neutral_analyst(state: CommodityDebateState) -> str:
    """
    Neutral analyst provides balanced perspective.
    Adapted from TradingAgents' neutral_analyst.py
    """
    lang_instruction = "Respond entirely in German." if state["lang"] == "de" else "Respond entirely in English."

    prompt = f"""You are the NEUTRAL/BALANCED Risk Analyst for {state['commodity']}.

## Investment Decision
The Investment Judge has decided: **{state['investment_decision']}**

## Current Price
${state['current_price']:.2f} per ounce

## Risky Analyst's Position
{state.get('risky_arguments', '')}

## Safe Analyst's Position
{state.get('safe_arguments', '')}

## Your Role

As the Neutral Analyst, you provide BALANCE:

1. **Weigh Both Sides**: Where is Risky too aggressive? Where is Safe too cautious?
2. **Find the Middle**: A moderate approach often works best
3. **Context Matters**: Current volatility should inform knockout distance
4. **Practical Advice**: What would a professional trader actually do?

Propose specific knockout levels for a MODERATE strategy:
- For LONG: Stop-loss 10-15% below current price
- For SHORT: Stop-loss 10-15% above current price

{lang_instruction}
Keep response under 300 words."""

    return call_gemini_with_search(prompt, use_search=False)


# =============================================================================
# PHASE 4: FINAL RISK JUDGE
# =============================================================================

def risk_judge(state: CommodityDebateState) -> dict:
    """
    Risk Judge synthesizes all debates and outputs structured JSON decision.
    Adapted from TradingAgents' risk_manager.py
    """
    lang_instruction = "Respond entirely in German for the detailed_analysis field." if state["lang"] == "de" else "Respond entirely in English for the detailed_analysis field."

    # EUR conversion (approximate)
    eur_rate = 0.92
    price_eur = state['current_price'] * eur_rate

    prompt = f"""You are the FINAL RISK JUDGE for {state['commodity']} analysis.

## Investment Decision
{state['investment_decision']}

## Current Price
- USD: ${state['current_price']:.2f} per ounce
- EUR: €{price_eur:.2f} per ounce

## Full Investment Debate
{state['investment_debate_history'][:2000]}

## Risk Debate
### Risky Analyst:
{state['risky_arguments']}

### Safe Analyst:
{state['safe_arguments']}

### Neutral Analyst:
{state['neutral_arguments']}

## Your Task

Synthesize ALL debates and output a FINAL TRADING DECISION as JSON.

You MUST output ONLY valid JSON matching this schema (no markdown, no explanation):

{{
    "signal": "LONG or SHORT or HOLD or IGNORE",
    "confidence": 0.75,
    "unable_to_assess": false,
    "price_usd": {state['current_price']:.2f},
    "price_eur": {price_eur:.2f},
    "strategies": {{
        "conservative": {{
            "ko_level_usd": <price for conservative knockout>,
            "distance_pct": <percentage distance from current price>,
            "risk": "low"
        }},
        "moderate": {{
            "ko_level_usd": <price for moderate knockout>,
            "distance_pct": <percentage distance>,
            "risk": "medium"
        }},
        "aggressive": {{
            "ko_level_usd": <price for aggressive knockout>,
            "distance_pct": <percentage distance>,
            "risk": "high"
        }}
    }},
    "hold_alternative": null,
    "support_zones": [
        {{"level_usd": <price>, "description": "<why this is support>"}},
        {{"level_usd": <price>, "description": "<why this is support>"}}
    ],
    "resistance_zones": [
        {{"level_usd": <price>, "description": "<why this is resistance>"}},
        {{"level_usd": <price>, "description": "<why this is resistance>"}}
    ],
    "detailed_analysis": "<Comprehensive 300-500 word analysis summarizing the debate, key arguments, and your reasoning. {lang_instruction}>"
}}

IMPORTANT:
- For LONG signals: knockout levels should be BELOW current price
- For SHORT signals: knockout levels should be ABOVE current price
- Conservative = furthest from price (safest), Aggressive = closest (riskiest)
- Confidence should reflect how clear the directional edge is (0.5 = uncertain, 0.9 = very confident)
- Support zones are below current price, Resistance zones are above

Output ONLY the JSON, nothing else."""

    response = call_gemini_deep_think(prompt)

    # Parse JSON response
    try:
        text = response.strip()
        # Remove markdown code blocks if present
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
        if text.endswith("```"):
            text = text[:-3].strip()

        return json.loads(text)
    except json.JSONDecodeError as e:
        # Return error state
        return {
            "signal": "IGNORE",
            "confidence": 0.0,
            "unable_to_assess": True,
            "price_usd": state['current_price'],
            "price_eur": price_eur,
            "strategies": {},
            "support_zones": [],
            "resistance_zones": [],
            "detailed_analysis": f"Error parsing risk judge response: {str(e)}\n\nRaw response:\n{response[:500]}",
        }


# =============================================================================
# MAIN ORCHESTRATOR
# =============================================================================

def run_commodity_analysis(symbol: str, lang: str = "en") -> dict:
    """
    Run full multi-agent commodity analysis.

    Architecture mirrors TradingAgents:
    1. Data Gathering (Gemini + Search)
    2. Investment Debate (Bull vs Bear, 2 rounds)
    3. Investment Judge (LONG/SHORT/HOLD)
    4. Risk Debate (Risky vs Safe vs Neutral)
    5. Risk Judge (Structured JSON output)

    Args:
        symbol: Commodity name (e.g., "Silver", "Gold")
        lang: Output language ("en" or "de")

    Returns:
        dict with trade_decision (structured) and final_trade_decision (text)
    """
    commodity = symbol.capitalize()
    today = date.today().isoformat()

    print(f"\n{'='*60}")
    print(f"COMMODITY MULTI-AGENT ANALYSIS: {commodity}")
    print(f"{'='*60}")

    # Phase 1: Data Gathering
    print("\n[1/5] Gathering market data via Google Search...")
    gathered_data = data_gatherer(commodity, lang)

    print(f"  - Spot Price: ${gathered_data['current_price']:.2f} (source: {gathered_data['price_source']})")

    # Initialize state
    state: CommodityDebateState = {
        "commodity": commodity,
        "commodity_symbol": symbol.upper(),
        "current_price": gathered_data["current_price"],
        "price_source": gathered_data["price_source"],
        "today": today,
        "lang": lang,
        "market_data": gathered_data["market_data"],
        "news_data": gathered_data["news_data"],
        "cot_data": gathered_data["cot_data"],
        "supply_demand_data": gathered_data["supply_demand_data"],
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

    # Phase 2: Investment Debate (2 rounds like TradingAgents)
    print("\n[2/5] Investment Debate: Bull vs Bear...")

    debate_history = ""
    for round_num in range(2):  # 2 rounds of debate
        print(f"  Round {round_num + 1}/2:")

        # Bull speaks
        print("    - Bull Analyst arguing...")
        bull_response = bull_analyst(state)
        state["bull_arguments"] = bull_response
        debate_history += f"\n\n### BULL (Round {round_num + 1}):\n{bull_response}"

        # Bear responds
        print("    - Bear Analyst countering...")
        bear_response = bear_analyst(state)
        state["bear_arguments"] = bear_response
        debate_history += f"\n\n### BEAR (Round {round_num + 1}):\n{bear_response}"

        state["investment_debate_history"] = debate_history

    # Phase 3: Investment Judge
    print("\n[3/5] Investment Judge deciding...")
    judge_response = investment_judge(state)
    state["investment_debate_history"] += f"\n\n### INVESTMENT JUDGE:\n{judge_response}"

    # Extract decision
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

    state["risk_debate_history"] = f"""
### RISKY ANALYST:
{state['risky_arguments']}

### SAFE ANALYST:
{state['safe_arguments']}

### NEUTRAL ANALYST:
{state['neutral_arguments']}
"""

    # Phase 5: Final Risk Judge
    print("\n[5/5] Risk Judge creating final decision...")
    final_decision = risk_judge(state)
    state["final_decision"] = final_decision

    print(f"  Signal: {final_decision.get('signal', 'UNKNOWN')}")
    print(f"  Confidence: {final_decision.get('confidence', 0):.0%}")

    print(f"\n{'='*60}")
    print("ANALYSIS COMPLETE")
    print(f"{'='*60}\n")

    # Return in same format as TradingAgents
    return {
        "trade_decision": final_decision,
        "final_trade_decision": final_decision.get("detailed_analysis", ""),
        "commodity_mode": True,
    }


if __name__ == "__main__":
    # Test
    import sys
    symbol = sys.argv[1] if len(sys.argv) > 1 else "Silver"
    lang = sys.argv[2] if len(sys.argv) > 2 else "de"

    result = run_commodity_analysis(symbol, lang)
    print(json.dumps(result["trade_decision"], indent=2, ensure_ascii=False))

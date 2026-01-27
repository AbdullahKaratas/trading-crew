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

import io
import json
from datetime import date
from typing import Optional, TypedDict

from gemini_utils import (
    call_gemini_flash,
    call_gemini_pro,
    call_gemini_vision,
    call_gemini_json,
    extract_price_from_text,
    get_language_instruction,
    parse_json_response,
    TradeDecisionSchema,
)
from chart_vision import create_chart_for_analysis


class UniversalDebateState(TypedDict):
    """State for the universal multi-agent debate."""
    symbol: str
    asset_name: str
    asset_type: str  # "stock", "commodity", "etf", "crypto"
    current_price: float
    price_source: str
    today: str
    lang: str

    # Chart for vision analysis (PNG as BytesIO, None if unavailable)
    chart_image: Optional[io.BytesIO]

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
# HELPER FUNCTIONS
# =============================================================================

def get_eur_usd_rate() -> float:
    """
    Get current EUR/USD exchange rate.

    Priority:
    1. yfinance (EURUSD=X) - fast and reliable
    2. Gemini Search fallback
    3. Conservative fallback (1.0)
    """
    # Try yfinance first
    try:
        import yfinance as yf
        ticker = yf.Ticker("EURUSD=X")
        data = ticker.history(period="1d")
        if not data.empty:
            rate = float(data['Close'].iloc[-1])
            print(f"  [FX] EUR/USD rate: {rate:.4f} (yfinance)")
            return rate
    except Exception as e:
        print(f"  [FX] yfinance failed: {str(e)[:50]}")

    # Fallback: Gemini Search
    try:
        prompt = "Current EUR/USD exchange rate today. Return ONLY JSON: {\"rate\": 1.08}"
        response = call_gemini_flash(prompt, use_search=True)
        data = parse_json_response(response)
        if data and data.get("rate"):
            rate = float(data["rate"])
            print(f"  [FX] EUR/USD rate: {rate:.4f} (gemini)")
            return rate
    except Exception as e:
        print(f"  [FX] Gemini fallback failed: {str(e)[:50]}")

    # Last resort: conservative fallback
    print("  [FX] Using fallback rate 1.0 (no conversion)")
    return 1.0


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
Keep response under 2000 words."""

    technical_data = call_gemini_flash(technical_prompt, use_search=True) or "No technical data available."

    # 3. Get news and events
    news_prompt = f"""Search for latest news about {symbol} from {trade_date}.

Focus on:
- Recent earnings/financial reports
- Analyst ratings and price targets
- Major announcements
- Sector/industry news
- Market-moving events
- Geopolitical events (wars, sanctions, elections)
- US/Trump tariffs and trade policy (China, Mexico, EU tariffs)
- Central bank policy (Fed, ECB interest rates, QE)
- Currency movements (USD strength/weakness)

{lang_instruction}
Keep response under 1500 words."""

    news_data = call_gemini_flash(news_prompt, use_search=True) or "No recent news available."

    # 4. Get fundamentals (for stocks) or market context (for commodities)
    if asset_type == "stock":
        fundamental_prompt = f"""Search for fundamental data of {symbol} as of {trade_date}.

Provide:
- Market Cap and P/E Ratio
- Revenue growth and profit margins
- Debt levels
- Competitive position
- Recent insider activity
- Supply chain exposure (China, Mexico, EU)
- Tariff/trade war risk for this company

{lang_instruction}
Keep response under 1500 words."""
    else:
        fundamental_prompt = f"""Search for market context of {symbol} as of {trade_date}.

Provide:
- Supply and demand factors
- Seasonal patterns
- Macro economic factors
- COT positioning (if applicable)
- ETF flows
- Central bank policy (Fed rates, gold/silver reserves)
- US/Trump tariffs impact (China, Mexico, EU)
- Geopolitical risk and safe-haven demand
- USD strength/weakness impact
- Import/export restrictions

{lang_instruction}
Keep response under 1500 words."""

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

    chart_instruction = ""
    if state.get("chart_image"):
        chart_instruction = """
## Chart Analysis
Analyze the attached chart image showing:
- Price action with SMA 50 (orange) and SMA 200 (purple)
- RSI indicator (yellow) with overbought (70) and oversold (30) lines
- Volume bars (green=bullish, red=bearish)
- CMF (cyan) and OBV (magenta) for money flow

Look for bullish patterns: Golden Cross, higher lows, bullish divergence, etc.
"""

    prompt = f"""You are a BULLISH Analyst advocating for a LONG position in {state['symbol']}.

## Current Data (as of {state['today']})
- **Asset**: {state['asset_name']} ({state['asset_type']})
- **Price**: ${state['current_price']:.2f}
{chart_instruction}
## Technical Analysis
{state['technical_data']}

## News & Events
{state['news_data']}

## Fundamentals/Context
{state['fundamental_data']}
{counter_section}

## Your Task
Build a strong case for why {state['symbol']} will RISE. Focus on:
1. Bullish technical signals (reference the chart if available)
2. Positive catalysts
3. Strong fundamentals or market tailwinds
4. Why bears are wrong

Be specific with price targets. {lang_instruction}
Keep response under 2000 words."""

    # Try vision API if chart available, fallback to text
    if state.get("chart_image"):
        try:
            return call_gemini_vision(prompt, state["chart_image"])
        except Exception as e:
            print(f"  [Bull Vision] {state['symbol']} fallback to text: {str(e)[:80]}")

    return call_gemini_flash(prompt, use_search=True, max_retries=2)


def bear_analyst(state: UniversalDebateState) -> str:
    """Bear analyst makes the case AGAINST going long."""
    lang_instruction = get_language_instruction(state["lang"])

    bull_args = state.get("bull_arguments", "")
    counter_section = ""
    if bull_args:
        counter_section = f"\n## Bull's Arguments to Counter:\n{bull_args}\n\nDirectly address and counter each point."

    chart_instruction = ""
    if state.get("chart_image"):
        chart_instruction = """
## Chart Analysis
Analyze the attached chart image showing:
- Price action with SMA 50 (orange) and SMA 200 (purple)
- RSI indicator (yellow) with overbought (70) and oversold (30) lines
- Volume bars (green=bullish, red=bearish)
- CMF (cyan) and OBV (magenta) for money flow

Look for bearish patterns: Death Cross, lower highs, bearish divergence, etc.
"""

    prompt = f"""You are a BEARISH Analyst arguing AGAINST a long position in {state['symbol']}.

## Current Data (as of {state['today']})
- **Asset**: {state['asset_name']} ({state['asset_type']})
- **Price**: ${state['current_price']:.2f}
{chart_instruction}
## Technical Analysis
{state['technical_data']}

## News & Events
{state['news_data']}

## Fundamentals/Context
{state['fundamental_data']}
{counter_section}

## Your Task
Build a strong case for why {state['symbol']} will FALL. Focus on:
1. Bearish technical signals (reference the chart if available)
2. Negative catalysts or risks
3. Weak fundamentals or headwinds
4. Why bulls are wrong

Be specific with downside targets. {lang_instruction}
Keep response under 2000 words."""

    # Try vision API if chart available, fallback to text
    if state.get("chart_image"):
        try:
            return call_gemini_vision(prompt, state["chart_image"])
        except Exception as e:
            print(f"  [Bear Vision] {state['symbol']} fallback to text: {str(e)[:80]}")

    return call_gemini_flash(prompt, use_search=True, max_retries=2)


def investment_judge(state: UniversalDebateState) -> str:
    """Investment Judge decides LONG/SHORT/HOLD."""
    lang_instruction = get_language_instruction(state["lang"])

    chart_instruction = ""
    if state.get("chart_image"):
        chart_instruction = """
## Chart Analysis
Review the attached chart to visually confirm the technical patterns discussed.
The chart shows: Price+SMA, RSI, Volume, and CMF/OBV indicators.
"""

    prompt = f"""You are the INVESTMENT JUDGE for {state['symbol']} analysis.

## Current Price: ${state['current_price']:.2f}
## Date: {state['today']}
{chart_instruction}
Use Google Search to verify the latest news and current situation for {state['symbol']}.

## Technical Analysis (Raw Data)
{state['technical_data']}

## News & Events (Raw Data)
{state['news_data']}

## Fundamentals/Context (Raw Data)
{state['fundamental_data']}

## Full Debate History
{state['investment_debate_history']}

## Your Task
1. Review the chart (if available) to verify technical claims
2. Consider ALL data: technicals, news, fundamentals - not just the debate summary
3. Pay special attention to geopolitical events, tariffs, partnerships, product launches
4. Evaluate which side presented stronger evidence
5. Identify the 2-3 most important factors
6. Acknowledge main risks
7. Make a decision: **LONG**, **SHORT**, or **HOLD**

End with exactly one of:
- RECOMMENDATION: **LONG**
- RECOMMENDATION: **SHORT**
- RECOMMENDATION: **HOLD**

{lang_instruction}
Keep response under 1500 words."""

    # Try vision API if chart available, fallback to text
    if state.get("chart_image"):
        try:
            return call_gemini_vision(prompt, state["chart_image"], model="gemini-3-pro-preview")
        except Exception as e:
            print(f"  [Judge Vision] {state['symbol']} fallback to text: {str(e)[:80]}")

    return call_gemini_pro(prompt, use_search=True)


# =============================================================================
# PHASE 3: RISK DEBATE (Risky vs Safe vs Neutral)
# =============================================================================

def risky_analyst(state: UniversalDebateState) -> str:
    """Risky analyst advocates for aggressive strategies."""
    lang_instruction = get_language_instruction(state["lang"])

    chart_instruction = ""
    if state.get("chart_image"):
        chart_instruction = "\nUse the attached chart to identify tight support/resistance for aggressive levels."

    prompt = f"""You are the AGGRESSIVE Risk Analyst for {state['symbol']}.

## Investment Decision: **{state['investment_decision']}**
## Current Price: ${state['current_price']:.2f}
{chart_instruction}
## Technical Analysis
{state['technical_data']}

## News & Events
{state['news_data']}

## Fundamentals/Context
{state['fundamental_data']}

Advocate for HIGH-REWARD strategies:
- Tight stop-losses (5-8% from price)
- Maximize upside potential
- Why waiting is wrong
- Consider news catalysts that could accelerate the move

Propose aggressive knockout levels. {lang_instruction}
Keep response under 1200 words."""

    # Try vision API if chart available, fallback to text
    if state.get("chart_image"):
        try:
            return call_gemini_vision(prompt, state["chart_image"])
        except Exception as e:
            print(f"  [Risky Vision] {state['symbol']} fallback to text: {str(e)[:80]}")

    return call_gemini_flash(prompt, use_search=True, max_retries=2)


def safe_analyst(state: UniversalDebateState) -> str:
    """Safe analyst prioritizes capital preservation."""
    lang_instruction = get_language_instruction(state["lang"])

    chart_instruction = ""
    if state.get("chart_image"):
        chart_instruction = "\nUse the attached chart to identify strong support zones for conservative levels."

    prompt = f"""You are the CONSERVATIVE Risk Analyst for {state['symbol']}.

## Investment Decision: **{state['investment_decision']}**
## Current Price: ${state['current_price']:.2f}
{chart_instruction}
## Technical Analysis
{state['technical_data']}

## News & Events
{state['news_data']}

## Fundamentals/Context
{state['fundamental_data']}

## Risky Analyst's Position:
{state.get('risky_arguments', '')}

Advocate for CAPITAL PRESERVATION:
- Wide stop-losses (15-25% from price)
- Why aggressive approach is dangerous given current news/geopolitical risks
- Wait for better entries
- Highlight news risks that could cause sudden moves against the position

Propose conservative knockout levels. {lang_instruction}
Keep response under 1200 words."""

    # Try vision API if chart available, fallback to text
    if state.get("chart_image"):
        try:
            return call_gemini_vision(prompt, state["chart_image"])
        except Exception as e:
            print(f"  [Safe Vision] {state['symbol']} fallback to text: {str(e)[:80]}")

    return call_gemini_flash(prompt, use_search=True, max_retries=2)


def neutral_analyst(state: UniversalDebateState) -> str:
    """Neutral analyst provides balanced perspective."""
    lang_instruction = get_language_instruction(state["lang"])

    chart_instruction = ""
    if state.get("chart_image"):
        chart_instruction = "\nUse the attached chart to find balanced support/resistance levels."

    prompt = f"""You are the NEUTRAL Risk Analyst for {state['symbol']}.

## Investment Decision: **{state['investment_decision']}**
## Current Price: ${state['current_price']:.2f}
{chart_instruction}
## Technical Analysis
{state['technical_data']}

## News & Events
{state['news_data']}

## Fundamentals/Context
{state['fundamental_data']}

## Risky Position:
{state.get('risky_arguments', '')}

## Safe Position:
{state.get('safe_arguments', '')}

Provide BALANCE:
- Where is Risky too aggressive given current news environment?
- Where is Safe too cautious given the fundamentals?
- What's the practical middle ground considering all factors?
- How do geopolitical/macro factors affect the risk/reward?

Propose moderate knockout levels. {lang_instruction}
Keep response under 1200 words."""

    # Try vision API if chart available, fallback to text
    if state.get("chart_image"):
        try:
            return call_gemini_vision(prompt, state["chart_image"])
        except Exception as e:
            print(f"  [Neutral Vision] {state['symbol']} fallback to text: {str(e)[:80]}")

    return call_gemini_flash(prompt, use_search=True, max_retries=2)


# =============================================================================
# PHASE 4: FINAL RISK JUDGE
# =============================================================================

def risk_judge(state: UniversalDebateState) -> dict:
    """Risk Judge outputs structured JSON decision."""
    lang_instruction = get_language_instruction(state["lang"], "Write")

    eur_rate = get_eur_usd_rate()
    price_eur = state['current_price'] / eur_rate  # USD to EUR conversion

    # Get chart analysis if chart is available (adds visual pattern recognition)
    chart_analysis = ""
    if state.get("chart_image"):
        try:
            chart_prompt = f"""Analyze this {state['symbol']} chart for final trading decision.

Identify and report:
1. Key chart patterns (Head & Shoulders, Double Top/Bottom, Triangles, etc.)
2. SMA 50/200 relationship (Golden Cross, Death Cross, trend)
3. RSI status (overbought >70, oversold <30, divergences)
4. Volume confirmation (increasing/decreasing on moves)
5. CMF/OBV money flow direction
6. Critical support and resistance levels visible on chart

Keep response under 1000 words, focus on actionable observations."""
            chart_analysis = call_gemini_vision(chart_prompt, state["chart_image"])
            if chart_analysis:
                chart_analysis = f"\n## Visual Chart Analysis:\n{chart_analysis}\n"
        except Exception as e:
            print(f"  [Chart Analysis] {state['symbol']} skipped: {str(e)[:80]}")

    prompt = f"""You are the FINAL RISK JUDGE for {state['symbol']}.

## TODAY'S DATE: {state['today']}
## AUTHORITATIVE PRICE: ${state['current_price']:.2f} USD / {price_eur:.2f} EUR

Use Google Search to verify latest news and price for {state['symbol']} today.
{chart_analysis}
## Technical Analysis (Raw Data)
{state['technical_data']}

## News & Events (Raw Data) - IMPORTANT: Consider geopolitical factors, tariffs, partnerships!
{state['news_data']}

## Fundamentals/Context (Raw Data)
{state['fundamental_data']}

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
    "signal": "LONG or SHORT or HOLD or IGNORE",
    "confidence": <float 0.0-1.0 - see guidelines below>,
    "unable_to_assess": <true or false - see guidelines below>,
    "unable_to_assess_reason": "<if unable_to_assess is true, explain why briefly>",
    "price_usd": {state['current_price']:.2f},
    "price_eur": {price_eur:.2f},
    "strategies": {{
        "conservative": {{"ko_level_usd": <15-25% from price>, "distance_pct": <15-25>, "risk": "low"}},
        "moderate": {{"ko_level_usd": <10-15% from price>, "distance_pct": <10-15>, "risk": "medium"}},
        "aggressive": {{"ko_level_usd": <5-10% from price>, "distance_pct": <5-10>, "risk": "high"}}
    }},
    "hold_alternative": <null if signal is LONG/SHORT, otherwise provide alternative - see guidelines>,
    "support_zones": [
        {{"level_usd": <price>, "description": "<reason>"}},
        {{"level_usd": <price>, "description": "<reason>"}}
    ],
    "resistance_zones": [
        {{"level_usd": <price>, "description": "<reason>"}},
        {{"level_usd": <price>, "description": "<reason>"}}
    ],
    "detailed_analysis": "<600-1000 word STRUCTURED analysis. MUST include these sections with headers:

**🐂 BULL-ARGUMENTE:**
- 2-3 key bullish points from the debate

**🐻 BEAR-ARGUMENTE:**
- 2-3 key bearish points from the debate

**⚖️ ENTSCHEIDUNG:**
- Why this signal was chosen
- Which side had stronger arguments

**🎯 STRATEGIE-EMPFEHLUNG:**
- Suggested allocation (e.g., 50% conservative, 35% moderate, 15% aggressive)
- When to take profits
- Risk management tips

**📰 AKTUELLE FAKTOREN:**
- Key news/events affecting the trade
- Geopolitical considerations

{lang_instruction}>",
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
For SHORT: KO levels ABOVE current price

**Confidence Guidelines (BE HONEST - vary this based on actual signal clarity):**
- 0.90-1.0: Exceptional - all indicators align, strong catalyst, clear trend
- 0.75-0.89: High - most indicators agree, good risk/reward
- 0.60-0.74: Moderate - mixed signals, some uncertainty
- 0.45-0.59: Low - conflicting data, unclear direction
- 0.30-0.44: Very Low - high uncertainty, weak signal
- <0.30: Unreliable - set unable_to_assess to true

**Unable to Assess Guidelines (BE HONEST - sometimes analysis is not possible):**
Set "unable_to_assess": true AND "signal": "IGNORE" when:
- Data is severely contradictory (confidence would be < 0.30)
- Critical information is missing (no price data, no recent news)
- Asset is illiquid, obscure, or potentially manipulated
- Extreme market conditions (circuit breakers, flash crash, trading halt)
- You genuinely cannot recommend any direction with confidence

When unable_to_assess is true: signal must be "IGNORE", confidence should be 0.0

**Hold Alternative Guidelines (for users who want to trade despite HOLD signal):**
When signal is HOLD, provide hold_alternative with:
{{
    "hold_alternative": {{
        "direction": "LONG or SHORT",
        "rationale": "<brief reason why this direction if user insists on trading>",
        "strategies": {{
            "conservative": {{"ko_level_usd": <15-25% from price>, "distance_pct": <15-25>, "risk": "low"}},
            "moderate": {{"ko_level_usd": <10-15% from price>, "distance_pct": <10-15>, "risk": "medium"}},
            "aggressive": {{"ko_level_usd": <5-10% from price>, "distance_pct": <5-10>, "risk": "high"}}
        }}
    }}
}}
When signal is LONG, SHORT, or IGNORE: set hold_alternative to null"""

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

    # Generate chart for vision analysis (all asset types - commodities use futures symbols)
    chart_image = None
    print("\n[1.5/5] Generating chart for vision analysis...")
    try:
        chart_image = create_chart_for_analysis(symbol)
        if chart_image:
            print(f"  - Chart generated successfully")
        else:
            print(f"  - Chart generation failed, using text-only mode")
    except Exception as e:
        print(f"  - Chart error: {e}, using text-only mode")

    # Initialize state
    state: UniversalDebateState = {
        "symbol": symbol.upper(),
        "asset_name": gathered_data["asset_name"],
        "asset_type": gathered_data["asset_type"],
        "current_price": gathered_data["current_price"],
        "price_source": gathered_data["price_source"],
        "today": trade_date,
        "lang": lang,
        "chart_image": chart_image,
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
        "chart_image": chart_image,  # BytesIO or None
    }


if __name__ == "__main__":
    import sys
    symbol = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    lang = sys.argv[2] if len(sys.argv) > 2 else "de"

    result = run_universal_analysis(symbol, lang=lang)
    print(json.dumps(result["trade_decision"], indent=2, ensure_ascii=False))

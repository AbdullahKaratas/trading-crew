import json
import re


# JSON Schema for structured trade decision
# Signal: LONG (buy), SHORT (sell), HOLD (wait), IGNORE (no trade)
TRADE_DECISION_SCHEMA = {
    "signal": "LONG | SHORT | HOLD | IGNORE",
    "confidence": 0.75,  # 0.0 to 1.0
    "unable_to_assess": False,  # True if analysis not possible
    "price_usd": 0.0,  # Current price in USD
    "price_eur": 0.0,  # Current price in EUR (estimated)
    "strategies": {
        "conservative": {"ko_level_usd": 0.0, "distance_pct": 0.0, "risk": "low"},
        "moderate": {"ko_level_usd": 0.0, "distance_pct": 0.0, "risk": "medium"},
        "aggressive": {"ko_level_usd": 0.0, "distance_pct": 0.0, "risk": "high"},
    },
    "hold_alternative": {  # Only if signal is HOLD - suggestion for those who want to enter anyway
        "direction": "LONG | SHORT",
        "strategies": {
            "conservative": {"ko_level_usd": 0.0, "distance_pct": 0.0, "risk": "low"},
            "moderate": {"ko_level_usd": 0.0, "distance_pct": 0.0, "risk": "medium"},
            "aggressive": {"ko_level_usd": 0.0, "distance_pct": 0.0, "risk": "high"},
        },
    },
    "support_zones": [
        {"level_usd": 0.0, "description": "Description of this support level"},
    ],
    "resistance_zones": [
        {"level_usd": 0.0, "description": "Description of this resistance level"},
    ],
    "detailed_analysis": "Full analysis text with reasoning",
}


def parse_trade_decision_json(text: str) -> dict | None:
    """
    Extract and parse JSON trade decision from LLM response.
    Returns None if parsing fails.
    """
    # Try to find JSON block in the text
    # Look for ```json ... ``` or ``` ... ``` blocks
    json_patterns = [
        r'```json\s*(\{[^`]+\})\s*```',  # ```json { } ```
        r'```\s*(\{[^`]+\})\s*```',       # ``` { } ```
        r'<json>\s*(\{.+?\})\s*</json>',  # <json> { } </json>
    ]

    for pattern in json_patterns:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                continue

    # Last resort: try to find any JSON object in the text
    try:
        # Find the last { ... } block that looks like our schema
        matches = re.findall(r'\{[^{}]*"signal"[^{}]*\}', text, re.DOTALL)
        if matches:
            return json.loads(matches[-1])
    except json.JSONDecodeError:
        pass

    return None


def create_risk_manager(llm, memory):
    def risk_manager_node(state) -> dict:

        company_name = state["company_of_interest"]
        output_language = state.get("output_language", "en")
        forced_direction = state.get("forced_direction")  # "long", "short", or None
        current_price = state.get("current_price")  # Authoritative price from yfinance

        history = state["risk_debate_state"]["history"]
        risk_debate_state = state["risk_debate_state"]
        market_research_report = state["market_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]
        sentiment_report = state["sentiment_report"]
        trader_plan = state["investment_plan"]

        curr_situation = f"{market_research_report}\n\n{sentiment_report}\n\n{news_report}\n\n{fundamentals_report}"
        past_memories = memory.get_memories(curr_situation, n_matches=2)

        past_memory_str = ""
        for i, rec in enumerate(past_memories, 1):
            past_memory_str += rec["recommendation"] + "\n\n"

        # Language instruction
        if output_language == "de":
            language_instruction = "\n\n**WICHTIG: Schreibe deine GESAMTE Antwort auf DEUTSCH. Alle Analysen, Empfehlungen und Begründungen müssen auf Deutsch sein. Nur Tickersymbole und technische Begriffe können auf Englisch bleiben.**\n\n"
        else:
            language_instruction = ""

        # Forced direction instruction
        if forced_direction:
            direction_upper = forced_direction.upper()
            direction_instruction = f"""
**IMPORTANT: FORCED DIRECTION = {direction_upper}**
The user has explicitly requested a {direction_upper} analysis. Your signal MUST be "{direction_upper}".
Provide knockout strategies for a {direction_upper} position regardless of whether you would normally recommend this direction.
Still provide honest analysis of risks and opportunities, but the final signal must be {direction_upper}.
"""
        else:
            direction_instruction = ""

        # Current price instruction (authoritative source)
        if current_price is not None:
            price_instruction = f"""
**CRITICAL: AUTHORITATIVE CURRENT PRICE = ${current_price:.2f} USD**
This price is from yfinance real-time data. You MUST use this exact price in your JSON output for price_usd.
Do NOT use any other price from the market report or your own estimation. This is the correct, verified price.
Estimate price_eur as approximately {current_price * 0.95:.2f} EUR.
"""
        else:
            price_instruction = ""

        prompt = f"""{language_instruction}{direction_instruction}{price_instruction}As the Risk Management Judge and Debate Facilitator, your goal is to evaluate the debate between three risk analysts—Risky, Neutral, and Safe/Conservative—and determine the best course of action for the trader.

Your decision must result in a clear recommendation:
- **LONG**: Buy/go long on the asset
- **SHORT**: Sell/go short on the asset
- **HOLD**: Wait for better entry. Valid reasons: waiting for pullback, key support test, earnings/catalyst, unclear near-term direction. Always provide alternative strategies for those who want to enter anyway.
- **IGNORE**: Do not trade this asset at all (fundamentally broken, fraud risk, etc.)

HOLD is a valid decision when genuinely justified (e.g., "wait for $230 support test before entering long"), but do NOT use it as a lazy fallback when you're simply unsure. Take a stance - markets reward conviction.

Guidelines for Decision-Making:
1. **Summarize Key Arguments**: Extract the strongest points from each analyst, focusing on relevance to the context.
2. **Provide Rationale**: Support your recommendation with direct quotes and counterarguments from the debate.
3. **Refine the Trader's Plan**: Start with the trader's original plan, **{trader_plan}**, and adjust it based on the analysts' insights.
4. **Learn from Past Mistakes**: Use lessons from **{past_memory_str}** to address prior misjudgments and improve the decision you are making now.

---

**Analysts Debate History:**
{history}

---

## CRITICAL: You MUST respond with a JSON block

At the VERY END of your response, you MUST include a structured JSON block. This is REQUIRED and must follow this EXACT format:

```json
{{
  "signal": "LONG",
  "confidence": 0.75,
  "unable_to_assess": false,
  "price_usd": 244.56,
  "price_eur": 235.50,
  "strategies": {{
    "conservative": {{"ko_level_usd": 195.00, "distance_pct": 20.0, "risk": "low"}},
    "moderate": {{"ko_level_usd": 210.00, "distance_pct": 14.0, "risk": "medium"}},
    "aggressive": {{"ko_level_usd": 225.00, "distance_pct": 8.0, "risk": "high"}}
  }},
  "hold_alternative": null,
  "support_zones": [
    {{"level_usd": 230.00, "description": "Recent swing low, strong buyer interest"}},
    {{"level_usd": 215.00, "description": "200-day moving average"}},
    {{"level_usd": 195.00, "description": "Major support from Q3 consolidation"}}
  ],
  "resistance_zones": [
    {{"level_usd": 260.00, "description": "Recent high, psychological level"}},
    {{"level_usd": 280.00, "description": "All-time high region"}},
    {{"level_usd": 300.00, "description": "Round number resistance"}}
  ],
  "detailed_analysis": "Your full analysis text here explaining the reasoning..."
}}
```

**JSON Field Requirements:**

1. **signal**: Must be exactly "LONG", "SHORT", "HOLD", or "IGNORE" (uppercase)

2. **confidence**: Your confidence level from 0.0 to 1.0 (e.g., 0.75 = 75%)

3. **unable_to_assess**: Set to true ONLY if you genuinely cannot make an assessment due to missing data

4. **price_usd**: Current price of the asset in USD

5. **price_eur**: Current price in EUR (estimate using ~0.96 EUR/USD rate if needed)

6. **strategies**: THREE knockout certificate strategies based on YOUR signal direction:
   - For LONG signal: KO-levels are BELOW current price (you get knocked out if price falls)
   - For SHORT signal: KO-levels are ABOVE current price (you get knocked out if price rises)
   - **conservative**: Far from current price, low risk, ~15-25% distance
   - **moderate**: Medium distance, medium risk, ~10-15% distance
   - **aggressive**: Close to current price, high risk, ~5-10% distance
   - distance_pct is the percentage distance from current price to KO level

7. **hold_alternative**: If signal is HOLD, provide an alternative suggestion for traders who want to enter anyway:
   ```json
   {{
     "direction": "LONG",
     "strategies": {{
       "conservative": {{"ko_level_usd": 195.00, "distance_pct": 20.0, "risk": "low"}},
       "moderate": {{"ko_level_usd": 210.00, "distance_pct": 14.0, "risk": "medium"}},
       "aggressive": {{"ko_level_usd": 225.00, "distance_pct": 8.0, "risk": "high"}}
     }}
   }}
   ```
   Set to null if signal is LONG, SHORT, or IGNORE.

8. **support_zones**: Array of 2-4 key support levels with USD price and description

9. **resistance_zones**: Array of 2-4 key resistance levels with USD price and description

10. **detailed_analysis**: A COMPREHENSIVE analysis that MUST include:

    **Structure your analysis like this:**

    ## Zusammenfassung der Kernargumente (Summary of Core Arguments)

    **Risky Analyst (Bullish):**
    - List 3-5 key bullish arguments from the debate

    **Safe Analyst (Bearish):**
    - List 3-5 key bearish arguments from the debate

    **Neutral Analyst:**
    - List the neutral perspective and key observations

    ## Meine Bewertung (My Evaluation)

    Explain which arguments you find most convincing and why.
    Address the strongest counter-arguments.

    ## Strategische Handlungsanweisungen (Strategic Action Items)

    Provide 3-5 concrete action items for the trader:
    - Entry/Exit timing
    - Risk management specifics
    - Key levels to watch
    - Catalysts or events to monitor
    - Re-entry criteria if applicable

    This detailed analysis should be 300-600 words, NOT just a short paragraph.

The JSON block MUST be the LAST thing in your response."""

        response = llm.invoke(prompt)
        # Handle case where content might be a list or dict (Claude returns content blocks)
        response_text = response.content
        if isinstance(response_text, list):
            # Handle list of content blocks (e.g., [{'type': 'text', 'text': '...'}])
            texts = []
            for block in response_text:
                if isinstance(block, dict) and 'text' in block:
                    texts.append(block['text'])
                elif hasattr(block, 'text'):
                    texts.append(block.text)
                else:
                    texts.append(str(block))
            response_text = "\n".join(texts)
        elif isinstance(response_text, dict) and 'text' in response_text:
            response_text = response_text['text']

        # Parse the structured JSON from the response
        trade_decision = parse_trade_decision_json(response_text)

        # Retry if parsing failed
        if trade_decision is None:
            print("[Risk Manager] JSON parsing failed, retrying with focused prompt...")

            retry_prompt = f"""Your previous response did not contain a valid JSON block.

Please provide ONLY a JSON response with your trading decision based on your analysis of {company_name}.

Respond with ONLY this JSON structure, nothing else:

```json
{{
  "signal": "LONG",
  "confidence": 0.75,
  "unable_to_assess": false,
  "price_usd": 100.00,
  "price_eur": 96.00,
  "strategies": {{
    "conservative": {{"ko_level_usd": 80.00, "distance_pct": 20.0, "risk": "low"}},
    "moderate": {{"ko_level_usd": 86.00, "distance_pct": 14.0, "risk": "medium"}},
    "aggressive": {{"ko_level_usd": 92.00, "distance_pct": 8.0, "risk": "high"}}
  }},
  "hold_alternative": null,
  "support_zones": [
    {{"level_usd": 95.00, "description": "Recent support level"}},
    {{"level_usd": 85.00, "description": "Major support zone"}}
  ],
  "resistance_zones": [
    {{"level_usd": 110.00, "description": "Recent resistance"}},
    {{"level_usd": 120.00, "description": "All-time high"}}
  ],
  "detailed_analysis": "Brief analysis here"
}}
```

Replace the example values with your actual recommendation.
- Signal must be "LONG", "SHORT", "HOLD", or "IGNORE"
- For LONG: KO levels should be BELOW current price
- For SHORT: KO levels should be ABOVE current price
- If HOLD: Include hold_alternative with direction and strategies"""

            retry_response = llm.invoke(retry_prompt)
            retry_text = retry_response.content
            if isinstance(retry_text, list):
                # Handle list of content blocks
                texts = []
                for block in retry_text:
                    if isinstance(block, dict) and 'text' in block:
                        texts.append(block['text'])
                    elif hasattr(block, 'text'):
                        texts.append(block.text)
                    else:
                        texts.append(str(block))
                retry_text = "\n".join(texts)
            elif isinstance(retry_text, dict) and 'text' in retry_text:
                retry_text = retry_text['text']
            trade_decision = parse_trade_decision_json(retry_text)

            if trade_decision is None:
                # Still failed after retry - raise error
                raise ValueError(
                    f"Failed to parse trade decision JSON after retry. "
                    f"Original response: {response_text[:500]}... "
                    f"Retry response: {retry_response.content[:500]}..."
                )

        new_risk_debate_state = {
            "judge_decision": response_text,
            "history": risk_debate_state["history"],
            "risky_history": risk_debate_state["risky_history"],
            "safe_history": risk_debate_state["safe_history"],
            "neutral_history": risk_debate_state["neutral_history"],
            "latest_speaker": "Judge",
            "current_risky_response": risk_debate_state["current_risky_response"],
            "current_safe_response": risk_debate_state["current_safe_response"],
            "current_neutral_response": risk_debate_state["current_neutral_response"],
            "count": risk_debate_state["count"],
        }

        return {
            "risk_debate_state": new_risk_debate_state,
            "final_trade_decision": response_text,
            "trade_decision": trade_decision,  # Structured data!
        }

    return risk_manager_node

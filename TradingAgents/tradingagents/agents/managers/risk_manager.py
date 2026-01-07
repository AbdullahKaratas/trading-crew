import time
import json
import re


# JSON Schema for structured trade decision
TRADE_DECISION_SCHEMA = {
    "signal": "BUY | SELL | HOLD",
    "confidence": 0.75,  # 0.0 to 1.0
    "entry_price": 0.0,
    "stop_loss_price": 0.0,
    "stop_loss_pct": 0.0,
    "target_1_price": 0.0,
    "target_1_pct": 0.0,
    "target_2_price": 0.0,
    "target_2_pct": 0.0,
    "risk_reward_ratio": 0.0,
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

        history = state["risk_debate_state"]["history"]
        risk_debate_state = state["risk_debate_state"]
        market_research_report = state["market_report"]
        news_report = state["news_report"]
        fundamentals_report = state["news_report"]
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

        prompt = f"""{language_instruction}As the Risk Management Judge and Debate Facilitator, your goal is to evaluate the debate between three risk analysts—Risky, Neutral, and Safe/Conservative—and determine the best course of action for the trader. Your decision must result in a clear recommendation: Buy, Sell, or Hold. Choose Hold only if strongly justified by specific arguments, not as a fallback when all sides seem valid. Strive for clarity and decisiveness.

Guidelines for Decision-Making:
1. **Summarize Key Arguments**: Extract the strongest points from each analyst, focusing on relevance to the context.
2. **Provide Rationale**: Support your recommendation with direct quotes and counterarguments from the debate.
3. **Refine the Trader's Plan**: Start with the trader's original plan, **{trader_plan}**, and adjust it based on the analysts' insights.
4. **Learn from Past Mistakes**: Use lessons from **{past_memory_str}** to address prior misjudgments and improve the decision you are making now to make sure you don't make a wrong BUY/SELL/HOLD call that loses money.

---

**Analysts Debate History:**
{history}

---

## Your Response Format

First, provide your detailed analysis and reasoning.

Then, at the VERY END of your response, you MUST include a structured JSON block with your trading decision. This is REQUIRED and must follow this exact format:

```json
{{
  "signal": "BUY",
  "confidence": 0.75,
  "entry_price": 150.50,
  "stop_loss_price": 142.00,
  "stop_loss_pct": -5.6,
  "target_1_price": 165.00,
  "target_1_pct": 9.6,
  "target_2_price": 180.00,
  "target_2_pct": 19.6,
  "risk_reward_ratio": 2.5
}}
```

**JSON Field Requirements:**
- `signal`: Must be exactly "BUY", "SELL", or "HOLD" (uppercase)
- `confidence`: Your confidence level from 0.0 (no confidence) to 1.0 (very confident)
- `entry_price`: Recommended entry price based on technical analysis
- `stop_loss_price`: Stop-loss price level
- `stop_loss_pct`: Stop-loss as negative percentage from entry (e.g., -5.6)
- `target_1_price`: First price target
- `target_1_pct`: First target as positive percentage from entry
- `target_2_price`: Second price target
- `target_2_pct`: Second target as positive percentage from entry
- `risk_reward_ratio`: Risk/reward ratio (e.g., 2.5 means 2.5:1)

Base all prices on the technical analysis, support/resistance levels, and risk management principles discussed in the debate. The JSON block must be the LAST thing in your response."""

        response = llm.invoke(prompt)
        response_text = response.content

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
  "signal": "BUY",
  "confidence": 0.75,
  "entry_price": 150.50,
  "stop_loss_price": 142.00,
  "stop_loss_pct": -5.6,
  "target_1_price": 165.00,
  "target_1_pct": 9.6,
  "target_2_price": 180.00,
  "target_2_pct": 19.6,
  "risk_reward_ratio": 2.5
}}
```

Replace the example values with your actual recommendation. Signal must be "BUY", "SELL", or "HOLD"."""

            retry_response = llm.invoke(retry_prompt)
            trade_decision = parse_trade_decision_json(retry_response.content)

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

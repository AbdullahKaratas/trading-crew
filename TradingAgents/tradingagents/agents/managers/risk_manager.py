import time
import json


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

Deliverables:
- A clear and actionable recommendation: Buy, Sell, or Hold.
- Detailed reasoning anchored in the debate and past reflections.
- **REQUIRED - Action Box**: At the END of your response, include a clearly formatted action box with specific prices:

```
📋 ACTION BOX
━━━━━━━━━━━━━━━━━━━━
Signal: [BUY/SELL/HOLD]
Entry: $XX.XX (ideal entry price)
Stop-Loss: $XX.XX (-X.X%)
Target 1: $XX.XX (+X.X%)
Target 2: $XX.XX (+X.X%)
Risk/Reward: X.X:1
━━━━━━━━━━━━━━━━━━━━
```

Base these prices on the technical analysis, support/resistance levels, and risk management principles discussed in the debate. The entry price should be a realistic price point based on current market conditions, not the current price.

---

**Analysts Debate History:**
{history}

---

Focus on actionable insights and continuous improvement. Build on past lessons, critically evaluate all perspectives, and ensure each decision advances better outcomes. Always end with the ACTION BOX containing specific price levels."""

        response = llm.invoke(prompt)

        new_risk_debate_state = {
            "judge_decision": response.content,
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
            "final_trade_decision": response.content,
        }

    return risk_manager_node

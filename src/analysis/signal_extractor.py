"""
Signal Extractor - Uses Claude to extract structured trading signals from TradingAgents output.
No hardcoded values - everything comes from the LLM analysis.
"""

import anthropic
from dataclasses import dataclass
from typing import Optional
import json
import re
from dotenv import load_dotenv

# Ensure .env is loaded (override system env vars)
load_dotenv(override=True)


@dataclass
class ExtractedSignal:
    """Structured trading signal extracted from LLM analysis."""
    # Core signal
    signal_type: str  # BUY, SELL, HOLD
    action_detail: str  # e.g., "SELL 60-70% of position"
    confidence_reasoning: str  # Why this confidence level

    # Price levels (all from LLM, no defaults)
    current_price: Optional[float]
    stop_loss: Optional[float]
    stop_loss_reasoning: str

    # Targets
    exit_targets: list[dict]  # [{"price": 26.0, "action": "exit on pop"}]

    # Key events and conditions
    key_events: list[str]  # ["January 7 Earnings", "Fed meeting"]
    exit_conditions: list[str]  # ["Gross margin < 13%", "Break below $20"]

    # Summary
    bull_case: str
    bear_case: str
    final_recommendation: str


def extract_signal_with_claude(
    final_decision: str,
    investment_plan: str,
    symbol: str,
    current_price: float
) -> ExtractedSignal:
    """
    Use Claude Haiku to extract structured trading signal from TradingAgents output.

    Args:
        final_decision: The final_trade_decision from TradingAgents
        investment_plan: The investment_plan from TradingAgents
        symbol: Stock ticker
        current_price: Current stock price from yfinance

    Returns:
        ExtractedSignal with all values from LLM analysis
    """
    client = anthropic.Anthropic()

    prompt = f"""Analyze this trading recommendation for {symbol} (current price: ${current_price:.2f}) and extract structured information.

FINAL TRADE DECISION:
{final_decision[:8000]}

INVESTMENT PLAN:
{investment_plan[:4000]}

Extract the following as JSON (use null if not found, never make up values):
{{
    "signal_type": "BUY" or "SELL" or "HOLD",
    "action_detail": "exact recommendation, e.g. 'SELL 60-70% of position'",
    "confidence_reasoning": "why this level of confidence",
    "stop_loss": number or null,
    "stop_loss_reasoning": "why this stop loss level",
    "exit_targets": [
        {{"price": number, "action": "description"}}
    ],
    "key_events": ["event 1", "event 2"],
    "exit_conditions": ["condition that would trigger exit"],
    "bull_case": "1-2 sentence bull case summary",
    "bear_case": "1-2 sentence bear case summary",
    "final_recommendation": "2-3 sentence actionable recommendation"
}}

Return ONLY valid JSON, no other text."""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}]
    )

    # Extract JSON from response
    response_text = response.content[0].text.strip()

    # Try to parse JSON (handle potential markdown code blocks)
    if response_text.startswith("```"):
        response_text = re.sub(r'^```json?\n?', '', response_text)
        response_text = re.sub(r'\n?```$', '', response_text)

    try:
        data = json.loads(response_text)
    except json.JSONDecodeError:
        # Fallback: try to extract JSON from response
        json_match = re.search(r'\{[\s\S]*\}', response_text)
        if json_match:
            data = json.loads(json_match.group())
        else:
            # Return minimal signal if parsing fails
            return ExtractedSignal(
                signal_type="HOLD",
                action_detail="Unable to parse recommendation - review manually",
                confidence_reasoning="Parsing error",
                current_price=current_price,
                stop_loss=None,
                stop_loss_reasoning="Not extracted",
                exit_targets=[],
                key_events=[],
                exit_conditions=[],
                bull_case="See full analysis",
                bear_case="See full analysis",
                final_recommendation="Manual review required"
            )

    return ExtractedSignal(
        signal_type=data.get("signal_type", "HOLD"),
        action_detail=data.get("action_detail", ""),
        confidence_reasoning=data.get("confidence_reasoning", ""),
        current_price=current_price,
        stop_loss=data.get("stop_loss"),
        stop_loss_reasoning=data.get("stop_loss_reasoning", ""),
        exit_targets=data.get("exit_targets", []),
        key_events=data.get("key_events", []),
        exit_conditions=data.get("exit_conditions", []),
        bull_case=data.get("bull_case", ""),
        bear_case=data.get("bear_case", ""),
        final_recommendation=data.get("final_recommendation", "")
    )


def format_signal_for_telegram(signal: ExtractedSignal, symbol: str, name: str) -> str:
    """
    Format extracted signal for Telegram message.
    Shows real LLM recommendations, not hardcoded values.
    """
    # Signal emoji
    emoji = {
        "BUY": "\U0001F7E2",   # Green circle
        "SELL": "\U0001F534",  # Red circle
        "HOLD": "\U0001F7E1"   # Yellow circle
    }.get(signal.signal_type, "\u26AA")  # White circle default

    lines = [
        f"{emoji} *{signal.signal_type} SIGNAL: {symbol}* ({name})",
        "",
        f"\U0001F4B0 *Preis:* ${signal.current_price:.2f}" if signal.current_price else "",
        f"\U0001F3AF *Aktion:* {signal.action_detail}",
    ]

    # Stop Loss
    if signal.stop_loss:
        pct = ((signal.stop_loss - signal.current_price) / signal.current_price * 100) if signal.current_price else 0
        lines.append(f"\U0001F6D1 *Stop-Loss:* ${signal.stop_loss:.2f} ({pct:+.1f}%)")

    # Exit Targets
    if signal.exit_targets:
        lines.append("")
        lines.append("\U0001F3AF *Exit Targets:*")
        for target in signal.exit_targets[:3]:  # Max 3 targets
            if isinstance(target, dict) and target.get("price"):
                lines.append(f"  \u2022 ${target['price']:.2f}: {target.get('action', '')}")

    # Key Events
    if signal.key_events:
        lines.append("")
        lines.append("\U0001F4C5 *Wichtige Events:*")
        for event in signal.key_events[:3]:
            lines.append(f"  \u2022 {event}")

    # Exit Conditions
    if signal.exit_conditions:
        lines.append("")
        lines.append("\u26A0\uFE0F *Exit wenn:*")
        for condition in signal.exit_conditions[:3]:
            lines.append(f"  \u2022 {condition}")

    # Final Recommendation
    if signal.final_recommendation:
        lines.append("")
        lines.append(f"\U0001F4AC *Empfehlung:*")
        lines.append(signal.final_recommendation)

    # Filter empty lines at start/end
    return "\n".join(line for line in lines if line is not None)

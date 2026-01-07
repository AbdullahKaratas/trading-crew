"""Analyze command handler."""

import asyncio
from typing import Optional

import structlog

from ..user_state import UserStateManager, UserState

logger = structlog.get_logger()


class AnalyzeCommand:
    """
    Handle /analyze command for single stock analysis.

    Usage:
        /analyze AAPL
        /analyze AAPL 5000  (with budget in EUR)
    """

    def __init__(self, user_state: UserStateManager, config: dict):
        self.user_state = user_state
        self.config = config

    async def execute(
        self,
        symbol: str,
        user: UserState,
        budget: Optional[float] = None
    ) -> str:
        """
        Execute analysis for a single stock.

        Args:
            symbol: Stock ticker symbol
            user: User state with profile and portfolio
            budget: Optional budget in EUR for position sizing

        Returns:
            Formatted analysis result
        """
        from tradingagents import TradingAgentsGraph

        logger.info("analyze_command", symbol=symbol, user_id=user.user_id, budget=budget)

        try:
            # Initialize TradingAgents
            ta = TradingAgentsGraph(config=self.config)

            # Run analysis
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: ta.propagate(symbol)
            )

            # Format response
            return self._format_result(symbol, result, user, budget)

        except Exception as e:
            logger.error("analyze_failed", symbol=symbol, error=str(e))
            raise

    def _format_result(
        self,
        symbol: str,
        result: dict,
        user: UserState,
        budget: Optional[float] = None
    ) -> str:
        """Format analysis result for Telegram."""
        # Extract key information
        final_trade_decision = result.get("final_trade_decision", "")

        # Parse the decision
        signal_type = "HOLD"
        if "BUY" in final_trade_decision.upper()[:100]:
            signal_type = "BUY"
            emoji = "🟢"
        elif "SELL" in final_trade_decision.upper()[:100] or "SHORT" in final_trade_decision.upper()[:100]:
            signal_type = "SELL"
            emoji = "🔴"
        else:
            emoji = "🟡"

        # Get risk settings
        risk_settings = user.get_risk_settings()
        stop_loss_pct = risk_settings["default_stop_loss_pct"]

        # Build response
        response = f"""
{emoji} *{signal_type}: {symbol}*

📊 *Analyse:*
{self._truncate(final_trade_decision, 1500)}
"""

        # Add budget-based position sizing
        if budget:
            response += f"""
💰 *Position Sizing (Budget: €{budget:,.0f}):*
├── Empfohlene Position: €{budget * 0.3:,.0f} - €{budget * 0.5:,.0f}
├── Max Risiko ({stop_loss_pct}% SL): €{budget * 0.5 * (stop_loss_pct/100):,.0f}
└── Profil: {user.risk_profile.capitalize()}
"""

        # Add chart link
        response += f"""
📈 [Chart auf TradingView](https://www.tradingview.com/chart/?symbol={symbol})
"""
        return response.strip()

    def _truncate(self, text: str, max_length: int) -> str:
        """Truncate text to max length."""
        if len(text) <= max_length:
            return text
        return text[:max_length-3] + "..."

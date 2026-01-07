"""Long/Short knockout certificate command handler."""

import asyncio
from typing import Optional

import structlog
import yfinance as yf

from ..user_state import UserStateManager, UserState

logger = structlog.get_logger()


class LongShortCommand:
    """
    Handle /long and /short commands for knockout certificate analysis.

    Usage:
        /long AAPL
        /long AAPL 1000  (with budget in EUR)
        /short TSLA
        /short TSLA 500
    """

    def __init__(self, user_state: UserStateManager, config: dict):
        self.user_state = user_state
        self.config = config

    async def execute(
        self,
        symbol: str,
        direction: str,  # "long" or "short"
        user: UserState,
        budget: Optional[float] = None
    ) -> str:
        """
        Execute knockout certificate analysis.

        Args:
            symbol: Stock ticker symbol
            direction: "long" or "short"
            user: User state with profile
            budget: Optional budget in EUR

        Returns:
            Formatted knockout analysis
        """
        from tradingagents import TradingAgentsGraph

        logger.info(
            "knockout_command",
            symbol=symbol,
            direction=direction,
            user_id=user.user_id,
            budget=budget
        )

        try:
            # Get current price and technical data
            stock_data = await self._get_stock_data(symbol)

            # Initialize TradingAgents for analysis
            ta = TradingAgentsGraph(config=self.config)

            # Run analysis
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: ta.propagate(symbol)
            )

            # Format knockout-specific response
            return self._format_knockout_result(
                symbol, direction, result, stock_data, user, budget
            )

        except Exception as e:
            logger.error("knockout_failed", symbol=symbol, direction=direction, error=str(e))
            raise

    async def _get_stock_data(self, symbol: str) -> dict:
        """Get current stock data for knockout calculations."""
        loop = asyncio.get_event_loop()

        def fetch():
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="3mo")
            info = ticker.info

            if hist.empty:
                raise ValueError(f"No data found for {symbol}")

            current_price = hist["Close"].iloc[-1]

            # Calculate support/resistance levels
            recent_low = hist["Low"].tail(20).min()
            recent_high = hist["High"].tail(20).max()

            # 52-week data
            hist_1y = ticker.history(period="1y")
            week_52_low = hist_1y["Low"].min() if not hist_1y.empty else recent_low
            week_52_high = hist_1y["High"].max() if not hist_1y.empty else recent_high

            # ATR for volatility
            high_low = hist["High"] - hist["Low"]
            atr = high_low.tail(14).mean()
            atr_pct = (atr / current_price) * 100

            return {
                "current_price": current_price,
                "recent_low": recent_low,
                "recent_high": recent_high,
                "week_52_low": week_52_low,
                "week_52_high": week_52_high,
                "atr": atr,
                "atr_pct": atr_pct,
                "name": info.get("shortName", symbol),
                "currency": info.get("currency", "USD"),
            }

        return await loop.run_in_executor(None, fetch)

    def _format_knockout_result(
        self,
        symbol: str,
        direction: str,
        analysis_result: dict,
        stock_data: dict,
        user: UserState,
        budget: Optional[float] = None
    ) -> str:
        """Format knockout certificate analysis."""
        risk_settings = user.get_risk_settings()
        max_leverage = risk_settings["max_leverage"]
        ko_buffer_pct = risk_settings["knockout_buffer_pct"]

        current_price = stock_data["current_price"]
        atr_pct = stock_data["atr_pct"]

        # Calculate knockout levels based on direction
        if direction == "long":
            emoji = "📈"
            # KO level below support
            ko_level = stock_data["recent_low"] * (1 - ko_buffer_pct / 100)
            distance_to_ko = ((current_price - ko_level) / current_price) * 100

            # Targets above current price
            target_1 = current_price * 1.05  # +5%
            target_2 = current_price * 1.10  # +10%

            # Recommended leverage based on distance to KO
            rec_leverage = min(max_leverage, max(2, int(100 / distance_to_ko)))

            direction_text = "LONG"
            direction_desc = "Bullish - Kurs steigt"
        else:
            emoji = "📉"
            # KO level above resistance
            ko_level = stock_data["recent_high"] * (1 + ko_buffer_pct / 100)
            distance_to_ko = ((ko_level - current_price) / current_price) * 100

            # Targets below current price
            target_1 = current_price * 0.95  # -5%
            target_2 = current_price * 0.90  # -10%

            # Recommended leverage
            rec_leverage = min(max_leverage, max(2, int(100 / distance_to_ko)))

            direction_text = "SHORT"
            direction_desc = "Bearish - Kurs fällt"

        # Extract reasoning from analysis
        final_decision = analysis_result.get("final_trade_decision", "")
        reasoning = self._extract_key_points(final_decision)

        # Build response
        currency = stock_data.get("currency", "USD")
        response = f"""
{emoji} *{direction_text} KNOCKOUT: {symbol}*
_{stock_data.get('name', symbol)}_

💵 *Aktueller Kurs:* {currency} {current_price:,.2f}

🎯 *Knockout-Empfehlung:*
├── KO-Level: {currency} {ko_level:,.2f}
├── Abstand zum KO: {distance_to_ko:.1f}%
├── Empf. Hebel: {rec_leverage}x (max: {max_leverage}x)
└── Richtung: {direction_desc}

📊 *Kursziele:*
├── Target 1: {currency} {target_1:,.2f} ({'+' if direction == 'long' else ''}{((target_1/current_price)-1)*100:.1f}%)
└── Target 2: {currency} {target_2:,.2f} ({'+' if direction == 'long' else ''}{((target_2/current_price)-1)*100:.1f}%)

📈 *Technische Daten:*
├── ATR (14): {atr_pct:.1f}% (Volatilität)
├── Support: {currency} {stock_data['recent_low']:,.2f}
└── Resistance: {currency} {stock_data['recent_high']:,.2f}
"""

        # Add position sizing if budget provided
        if budget:
            position_size = budget * 0.3  # 30% of budget
            max_loss_eur = position_size  # KO = total loss
            potential_gain = position_size * rec_leverage * 0.05  # 5% move

            response += f"""
💰 *Position (Budget: €{budget:,.0f}):*
├── Empf. Einsatz: €{position_size:,.0f}
├── Max. Verlust (KO): €{position_size:,.0f}
├── Pot. Gewinn (+5%): €{potential_gain:,.0f}
└── Profil: {user.risk_profile.capitalize()}
"""

        # Add key reasoning
        response += f"""
💡 *Analyse:*
{reasoning}

⚠️ *Risiko:* Bei Knockout = Totalverlust!
Nur mit Geld handeln, das du verlieren kannst.

📈 [Chart](https://www.tradingview.com/chart/?symbol={symbol})
"""
        return response.strip()

    def _extract_key_points(self, text: str, max_length: int = 400) -> str:
        """Extract key points from analysis text."""
        if not text:
            return "Keine detaillierte Analyse verfügbar."

        # Try to get first few sentences
        sentences = text.split(".")
        result = ""
        for sentence in sentences[:4]:
            if len(result) + len(sentence) < max_length:
                result += sentence.strip() + ". "
            else:
                break

        return result.strip() if result else text[:max_length] + "..."

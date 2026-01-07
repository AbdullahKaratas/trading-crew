"""Compare command handler."""

import asyncio
from typing import Optional

import structlog
import yfinance as yf

from ..user_state import UserStateManager, UserState

logger = structlog.get_logger()


class CompareCommand:
    """
    Handle /compare command for comparing two stocks.

    Usage:
        /compare AAPL MSFT
    """

    def __init__(self, user_state: UserStateManager, config: dict):
        self.user_state = user_state
        self.config = config

    async def execute(
        self,
        symbol1: str,
        symbol2: str,
        user: UserState
    ) -> str:
        """
        Compare two stocks.

        Args:
            symbol1: First stock ticker
            symbol2: Second stock ticker
            user: User state

        Returns:
            Formatted comparison result
        """
        from tradingagents import TradingAgentsGraph

        logger.info("compare_command", symbols=[symbol1, symbol2], user_id=user.user_id)

        try:
            # Get stock data for both
            data1, data2 = await asyncio.gather(
                self._get_stock_metrics(symbol1),
                self._get_stock_metrics(symbol2)
            )

            # Run TradingAgents analysis for both (in parallel)
            ta = TradingAgentsGraph(config=self.config)
            loop = asyncio.get_event_loop()

            result1, result2 = await asyncio.gather(
                loop.run_in_executor(None, lambda: ta.propagate(symbol1)),
                loop.run_in_executor(None, lambda: ta.propagate(symbol2))
            )

            # Format comparison
            return self._format_comparison(
                symbol1, symbol2,
                data1, data2,
                result1, result2,
                user
            )

        except Exception as e:
            logger.error("compare_failed", symbols=[symbol1, symbol2], error=str(e))
            raise

    async def _get_stock_metrics(self, symbol: str) -> dict:
        """Get key metrics for a stock."""
        loop = asyncio.get_event_loop()

        def fetch():
            ticker = yf.Ticker(symbol)
            info = ticker.info
            hist = ticker.history(period="1y")

            if hist.empty:
                raise ValueError(f"No data for {symbol}")

            current_price = hist["Close"].iloc[-1]
            price_1m = hist["Close"].iloc[-22] if len(hist) > 22 else current_price
            price_3m = hist["Close"].iloc[-66] if len(hist) > 66 else current_price
            price_1y = hist["Close"].iloc[0] if len(hist) > 200 else current_price

            return {
                "name": info.get("shortName", symbol),
                "price": current_price,
                "currency": info.get("currency", "USD"),
                "market_cap": info.get("marketCap", 0),
                "pe_ratio": info.get("trailingPE", None),
                "forward_pe": info.get("forwardPE", None),
                "dividend_yield": info.get("dividendYield", 0) or 0,
                "beta": info.get("beta", 1),
                "return_1m": ((current_price / price_1m) - 1) * 100,
                "return_3m": ((current_price / price_3m) - 1) * 100,
                "return_1y": ((current_price / price_1y) - 1) * 100,
                "sector": info.get("sector", "Unknown"),
                "industry": info.get("industry", "Unknown"),
            }

        return await loop.run_in_executor(None, fetch)

    def _format_comparison(
        self,
        symbol1: str, symbol2: str,
        data1: dict, data2: dict,
        result1: dict, result2: dict,
        user: UserState
    ) -> str:
        """Format the comparison output."""
        # Determine signals
        decision1 = result1.get("final_trade_decision", "").upper()[:200]
        decision2 = result2.get("final_trade_decision", "").upper()[:200]

        signal1 = "BUY" if "BUY" in decision1 else ("SELL" if "SELL" in decision1 or "SHORT" in decision1 else "HOLD")
        signal2 = "BUY" if "BUY" in decision2 else ("SELL" if "SELL" in decision2 or "SHORT" in decision2 else "HOLD")

        emoji1 = "🟢" if signal1 == "BUY" else ("🔴" if signal1 == "SELL" else "🟡")
        emoji2 = "🟢" if signal2 == "BUY" else ("🔴" if signal2 == "SELL" else "🟡")

        # Score comparison
        score1, score2 = self._calculate_scores(data1, data2)

        # Winner determination
        if score1 > score2:
            winner = symbol1
            winner_emoji = "👑"
        elif score2 > score1:
            winner = symbol2
            winner_emoji = "👑"
        else:
            winner = "Gleichstand"
            winner_emoji = "⚖️"

        # Format numbers
        def fmt_cap(cap):
            if cap >= 1e12:
                return f"${cap/1e12:.1f}T"
            elif cap >= 1e9:
                return f"${cap/1e9:.1f}B"
            elif cap >= 1e6:
                return f"${cap/1e6:.1f}M"
            return f"${cap:,.0f}"

        def fmt_pe(pe):
            return f"{pe:.1f}" if pe else "N/A"

        def fmt_pct(pct):
            return f"{'+' if pct >= 0 else ''}{pct:.1f}%"

        response = f"""
⚖️ *VERGLEICH: {symbol1} vs {symbol2}*

{winner_emoji} *Gewinner: {winner}* (Score: {score1:.0f} vs {score2:.0f})

┌─────────────────────────────────────┐
│ *{symbol1}* ({data1['name'][:15]})
│ {emoji1} Signal: {signal1}
│ 💵 Kurs: {data1['currency']} {data1['price']:,.2f}
│ 📊 Market Cap: {fmt_cap(data1['market_cap'])}
│ 📈 P/E: {fmt_pe(data1['pe_ratio'])} | Fwd: {fmt_pe(data1['forward_pe'])}
│ 💰 Dividende: {data1['dividend_yield']*100:.2f}%
│ ⚡ Beta: {data1['beta']:.2f}
│
│ Performance:
│ • 1M: {fmt_pct(data1['return_1m'])}
│ • 3M: {fmt_pct(data1['return_3m'])}
│ • 1Y: {fmt_pct(data1['return_1y'])}
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│ *{symbol2}* ({data2['name'][:15]})
│ {emoji2} Signal: {signal2}
│ 💵 Kurs: {data2['currency']} {data2['price']:,.2f}
│ 📊 Market Cap: {fmt_cap(data2['market_cap'])}
│ 📈 P/E: {fmt_pe(data2['pe_ratio'])} | Fwd: {fmt_pe(data2['forward_pe'])}
│ 💰 Dividende: {data2['dividend_yield']*100:.2f}%
│ ⚡ Beta: {data2['beta']:.2f}
│
│ Performance:
│ • 1M: {fmt_pct(data2['return_1m'])}
│ • 3M: {fmt_pct(data2['return_3m'])}
│ • 1Y: {fmt_pct(data2['return_1y'])}
└─────────────────────────────────────┘

📊 *Sektor:*
• {symbol1}: {data1['sector']} / {data1['industry'][:20]}
• {symbol2}: {data2['sector']} / {data2['industry'][:20]}

💡 *Empfehlung:*
{self._generate_recommendation(symbol1, symbol2, signal1, signal2, data1, data2, winner)}
"""
        return response.strip()

    def _calculate_scores(self, data1: dict, data2: dict) -> tuple[float, float]:
        """Calculate comparison scores based on multiple factors."""
        score1, score2 = 50, 50

        # Performance comparison (40 points max)
        if data1["return_1y"] > data2["return_1y"]:
            score1 += 15
        else:
            score2 += 15

        if data1["return_3m"] > data2["return_3m"]:
            score1 += 15
        else:
            score2 += 15

        if data1["return_1m"] > data2["return_1m"]:
            score1 += 10
        else:
            score2 += 10

        # Valuation (20 points) - lower P/E is better
        pe1 = data1["pe_ratio"] or 100
        pe2 = data2["pe_ratio"] or 100
        if pe1 < pe2:
            score1 += 20
        elif pe2 < pe1:
            score2 += 20

        # Dividend (10 points)
        if data1["dividend_yield"] > data2["dividend_yield"]:
            score1 += 10
        else:
            score2 += 10

        return score1, score2

    def _generate_recommendation(
        self,
        symbol1: str, symbol2: str,
        signal1: str, signal2: str,
        data1: dict, data2: dict,
        winner: str
    ) -> str:
        """Generate a recommendation based on comparison."""
        if signal1 == "BUY" and signal2 != "BUY":
            return f"{symbol1} hat ein BUY-Signal und scheint der bessere Trade zu sein."
        elif signal2 == "BUY" and signal1 != "BUY":
            return f"{symbol2} hat ein BUY-Signal und scheint der bessere Trade zu sein."
        elif signal1 == signal2 == "BUY":
            return f"Beide haben BUY-Signale. {winner} hat bessere Metriken."
        elif signal1 == signal2 == "HOLD":
            return f"Beide auf HOLD. Abwarten für bessere Einstiegspunkte."
        else:
            return f"Basierend auf der Analyse: {winner} bevorzugt."

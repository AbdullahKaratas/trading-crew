"""Risk assessment command handler."""

import asyncio
from collections import defaultdict
from typing import Optional

import structlog
import yfinance as yf
import numpy as np

from ..user_state import UserStateManager, UserState

logger = structlog.get_logger()


# Sector mapping for common stocks
SECTOR_OVERRIDES = {
    "BTC-USD": "Crypto",
    "ETH-USD": "Crypto",
    "GC=F": "Commodities",
    "SI=F": "Commodities",
    "CL=F": "Commodities",
}


class RiskCommand:
    """
    Handle /risk command for portfolio risk assessment.

    Analyzes:
    - Sector concentration
    - Correlation between holdings
    - Portfolio beta
    - Event risk (earnings dates)
    - Drawdown scenarios
    """

    def __init__(self, user_state: UserStateManager, config: dict):
        self.user_state = user_state
        self.config = config

    async def execute(self, user: UserState) -> str:
        """
        Execute portfolio risk assessment.

        Args:
            user: User state with portfolio

        Returns:
            Formatted risk assessment
        """
        logger.info("risk_command", user_id=user.user_id, positions=len(user.portfolio))

        if not user.portfolio:
            return "❌ Kein Portfolio gesetzt. Nutze `/portfolio AAPL:5000 MSFT:3000`"

        # Fetch data for all positions
        portfolio_data = await self._fetch_portfolio_data(user.portfolio)

        # Calculate risk metrics
        risk_metrics = self._calculate_risk_metrics(
            user.portfolio,
            portfolio_data,
            user.get_risk_settings()
        )

        # Format response
        return self._format_risk_report(user, portfolio_data, risk_metrics)

    async def _fetch_portfolio_data(self, portfolio: dict[str, float]) -> dict:
        """Fetch market data for all portfolio positions."""
        loop = asyncio.get_event_loop()

        async def fetch_single(symbol: str) -> tuple[str, dict]:
            def _fetch():
                try:
                    ticker = yf.Ticker(symbol)
                    info = ticker.info
                    hist = ticker.history(period="1y")

                    if hist.empty:
                        return symbol, None

                    # Get earnings date
                    try:
                        calendar = ticker.calendar
                        earnings_date = calendar.get("Earnings Date", [None])[0] if calendar else None
                    except Exception:
                        earnings_date = None

                    return symbol, {
                        "name": info.get("shortName", symbol),
                        "sector": SECTOR_OVERRIDES.get(symbol, info.get("sector", "Unknown")),
                        "industry": info.get("industry", "Unknown"),
                        "beta": info.get("beta", 1.0) or 1.0,
                        "price": hist["Close"].iloc[-1],
                        "returns": hist["Close"].pct_change().dropna(),
                        "earnings_date": earnings_date,
                        "market_cap": info.get("marketCap", 0),
                    }
                except Exception as e:
                    logger.warning("fetch_failed", symbol=symbol, error=str(e))
                    return symbol, None

            return await loop.run_in_executor(None, _fetch)

        # Fetch all in parallel
        results = await asyncio.gather(*[fetch_single(s) for s in portfolio.keys()])
        return {symbol: data for symbol, data in results if data is not None}

    def _calculate_risk_metrics(
        self,
        portfolio: dict[str, float],
        portfolio_data: dict,
        risk_settings: dict
    ) -> dict:
        """Calculate comprehensive risk metrics."""
        total_value = sum(portfolio.values())
        weights = {s: v / total_value for s, v in portfolio.items()}

        # Sector concentration
        sector_weights = defaultdict(float)
        for symbol, weight in weights.items():
            if symbol in portfolio_data:
                sector = portfolio_data[symbol]["sector"]
                sector_weights[sector] += weight

        max_sector_weight = max(sector_weights.values()) if sector_weights else 0
        sector_concentration_ok = max_sector_weight <= risk_settings["max_sector_concentration"]

        # Top holdings concentration
        sorted_weights = sorted(weights.values(), reverse=True)
        top_2_concentration = sum(sorted_weights[:2]) if len(sorted_weights) >= 2 else 1.0

        # Portfolio beta
        portfolio_beta = sum(
            weights.get(s, 0) * portfolio_data[s]["beta"]
            for s in portfolio_data.keys()
        )

        # Correlation matrix (simplified - using returns correlation)
        correlations = {}
        symbols_with_returns = [s for s in portfolio_data if portfolio_data[s]["returns"] is not None]
        if len(symbols_with_returns) >= 2:
            for i, s1 in enumerate(symbols_with_returns):
                for s2 in symbols_with_returns[i+1:]:
                    try:
                        r1 = portfolio_data[s1]["returns"]
                        r2 = portfolio_data[s2]["returns"]
                        # Align dates
                        common_idx = r1.index.intersection(r2.index)
                        if len(common_idx) > 20:
                            corr = r1.loc[common_idx].corr(r2.loc[common_idx])
                            correlations[f"{s1}-{s2}"] = corr
                    except Exception:
                        pass

        # Average correlation
        avg_correlation = np.mean(list(correlations.values())) if correlations else 0

        # High correlations (>0.7)
        high_correlations = {k: v for k, v in correlations.items() if v > 0.7}

        # Upcoming earnings (within 14 days)
        from datetime import datetime, timedelta
        upcoming_earnings = []
        now = datetime.now()
        for symbol, data in portfolio_data.items():
            if data.get("earnings_date"):
                try:
                    earnings_dt = data["earnings_date"]
                    if hasattr(earnings_dt, 'date'):
                        earnings_dt = earnings_dt.date()
                    days_until = (earnings_dt - now.date()).days
                    if 0 <= days_until <= 14:
                        upcoming_earnings.append((symbol, days_until))
                except Exception:
                    pass

        # Calculate overall risk score (0-100)
        risk_score = 50  # Base score

        # Sector concentration adds risk
        if max_sector_weight > 0.8:
            risk_score += 25
        elif max_sector_weight > 0.6:
            risk_score += 15
        elif max_sector_weight > 0.4:
            risk_score += 5

        # High beta adds risk
        if portfolio_beta > 1.5:
            risk_score += 15
        elif portfolio_beta > 1.2:
            risk_score += 10

        # High correlation adds risk
        if avg_correlation > 0.7:
            risk_score += 10
        elif avg_correlation > 0.5:
            risk_score += 5

        # Upcoming earnings add risk
        risk_score += len(upcoming_earnings) * 3

        # Top 2 concentration
        if top_2_concentration > 0.7:
            risk_score += 10

        risk_score = min(100, max(0, risk_score))

        return {
            "risk_score": risk_score,
            "sector_weights": dict(sector_weights),
            "max_sector_weight": max_sector_weight,
            "sector_concentration_ok": sector_concentration_ok,
            "top_2_concentration": top_2_concentration,
            "portfolio_beta": portfolio_beta,
            "correlations": correlations,
            "high_correlations": high_correlations,
            "avg_correlation": avg_correlation,
            "upcoming_earnings": upcoming_earnings,
            "total_value": total_value,
        }

    def _format_risk_report(
        self,
        user: UserState,
        portfolio_data: dict,
        metrics: dict
    ) -> str:
        """Format risk assessment report."""
        risk_score = metrics["risk_score"]
        risk_settings = user.get_risk_settings()

        # Risk level text and emoji
        if risk_score <= 30:
            risk_level = "Niedrig"
            risk_emoji = "🟢"
        elif risk_score <= 50:
            risk_level = "Moderat"
            risk_emoji = "🟡"
        elif risk_score <= 70:
            risk_level = "Erhöht"
            risk_emoji = "🟠"
        else:
            risk_level = "Hoch"
            risk_emoji = "🔴"

        response = f"""
📊 *PORTFOLIO RISK ASSESSMENT*

Portfolio: €{metrics['total_value']:,.0f} | Profil: {user.risk_profile.capitalize()}

{risk_emoji} *RISIKO-SCORE: {risk_score}/100 ({risk_level})*

*KONZENTRATION:*
"""
        # Sector breakdown
        sorted_sectors = sorted(
            metrics["sector_weights"].items(),
            key=lambda x: x[1],
            reverse=True
        )

        for sector, weight in sorted_sectors[:5]:
            pct = weight * 100
            warning = " ⚠️" if pct > risk_settings["max_sector_concentration"] * 100 else ""
            response += f"├── {sector}: {pct:.0f}%{warning}\n"

        response += f"├── Top 2 Holdings: {metrics['top_2_concentration']*100:.0f}%\n"

        # Correlation
        response += f"""
*KORRELATION:*
├── Durchschnitt: {metrics['avg_correlation']:.2f}
"""
        if metrics["high_correlations"]:
            for pair, corr in list(metrics["high_correlations"].items())[:3]:
                response += f"├── {pair}: {corr:.2f} ⚠️\n"

        response += f"└── Portfolio-Beta: {metrics['portfolio_beta']:.2f}"

        if metrics["portfolio_beta"] > 1.2:
            response += " (volatiler als S&P500)"
        elif metrics["portfolio_beta"] < 0.8:
            response += " (defensiver als S&P500)"
        response += "\n"

        # Upcoming earnings
        if metrics["upcoming_earnings"]:
            response += "\n*EREIGNIS-RISIKO:*\n"
            for symbol, days in sorted(metrics["upcoming_earnings"], key=lambda x: x[1]):
                if days == 0:
                    response += f"├── {symbol} Earnings: HEUTE ⚠️\n"
                else:
                    response += f"├── {symbol} Earnings: in {days} Tagen\n"

        # Drawdown scenario
        beta = metrics["portfolio_beta"]
        response += f"""
*DRAWDOWN-SZENARIO:*
├── Bei -10% S&P500: ~{-10 * beta:.0f}% Portfolio
└── Bei -20% S&P500: ~{-20 * beta:.0f}% Portfolio
"""

        # Recommendations
        recommendations = self._generate_recommendations(metrics, risk_settings)
        if recommendations:
            response += "\n💡 *EMPFEHLUNGEN:*\n"
            for i, rec in enumerate(recommendations[:4], 1):
                response += f"{i}. {rec}\n"

        return response.strip()

    def _generate_recommendations(self, metrics: dict, risk_settings: dict) -> list[str]:
        """Generate risk reduction recommendations."""
        recommendations = []

        # Sector concentration
        max_allowed = risk_settings["max_sector_concentration"]
        for sector, weight in metrics["sector_weights"].items():
            if weight > max_allowed:
                recommendations.append(
                    f"Reduziere {sector}-Sektor ({weight*100:.0f}% > {max_allowed*100:.0f}% erlaubt)"
                )

        # Correlation
        if metrics["high_correlations"]:
            pairs = list(metrics["high_correlations"].keys())[:2]
            recommendations.append(
                f"Hohe Korrelation: {', '.join(pairs)} - ggf. diversifizieren"
            )

        # Beta
        if metrics["portfolio_beta"] > 1.5:
            recommendations.append(
                f"Portfolio sehr volatil (Beta {metrics['portfolio_beta']:.1f}) - defensive Werte hinzufügen?"
            )

        # Earnings
        if metrics["upcoming_earnings"]:
            symbols = [s for s, _ in metrics["upcoming_earnings"]]
            recommendations.append(
                f"Earnings bald: {', '.join(symbols)} - Positionen reduzieren?"
            )

        # Top concentration
        if metrics["top_2_concentration"] > 0.6:
            recommendations.append(
                "Top 2 Positionen >60% - mehr diversifizieren"
            )

        if not recommendations:
            recommendations.append("Portfolio sieht gut diversifiziert aus!")

        return recommendations

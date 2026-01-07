"""Portfolio command handler."""

import structlog

from ..user_state import UserStateManager, UserState

logger = structlog.get_logger()


class PortfolioCommand:
    """
    Handle /portfolio command for setting and viewing portfolio.

    Usage:
        /portfolio                    - Show current portfolio
        /portfolio AAPL:5000 MSFT:3000 - Set portfolio (amounts in EUR)
    """

    def __init__(self, user_state: UserStateManager):
        self.user_state = user_state

    def show_portfolio(self, user: UserState) -> str:
        """Show current portfolio."""
        if not user.portfolio:
            return """
📁 *Kein Portfolio gesetzt*

Setze dein Portfolio:
`/portfolio AAPL:5000 MSFT:3000 NVDA:2000`

Die Beträge sind in EUR.
"""

        total = user.total_portfolio_value
        percentages = user.get_portfolio_percentages()

        lines = ["📁 *Dein Portfolio*\n"]

        # Sort by value descending
        sorted_positions = sorted(
            user.portfolio.items(),
            key=lambda x: x[1],
            reverse=True
        )

        for symbol, amount in sorted_positions:
            pct = percentages[symbol]
            bar_length = int(pct / 5)  # 20 chars max
            bar = "█" * bar_length + "░" * (20 - bar_length)
            lines.append(f"├── *{symbol}*: €{amount:,.0f} ({pct:.1f}%)")
            lines.append(f"│   {bar}")

        lines.append(f"└── *Total*: €{total:,.0f}")
        lines.append(f"\n🎯 Profil: {user.risk_profile.capitalize()}")
        lines.append("\n_Ändern: `/portfolio SYMBOL:BETRAG ...`_")

        return "\n".join(lines)

    def set_portfolio(self, user_id: int, portfolio: dict[str, float]) -> str:
        """Set user's portfolio."""
        user = self.user_state.set_portfolio(user_id, portfolio)

        total = user.total_portfolio_value
        percentages = user.get_portfolio_percentages()

        lines = ["✅ *Portfolio gespeichert!*\n"]

        # Sort by value descending
        sorted_positions = sorted(
            portfolio.items(),
            key=lambda x: x[1],
            reverse=True
        )

        for symbol, amount in sorted_positions:
            pct = percentages[symbol.upper()]
            lines.append(f"├── *{symbol.upper()}*: €{amount:,.0f} ({pct:.1f}%)")

        lines.append(f"└── *Total*: €{total:,.0f}")
        lines.append(f"\n🎯 Profil: {user.risk_profile.capitalize()}")
        lines.append("\n_Nutze `/risk` für Portfolio-Analyse_")

        return "\n".join(lines)

    def add_position(self, user_id: int, symbol: str, amount: float) -> str:
        """Add or update a single position."""
        user = self.user_state.get_user(user_id)
        user.portfolio[symbol.upper()] = amount
        self.user_state.update_user(user)

        return f"✅ *{symbol.upper()}*: €{amount:,.0f} hinzugefügt/aktualisiert"

    def remove_position(self, user_id: int, symbol: str) -> str:
        """Remove a position from portfolio."""
        user = self.user_state.get_user(user_id)

        if symbol.upper() not in user.portfolio:
            return f"❌ *{symbol.upper()}* nicht im Portfolio"

        del user.portfolio[symbol.upper()]
        self.user_state.update_user(user)

        return f"✅ *{symbol.upper()}* entfernt"

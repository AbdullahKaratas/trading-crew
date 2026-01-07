"""Interactive Telegram bot with command handlers for on-demand analysis."""

import asyncio
import os
import re
from typing import Optional

import structlog
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from .user_state import UserStateManager, RiskProfile
from .commands import (
    AnalyzeCommand,
    CompareCommand,
    LongShortCommand,
    PortfolioCommand,
    ProfileCommand,
    RiskCommand,
    HelpCommand,
)

logger = structlog.get_logger()


class InteractiveTradingBot:
    """
    Interactive Telegram bot for on-demand trading analysis.

    Supports commands:
    - /analyze SYMBOL [budget] - Analyze a stock
    - /long SYMBOL [budget] - Long knockout analysis
    - /short SYMBOL [budget] - Short knockout analysis
    - /compare SYMBOL1 SYMBOL2 - Compare two stocks
    - /portfolio SYMBOL:amount ... - Set portfolio
    - /profile [conservative|moderate|aggressive|yolo] - Set risk profile
    - /risk - Portfolio risk assessment
    - /help - Show all commands
    """

    def __init__(
        self,
        bot_token: Optional[str] = None,
        user_state_manager: Optional[UserStateManager] = None,
        config: Optional[dict] = None,
    ):
        """
        Initialize interactive bot.

        Args:
            bot_token: Telegram bot token
            user_state_manager: User state persistence manager
            config: TradingAgents configuration
        """
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        if not self.bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN is required")

        self.user_state = user_state_manager or UserStateManager()
        self.config = config or {}
        self.application: Optional[Application] = None

        # Initialize command handlers
        self.analyze_cmd = AnalyzeCommand(self.user_state, self.config)
        self.compare_cmd = CompareCommand(self.user_state, self.config)
        self.long_short_cmd = LongShortCommand(self.user_state, self.config)
        self.portfolio_cmd = PortfolioCommand(self.user_state)
        self.profile_cmd = ProfileCommand(self.user_state)
        self.risk_cmd = RiskCommand(self.user_state, self.config)
        self.help_cmd = HelpCommand()

    async def start(self) -> None:
        """Start the bot and begin polling for messages."""
        self.application = Application.builder().token(self.bot_token).build()

        # Register command handlers
        self.application.add_handler(CommandHandler("start", self._handle_start))
        self.application.add_handler(CommandHandler("help", self._handle_help))
        self.application.add_handler(CommandHandler("analyze", self._handle_analyze))
        self.application.add_handler(CommandHandler("a", self._handle_analyze))  # Shortcut
        self.application.add_handler(CommandHandler("long", self._handle_long))
        self.application.add_handler(CommandHandler("short", self._handle_short))
        self.application.add_handler(CommandHandler("compare", self._handle_compare))
        self.application.add_handler(CommandHandler("portfolio", self._handle_portfolio))
        self.application.add_handler(CommandHandler("p", self._handle_portfolio))  # Shortcut
        self.application.add_handler(CommandHandler("profile", self._handle_profile))
        self.application.add_handler(CommandHandler("risk", self._handle_risk))
        self.application.add_handler(CommandHandler("alerts", self._handle_alerts))

        # Handle unknown commands
        self.application.add_handler(
            MessageHandler(filters.COMMAND, self._handle_unknown)
        )

        logger.info("bot_starting")
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling(drop_pending_updates=True)
        logger.info("bot_started", username=self.application.bot.username)

    async def stop(self) -> None:
        """Stop the bot gracefully."""
        if self.application:
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
            logger.info("bot_stopped")

    async def run(self) -> None:
        """Run the bot until interrupted."""
        await self.start()
        try:
            # Keep running until interrupted
            while True:
                await asyncio.sleep(1)
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass
        finally:
            await self.stop()

    # ==================== Command Handlers ====================

    async def _handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command."""
        user = update.effective_user
        self.user_state.get_user(user.id, user.username)

        welcome_message = f"""
🤖 *Trading Analysis Bot*

Willkommen {user.first_name}!

Ich analysiere Aktien mit Multi-Agent AI (Gemini + Claude).

*Schnellstart:*
• `/analyze AAPL` - Aktie analysieren
• `/analyze AAPL 5000` - Mit Budget (€)
• `/long NVDA 1000` - Long Knockout
• `/short TSLA 500` - Short Knockout

*Portfolio & Risiko:*
• `/portfolio AAPL:5000 MSFT:3000`
• `/profile aggressive`
• `/risk` - Portfolio-Risiko

Tippe /help für alle Commands.
"""
        await update.message.reply_text(welcome_message, parse_mode="Markdown")

    async def _handle_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /help command."""
        response = self.help_cmd.execute()
        await update.message.reply_text(response, parse_mode="Markdown")

    async def _handle_analyze(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /analyze command."""
        user = update.effective_user
        user_state = self.user_state.get_user(user.id, user.username)
        args = context.args

        if not args:
            await update.message.reply_text(
                "❌ Bitte Symbol angeben: `/analyze AAPL` oder `/analyze AAPL 5000`",
                parse_mode="Markdown"
            )
            return

        symbol = args[0].upper()
        budget = None
        if len(args) > 1:
            try:
                budget = float(args[1].replace("€", "").replace(",", "."))
            except ValueError:
                await update.message.reply_text(
                    f"❌ Ungültiges Budget: {args[1]}",
                    parse_mode="Markdown"
                )
                return

        # Send "analyzing" message
        status_msg = await update.message.reply_text(
            f"🔄 Analysiere *{symbol}*...\n\nDas dauert ca. 1-2 Minuten.",
            parse_mode="Markdown"
        )

        try:
            response = await self.analyze_cmd.execute(symbol, user_state, budget)
            await status_msg.edit_text(response, parse_mode="Markdown")
        except Exception as e:
            logger.error("analyze_error", symbol=symbol, error=str(e))
            await status_msg.edit_text(
                f"❌ Fehler bei Analyse von {symbol}: {str(e)[:200]}",
                parse_mode="Markdown"
            )

    async def _handle_long(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /long command for knockout certificates."""
        await self._handle_knockout(update, context, direction="long")

    async def _handle_short(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /short command for knockout certificates."""
        await self._handle_knockout(update, context, direction="short")

    async def _handle_knockout(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        direction: str
    ) -> None:
        """Handle knockout certificate analysis."""
        user = update.effective_user
        user_state = self.user_state.get_user(user.id, user.username)
        args = context.args

        if not args:
            await update.message.reply_text(
                f"❌ Bitte Symbol angeben: `/{direction} AAPL` oder `/{direction} AAPL 1000`",
                parse_mode="Markdown"
            )
            return

        symbol = args[0].upper()
        budget = None
        if len(args) > 1:
            try:
                budget = float(args[1].replace("€", "").replace(",", "."))
            except ValueError:
                pass

        emoji = "📈" if direction == "long" else "📉"
        status_msg = await update.message.reply_text(
            f"{emoji} Analysiere *{symbol}* für {direction.upper()} Knockout...\n\nDas dauert ca. 1-2 Minuten.",
            parse_mode="Markdown"
        )

        try:
            response = await self.long_short_cmd.execute(symbol, direction, user_state, budget)
            await status_msg.edit_text(response, parse_mode="Markdown")
        except Exception as e:
            logger.error("knockout_error", symbol=symbol, direction=direction, error=str(e))
            await status_msg.edit_text(
                f"❌ Fehler bei {direction.upper()} Analyse von {symbol}: {str(e)[:200]}",
                parse_mode="Markdown"
            )

    async def _handle_compare(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /compare command."""
        user = update.effective_user
        user_state = self.user_state.get_user(user.id, user.username)
        args = context.args

        if len(args) < 2:
            await update.message.reply_text(
                "❌ Bitte zwei Symbole angeben: `/compare AAPL MSFT`",
                parse_mode="Markdown"
            )
            return

        symbol1 = args[0].upper()
        symbol2 = args[1].upper()

        status_msg = await update.message.reply_text(
            f"⚖️ Vergleiche *{symbol1}* vs *{symbol2}*...\n\nDas dauert ca. 2-3 Minuten.",
            parse_mode="Markdown"
        )

        try:
            response = await self.compare_cmd.execute(symbol1, symbol2, user_state)
            await status_msg.edit_text(response, parse_mode="Markdown")
        except Exception as e:
            logger.error("compare_error", symbols=[symbol1, symbol2], error=str(e))
            await status_msg.edit_text(
                f"❌ Fehler bei Vergleich: {str(e)[:200]}",
                parse_mode="Markdown"
            )

    async def _handle_portfolio(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /portfolio command."""
        user = update.effective_user
        args = context.args

        if not args:
            # Show current portfolio
            user_state = self.user_state.get_user(user.id, user.username)
            response = self.portfolio_cmd.show_portfolio(user_state)
            await update.message.reply_text(response, parse_mode="Markdown")
            return

        # Parse portfolio: AAPL:5000 MSFT:3000 ...
        portfolio = {}
        for arg in args:
            match = re.match(r"([A-Za-z0-9\.\-]+):(\d+(?:\.\d+)?)", arg)
            if match:
                symbol = match.group(1).upper()
                amount = float(match.group(2))
                portfolio[symbol] = amount
            else:
                await update.message.reply_text(
                    f"❌ Ungültiges Format: `{arg}`\nErwartet: `SYMBOL:BETRAG` (z.B. `AAPL:5000`)",
                    parse_mode="Markdown"
                )
                return

        if not portfolio:
            await update.message.reply_text(
                "❌ Kein gültiges Portfolio angegeben.\nBeispiel: `/portfolio AAPL:5000 MSFT:3000`",
                parse_mode="Markdown"
            )
            return

        response = self.portfolio_cmd.set_portfolio(user.id, portfolio)
        await update.message.reply_text(response, parse_mode="Markdown")

    async def _handle_profile(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /profile command."""
        user = update.effective_user
        args = context.args

        if not args:
            # Show current profile
            user_state = self.user_state.get_user(user.id, user.username)
            response = self.profile_cmd.show_profile(user_state)
            await update.message.reply_text(response, parse_mode="Markdown")
            return

        profile = args[0].lower()
        try:
            response = self.profile_cmd.set_profile(user.id, profile)
            await update.message.reply_text(response, parse_mode="Markdown")
        except ValueError as e:
            await update.message.reply_text(f"❌ {str(e)}", parse_mode="Markdown")

    async def _handle_risk(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /risk command."""
        user = update.effective_user
        user_state = self.user_state.get_user(user.id, user.username)

        if not user_state.portfolio:
            await update.message.reply_text(
                "❌ Kein Portfolio gesetzt.\n\nSetze zuerst dein Portfolio:\n`/portfolio AAPL:5000 MSFT:3000`",
                parse_mode="Markdown"
            )
            return

        status_msg = await update.message.reply_text(
            "📊 Berechne Portfolio-Risiko...",
            parse_mode="Markdown"
        )

        try:
            response = await self.risk_cmd.execute(user_state)
            await status_msg.edit_text(response, parse_mode="Markdown")
        except Exception as e:
            logger.error("risk_error", user_id=user.id, error=str(e))
            await status_msg.edit_text(
                f"❌ Fehler bei Risiko-Berechnung: {str(e)[:200]}",
                parse_mode="Markdown"
            )

    async def _handle_alerts(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /alerts command - show or manage price alerts."""
        user = update.effective_user
        user_state = self.user_state.get_user(user.id, user.username)

        # For now, just show existing alerts
        if not user_state.alerts:
            await update.message.reply_text(
                "📭 Keine aktiven Alerts.\n\n*Coming soon:* `/alert AAPL < 180`",
                parse_mode="Markdown"
            )
            return

        alerts_text = "🔔 *Deine Alerts:*\n\n"
        for i, alert in enumerate(user_state.alerts):
            status = "✅" if alert.get("triggered") else "⏳"
            alerts_text += f"{i+1}. {status} {alert.get('symbol', '?')} {alert.get('condition', '?')}\n"

        await update.message.reply_text(alerts_text, parse_mode="Markdown")

    async def _handle_unknown(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle unknown commands."""
        await update.message.reply_text(
            "❓ Unbekannter Befehl.\n\nTippe /help für alle verfügbaren Commands.",
            parse_mode="Markdown"
        )


async def run_interactive_bot(config: Optional[dict] = None) -> None:
    """
    Run the interactive bot.

    Args:
        config: TradingAgents configuration
    """
    bot = InteractiveTradingBot(config=config)
    await bot.run()

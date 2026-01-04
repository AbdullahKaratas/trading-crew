"""Telegram bot integration for sending trading alerts."""

import asyncio
import os
from typing import Optional

import structlog
from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import TelegramError
from tenacity import retry, stop_after_attempt, wait_exponential

from ..analysis.signals import DailySummary, TradingSignal
from .formatters import SignalFormatter, SummaryFormatter

logger = structlog.get_logger()


class TelegramNotifier:
    """
    Telegram notification handler for trading alerts.

    Sends formatted trading signals and summaries to a Telegram chat.
    """

    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
        signal_formatter: Optional[SignalFormatter] = None,
        summary_formatter: Optional[SummaryFormatter] = None,
        dry_run: bool = False,
    ):
        """
        Initialize Telegram notifier.

        Args:
            bot_token: Telegram bot token (default: from TELEGRAM_BOT_TOKEN env)
            chat_id: Target chat ID (default: from TELEGRAM_CHAT_ID env)
            signal_formatter: Custom signal formatter
            summary_formatter: Custom summary formatter
            dry_run: If True, don't actually send messages (for testing)
        """
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")
        self.dry_run = dry_run

        if not self.bot_token and not dry_run:
            raise ValueError("TELEGRAM_BOT_TOKEN is required")
        if not self.chat_id and not dry_run:
            raise ValueError("TELEGRAM_CHAT_ID is required")

        self.bot = Bot(token=self.bot_token) if self.bot_token else None
        self.signal_formatter = signal_formatter or SignalFormatter()
        self.summary_formatter = summary_formatter or SummaryFormatter()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=30),
    )
    async def _send_message(self, text: str, parse_mode: str = ParseMode.MARKDOWN) -> bool:
        """
        Send a message to Telegram with retry logic.

        Args:
            text: Message text
            parse_mode: Telegram parse mode

        Returns:
            True if message sent successfully
        """
        if self.dry_run:
            logger.info("dry_run_message", text=text[:100] + "...")
            return True

        if not self.bot or not self.chat_id:
            logger.warning("telegram_not_configured")
            return False

        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=text,
                parse_mode=parse_mode,
                disable_web_page_preview=True,
            )
            logger.debug("message_sent", length=len(text))
            return True
        except TelegramError as e:
            logger.error("telegram_error", error=str(e))
            # Try without markdown if parsing fails
            if "parse" in str(e).lower():
                try:
                    await self.bot.send_message(
                        chat_id=self.chat_id,
                        text=text,
                        disable_web_page_preview=True,
                    )
                    return True
                except TelegramError:
                    pass
            raise

    async def send_signal(self, signal: TradingSignal) -> bool:
        """
        Send a trading signal notification.

        Args:
            signal: TradingSignal to send

        Returns:
            True if sent successfully
        """
        try:
            message = self.signal_formatter.format_signal(signal)
            success = await self._send_message(message)

            if success:
                logger.info(
                    "signal_sent",
                    symbol=signal.symbol,
                    signal_type=signal.signal_type.value,
                    confidence=signal.confidence,
                )
            return success
        except Exception as e:
            logger.error("send_signal_error", symbol=signal.symbol, error=str(e))
            return False

    async def send_actionable_signal(
        self, signal: TradingSignal, min_confidence: float = 65
    ) -> bool:
        """
        Send signal only if it's actionable (meets confidence threshold).

        Args:
            signal: TradingSignal to potentially send
            min_confidence: Minimum confidence to send

        Returns:
            True if sent (or skipped because not actionable)
        """
        if not signal.is_actionable(min_confidence):
            logger.debug(
                "signal_not_actionable",
                symbol=signal.symbol,
                signal_type=signal.signal_type.value,
                confidence=signal.confidence,
            )
            return True  # Not an error, just skipped

        return await self.send_signal(signal)

    async def send_daily_summary(self, summary: DailySummary) -> bool:
        """
        Send daily analysis summary.

        Args:
            summary: DailySummary to send

        Returns:
            True if sent successfully
        """
        try:
            message = self.summary_formatter.format_summary(summary)
            success = await self._send_message(message)

            if success:
                logger.info(
                    "summary_sent",
                    total_analyzed=summary.total_analyzed,
                    actionable=summary.actionable_count,
                )
            return success
        except Exception as e:
            logger.error("send_summary_error", error=str(e))
            return False

    async def send_error_notification(self, error_message: str) -> bool:
        """
        Send error notification.

        Args:
            error_message: Error description

        Returns:
            True if sent successfully
        """
        message = f"⚠️ *TRADING BOT ERROR*\n\n{error_message}"
        try:
            return await self._send_message(message)
        except Exception as e:
            logger.error("send_error_notification_failed", error=str(e))
            return False

    async def send_startup_message(self) -> bool:
        """Send bot startup notification."""
        message = "🤖 *Trading Bot Started*\n\nAnalyse läuft..."
        return await self._send_message(message)

    async def send_completion_message(self, analyzed: int, alerts: int) -> bool:
        """
        Send analysis completion notification.

        Args:
            analyzed: Number of stocks analyzed
            alerts: Number of alerts sent

        Returns:
            True if sent successfully
        """
        message = (
            f"✅ *Analyse Abgeschlossen*\n\n"
            f"📊 Analysiert: {analyzed} Aktien\n"
            f"🔔 Alerts: {alerts}"
        )
        return await self._send_message(message)

    async def test_connection(self) -> bool:
        """
        Test Telegram connection.

        Returns:
            True if connection is working
        """
        if self.dry_run:
            logger.info("dry_run_test_connection")
            return True

        if not self.bot:
            return False

        try:
            me = await self.bot.get_me()
            logger.info("telegram_connected", bot_username=me.username)
            return True
        except TelegramError as e:
            logger.error("telegram_connection_failed", error=str(e))
            return False


async def send_single_alert(signal: TradingSignal, dry_run: bool = False) -> bool:
    """
    Convenience function to send a single alert.

    Args:
        signal: Signal to send
        dry_run: If True, don't actually send

    Returns:
        True if sent successfully
    """
    notifier = TelegramNotifier(dry_run=dry_run)
    return await notifier.send_signal(signal)

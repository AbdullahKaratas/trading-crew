"""Message formatters for Telegram notifications."""

from datetime import datetime
from typing import Optional

from ..analysis.signals import DailySummary, SignalType, TradingSignal
from ..utils.market_hours import MarketHoursChecker


class SignalFormatter:
    """Formats trading signals into Telegram messages."""

    def __init__(self, market_checker: Optional[MarketHoursChecker] = None):
        self.market_checker = market_checker or MarketHoursChecker()

    def format_signal(self, signal: TradingSignal) -> str:
        """
        Format a trading signal into a Telegram message.

        Args:
            signal: TradingSignal to format

        Returns:
            Formatted message string
        """
        if signal.signal_type in {SignalType.BUY, SignalType.LONG}:
            return self._format_buy_signal(signal)
        elif signal.signal_type in {SignalType.SELL, SignalType.SHORT}:
            return self._format_sell_signal(signal)
        elif signal.signal_type == SignalType.SUPPORT_ALERT:
            return self._format_support_alert(signal)
        elif signal.signal_type == SignalType.RESISTANCE_ALERT:
            return self._format_resistance_alert(signal)
        elif signal.signal_type == SignalType.NEWS_ALERT:
            return self._format_news_alert(signal)
        else:
            return self._format_hold_signal(signal)

    def _format_buy_signal(self, signal: TradingSignal) -> str:
        """Format BUY/LONG signal with rich LLM-extracted data."""
        emoji = "🚀" if signal.signal_type == SignalType.BUY else "📈"
        signal_label = signal.signal_type.value

        lines = [
            f"{emoji} *{signal_label} SIGNAL: {signal.symbol}* ({signal.name})",
            "",
            f"💰 *Preis:* ${signal.current_price:.2f}",
        ]

        # Action detail from LLM (e.g., "BUY with 30-40% of position")
        if signal.action_detail:
            lines.append(f"🎯 *Aktion:* {signal.action_detail}")

        # Stop Loss from LLM
        if signal.stop_loss:
            stop_pct = self._calc_pct(signal.current_price, signal.stop_loss)
            lines.append(f"🛑 *Stop-Loss:* ${signal.stop_loss:.2f} ({stop_pct})")
            if signal.stop_loss_reasoning:
                lines.append(f"   _{signal.stop_loss_reasoning[:60]}_")

        # Exit targets from LLM
        if signal.exit_targets:
            lines.append("")
            lines.append("🎯 *Targets:*")
            for target in signal.exit_targets[:3]:
                if isinstance(target, dict):
                    price = target.get("price")
                    action = target.get("action", "")
                    if price:
                        pct = self._calc_pct(signal.current_price, price)
                        lines.append(f"   • ${price:.2f} ({pct}): {action}")

        # Key events from LLM
        if signal.key_events:
            lines.append("")
            lines.append("📅 *Wichtige Events:*")
            for event in signal.key_events[:3]:
                lines.append(f"   • {event}")

        # Exit conditions from LLM
        if signal.exit_conditions:
            lines.append("")
            lines.append("⚠️ *Exit wenn:*")
            for condition in signal.exit_conditions[:3]:
                lines.append(f"   • {condition}")

        # Final recommendation from LLM
        if signal.final_recommendation:
            lines.append("")
            lines.append("💡 *Empfehlung:*")
            # Wrap long text
            rec = signal.final_recommendation[:400]
            lines.append(f"_{rec}_")

        # Timestamp and market status
        market_status = self.market_checker.get_market_status()
        time_str = signal.timestamp.strftime("%H:%M")
        lines.extend(["", f"🕐 {time_str} CET | {market_status}"])

        return "\n".join(lines)

    def _format_sell_signal(self, signal: TradingSignal) -> str:
        """Format SELL/SHORT signal with rich LLM-extracted data."""
        emoji = "🔴" if signal.signal_type == SignalType.SELL else "📉"
        signal_label = signal.signal_type.value

        lines = [
            f"{emoji} *{signal_label} SIGNAL: {signal.symbol}* ({signal.name})",
            "",
            f"💰 *Preis:* ${signal.current_price:.2f}",
        ]

        # Action detail from LLM (e.g., "SELL 60-70% of position")
        if signal.action_detail:
            lines.append(f"🎯 *Aktion:* {signal.action_detail}")

        # Stop Loss from LLM
        if signal.stop_loss:
            stop_pct = self._calc_pct(signal.current_price, signal.stop_loss)
            lines.append(f"🛑 *Stop-Loss:* ${signal.stop_loss:.2f} ({stop_pct})")
            if signal.stop_loss_reasoning:
                lines.append(f"   _{signal.stop_loss_reasoning[:60]}_")

        # Exit targets from LLM
        if signal.exit_targets:
            lines.append("")
            lines.append("🎯 *Exit Targets:*")
            for target in signal.exit_targets[:3]:
                if isinstance(target, dict):
                    price = target.get("price")
                    action = target.get("action", "")
                    if price:
                        pct = self._calc_pct(signal.current_price, price)
                        lines.append(f"   • ${price:.2f} ({pct}): {action}")

        # Key events from LLM
        if signal.key_events:
            lines.append("")
            lines.append("📅 *Wichtige Events:*")
            for event in signal.key_events[:3]:
                lines.append(f"   • {event}")

        # Exit conditions from LLM
        if signal.exit_conditions:
            lines.append("")
            lines.append("⚠️ *Exit wenn:*")
            for condition in signal.exit_conditions[:3]:
                lines.append(f"   • {condition}")

        # Final recommendation from LLM
        if signal.final_recommendation:
            lines.append("")
            lines.append("💡 *Empfehlung:*")
            rec = signal.final_recommendation[:400]
            lines.append(f"_{rec}_")

        # Timestamp and market status
        market_status = self.market_checker.get_market_status()
        time_str = signal.timestamp.strftime("%H:%M")
        lines.extend(["", f"🕐 {time_str} CET | {market_status}"])

        return "\n".join(lines)

    def _format_support_alert(self, signal: TradingSignal) -> str:
        """Format support level alert."""
        support_pct = self._calc_pct(signal.current_price, signal.support_level or 0)
        resistance_pct = self._calc_pct(
            signal.current_price, signal.resistance_level or 0
        )

        lines = [
            f"📍 *SUPPORT ALERT: {signal.symbol}*",
            "",
            "⚠️ Preis nähert sich kritischem Support!",
            "",
            f"💰 Aktuell: ${signal.current_price:.2f}",
        ]

        if signal.support_level:
            lines.append(f"🔻 Support: ${signal.support_level:.2f} ({support_pct})")
        if signal.resistance_level:
            lines.append(f"🔺 Resistance: ${signal.resistance_level:.2f} ({resistance_pct})")

        lines.extend(
            [
                "",
                "💡 *Mögliche Aktion:*",
                f"• Buy Limit bei ${(signal.support_level or signal.current_price * 0.98):.2f} setzen",
                f"• Stop-Loss unter ${(signal.support_level or signal.current_price) * 0.97:.2f}",
                "",
                f"📊 Confidence: {signal.confidence:.0f}%",
                f"🕐 {signal.timestamp.strftime('%H:%M')} CET",
            ]
        )

        return "\n".join(lines)

    def _format_resistance_alert(self, signal: TradingSignal) -> str:
        """Format resistance level alert."""
        lines = [
            f"🚧 *RESISTANCE ALERT: {signal.symbol}*",
            "",
            "⚠️ Preis nähert sich Widerstand!",
            "",
            f"💰 Aktuell: ${signal.current_price:.2f}",
        ]

        if signal.resistance_level:
            resistance_pct = self._calc_pct(
                signal.current_price, signal.resistance_level
            )
            lines.append(f"🔺 Resistance: ${signal.resistance_level:.2f} ({resistance_pct})")

        if signal.support_level:
            support_pct = self._calc_pct(signal.current_price, signal.support_level)
            lines.append(f"🔻 Support: ${signal.support_level:.2f} ({support_pct})")

        lines.extend(
            [
                "",
                "💡 *Optionen:*",
                "• Bei Breakout: Buy mit Momentum",
                "• Bei Rejection: Take Profit oder Short",
                "",
                f"📊 Confidence: {signal.confidence:.0f}%",
                f"🕐 {signal.timestamp.strftime('%H:%M')} CET",
            ]
        )

        return "\n".join(lines)

    def _format_news_alert(self, signal: TradingSignal) -> str:
        """Format news alert."""
        lines = [
            f"📰 *NEWS ALERT: {signal.symbol}* ({signal.name})",
            "",
            f"💰 Aktuell: ${signal.current_price:.2f}",
            "",
        ]

        if signal.news_summary:
            lines.append(f"📌 {signal.news_summary}")

        sentiment_label = self._sentiment_label(signal.sentiment_score)
        lines.extend(
            [
                "",
                f"💭 Sentiment: {sentiment_label}",
                f"📊 Impact Score: {signal.confidence:.0f}%",
                "",
                f"🕐 {signal.timestamp.strftime('%H:%M')} CET",
            ]
        )

        return "\n".join(lines)

    def _format_hold_signal(self, signal: TradingSignal) -> str:
        """Format HOLD signal with full details (same as BUY/SELL)."""
        lines = [
            f"⏸️ *HOLD SIGNAL: {signal.symbol}* ({signal.name})",
            "",
            f"💰 *Preis:* ${signal.current_price:.2f}",
        ]

        # Action detail from LLM
        if signal.action_detail:
            lines.append(f"🎯 *Aktion:* {signal.action_detail}")

        # Stop Loss from LLM (trailing stop for HOLD)
        if signal.stop_loss:
            stop_pct = self._calc_pct(signal.current_price, signal.stop_loss)
            lines.append(f"🛑 *Stop-Loss:* ${signal.stop_loss:.2f} ({stop_pct})")
            if signal.stop_loss_reasoning:
                lines.append(f"   _{signal.stop_loss_reasoning[:80]}_")

        # Entry/Exit targets from LLM (re-entry levels for HOLD)
        if signal.exit_targets:
            lines.append("")
            lines.append("🎯 *Entry/Exit Levels:*")
            for target in signal.exit_targets[:3]:
                if isinstance(target, dict):
                    price = target.get("price")
                    action = target.get("action", "")
                    if price:
                        pct = self._calc_pct(signal.current_price, price)
                        lines.append(f"   • ${price:.2f} ({pct}): {action}")

        # Key events from LLM
        if signal.key_events:
            lines.append("")
            lines.append("📅 *Wichtige Events:*")
            for event in signal.key_events[:3]:
                lines.append(f"   • {event}")

        # Exit/Entry conditions from LLM
        if signal.exit_conditions:
            lines.append("")
            lines.append("⚠️ *Bedingungen:*")
            for condition in signal.exit_conditions[:3]:
                lines.append(f"   • {condition}")

        # Final recommendation from LLM
        if signal.final_recommendation:
            lines.append("")
            lines.append("💡 *Empfehlung:*")
            rec = signal.final_recommendation[:400]
            lines.append(f"_{rec}_")

        # Timestamp and market status
        market_status = self.market_checker.get_market_status()
        time_str = signal.timestamp.strftime("%H:%M")
        lines.extend(["", f"🕐 {time_str} CET | {market_status}"])

        return "\n".join(lines)

    def _calc_pct(self, current: float, target: float) -> str:
        """Calculate percentage change string."""
        if current == 0:
            return "N/A"
        pct = ((target - current) / current) * 100
        sign = "+" if pct > 0 else ""
        return f"{sign}{pct:.0f}%"

    def _sentiment_label(self, score: float) -> str:
        """Convert sentiment score to label."""
        if score >= 0.5:
            return "Positiv"
        elif score >= 0.2:
            return "Leicht Positiv"
        elif score <= -0.5:
            return "Negativ"
        elif score <= -0.2:
            return "Leicht Negativ"
        else:
            return "Neutral"


class SummaryFormatter:
    """Formats daily summary messages."""

    def format_summary(self, summary: DailySummary) -> str:
        """
        Format daily summary into Telegram message.

        Args:
            summary: DailySummary object

        Returns:
            Formatted message string
        """
        date_str = summary.date.strftime("%d.%m.%Y")

        lines = [f"📊 *DAILY SUMMARY - {date_str}*", ""]

        # BUY signals
        if summary.buy_signals:
            lines.append(f"🚀 *BUY Signals:* {len(summary.buy_signals)}")
            for signal in summary.buy_signals:
                action = signal.action_detail[:80] if signal.action_detail else "BUY"
                lines.append(f"   • {signal.symbol} - {action}")
            lines.append("")

        # SELL signals
        if summary.sell_signals:
            lines.append(f"🔴 *SELL Signals:* {len(summary.sell_signals)}")
            for signal in summary.sell_signals:
                action = signal.action_detail[:80] if signal.action_detail else "SELL"
                lines.append(f"   • {signal.symbol} - {action}")
            lines.append("")

        # Support alerts
        if summary.support_alerts:
            lines.append(f"📍 *Support Alerts:* {len(summary.support_alerts)}")
            for signal in summary.support_alerts:
                lines.append(
                    f"   • {signal.symbol} near ${signal.support_level:.2f}"
                    if signal.support_level
                    else f"   • {signal.symbol}"
                )
            lines.append("")

        # Resistance alerts
        if summary.resistance_alerts:
            lines.append(f"🚧 *Resistance Alerts:* {len(summary.resistance_alerts)}")
            for signal in summary.resistance_alerts:
                lines.append(
                    f"   • {signal.symbol} near ${signal.resistance_level:.2f}"
                    if signal.resistance_level
                    else f"   • {signal.symbol}"
                )
            lines.append("")

        # HOLD signals with details
        if summary.hold_signals:
            lines.append(f"⏸️ *HOLD:* {len(summary.hold_signals)} Aktien")
            for signal in summary.hold_signals[:3]:  # Max 3 to keep summary short
                action_short = (signal.action_detail or "Halten")[:80]
                lines.append(f"   • {signal.symbol} - {action_short}")
            lines.append("")

        # Top pick
        if summary.top_pick:
            lines.append(f"💡 *Top Pick:* {summary.top_pick.symbol}")
            if summary.top_pick.action_detail:
                lines.append(f"   {summary.top_pick.action_detail[:100]}")
            lines.append("")

        # Errors if any
        if summary.errors:
            lines.append(f"⚠️ *Fehler:* {len(summary.errors)} Analysen fehlgeschlagen")
            lines.append("")

        # Next analysis
        lines.append("🕐 Nächste Analyse: Morgen 14:00 CET")

        return "\n".join(lines)

    def format_error_summary(self, errors: list[tuple[str, str]]) -> str:
        """
        Format error summary for failed analyses.

        Args:
            errors: List of (symbol, error_message) tuples

        Returns:
            Formatted error message
        """
        lines = ["⚠️ *ANALYSE FEHLER*", ""]

        for symbol, error in errors[:10]:  # Limit to 10 errors
            lines.append(f"• {symbol}: {error[:50]}...")

        if len(errors) > 10:
            lines.append(f"... und {len(errors) - 10} weitere Fehler")

        return "\n".join(lines)

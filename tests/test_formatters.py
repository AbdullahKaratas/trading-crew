"""Tests for message formatters."""

from datetime import datetime

import pytest

from src.analysis.signals import DailySummary, SignalType, TradingSignal
from src.notifications.formatters import SignalFormatter, SummaryFormatter


class TestSignalFormatter:
    """Tests for SignalFormatter class."""

    @pytest.fixture
    def formatter(self):
        """Create formatter instance."""
        return SignalFormatter()

    def create_signal(
        self,
        signal_type: SignalType = SignalType.BUY,
        confidence: float = 78,
    ) -> TradingSignal:
        """Create a test signal."""
        return TradingSignal(
            symbol="APLD",
            name="Applied Digital",
            signal_type=signal_type,
            confidence=confidence,
            current_price=8.45,
            entry_zone=(8.30, 8.50),
            targets=[9.20, 10.50],
            stop_loss=7.80,
            risk_reward_ratio=3.0,
            reasoning="Strong technical setup with bullish momentum",
            technical_factors=["Bullish MACD Crossover", "RSI: 45 (neutral)"],
            sentiment_score=0.65,
            timestamp=datetime.now(),
            support_level=7.80,
            resistance_level=10.50,
            news_summary="Neuer GPU-Cluster Deal angekündigt",
        )

    def test_format_buy_signal(self, formatter):
        """Test BUY signal formatting."""
        signal = self.create_signal(SignalType.BUY)
        message = formatter.format_signal(signal)

        assert "BUY SIGNAL" in message
        assert "APLD" in message
        assert "Applied Digital" in message
        assert "$8.45" in message
        assert "Entry Zone" in message
        assert "Target" in message
        assert "Stop-Loss" in message
        assert "78%" in message

    def test_format_sell_signal(self, formatter):
        """Test SELL signal formatting."""
        signal = self.create_signal(SignalType.SELL)
        message = formatter.format_signal(signal)

        assert "SELL SIGNAL" in message
        assert "APLD" in message

    def test_format_support_alert(self, formatter):
        """Test SUPPORT_ALERT formatting."""
        signal = self.create_signal(SignalType.SUPPORT_ALERT)
        message = formatter.format_signal(signal)

        assert "SUPPORT ALERT" in message
        assert "Support" in message

    def test_format_hold_signal(self, formatter):
        """Test HOLD signal formatting."""
        signal = self.create_signal(SignalType.HOLD)
        message = formatter.format_signal(signal)

        assert "HOLD" in message
        assert "APLD" in message

    def test_format_includes_technical_factors(self, formatter):
        """Test that technical factors are included."""
        signal = self.create_signal()
        message = formatter.format_signal(signal)

        assert "MACD" in message or "Technisch" in message

    def test_format_includes_sentiment(self, formatter):
        """Test that sentiment is included."""
        signal = self.create_signal()
        message = formatter.format_signal(signal)

        assert "Sentiment" in message

    def test_format_includes_news(self, formatter):
        """Test that news is included when present."""
        signal = self.create_signal()
        message = formatter.format_signal(signal)

        assert "News" in message or "GPU" in message


class TestSummaryFormatter:
    """Tests for SummaryFormatter class."""

    @pytest.fixture
    def formatter(self):
        """Create formatter instance."""
        return SummaryFormatter()

    def create_signal(
        self,
        symbol: str,
        signal_type: SignalType,
        confidence: float,
    ) -> TradingSignal:
        """Create a test signal."""
        return TradingSignal(
            symbol=symbol,
            name=f"{symbol} Inc",
            signal_type=signal_type,
            confidence=confidence,
            current_price=100.0,
            entry_zone=(98.0, 102.0),
            targets=[110.0, 120.0],
            stop_loss=92.0,
            risk_reward_ratio=2.5,
            reasoning="Test reasoning for summary",
            technical_factors=[],
            sentiment_score=0.5,
            timestamp=datetime.now(),
            support_level=95.0,
            resistance_level=115.0,
        )

    def test_format_summary_with_signals(self, formatter):
        """Test summary formatting with signals."""
        summary = DailySummary(date=datetime.now(), total_analyzed=3)
        summary.add_signal(self.create_signal("APLD", SignalType.BUY, 78))
        summary.add_signal(self.create_signal("QBTS", SignalType.SELL, 72))
        summary.add_signal(self.create_signal("IREN", SignalType.HOLD, 50))
        summary.determine_top_pick()

        message = formatter.format_summary(summary)

        assert "DAILY SUMMARY" in message
        assert "BUY Signals" in message
        assert "SELL Signals" in message
        assert "APLD" in message
        assert "QBTS" in message

    def test_format_summary_empty(self, formatter):
        """Test summary formatting with no signals."""
        summary = DailySummary(date=datetime.now(), total_analyzed=0)

        message = formatter.format_summary(summary)

        assert "DAILY SUMMARY" in message

    def test_format_summary_includes_top_pick(self, formatter):
        """Test that top pick is included."""
        summary = DailySummary(date=datetime.now(), total_analyzed=2)
        summary.add_signal(self.create_signal("APLD", SignalType.BUY, 85))
        summary.add_signal(self.create_signal("RKLB", SignalType.BUY, 70))
        summary.determine_top_pick()

        message = formatter.format_summary(summary)

        assert "Top Pick" in message
        assert "APLD" in message

    def test_format_summary_includes_errors(self, formatter):
        """Test that errors are included."""
        summary = DailySummary(date=datetime.now(), total_analyzed=1)
        summary.errors.append("TEST: API timeout")

        message = formatter.format_summary(summary)

        assert "Fehler" in message

    def test_format_error_summary(self, formatter):
        """Test error summary formatting."""
        errors = [
            ("APLD", "Connection timeout"),
            ("QBTS", "Invalid response"),
        ]

        message = formatter.format_error_summary(errors)

        assert "FEHLER" in message
        assert "APLD" in message
        assert "QBTS" in message

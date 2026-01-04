"""Tests for trading signals module."""

from datetime import datetime

import pytest

from src.analysis.signals import DailySummary, SignalType, TradingSignal


class TestTradingSignal:
    """Tests for TradingSignal class."""

    def create_signal(
        self,
        signal_type: SignalType = SignalType.BUY,
        confidence: float = 75,
        current_price: float = 100.0,
    ) -> TradingSignal:
        """Create a test signal."""
        return TradingSignal(
            symbol="TEST",
            name="Test Stock",
            signal_type=signal_type,
            confidence=confidence,
            current_price=current_price,
            entry_zone=(98.0, 102.0),
            targets=[110.0, 120.0],
            stop_loss=92.0,
            risk_reward_ratio=2.5,
            reasoning="Test reasoning",
            technical_factors=["Bullish MACD", "RSI Neutral"],
            sentiment_score=0.5,
            timestamp=datetime.now(),
            support_level=95.0,
            resistance_level=115.0,
        )

    def test_is_actionable_buy_high_confidence(self):
        """Test BUY signal with high confidence is actionable."""
        signal = self.create_signal(SignalType.BUY, confidence=80)
        assert signal.is_actionable(min_confidence=65)

    def test_is_actionable_buy_low_confidence(self):
        """Test BUY signal with low confidence is not actionable."""
        signal = self.create_signal(SignalType.BUY, confidence=50)
        assert not signal.is_actionable(min_confidence=65)

    def test_is_actionable_hold(self):
        """Test HOLD signal is never actionable."""
        signal = self.create_signal(SignalType.HOLD, confidence=90)
        assert not signal.is_actionable(min_confidence=65)

    def test_is_actionable_support_alert(self):
        """Test SUPPORT_ALERT is actionable with high confidence."""
        signal = self.create_signal(SignalType.SUPPORT_ALERT, confidence=70)
        assert signal.is_actionable(min_confidence=65)

    def test_is_bullish(self):
        """Test bullish signal detection."""
        buy_signal = self.create_signal(SignalType.BUY)
        long_signal = self.create_signal(SignalType.LONG)
        sell_signal = self.create_signal(SignalType.SELL)

        assert buy_signal.is_bullish()
        assert long_signal.is_bullish()
        assert not sell_signal.is_bullish()

    def test_is_bearish(self):
        """Test bearish signal detection."""
        sell_signal = self.create_signal(SignalType.SELL)
        short_signal = self.create_signal(SignalType.SHORT)
        buy_signal = self.create_signal(SignalType.BUY)

        assert sell_signal.is_bearish()
        assert short_signal.is_bearish()
        assert not buy_signal.is_bearish()

    def test_get_potential_profit_pct(self):
        """Test potential profit calculation."""
        signal = self.create_signal(current_price=100.0)
        signal.targets = [110.0, 120.0]

        profit_pct = signal.get_potential_profit_pct()
        assert profit_pct == pytest.approx(10.0, rel=0.01)

    def test_get_potential_loss_pct(self):
        """Test potential loss calculation."""
        signal = self.create_signal(current_price=100.0)
        signal.stop_loss = 92.0

        loss_pct = signal.get_potential_loss_pct()
        assert loss_pct == pytest.approx(-8.0, rel=0.01)


class TestDailySummary:
    """Tests for DailySummary class."""

    def create_signal(
        self,
        symbol: str,
        signal_type: SignalType,
        confidence: float,
        risk_reward: float = 2.0,
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
            risk_reward_ratio=risk_reward,
            reasoning="Test",
            technical_factors=[],
            sentiment_score=0.0,
            timestamp=datetime.now(),
        )

    def test_add_buy_signal(self):
        """Test adding a BUY signal."""
        summary = DailySummary(date=datetime.now(), total_analyzed=1)
        signal = self.create_signal("TEST", SignalType.BUY, 80)

        summary.add_signal(signal)

        assert len(summary.buy_signals) == 1
        assert len(summary.sell_signals) == 0

    def test_add_sell_signal(self):
        """Test adding a SELL signal."""
        summary = DailySummary(date=datetime.now(), total_analyzed=1)
        signal = self.create_signal("TEST", SignalType.SELL, 75)

        summary.add_signal(signal)

        assert len(summary.sell_signals) == 1
        assert len(summary.buy_signals) == 0

    def test_add_support_alert(self):
        """Test adding a SUPPORT_ALERT."""
        summary = DailySummary(date=datetime.now(), total_analyzed=1)
        signal = self.create_signal("TEST", SignalType.SUPPORT_ALERT, 70)

        summary.add_signal(signal)

        assert len(summary.support_alerts) == 1

    def test_determine_top_pick(self):
        """Test top pick determination."""
        summary = DailySummary(date=datetime.now(), total_analyzed=3)

        # Add signals with different confidence and risk/reward
        signal1 = self.create_signal("LOW", SignalType.BUY, 60, risk_reward=1.5)
        signal2 = self.create_signal("HIGH", SignalType.BUY, 85, risk_reward=3.0)
        signal3 = self.create_signal("MED", SignalType.BUY, 75, risk_reward=2.0)

        summary.add_signal(signal1)
        summary.add_signal(signal2)
        summary.add_signal(signal3)
        summary.determine_top_pick()

        assert summary.top_pick is not None
        assert summary.top_pick.symbol == "HIGH"

    def test_actionable_count(self):
        """Test actionable signal counting."""
        summary = DailySummary(date=datetime.now(), total_analyzed=4)

        summary.add_signal(self.create_signal("BUY1", SignalType.BUY, 80))
        summary.add_signal(self.create_signal("SELL1", SignalType.SELL, 75))
        summary.add_signal(self.create_signal("HOLD1", SignalType.HOLD, 90))
        summary.add_signal(self.create_signal("SUP1", SignalType.SUPPORT_ALERT, 70))

        assert summary.actionable_count == 3  # BUY, SELL, SUPPORT_ALERT

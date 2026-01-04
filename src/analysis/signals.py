"""Trading signal data classes and types."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class SignalType(str, Enum):
    """Types of trading signals."""

    BUY = "BUY"
    SELL = "SELL"
    LONG = "LONG"
    SHORT = "SHORT"
    HOLD = "HOLD"
    SUPPORT_ALERT = "SUPPORT_ALERT"
    RESISTANCE_ALERT = "RESISTANCE_ALERT"
    NEWS_ALERT = "NEWS_ALERT"


@dataclass
class TradingSignal:
    """Represents a trading signal with all relevant information."""

    symbol: str
    name: str
    signal_type: SignalType
    current_price: float
    timestamp: datetime

    # Rich LLM-extracted fields (no hardcoded defaults!)
    action_detail: str = ""  # e.g., "SELL 60-70% of position"
    stop_loss: Optional[float] = None
    stop_loss_reasoning: str = ""
    exit_targets: list[dict] = field(default_factory=list)  # [{"price": 26.0, "action": "exit on pop"}]
    key_events: list[str] = field(default_factory=list)  # ["January 7 Earnings"]
    exit_conditions: list[str] = field(default_factory=list)  # ["Gross margin < 13%"]
    final_recommendation: str = ""
    bull_case: str = ""
    bear_case: str = ""

    # Legacy fields (kept for compatibility)
    confidence: float = 0.0  # Will be removed - confidence is in reasoning now
    entry_zone: Optional[tuple[float, float]] = None
    targets: list[float] = field(default_factory=list)
    risk_reward_ratio: float = 0.0
    reasoning: str = ""
    technical_factors: list[str] = field(default_factory=list)
    sentiment_score: float = 0.0
    support_level: Optional[float] = None
    resistance_level: Optional[float] = None
    news_summary: Optional[str] = None
    volume_analysis: Optional[str] = None
    market_context: Optional[str] = None

    def is_actionable(self, min_confidence: float = 0) -> bool:
        """Check if signal should trigger a notification.

        Note: min_confidence is ignored now - all BUY/SELL signals from LLM are actionable.
        The LLM already applies judgment about whether to recommend action.
        """
        actionable_types = {
            SignalType.BUY,
            SignalType.SELL,
            SignalType.LONG,
            SignalType.SHORT,
            SignalType.SUPPORT_ALERT,
            SignalType.RESISTANCE_ALERT,
        }
        return self.signal_type in actionable_types

    def is_bullish(self) -> bool:
        """Check if signal is bullish."""
        return self.signal_type in {SignalType.BUY, SignalType.LONG}

    def is_bearish(self) -> bool:
        """Check if signal is bearish."""
        return self.signal_type in {SignalType.SELL, SignalType.SHORT}

    def get_potential_profit_pct(self) -> float:
        """Calculate potential profit percentage to first target."""
        if not self.targets:
            return 0.0
        first_target = self.targets[0]
        return ((first_target - self.current_price) / self.current_price) * 100

    def get_potential_loss_pct(self) -> float:
        """Calculate potential loss percentage to stop loss."""
        return ((self.stop_loss - self.current_price) / self.current_price) * 100


@dataclass
class DailySummary:
    """Summary of all signals for the day."""

    date: datetime
    total_analyzed: int
    buy_signals: list[TradingSignal] = field(default_factory=list)
    sell_signals: list[TradingSignal] = field(default_factory=list)
    support_alerts: list[TradingSignal] = field(default_factory=list)
    resistance_alerts: list[TradingSignal] = field(default_factory=list)
    hold_signals: list[TradingSignal] = field(default_factory=list)
    news_alerts: list[TradingSignal] = field(default_factory=list)
    top_pick: Optional[TradingSignal] = None
    errors: list[str] = field(default_factory=list)

    def add_signal(self, signal: TradingSignal) -> None:
        """Add a signal to the appropriate list."""
        if signal.signal_type in {SignalType.BUY, SignalType.LONG}:
            self.buy_signals.append(signal)
        elif signal.signal_type in {SignalType.SELL, SignalType.SHORT}:
            self.sell_signals.append(signal)
        elif signal.signal_type == SignalType.SUPPORT_ALERT:
            self.support_alerts.append(signal)
        elif signal.signal_type == SignalType.RESISTANCE_ALERT:
            self.resistance_alerts.append(signal)
        elif signal.signal_type == SignalType.NEWS_ALERT:
            self.news_alerts.append(signal)
        else:
            self.hold_signals.append(signal)

    def determine_top_pick(self) -> None:
        """Determine the top pick - just pick the first actionable signal.

        Since we no longer use hardcoded confidence scores, we trust the LLM's
        judgment. The first BUY or SELL signal is the top pick.
        """
        all_actionable = self.buy_signals + self.sell_signals
        if all_actionable:
            self.top_pick = all_actionable[0]

    @property
    def actionable_count(self) -> int:
        """Count of actionable signals."""
        return (
            len(self.buy_signals)
            + len(self.sell_signals)
            + len(self.support_alerts)
            + len(self.resistance_alerts)
        )

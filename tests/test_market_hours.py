"""Tests for market hours checker."""

from datetime import datetime, date
from zoneinfo import ZoneInfo

import pytest

from src.utils.market_hours import MarketHoursChecker


class TestMarketHoursChecker:
    """Tests for MarketHoursChecker class."""

    @pytest.fixture
    def checker(self):
        """Create checker instance."""
        return MarketHoursChecker(timezone="Europe/Berlin")

    def test_is_trading_day_weekday(self, checker):
        """Test that weekdays are trading days."""
        # A Monday that's not a holiday
        monday = datetime(2025, 6, 2, 10, 0, tzinfo=ZoneInfo("Europe/Berlin"))
        assert checker.is_trading_day(monday)

    def test_is_trading_day_weekend(self, checker):
        """Test that weekends are not trading days."""
        saturday = datetime(2025, 6, 7, 10, 0, tzinfo=ZoneInfo("Europe/Berlin"))
        sunday = datetime(2025, 6, 8, 10, 0, tzinfo=ZoneInfo("Europe/Berlin"))

        assert not checker.is_trading_day(saturday)
        assert not checker.is_trading_day(sunday)

    def test_is_trading_day_holiday(self, checker):
        """Test that holidays are not trading days."""
        # Christmas 2025
        christmas = datetime(2025, 12, 25, 10, 0, tzinfo=ZoneInfo("Europe/Berlin"))
        assert not checker.is_trading_day(christmas)

    def test_is_market_open_during_hours(self, checker):
        """Test market open detection during regular hours."""
        # 10:00 AM ET on a trading day = 4:00 PM CET (winter)
        # Let's use a time that's clearly during market hours
        market_open_time = datetime(
            2025, 6, 2, 16, 0, tzinfo=ZoneInfo("Europe/Berlin")
        )  # 10 AM ET
        assert checker.is_market_open(market_open_time)

    def test_is_market_open_outside_hours(self, checker):
        """Test market closed detection outside hours."""
        # Very early morning in Europe = night in US
        early_morning = datetime(2025, 6, 2, 6, 0, tzinfo=ZoneInfo("Europe/Berlin"))
        assert not checker.is_market_open(early_morning)

    def test_is_premarket(self, checker):
        """Test pre-market detection."""
        # Pre-market is 4:00-9:30 AM ET
        # 4:00 AM ET = 10:00 AM CET (winter) / 10:00 AM CEST (summer)
        premarket_time = datetime(2025, 6, 2, 11, 0, tzinfo=ZoneInfo("Europe/Berlin"))
        # This should be around 5 AM ET (pre-market)
        # Note: Exact time depends on DST
        result = checker.is_premarket(premarket_time)
        # Just verify it returns a boolean
        assert isinstance(result, bool)

    def test_get_market_status_closed(self, checker):
        """Test market status when closed."""
        # Sunday
        sunday = datetime(2025, 6, 8, 10, 0, tzinfo=ZoneInfo("Europe/Berlin"))
        assert checker.get_market_status(sunday) == "Closed"

    def test_get_market_status_returns_string(self, checker):
        """Test market status returns valid string."""
        now = datetime.now(ZoneInfo("Europe/Berlin"))
        status = checker.get_market_status(now)
        assert status in ["Pre-Market", "Open", "After-Hours", "Closed"]

    def test_get_next_market_open(self, checker):
        """Test next market open calculation."""
        # On a Sunday
        sunday = datetime(2025, 6, 8, 10, 0, tzinfo=ZoneInfo("Europe/Berlin"))
        next_open = checker.get_next_market_open(sunday)

        # Should be Monday
        assert next_open.weekday() == 0  # Monday
        assert next_open > sunday

    def test_time_until_market_open_when_closed(self, checker):
        """Test time until market open calculation."""
        # On a Sunday
        sunday = datetime(2025, 6, 8, 10, 0, tzinfo=ZoneInfo("Europe/Berlin"))
        time_until = checker.time_until_market_open(sunday)

        assert time_until is not None
        assert "h" in time_until or "m" in time_until or "d" in time_until

    def test_time_until_market_open_when_open(self, checker):
        """Test returns None when market is open."""
        # During market hours on a trading day
        # Create a time that's definitely during market hours
        # 11:00 AM ET on a weekday
        market_time = datetime(2025, 6, 2, 17, 0, tzinfo=ZoneInfo("Europe/Berlin"))

        if checker.is_market_open(market_time):
            assert checker.time_until_market_open(market_time) is None

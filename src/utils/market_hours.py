"""Market hours checker for US stock exchanges."""

from datetime import datetime, time, date
from typing import Optional
from zoneinfo import ZoneInfo

import structlog

logger = structlog.get_logger()

# US Market holidays for 2025-2026
# Update annually
US_MARKET_HOLIDAYS = {
    # 2025
    date(2025, 1, 1),   # New Year's Day
    date(2025, 1, 20),  # MLK Day
    date(2025, 2, 17),  # Presidents Day
    date(2025, 4, 18),  # Good Friday
    date(2025, 5, 26),  # Memorial Day
    date(2025, 6, 19),  # Juneteenth
    date(2025, 7, 4),   # Independence Day
    date(2025, 9, 1),   # Labor Day
    date(2025, 11, 27), # Thanksgiving
    date(2025, 12, 25), # Christmas
    # 2026
    date(2026, 1, 1),   # New Year's Day
    date(2026, 1, 19),  # MLK Day
    date(2026, 2, 16),  # Presidents Day
    date(2026, 4, 3),   # Good Friday
    date(2026, 5, 25),  # Memorial Day
    date(2026, 6, 19),  # Juneteenth
    date(2026, 7, 3),   # Independence Day (observed)
    date(2026, 9, 7),   # Labor Day
    date(2026, 11, 26), # Thanksgiving
    date(2026, 12, 25), # Christmas
}


class MarketHoursChecker:
    """
    Utility class to check US stock market trading hours.

    US Market Hours (Eastern Time):
    - Pre-market: 4:00 AM - 9:30 AM ET
    - Regular: 9:30 AM - 4:00 PM ET
    - After-hours: 4:00 PM - 8:00 PM ET
    """

    # Market times in Eastern Time
    PREMARKET_OPEN = time(4, 0)
    MARKET_OPEN = time(9, 30)
    MARKET_CLOSE = time(16, 0)
    AFTERHOURS_CLOSE = time(20, 0)

    def __init__(self, timezone: str = "Europe/Berlin"):
        """
        Initialize market hours checker.

        Args:
            timezone: Local timezone for display/scheduling
        """
        self.local_tz = ZoneInfo(timezone)
        self.market_tz = ZoneInfo("America/New_York")

    def is_market_open(self, dt: Optional[datetime] = None) -> bool:
        """
        Check if regular market hours are active.

        Args:
            dt: Datetime to check (default: now)

        Returns:
            True if market is open for regular trading
        """
        if dt is None:
            dt = datetime.now(self.local_tz)

        # Convert to market timezone
        market_time = dt.astimezone(self.market_tz)

        # Check if it's a trading day
        if not self._is_trading_day(market_time.date()):
            return False

        # Check if within regular hours
        current_time = market_time.time()
        return self.MARKET_OPEN <= current_time < self.MARKET_CLOSE

    def is_premarket(self, dt: Optional[datetime] = None) -> bool:
        """Check if pre-market hours are active."""
        if dt is None:
            dt = datetime.now(self.local_tz)

        market_time = dt.astimezone(self.market_tz)

        if not self._is_trading_day(market_time.date()):
            return False

        current_time = market_time.time()
        return self.PREMARKET_OPEN <= current_time < self.MARKET_OPEN

    def is_afterhours(self, dt: Optional[datetime] = None) -> bool:
        """Check if after-hours trading is active."""
        if dt is None:
            dt = datetime.now(self.local_tz)

        market_time = dt.astimezone(self.market_tz)

        if not self._is_trading_day(market_time.date()):
            return False

        current_time = market_time.time()
        return self.MARKET_CLOSE <= current_time < self.AFTERHOURS_CLOSE

    def is_extended_hours(self, dt: Optional[datetime] = None) -> bool:
        """Check if any trading session is active (pre-market, regular, or after-hours)."""
        return self.is_premarket(dt) or self.is_market_open(dt) or self.is_afterhours(dt)

    def _is_trading_day(self, check_date: date) -> bool:
        """Check if given date is a trading day (not weekend or holiday)."""
        # Check weekend
        if check_date.weekday() >= 5:  # Saturday = 5, Sunday = 6
            return False

        # Check holidays
        if check_date in US_MARKET_HOLIDAYS:
            return False

        return True

    def is_trading_day(self, dt: Optional[datetime] = None) -> bool:
        """
        Public method to check if it's a trading day.

        Args:
            dt: Datetime to check (default: now)

        Returns:
            True if it's a trading day
        """
        if dt is None:
            dt = datetime.now(self.local_tz)

        market_time = dt.astimezone(self.market_tz)
        return self._is_trading_day(market_time.date())

    def get_market_status(self, dt: Optional[datetime] = None) -> str:
        """
        Get human-readable market status.

        Returns:
            Status string: "Pre-Market", "Open", "After-Hours", "Closed"
        """
        if self.is_premarket(dt):
            return "Pre-Market"
        elif self.is_market_open(dt):
            return "Open"
        elif self.is_afterhours(dt):
            return "After-Hours"
        else:
            return "Closed"

    def get_next_market_open(self, dt: Optional[datetime] = None) -> datetime:
        """
        Get the next market open time.

        Args:
            dt: Starting datetime (default: now)

        Returns:
            Datetime of next market open in local timezone
        """
        if dt is None:
            dt = datetime.now(self.local_tz)

        market_time = dt.astimezone(self.market_tz)

        # Start from current date
        check_date = market_time.date()

        # If market hasn't opened yet today and it's a trading day
        if self._is_trading_day(check_date):
            open_today = datetime.combine(
                check_date, self.MARKET_OPEN, tzinfo=self.market_tz
            )
            if market_time < open_today:
                return open_today.astimezone(self.local_tz)

        # Find next trading day
        from datetime import timedelta

        check_date += timedelta(days=1)
        while not self._is_trading_day(check_date):
            check_date += timedelta(days=1)
            if check_date > market_time.date() + timedelta(days=10):
                # Safety limit
                break

        next_open = datetime.combine(check_date, self.MARKET_OPEN, tzinfo=self.market_tz)
        return next_open.astimezone(self.local_tz)

    def time_until_market_open(self, dt: Optional[datetime] = None) -> Optional[str]:
        """
        Get human-readable time until market opens.

        Returns:
            String like "2h 30m" or None if market is open
        """
        if self.is_market_open(dt):
            return None

        if dt is None:
            dt = datetime.now(self.local_tz)

        next_open = self.get_next_market_open(dt)
        delta = next_open - dt.astimezone(self.local_tz)

        hours = int(delta.total_seconds() // 3600)
        minutes = int((delta.total_seconds() % 3600) // 60)

        if hours > 24:
            days = hours // 24
            hours = hours % 24
            return f"{days}d {hours}h {minutes}m"
        elif hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"

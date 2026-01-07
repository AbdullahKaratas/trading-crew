"""User state management for portfolio and profile settings."""

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

import structlog

logger = structlog.get_logger()


class RiskProfile(str, Enum):
    """User risk tolerance profiles."""
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"
    YOLO = "yolo"

    @property
    def settings(self) -> dict:
        """Get settings for this profile."""
        profiles = {
            "conservative": {
                "max_sector_concentration": 0.40,
                "max_leverage": 2,
                "default_stop_loss_pct": 5,
                "knockout_buffer_pct": 8,
                "description": "Konservativ - Kapitalerhalt priorisiert",
            },
            "moderate": {
                "max_sector_concentration": 0.60,
                "max_leverage": 5,
                "default_stop_loss_pct": 8,
                "knockout_buffer_pct": 5,
                "description": "Moderat - Balance zwischen Risiko und Rendite",
            },
            "aggressive": {
                "max_sector_concentration": 0.80,
                "max_leverage": 10,
                "default_stop_loss_pct": 15,
                "knockout_buffer_pct": 3,
                "description": "Aggressiv - Höhere Rendite, höheres Risiko",
            },
            "yolo": {
                "max_sector_concentration": 1.0,
                "max_leverage": 20,
                "default_stop_loss_pct": 25,
                "knockout_buffer_pct": 2,
                "description": "YOLO - Maximales Risiko (nicht empfohlen!)",
            },
        }
        return profiles[self.value]


@dataclass
class PortfolioPosition:
    """A single portfolio position."""
    symbol: str
    amount_eur: float
    added_at: str = field(default_factory=lambda: datetime.now().isoformat())

    @property
    def percentage(self) -> float:
        """Calculated dynamically based on total portfolio."""
        return 0.0  # Set by UserState


@dataclass
class UserState:
    """Complete user state including portfolio and settings."""
    user_id: int
    username: Optional[str] = None
    risk_profile: str = "moderate"
    portfolio: dict = field(default_factory=dict)  # symbol -> amount_eur
    alerts: list = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    @property
    def total_portfolio_value(self) -> float:
        """Total portfolio value in EUR."""
        return sum(self.portfolio.values())

    def get_portfolio_percentages(self) -> dict[str, float]:
        """Get portfolio as percentages."""
        total = self.total_portfolio_value
        if total == 0:
            return {}
        return {symbol: (amount / total) * 100 for symbol, amount in self.portfolio.items()}

    def get_risk_settings(self) -> dict:
        """Get risk settings based on profile."""
        try:
            return RiskProfile(self.risk_profile).settings
        except ValueError:
            return RiskProfile.MODERATE.settings

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON storage."""
        return {
            "user_id": self.user_id,
            "username": self.username,
            "risk_profile": self.risk_profile,
            "portfolio": self.portfolio,
            "alerts": self.alerts,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "UserState":
        """Create from dictionary."""
        return cls(
            user_id=data["user_id"],
            username=data.get("username"),
            risk_profile=data.get("risk_profile", "moderate"),
            portfolio=data.get("portfolio", {}),
            alerts=data.get("alerts", []),
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
        )


class UserStateManager:
    """
    Manages user state persistence using JSON file storage.

    Each user's state includes their portfolio, risk profile, and alerts.
    """

    def __init__(self, storage_path: Optional[str] = None):
        """
        Initialize user state manager.

        Args:
            storage_path: Path to JSON storage file. Defaults to data/user_states.json
        """
        if storage_path is None:
            storage_path = os.getenv(
                "USER_STATES_PATH",
                "data/user_states.json"
            )
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._cache: dict[int, UserState] = {}
        self._load_all()

    def _load_all(self) -> None:
        """Load all user states from storage."""
        if not self.storage_path.exists():
            self._cache = {}
            return

        try:
            with open(self.storage_path, "r") as f:
                data = json.load(f)
            self._cache = {
                int(user_id): UserState.from_dict(state)
                for user_id, state in data.items()
            }
            logger.info("user_states_loaded", count=len(self._cache))
        except Exception as e:
            logger.error("load_user_states_failed", error=str(e))
            self._cache = {}

    def _save_all(self) -> None:
        """Save all user states to storage."""
        try:
            data = {
                str(user_id): state.to_dict()
                for user_id, state in self._cache.items()
            }
            with open(self.storage_path, "w") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.debug("user_states_saved", count=len(self._cache))
        except Exception as e:
            logger.error("save_user_states_failed", error=str(e))

    def get_user(self, user_id: int, username: Optional[str] = None) -> UserState:
        """
        Get or create user state.

        Args:
            user_id: Telegram user ID
            username: Telegram username (optional, for display)

        Returns:
            UserState for this user
        """
        if user_id not in self._cache:
            self._cache[user_id] = UserState(user_id=user_id, username=username)
            self._save_all()
            logger.info("new_user_created", user_id=user_id, username=username)
        elif username and self._cache[user_id].username != username:
            self._cache[user_id].username = username
            self._save_all()
        return self._cache[user_id]

    def update_user(self, user_state: UserState) -> None:
        """
        Update user state and persist.

        Args:
            user_state: Updated user state
        """
        user_state.updated_at = datetime.now().isoformat()
        self._cache[user_state.user_id] = user_state
        self._save_all()

    def set_portfolio(self, user_id: int, portfolio: dict[str, float]) -> UserState:
        """
        Set user's portfolio.

        Args:
            user_id: Telegram user ID
            portfolio: Dict of symbol -> amount in EUR

        Returns:
            Updated user state
        """
        user = self.get_user(user_id)
        user.portfolio = {k.upper(): v for k, v in portfolio.items()}
        self.update_user(user)
        logger.info("portfolio_updated", user_id=user_id, positions=len(portfolio))
        return user

    def set_profile(self, user_id: int, profile: str) -> UserState:
        """
        Set user's risk profile.

        Args:
            user_id: Telegram user ID
            profile: Risk profile name

        Returns:
            Updated user state
        """
        # Validate profile
        try:
            RiskProfile(profile.lower())
        except ValueError:
            raise ValueError(f"Invalid profile: {profile}. Use: conservative, moderate, aggressive, yolo")

        user = self.get_user(user_id)
        user.risk_profile = profile.lower()
        self.update_user(user)
        logger.info("profile_updated", user_id=user_id, profile=profile)
        return user

    def add_alert(self, user_id: int, alert: dict) -> UserState:
        """
        Add price alert for user.

        Args:
            user_id: Telegram user ID
            alert: Alert configuration dict

        Returns:
            Updated user state
        """
        user = self.get_user(user_id)
        alert["created_at"] = datetime.now().isoformat()
        alert["triggered"] = False
        user.alerts.append(alert)
        self.update_user(user)
        logger.info("alert_added", user_id=user_id, alert=alert)
        return user

    def remove_alert(self, user_id: int, alert_index: int) -> UserState:
        """Remove alert by index."""
        user = self.get_user(user_id)
        if 0 <= alert_index < len(user.alerts):
            removed = user.alerts.pop(alert_index)
            self.update_user(user)
            logger.info("alert_removed", user_id=user_id, alert=removed)
        return user

    def get_all_users_with_alerts(self) -> list[UserState]:
        """Get all users who have active alerts."""
        return [
            user for user in self._cache.values()
            if user.alerts and any(not a.get("triggered") for a in user.alerts)
        ]

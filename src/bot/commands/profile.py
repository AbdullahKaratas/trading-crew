"""Profile command handler."""

import structlog

from ..user_state import UserStateManager, UserState, RiskProfile

logger = structlog.get_logger()


class ProfileCommand:
    """
    Handle /profile command for setting risk tolerance.

    Usage:
        /profile                  - Show current profile
        /profile conservative     - Set conservative profile
        /profile moderate         - Set moderate profile
        /profile aggressive       - Set aggressive profile
        /profile yolo             - Set YOLO profile (high risk!)
    """

    def __init__(self, user_state: UserStateManager):
        self.user_state = user_state

    def show_profile(self, user: UserState) -> str:
        """Show current profile and all available profiles."""
        current = user.risk_profile
        settings = user.get_risk_settings()

        response = f"""
🎯 *Dein Risiko-Profil: {current.upper()}*

{settings['description']}

*Einstellungen:*
├── Max Sektor-Konzentration: {settings['max_sector_concentration']*100:.0f}%
├── Max Hebel (Knockouts): {settings['max_leverage']}x
├── Standard Stop-Loss: {settings['default_stop_loss_pct']}%
└── KO-Puffer: {settings['knockout_buffer_pct']}%

*Alle Profile:*
"""
        for profile in RiskProfile:
            s = profile.settings
            marker = "→" if profile.value == current else "  "
            emoji = self._get_profile_emoji(profile.value)
            response += f"{marker} {emoji} *{profile.value}*: {s['description'][:30]}...\n"

        response += "\n_Ändern: `/profile conservative|moderate|aggressive|yolo`_"

        return response

    def set_profile(self, user_id: int, profile: str) -> str:
        """Set user's risk profile."""
        # Validate
        profile = profile.lower()
        try:
            profile_enum = RiskProfile(profile)
        except ValueError:
            valid = ", ".join([p.value for p in RiskProfile])
            raise ValueError(f"Ungültiges Profil: {profile}\nVerfügbar: {valid}")

        user = self.user_state.set_profile(user_id, profile)
        settings = user.get_risk_settings()
        emoji = self._get_profile_emoji(profile)

        response = f"""
{emoji} *Profil geändert: {profile.upper()}*

{settings['description']}

*Neue Einstellungen:*
├── Max Sektor-Konzentration: {settings['max_sector_concentration']*100:.0f}%
├── Max Hebel (Knockouts): {settings['max_leverage']}x
├── Standard Stop-Loss: {settings['default_stop_loss_pct']}%
└── KO-Puffer: {settings['knockout_buffer_pct']}%
"""

        if profile == "yolo":
            response += "\n⚠️ *WARNUNG:* YOLO-Profil hat maximales Risiko!"
            response += "\nNur mit Geld handeln, das du verlieren kannst."

        return response

    def _get_profile_emoji(self, profile: str) -> str:
        """Get emoji for profile."""
        emojis = {
            "conservative": "🛡️",
            "moderate": "⚖️",
            "aggressive": "🔥",
            "yolo": "🚀",
        }
        return emojis.get(profile, "🎯")

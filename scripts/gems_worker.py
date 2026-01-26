#!/usr/bin/env python3
"""
GEM Scanner Worker for GitHub Actions.

Scans for trending penny stocks using Web Search (no Reddit API needed)
and sends results via Telegram.
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

import requests


def send_telegram_message(chat_id: str, text: str) -> bool:
    """Send a message to Telegram."""
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    url = f"https://api.telegram.org/bot{token}/sendMessage"

    # Telegram has a 4096 character limit
    if len(text) > 4000:
        text = text[:3997] + "..."

    response = requests.post(url, json={
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    })
    return response.ok


def main():
    """Main entry point."""
    from web_search_scanner import WebSearchScanner

    # Get environment variables
    chat_id = os.environ.get("CHAT_ID")
    lang = os.environ.get("LANG", "de").lower()
    category_filter = os.environ.get("CATEGORY", "all").lower()

    # Map old subreddit filter to new category
    subreddit_filter = os.environ.get("SUBREDDIT", "").lower()
    if subreddit_filter == "wsb":
        category_filter = "wsb"
    elif subreddit_filter == "pennys":
        category_filter = "pennys"
    elif subreddit_filter == "squeeze":
        category_filter = "squeeze"

    if not chat_id:
        print("Error: No CHAT_ID provided")
        return 1

    print(f"Scanning for gems (category: {category_filter}, lang: {lang})")

    try:
        scanner = WebSearchScanner(
            max_market_cap=2_000_000_000,  # $2B max
            min_price=0.10,
            max_price=50.00,
        )

        gems = scanner.find_gems(
            category=category_filter,
            limit=7,
        )

        if gems:
            message = scanner.format_gems_summary(gems, lang=lang)
            print(f"Found {len(gems)} gems")
        else:
            if lang == "en":
                message = "🔍 *GEM SCANNER*\n\nNo gems found at the moment. The scanner searches for:\n• Small cap stocks (< $2B)\n• Trending online mentions\n• Unusual volume activity\n\nTry again later or use `/analyze SYMBOL` for specific stocks."
            else:
                message = "🔍 *GEM SCANNER*\n\nKeine Gems gefunden im Moment. Der Scanner sucht nach:\n• Small Cap Aktien (< $2B)\n• Trending Online-Erwähnungen\n• Ungewöhnliche Volumen-Aktivität\n\nVersuch es später nochmal oder nutze `/analyze SYMBOL` für spezifische Aktien."

        success = send_telegram_message(chat_id, message)

        if success:
            print(f"Results sent to chat {chat_id}")
            return 0
        else:
            print("Failed to send message")
            return 1

    except Exception as e:
        error_msg = f"❌ GEM Scanner Error:\n\n`{str(e)[:200]}`"
        send_telegram_message(chat_id, error_msg)
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
Scheduled Analysis Script for GitHub Actions.

Runs Mo-Fr at 13:30 UTC (before US market open).
Uses the same analysis pipeline as /analyze command.
"""

import os
import sys
import time
import argparse
from pathlib import Path
from datetime import datetime

import yaml

# Import from telegram_worker (same directory)
from telegram_worker import (
    run_analysis,
    format_analyze_result,
    send_telegram_message,
    get_stock_data,
)


def get_current_day() -> str:
    """Get current day of week as lowercase string."""
    days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    return days[datetime.now().weekday()]


def load_watchlist(config_dir: Path, days: list[str] = None) -> list[dict]:
    """Load watchlist and filter by day.

    Args:
        config_dir: Path to config directory
        days: List of days to include. If None, uses current day.
    """
    watchlist_path = config_dir / "watchlist.yaml"

    with open(watchlist_path) as f:
        data = yaml.safe_load(f)

    # Use provided days or current day
    target_days = days if days else [get_current_day()]
    target_days = [d.lower() for d in target_days]

    stocks = []
    for category, items in data.get("watchlist", {}).items():
        for stock in items:
            stock_day = stock.get("day", "").lower()
            # Skip demo stocks unless explicitly requested
            if stock_day == "demo" and "demo" not in target_days:
                continue
            # Include if day matches or no day specified
            if not stock_day or stock_day in target_days:
                stock["category"] = category
                stocks.append(stock)

    return stocks


def run_scheduled_analysis(
    stocks: list[dict],
    lang: str = "de",
    dry_run: bool = False,
    delay_seconds: int = 30,
) -> dict:
    """Run analysis for all stocks in the list.

    Args:
        stocks: List of stock dicts with symbol, name, category
        lang: Output language
        dry_run: If True, don't send Telegram messages
        delay_seconds: Delay between analyses to avoid rate limits

    Returns:
        Summary dict with results
    """
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    results = {"success": [], "errors": []}

    total = len(stocks)
    print(f"\n{'='*60}")
    print(f"SCHEDULED ANALYSIS - {get_current_day().upper()}")
    print(f"{'='*60}")
    print(f"Stocks to analyze: {total}")
    print(f"Language: {lang}")
    print(f"Dry run: {dry_run}")
    print(f"{'='*60}\n")

    # Send start message
    if not dry_run and chat_id:
        start_msg = f"🚀 *Tägliche Analyse gestartet*\n\n📊 {total} Aktien für {get_current_day().capitalize()}"
        send_telegram_message(chat_id, start_msg)

    for i, stock in enumerate(stocks):
        symbol = stock["symbol"]
        name = stock["name"]
        category = stock.get("category", "")

        print(f"\n[{i+1}/{total}] Analyzing {symbol} ({name})...")

        try:
            # Get stock data
            stock_data = get_stock_data(symbol)
            print(f"  Price: ${stock_data['price']:.2f}")

            # Run analysis (same as /analyze command) - pass current price for accuracy
            result = run_analysis(symbol, lang=lang, current_price=stock_data['price'])

            # Format result
            message = format_analyze_result(symbol, result, stock_data, lang=lang)

            # Send to Telegram
            if not dry_run and chat_id:
                success = send_telegram_message(chat_id, message)
                if success:
                    print(f"  ✅ Sent to Telegram")
                else:
                    print(f"  ⚠️ Failed to send")
            else:
                print(f"  📝 Dry run - not sending")
                print(f"\n{'-'*40}")
                print(message[:500] + "..." if len(message) > 500 else message)
                print(f"{'-'*40}\n")

            results["success"].append(symbol)

        except Exception as e:
            error_msg = str(e)[:200]
            print(f"  ❌ Error: {error_msg}")
            results["errors"].append(f"{symbol}: {error_msg}")

            # Send error notification
            if not dry_run and chat_id:
                send_telegram_message(
                    chat_id,
                    f"❌ Fehler bei *{symbol}*:\n`{error_msg}`"
                )

        # Delay between stocks (except for last one)
        if i < total - 1:
            print(f"  ⏳ Waiting {delay_seconds}s...")
            time.sleep(delay_seconds)

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"✅ Success: {len(results['success'])}")
    print(f"❌ Errors: {len(results['errors'])}")

    if results["errors"]:
        print("\nErrors:")
        for err in results["errors"]:
            print(f"  - {err}")

    # Send completion message
    if not dry_run and chat_id:
        summary_msg = f"""✅ *Tägliche Analyse abgeschlossen*

📊 Analysiert: {len(results['success'])}/{total}
❌ Fehler: {len(results['errors'])}"""
        send_telegram_message(chat_id, summary_msg)

    return results


def main():
    parser = argparse.ArgumentParser(description="Scheduled Stock Analysis")
    parser.add_argument("--symbol", type=str, help="Analyze single symbol only")
    parser.add_argument("--days", type=str, help="Comma-separated days (e.g., 'monday,tuesday')")
    parser.add_argument("--all", action="store_true", help="Analyze all stocks (ignore day filter)")
    parser.add_argument("--dry-run", action="store_true", help="Don't send Telegram messages")
    parser.add_argument("--lang", type=str, default="de", help="Output language (de/en)")
    parser.add_argument("--delay", type=int, default=30, help="Delay between stocks in seconds")
    # Default config dir is relative to script location (../config from scripts/)
    default_config = Path(__file__).parent.parent / "config"
    parser.add_argument("--config-dir", type=str, default=str(default_config), help="Config directory path")

    args = parser.parse_args()

    # Check dry run from env
    dry_run = args.dry_run or os.environ.get("DRY_RUN", "").lower() == "true"

    # Load watchlist
    config_dir = Path(args.config_dir)

    if args.symbol:
        # Single symbol mode
        stocks = [{"symbol": args.symbol.upper(), "name": args.symbol.upper()}]
    elif args.all:
        # All stocks (pass all weekdays)
        stocks = load_watchlist(config_dir, days=["monday", "tuesday", "wednesday", "thursday", "friday"])
    elif args.days:
        # Specific days
        days = [d.strip() for d in args.days.split(",")]
        stocks = load_watchlist(config_dir, days=days)
    else:
        # Current day
        stocks = load_watchlist(config_dir)

    if not stocks:
        print(f"No stocks scheduled for {get_current_day()}")
        return 0

    # Run analysis
    results = run_scheduled_analysis(
        stocks=stocks,
        lang=args.lang,
        dry_run=dry_run,
        delay_seconds=args.delay,
    )

    # Exit with error if all failed
    if not results["success"] and results["errors"]:
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

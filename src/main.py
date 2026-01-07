"""
Stock Trading Bot - Main Entry Point

Uses TradingAgents framework with Claude AI for multi-agent stock analysis.
Sends trading recommendations via Telegram instead of executing trades.
"""

import argparse
import asyncio
import os
import sys
from datetime import datetime, date
from pathlib import Path
from typing import Optional

import yaml
from dotenv import load_dotenv

# Add TradingAgents to path
sys.path.insert(0, str(Path(__file__).parent.parent / "TradingAgents"))

from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

from .analysis.signals import DailySummary, SignalType, TradingSignal
from .analysis.signal_extractor import extract_signal_with_claude
from .notifications.telegram_bot import TelegramNotifier
from .notifications.formatters import SignalFormatter
from .utils.logger import setup_logging, get_logger
from .utils.market_hours import MarketHoursChecker


def get_current_day_name() -> str:
    """Get current day of week as lowercase string."""
    from datetime import datetime
    days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    return days[datetime.now().weekday()]


def load_config(config_dir: Path, filter_by_day: bool = True, days: list[str] = None) -> tuple[dict, list[dict]]:
    """Load configuration files.

    Args:
        config_dir: Path to config directory
        filter_by_day: If True, only return stocks scheduled for specified days
        days: List of days to include (e.g., ["monday", "tuesday"]). If None, uses current day.
    """
    settings_path = config_dir / "settings.yaml"
    watchlist_path = config_dir / "watchlist.yaml"

    with open(settings_path) as f:
        settings = yaml.safe_load(f)

    with open(watchlist_path) as f:
        watchlist_data = yaml.safe_load(f)

    # Flatten watchlist into list of stocks
    watchlist = []

    # Use provided days or default to current day
    if days:
        target_days = [d.lower() for d in days]
    else:
        target_days = [get_current_day_name()]

    for category, stocks in watchlist_data.get("watchlist", {}).items():
        for stock in stocks:
            stock["category"] = category
            # Filter by day if enabled
            stock_day = stock.get("day", "").lower()
            if filter_by_day and stock_day:
                if stock_day in target_days:
                    watchlist.append(stock)
            else:
                # No day specified = analyze every day
                watchlist.append(stock)

    return settings, watchlist


def create_trading_agents_config(settings: dict) -> dict:
    """
    Create TradingAgents config with mixed LLM providers.

    Mixed Mode:
    - Gemini 3 Flash for analysts (quick_think_llm) - cheaper, faster
    - Claude Opus for final decision (deep_think_llm) - best reasoning

    Args:
        settings: Our settings.yaml config

    Returns:
        TradingAgents compatible config dict
    """
    config = DEFAULT_CONFIG.copy()

    # Determine LLM provider mode
    llm_provider = settings.get("llm", {}).get("provider", "mixed")
    config["llm_provider"] = llm_provider

    if llm_provider == "mixed":
        # Mixed mode: Gemini for analysts, Opus for final decision
        config["quick_think_llm"] = settings.get("llm", {}).get(
            "quick_think_model", "gemini-3-flash-preview"  # Gemini 3 for analysts
        )
        config["deep_think_llm"] = settings.get("llm", {}).get(
            "deep_think_model", "claude-opus-4-5-20251101"  # Opus for final
        )
    elif llm_provider == "anthropic":
        # Full Anthropic mode (original)
        config["quick_think_llm"] = settings.get("llm", {}).get(
            "quick_think_model", "claude-haiku-4-5-20251001"
        )
        config["deep_think_llm"] = settings.get("llm", {}).get(
            "deep_think_model", "claude-opus-4-5-20251101"
        )
    elif llm_provider == "google":
        # Full Google mode
        config["quick_think_llm"] = settings.get("llm", {}).get(
            "quick_think_model", "gemini-3-flash-preview"
        )
        config["deep_think_llm"] = settings.get("llm", {}).get(
            "deep_think_model", "gemini-2.5-pro"
        )

    # Backend URL (not used for Anthropic/Google, but needed for OpenAI/Ollama)
    config["backend_url"] = settings.get("llm", {}).get("backend_url", "https://api.anthropic.com")

    # Debate settings
    config["max_debate_rounds"] = settings.get("llm", {}).get("max_debate_rounds", 2)
    config["max_risk_discuss_rounds"] = settings.get("llm", {}).get("max_risk_discuss_rounds", 1)

    # Data vendors (use defaults - yfinance + alpha_vantage)
    config["data_vendors"] = {
        "core_stock_apis": "yfinance",
        "technical_indicators": "yfinance",
        "fundamental_data": "alpha_vantage",
        "news_data": "alpha_vantage",
    }

    return config


def get_current_price(symbol: str) -> float:
    """Get current stock price from yfinance.

    Tries multiple sources in order of preference:
    1. regularMarketPrice (real-time during market hours)
    2. currentPrice (may include pre/post market)
    3. preMarketPrice (before market open)
    4. postMarketPrice (after market close)
    5. previousClose (last trading day close)
    6. Historical data fallback
    """
    import yfinance as yf
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info

        # Try various price fields in order of preference
        price_fields = [
            'regularMarketPrice',
            'currentPrice',
            'preMarketPrice',
            'postMarketPrice',
            'previousClose',
        ]

        for field in price_fields:
            price = info.get(field)
            if price and price > 0:
                return float(price)

        # Fallback to historical data
        hist = ticker.history(period="5d")
        if not hist.empty:
            return float(hist['Close'].iloc[-1])
    except Exception:
        pass
    return 0.0


def create_signal_from_state(
    final_state: dict,
    symbol: str,
    name: str,
    logger
) -> TradingSignal:
    """
    Create TradingSignal from TradingAgents state using Claude to extract structured data.

    NO hardcoded percentages - everything comes from the LLM analysis!
    """
    # Get current price from yfinance (reliable source)
    current_price = get_current_price(symbol)

    # Get the LLM decisions from state
    final_decision = final_state.get("final_trade_decision", "")
    investment_plan = final_state.get("investment_plan", "")

    logger.info("extracting_signal", symbol=symbol)

    # Use Claude to extract structured signal
    extracted = extract_signal_with_claude(
        final_decision=final_decision,
        investment_plan=investment_plan,
        symbol=symbol,
        current_price=current_price
    )

    # Map signal type
    signal_type_map = {
        "BUY": SignalType.BUY,
        "SELL": SignalType.SELL,
        "HOLD": SignalType.HOLD,
        "LONG": SignalType.LONG,
        "SHORT": SignalType.SHORT,
    }
    signal_type = signal_type_map.get(extracted.signal_type.upper(), SignalType.HOLD)

    logger.info(
        "signal_extracted",
        symbol=symbol,
        signal_type=signal_type.value,
        action=extracted.action_detail,
        stop_loss=extracted.stop_loss,
    )

    return TradingSignal(
        symbol=symbol,
        name=name,
        signal_type=signal_type,
        current_price=current_price,
        timestamp=datetime.now(),
        # Rich LLM-extracted fields
        action_detail=extracted.action_detail,
        stop_loss=extracted.stop_loss,
        stop_loss_reasoning=extracted.stop_loss_reasoning,
        exit_targets=extracted.exit_targets,
        key_events=extracted.key_events,
        exit_conditions=extracted.exit_conditions,
        final_recommendation=extracted.final_recommendation,
        bull_case=extracted.bull_case,
        bear_case=extracted.bear_case,
    )


class TradingBot:
    """Main trading bot using TradingAgents framework."""

    def __init__(
        self,
        settings: dict,
        watchlist: list[dict],
        dry_run: bool = False,
        single_symbol: Optional[str] = None,
    ):
        self.settings = settings
        self.watchlist = watchlist
        self.dry_run = dry_run
        self.single_symbol = single_symbol
        self.logger = get_logger("TradingBot")

        # Initialize components
        self.market_checker = MarketHoursChecker(
            timezone=settings.get("analysis", {}).get("timezone", "Europe/Berlin")
        )

        self.notifier = TelegramNotifier(dry_run=dry_run)

        self.min_confidence = settings.get("trading", {}).get(
            "min_confidence_for_alert", 65
        )
        self.ticker_delay = settings.get("analysis", {}).get("ticker_delay", 5)

        # Create TradingAgents config with Claude
        self.ta_config = create_trading_agents_config(settings)

        self.logger.info(
            "initialized",
            llm_provider=self.ta_config["llm_provider"],
            deep_think=self.ta_config["deep_think_llm"],
            quick_think=self.ta_config["quick_think_llm"],
        )

    def run(self) -> DailySummary:
        """Run the full analysis pipeline (synchronous for TradingAgents)."""
        self.logger.info("starting_trading_bot")

        # Check if it's a trading day
        if not self.market_checker.is_trading_day():
            self.logger.info("market_closed_today")
            return DailySummary(
                date=datetime.now(),
                total_analyzed=0,
                errors=["Market is closed today"],
            )

        # Filter watchlist if single symbol specified
        stocks_to_analyze = self.watchlist
        if self.single_symbol:
            stocks_to_analyze = [
                s for s in self.watchlist if s["symbol"] == self.single_symbol
            ]
            if not stocks_to_analyze:
                self.logger.error("symbol_not_in_watchlist", symbol=self.single_symbol)
                return DailySummary(
                    date=datetime.now(),
                    total_analyzed=0,
                    errors=[f"Symbol {self.single_symbol} not in watchlist"],
                )

        # Create daily summary
        summary = DailySummary(
            date=datetime.now(),
            total_analyzed=len(stocks_to_analyze),
        )

        # Today's date for TradingAgents
        today = date.today().isoformat()

        # Analyze each stock
        for i, stock in enumerate(stocks_to_analyze):
            symbol = stock["symbol"]
            name = stock["name"]

            self.logger.info(
                "analyzing_stock",
                symbol=symbol,
                progress=f"{i + 1}/{len(stocks_to_analyze)}",
            )

            # Retry logic for rate limits
            max_retries = 3
            retry_count = 0
            success = False

            while retry_count < max_retries and not success:
                try:
                    # Initialize TradingAgents for this analysis
                    ta = TradingAgentsGraph(
                        debug=False,  # Set to True for verbose output
                        config=self.ta_config,
                    )

                    # Run TradingAgents analysis
                    self.logger.info("running_tradingagents", symbol=symbol, date=today)
                    final_state, decision = ta.propagate(symbol, today)

                    self.logger.info("tradingagents_decision", symbol=symbol, decision=decision[:100])

                    # Extract structured signal from LLM output (no hardcoded values!)
                    signal = create_signal_from_state(
                        final_state=final_state,
                        symbol=symbol,
                        name=name,
                        logger=self.logger
                    )
                    summary.add_signal(signal)

                    self.logger.info(
                        "signal_generated",
                        symbol=symbol,
                        signal_type=signal.signal_type.value,
                        action=signal.action_detail,
                    )
                    success = True

                except Exception as e:
                    error_str = str(e)
                    # Check if it's a rate limit error
                    if "429" in error_str or "rate_limit" in error_str.lower():
                        retry_count += 1
                        if retry_count < max_retries:
                            # Exponential backoff: 60s, 120s, 180s
                            wait_time = 60 * retry_count
                            self.logger.warning(
                                "rate_limit_hit",
                                symbol=symbol,
                                retry=retry_count,
                                wait_seconds=wait_time,
                            )
                            print(f"Rate limit hit for {symbol}. Waiting {wait_time}s before retry {retry_count}/{max_retries}...")
                            import time
                            time.sleep(wait_time)
                        else:
                            error_msg = f"{symbol}: Rate limit exceeded after {max_retries} retries"
                            self.logger.error("rate_limit_exhausted", symbol=symbol)
                            summary.errors.append(error_msg)
                    else:
                        # Non-rate-limit error, don't retry
                        error_msg = f"{symbol}: {error_str}"
                        self.logger.error("analysis_failed", symbol=symbol, error=error_str)
                        summary.errors.append(error_msg)
                        break

            # Delay between tickers (longer to avoid rate limits)
            if i < len(stocks_to_analyze) - 1:
                import time
                # Wait 30 seconds between tickers to stay under rate limit
                delay = max(self.ticker_delay, 30)
                self.logger.info("waiting_between_tickers", seconds=delay)
                time.sleep(delay)

        # Determine top pick
        summary.determine_top_pick()

        self.logger.info(
            "analysis_complete",
            total=summary.total_analyzed,
            buy_signals=len(summary.buy_signals),
            sell_signals=len(summary.sell_signals),
            errors=len(summary.errors),
        )

        return summary


async def send_notifications(
    summary: DailySummary,
    notifier: TelegramNotifier,
    min_confidence: float,
    send_summary: bool,
) -> int:
    """Send Telegram notifications for the analysis results."""
    alerts_sent = 0

    # Send startup message
    await notifier.send_startup_message()

    # Send actionable signals (BUY, SELL, alerts)
    actionable_signals = (
        summary.buy_signals +
        summary.sell_signals +
        summary.support_alerts +
        summary.resistance_alerts
    )

    for signal in actionable_signals:
        if signal.is_actionable(min_confidence):
            await notifier.send_signal(signal)
            alerts_sent += 1

    # Send HOLD signals as individual messages too (full details)
    for signal in summary.hold_signals:
        await notifier.send_signal(signal)

    # Send daily summary
    if send_summary:
        await notifier.send_daily_summary(summary)

    # Send completion message
    await notifier.send_completion_message(
        analyzed=summary.total_analyzed,
        alerts=alerts_sent,
    )

    return alerts_sent


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Stock Trading Bot - TradingAgents with Claude AI"
    )

    parser.add_argument(
        "--symbol",
        type=str,
        help="Analyze only this symbol",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't send Telegram messages",
    )

    parser.add_argument(
        "--test",
        action="store_true",
        help="Test mode (implies --dry-run)",
    )

    parser.add_argument(
        "--config-dir",
        type=str,
        default="config",
        help="Path to config directory",
    )

    parser.add_argument(
        "--log-level",
        type=str,
        default=None,
        help="Log level (DEBUG, INFO, WARNING, ERROR)",
    )

    parser.add_argument(
        "--all-stocks",
        action="store_true",
        help="Analyze all stocks regardless of day rotation",
    )

    parser.add_argument(
        "--days",
        type=str,
        help="Comma-separated days to analyze (e.g., 'monday,tuesday')",
    )

    return parser.parse_args()


def main() -> int:
    """Main entry point."""
    args = parse_args()

    # Load environment variables (override=True to use .env over system env vars)
    load_dotenv(override=True)

    # Determine log level
    log_level = args.log_level or os.getenv("LOG_LEVEL", "INFO")

    # Setup logging
    setup_logging(
        level=log_level,
        log_file="logs/trading_bot.log",
    )

    logger = get_logger("main")
    logger.info("starting", args=vars(args))

    # Validate required environment variables
    required_vars = ["ANTHROPIC_API_KEY", "ALPHA_VANTAGE_API_KEY"]
    missing = [v for v in required_vars if not os.getenv(v)]
    if missing:
        logger.error("missing_env_vars", vars=missing)
        print(f"Error: Missing required environment variables: {missing}")
        return 1

    # Check Telegram config unless dry run
    dry_run = args.dry_run or args.test or os.getenv("DRY_RUN", "").lower() == "true"
    if not dry_run:
        telegram_vars = ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"]
        missing_telegram = [v for v in telegram_vars if not os.getenv(v)]
        if missing_telegram:
            logger.error("missing_telegram_vars", vars=missing_telegram)
            print(f"Error: Missing Telegram variables: {missing_telegram}")
            return 1

    # Load configuration
    config_dir = Path(args.config_dir)
    if not config_dir.exists():
        logger.error("config_dir_not_found", path=str(config_dir))
        print(f"Error: Config directory not found: {config_dir}")
        return 1

    try:
        # filter_by_day=False if --all-stocks is set
        filter_by_day = not args.all_stocks
        # Parse --days argument if provided
        days_list = None
        if args.days:
            days_list = [d.strip() for d in args.days.split(",")]
        settings, watchlist = load_config(config_dir, filter_by_day=filter_by_day, days=days_list)
    except Exception as e:
        logger.error("config_load_error", error=str(e))
        print(f"Error loading config: {e}")
        return 1

    current_day = get_current_day_name()
    if args.days:
        logger.info("config_loaded", stocks_count=len(watchlist), days=args.days)
    elif filter_by_day:
        logger.info("config_loaded", stocks_count=len(watchlist), day=current_day)
    else:
        logger.info("config_loaded", stocks_count=len(watchlist), mode="all_stocks")

    # Create and run bot
    bot = TradingBot(
        settings=settings,
        watchlist=watchlist,
        dry_run=dry_run,
        single_symbol=args.symbol,
    )

    try:
        # Run analysis (synchronous - TradingAgents is sync)
        summary = bot.run()

        # Send notifications (async)
        if not dry_run:
            notifier = TelegramNotifier(dry_run=False)
            asyncio.run(send_notifications(
                summary=summary,
                notifier=notifier,
                min_confidence=bot.min_confidence,
                send_summary=settings.get("telegram", {}).get("send_daily_summary", True),
            ))
        else:
            # Print summary to console in dry-run mode
            print("\n" + "="*60)
            print("DRY RUN - Analysis Complete")
            print("="*60)
            print(f"Analyzed: {summary.total_analyzed} stocks")
            print(f"BUY signals: {len(summary.buy_signals)}")
            print(f"SELL signals: {len(summary.sell_signals)}")
            print(f"Errors: {len(summary.errors)}")

            if summary.buy_signals:
                print("\nBUY Signals:")
                for s in summary.buy_signals:
                    print(f"  - {s.symbol}: {s.confidence}% confidence")

            if summary.sell_signals:
                print("\nSELL Signals:")
                for s in summary.sell_signals:
                    print(f"  - {s.symbol}: {s.confidence}% confidence")

            if summary.top_pick:
                print(f"\nTop Pick: {summary.top_pick.symbol}")

            if summary.errors:
                print("\nErrors:")
                for e in summary.errors:
                    print(f"  - {e}")
            print("="*60)

        # Return non-zero if there were errors
        if summary.errors and not summary.buy_signals and not summary.sell_signals:
            return 1

        return 0

    except KeyboardInterrupt:
        logger.info("interrupted")
        return 130

    except Exception as e:
        logger.exception("fatal_error", error=str(e))
        print(f"Fatal error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

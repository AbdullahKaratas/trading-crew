#!/usr/bin/env python3
"""
Portfolio Worker for /portfolio command.

Handles portfolio tracking with KI-based recommendations:
- SALE: Dringender Verkauf (KO-Risiko, starker Mismatch)
- TAKE PROFIT: Gewinne sichern
- HOLD: Position halten
- BUY MORE: Position ausbauen
- RESTRUCTURE: Kapital umschichten
"""

import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from universal_agents import run_universal_analysis
from gemini_utils import call_gemini_pro, get_language_instruction
from telegram_worker import send_telegram_message, send_telegram_photo, resolve_symbol
from supabase_client import get_supabase_client


@dataclass
class Position:
    """Represents a portfolio position."""

    symbol: str  # yfinance symbol
    display_name: str  # User-provided name
    direction: str  # LONG/SHORT/NORMAL
    current_value: float  # Current total value of position in €
    factor: float  # Leverage (1 for normal stocks)
    knockout_level: float  # 0 for normal stocks
    performance: Optional[float] = None  # Performance in % (e.g., 49.40 or -15.5)
    currency: str = "USD"  # Currency for KO level (USD or EUR)


def parse_position(pos_str: str) -> Optional[Position]:
    """
    Parse a position string into a Position object.

    Format: <Stock>-<Direction>-<CurrentValue>-<Factor>-<KnockoutLevel>[-<Performance>][-<Currency>]

    Performance can be negative (e.g., -15.5 for -15.5%)

    Examples:
        SILVER-LONG-956-4.16-78
        SILVER-LONG-956-4.16-78-49.40          (49.40% profit)
        SILVER-LONG-956-4.16-78--15.5          (15.5% loss, note double dash)
        SILVER-LONG-956-4.16-78-49.40-USD
        SiemensEnergy-LONG-365-5.17-115-49.40-EUR
        AAPL-NORMAL-1000-1-0
    """
    # Handle negative performance: replace -- with a placeholder
    pos_str_normalized = pos_str.replace("--", "-NEG")
    parts = pos_str_normalized.split("-")

    if len(parts) < 5:
        print(f"  Invalid position format: {pos_str} (need at least 5 parts)")
        return None

    try:
        display_name = parts[0]
        direction = parts[1].upper()

        if direction not in ["LONG", "SHORT", "NORMAL"]:
            print(f"  Invalid direction: {direction}")
            return None

        current_value = float(parts[2])
        factor = float(parts[3])
        knockout_level = float(parts[4])

        # Optional performance (6th part) and currency (7th part)
        performance = None
        currency = "USD"  # Default currency

        if len(parts) > 5:
            part5 = parts[5]
            # Check if 6th part is a currency or performance
            if part5.upper() in ["USD", "EUR"]:
                currency = part5.upper()
            else:
                # Handle negative performance (NEG prefix from normalization)
                if part5.startswith("NEG"):
                    performance = -float(part5[3:])
                else:
                    performance = float(part5)
                # Check for currency in 7th part
                if len(parts) > 6 and parts[6].upper() in ["USD", "EUR"]:
                    currency = parts[6].upper()

        return Position(
            symbol="",  # Will be resolved later
            display_name=display_name,
            direction=direction,
            current_value=current_value,
            factor=factor,
            knockout_level=knockout_level,
            performance=performance,
            currency=currency,
        )
    except (ValueError, IndexError) as e:
        print(f"  Error parsing position {pos_str}: {e}")
        return None


def calculate_ko_proximity(current_price: float, knockout_level: float, direction: str) -> float:
    """
    Calculate distance to knockout level in percentage.

    LONG: (current_price - knockout) / current_price * 100
    SHORT: (knockout - current_price) / current_price * 100
    """
    if knockout_level <= 0 or current_price <= 0:
        return 100.0  # No KO risk for normal stocks

    if direction == "LONG":
        return (current_price - knockout_level) / current_price * 100
    elif direction == "SHORT":
        return (knockout_level - current_price) / current_price * 100
    else:
        return 100.0  # NORMAL stocks have no KO


def calculate_original_investment(current_value: float, performance: Optional[float]) -> Optional[float]:
    """
    Calculate original investment from current value and performance.

    Formula: original = current_value / (1 + performance/100)

    Example: current=956€, performance=+49.40% → original = 956 / 1.494 = 639.89€
    """
    if performance is None:
        return None

    if performance == -100:  # Edge case: total loss
        return None

    return current_value / (1 + performance / 100)


def run_single_analysis(symbol: str, lang: str, chat_id: str = None) -> dict:
    """Run analysis for a single symbol and optionally send chart."""
    try:
        today = date.today().isoformat()
        result = run_universal_analysis(symbol, trade_date=today, lang=lang)

        # Send chart to Telegram if available
        if chat_id and result.get("chart_image"):
            try:
                chart_bytes = result["chart_image"].getvalue()
                trade = result.get("trade_decision", {})
                signal = trade.get("signal", "?")
                conf = trade.get("confidence", 0)
                caption = f"{symbol}: {signal} ({conf:.0%})"
                send_telegram_photo(chat_id, chart_bytes, caption)
                print(f"  [Chart] {symbol} sent to Telegram")
            except Exception as e:
                print(f"  [Chart] Failed to send {symbol}: {str(e)[:50]}")

        return {
            "symbol": symbol,
            "success": True,
            "result": result,
        }
    except Exception as e:
        print(f"  Error analyzing {symbol}: {e}")
        return {
            "symbol": symbol,
            "success": False,
            "error": str(e),
        }


def generate_portfolio_recommendations(positions_with_analysis: list, lang: str) -> str:
    """
    Use Gemini Pro to generate portfolio-level recommendations.

    Recommendations: SALE, TAKE PROFIT, HOLD, BUY MORE, RESTRUCTURE
    """
    lang_instruction = get_language_instruction(lang, "Write")
    is_de = lang == "de"

    # Build position summaries
    summaries = []
    for item in positions_with_analysis:
        pos = item["position"]
        analysis = item.get("analysis", {})
        current_price = item.get("current_price", 0)
        ko_proximity = item.get("ko_proximity", 100)

        trade = analysis.get("trade_decision", {}) if analysis else {}
        signal = trade.get("signal", "N/A")
        confidence = trade.get("confidence", 0)

        perf_str = f", Performance: {pos.performance:+.1f}%" if pos.performance is not None else ""
        curr_symbol = "€" if pos.currency == "EUR" else "$"

        summary = f"""
**{pos.display_name}** ({pos.symbol})
- Position: {pos.direction} | Current Value: {pos.current_value:.2f}€ | Factor: {pos.factor}x{perf_str}
- Asset Price: {curr_symbol}{current_price:.2f}
- KO Level: {pos.knockout_level} | KO Distance: {ko_proximity:.1f}%
- Analysis Signal: {signal} | Confidence: {confidence:.0%}
- Analysis: {trade.get('detailed_analysis', 'N/A')[:300]}
"""
        summaries.append(summary)

    prompt = f"""You are a portfolio risk manager analyzing a user's trading positions.

## Portfolio Positions:
{''.join(summaries)}

## Your Task:
Generate recommendations for EACH position using these categories:

1. **SALE** - Urgent sell:
   - KO distance < 5% (CRITICAL)
   - KO distance < 10% AND signal mismatches direction
   - Strong opposing signal with high confidence

2. **TAKE PROFIT** - Secure gains:
   - Good P/L profit AND signal turning neutral/opposite
   - Target reached, trend weakening
   - Direction mismatch but no immediate KO risk

3. **HOLD** - Keep position:
   - Direction aligned with signal
   - KO distance safe (>15%)
   - Thesis still intact

4. **BUY MORE** - Increase position:
   - Strong signal aligned with direction
   - High confidence (>75%)
   - Good entry point, KO safe

5. **RESTRUCTURE** - Shift capital between positions:
   - One position has much better signal than another
   - Better risk/reward ratio elsewhere
   - Consider correlation (don't suggest Gold to Silver)

## Output Format:
For each position, provide:
- [RECOMMENDATION] Symbol
- Reason (2-3 sentences)
- Priority: HIGH/MEDIUM/LOW

Then provide:
- Portfolio summary (2-3 sentences)
- Top priority action

{lang_instruction}
Keep response under 800 words. Be decisive and actionable."""

    return call_gemini_pro(prompt, use_search=False)


def format_portfolio_output(
    positions_with_analysis: list,
    recommendations: str,
    lang: str,
) -> str:
    """Format the portfolio output for Telegram."""
    is_de = lang == "de"

    # Header
    header = f"""{"Portfolio-Analyse" if is_de else "Portfolio Analysis"}
{"─" * 30}
"""

    # Individual position summaries
    position_lines = ""
    for item in positions_with_analysis:
        pos = item["position"]
        current_price = item.get("current_price", 0)
        ko_proximity = item.get("ko_proximity", 100)
        analysis = item.get("analysis", {})
        trade = analysis.get("trade_decision", {}) if analysis else {}

        signal = trade.get("signal", "N/A")
        confidence = trade.get("confidence", 0)

        # Direction emoji
        dir_emoji = {"LONG": "", "SHORT": "", "NORMAL": ""}.get(pos.direction, "")

        # KO status emoji
        if ko_proximity < 5:
            ko_emoji = ""  # CRITICAL
        elif ko_proximity < 10:
            ko_emoji = ""  # WARNING
        elif ko_proximity < 15:
            ko_emoji = ""  # CAUTION
        else:
            ko_emoji = ""  # SAFE

        # Currency symbol for KO level
        curr_symbol = "€" if pos.currency == "EUR" else "$"

        # Performance display
        if pos.performance is not None:
            perf_emoji = "" if pos.performance >= 0 else ""
            perf_str = f" | {pos.performance:+.1f}% {perf_emoji}"
        else:
            perf_str = ""

        # Signal emoji
        signal_emoji = {"LONG": "", "SHORT": "", "HOLD": "", "IGNORE": ""}.get(signal, "")

        position_lines += f"""
{dir_emoji} *{pos.display_name}* ({pos.direction})
├── {pos.current_value:,.0f}€{perf_str} | {pos.factor}x
├── {curr_symbol}{current_price:,.2f} | KO: {curr_symbol}{pos.knockout_level} ({ko_proximity:.1f}% {"entfernt" if is_de else "away"}) {ko_emoji}
├── Signal: {signal} ({confidence:.0%}) {signal_emoji}
"""

    # Recommendations section
    rec_header = "Empfehlungen" if is_de else "Recommendations"
    rec_section = f"""
{"─" * 30}
*{rec_header}*

{recommendations}
"""

    return header + position_lines + rec_section


def show_portfolio(user_id: str, chat_id: str, lang: str) -> int:
    """Show current portfolio without running new analyses."""
    is_de = lang == "de"

    db = get_supabase_client()
    if not db:
        msg = " Supabase nicht konfiguriert." if is_de else " Supabase not configured."
        send_telegram_message(chat_id, msg)
        return 1

    positions = db.get_portfolio(user_id)

    if not positions:
        msg = " Kein Portfolio gefunden. Nutze `/portfolio SYMBOL-DIRECTION-VALUE-FACTOR-KO` zum Hinzufugen." if is_de else " No portfolio found. Use `/portfolio SYMBOL-DIRECTION-VALUE-FACTOR-KO` to add positions."
        send_telegram_message(chat_id, msg)
        return 0

    # Format simple list
    lines = [f"*{'Dein Portfolio' if is_de else 'Your Portfolio'}*", "─" * 25]

    for pos in positions:
        direction = pos.get("direction", "?")
        dir_emoji = {"LONG": "", "SHORT": "", "NORMAL": ""}.get(direction, "")
        performance = pos.get("performance")
        currency = pos.get("currency", "USD")
        curr_symbol = "€" if currency == "EUR" else "$"

        # Performance display
        if performance is not None:
            perf_emoji = "" if performance >= 0 else ""
            perf_str = f" | {performance:+.1f}% {perf_emoji}"
        else:
            perf_str = ""

        lines.append(
            f"{dir_emoji} *{pos.get('display_name', pos.get('symbol'))}* ({direction})"
        )
        lines.append(f"├── {pos.get('current_value', 0):.0f}€{perf_str} | {pos.get('factor', 1)}x | KO: {curr_symbol}{pos.get('knockout_level', 0)}")

    lines.append("")
    lines.append(f"{'Nutze' if is_de else 'Use'} `/portfolio` {'fur Analyse' if is_de else 'for analysis'}")

    send_telegram_message(chat_id, "\n".join(lines))
    return 0


def clear_portfolio(user_id: str, chat_id: str, lang: str) -> int:
    """Clear all positions from portfolio."""
    is_de = lang == "de"

    db = get_supabase_client()
    if not db:
        msg = " Supabase nicht konfiguriert." if is_de else " Supabase not configured."
        send_telegram_message(chat_id, msg)
        return 1

    db.clear_portfolio(user_id)
    msg = " Portfolio geloscht." if is_de else " Portfolio cleared."
    send_telegram_message(chat_id, msg)
    return 0


def remove_position(user_id: str, symbol: str, chat_id: str, lang: str) -> int:
    """Remove a specific position from portfolio."""
    is_de = lang == "de"

    db = get_supabase_client()
    if not db:
        msg = " Supabase nicht konfiguriert." if is_de else " Supabase not configured."
        send_telegram_message(chat_id, msg)
        return 1

    # Resolve symbol first
    resolved_symbol, _ = resolve_symbol(symbol)

    db.remove_position(user_id, resolved_symbol)
    msg = f" {symbol} entfernt." if is_de else f" {symbol} removed."
    send_telegram_message(chat_id, msg)
    return 0


def update_portfolio(user_id: str, chat_id: str, lang: str) -> int:
    """
    Load portfolio from DB and run fresh analysis with updated prices.

    This is the /portfolio update command.
    """
    is_de = lang == "de"

    db = get_supabase_client()
    if not db:
        msg = " Supabase nicht konfiguriert." if is_de else " Supabase not configured."
        send_telegram_message(chat_id, msg)
        return 1

    db_positions = db.get_portfolio(user_id)

    if not db_positions:
        msg = " Kein Portfolio gefunden. Nutze `/portfolio SYMBOL-DIRECTION-AMOUNT-FACTOR-KO` zum Hinzufugen." if is_de else " No portfolio found. Use `/portfolio SYMBOL-DIRECTION-AMOUNT-FACTOR-KO` to add positions."
        send_telegram_message(chat_id, msg)
        return 0

    # Convert DB records to Position objects
    positions = []
    for db_pos in db_positions:
        positions.append(Position(
            symbol=db_pos.get("symbol", ""),
            display_name=db_pos.get("display_name", db_pos.get("symbol", "")),
            direction=db_pos.get("direction", "NORMAL"),
            current_value=float(db_pos.get("current_value", 0)),
            factor=float(db_pos.get("factor", 1)),
            knockout_level=float(db_pos.get("knockout_level", 0)),
            performance=float(db_pos["performance"]) if db_pos.get("performance") is not None else None,
            currency=db_pos.get("currency", "USD"),
        ))

    print(f"\n{'='*60}")
    print(f"PORTFOLIO UPDATE: {len(positions)} positions from DB")
    print(f"{'='*60}")

    for pos in positions:
        print(f"  Loaded: {pos.display_name} ({pos.symbol}) - {pos.direction}")

    # Run analysis (same as main flow)
    return run_portfolio_analysis(positions, user_id, chat_id, lang, save_to_db=False)


def run_portfolio_analysis(
    positions: list,
    user_id: str,
    chat_id: str,
    lang: str,
    save_to_db: bool = True,
) -> int:
    """
    Core portfolio analysis logic.

    Args:
        positions: List of Position objects
        user_id: Telegram user ID
        chat_id: Telegram chat ID
        lang: Language code (de/en)
        save_to_db: Whether to save positions to Supabase
    """
    is_de = lang == "de"

    # Save to Supabase (if enabled)
    if save_to_db:
        db = get_supabase_client()
        if db:
            print("\nSaving positions to Supabase...")
            for pos in positions:
                db.upsert_position({
                    "user_id": user_id,
                    "symbol": pos.symbol,
                    "display_name": pos.display_name,
                    "direction": pos.direction,
                    "current_value": pos.current_value,
                    "factor": pos.factor,
                    "knockout_level": pos.knockout_level,
                    "performance": pos.performance,
                    "currency": pos.currency,
                })
            print(f"  Saved {len(positions)} positions")
        else:
            print("  Supabase not configured, skipping save")
    else:
        print("  Skipping DB save (--nosave or update mode)")

    # Send "working" message
    working_msg = f" {'Analysiere Portfolio...' if is_de else 'Analyzing portfolio...'}\n{'Dies kann einige Minuten dauern.' if is_de else 'This may take a few minutes.'}"
    send_telegram_message(chat_id, working_msg)

    # Run parallel analyses (max 3 at a time)
    print("\nRunning parallel analyses...")
    analysis_results = {}

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {}
        for i, pos in enumerate(positions):
            if i > 0:
                time.sleep(2)  # Small delay to avoid rate limits
            futures[executor.submit(run_single_analysis, pos.symbol, lang, chat_id)] = pos.symbol

        for future in as_completed(futures):
            symbol = futures[future]
            try:
                result = future.result()
                analysis_results[symbol] = result
                status = "" if result["success"] else ""
                print(f"  [{status}] {symbol} completed")
            except Exception as e:
                print(f"  [] {symbol} error: {e}")
                analysis_results[symbol] = {"symbol": symbol, "success": False, "error": str(e)}

    # Build combined data for recommendations
    positions_with_analysis = []
    for pos in positions:
        analysis = analysis_results.get(pos.symbol, {})
        trade = {}
        current_price = 0

        if analysis.get("success"):
            result = analysis.get("result", {})
            trade = result.get("trade_decision", {})
            # Use EUR price if position is in EUR
            if pos.currency == "EUR":
                current_price = trade.get("price_eur", 0)
            else:
                current_price = trade.get("price_usd", 0)

        ko_proximity = calculate_ko_proximity(current_price, pos.knockout_level, pos.direction)

        positions_with_analysis.append({
            "position": pos,
            "analysis": analysis.get("result") if analysis.get("success") else None,
            "current_price": current_price,
            "ko_proximity": ko_proximity,
        })

    # Generate portfolio-level recommendations
    print("\nGenerating portfolio recommendations...")
    recommendations = generate_portfolio_recommendations(positions_with_analysis, lang)

    # Format and send output
    message = format_portfolio_output(positions_with_analysis, recommendations, lang)
    success = send_telegram_message(chat_id, message)

    if success:
        print(f"\nPortfolio analysis sent to chat {chat_id}")
        return 0
    else:
        print("\nFailed to send portfolio analysis")
        return 1


def main():
    """Main entry point."""
    portfolio_args = os.environ.get("PORTFOLIO_ARGS", "").strip()
    user_id = os.environ.get("USER_ID", "")
    chat_id = os.environ.get("CHAT_ID", "")
    lang = os.environ.get("LANG", "de").lower()

    if lang not in ["de", "en"]:
        lang = "de"

    is_de = lang == "de"

    if not user_id or not chat_id:
        print("Error: USER_ID and CHAT_ID required")
        return 1

    # Parse command and flags
    args = portfolio_args.split()

    # Check for --nosave flag
    save_to_db = True
    if "--nosave" in args:
        save_to_db = False
        args.remove("--nosave")
        print("  --nosave flag detected, will not save to database")

    # Handle subcommands
    if not args or args[0].lower() == "show":
        return show_portfolio(user_id, chat_id, lang)

    if args[0].lower() == "clear":
        return clear_portfolio(user_id, chat_id, lang)

    if args[0].lower() == "remove" and len(args) > 1:
        return remove_position(user_id, args[1], chat_id, lang)

    if args[0].lower() == "update":
        return update_portfolio(user_id, chat_id, lang)

    # Parse positions from args
    positions = []
    for arg in args:
        pos = parse_position(arg)
        if pos:
            positions.append(pos)

    if not positions:
        msg = " Keine gultigen Positionen gefunden.\nFormat: `SYMBOL-DIRECTION-VALUE-FACTOR-KO[-PERF][-EUR/USD]`\n\nBeispiel: `SILVER-LONG-956-4.16-78-49.40`\nNegative Perf: `SILVER-LONG-500-4.16-78--15.5`\n\nFlags: `--nosave` (nicht speichern)" if is_de else " No valid positions found.\nFormat: `SYMBOL-DIRECTION-VALUE-FACTOR-KO[-PERF][-EUR/USD]`\n\nExample: `SILVER-LONG-956-4.16-78-49.40`\nNegative perf: `SILVER-LONG-500-4.16-78--15.5`\n\nFlags: `--nosave` (don't save)"
        send_telegram_message(chat_id, msg)
        return 1

    # Resolve symbols
    print(f"\n{'='*60}")
    print(f"PORTFOLIO ANALYSIS: {len(positions)} positions")
    print(f"{'='*60}")

    for pos in positions:
        symbol, name = resolve_symbol(pos.display_name)
        pos.symbol = symbol
        print(f"  Resolved: {pos.display_name} -> {symbol} ({pos.currency})")

    # Run analysis with save_to_db flag
    return run_portfolio_analysis(positions, user_id, chat_id, lang, save_to_db=save_to_db)


if __name__ == "__main__":
    sys.exit(main())

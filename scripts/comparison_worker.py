#!/usr/bin/env python3
"""
Comparison Worker for /vs command.
Runs parallel analyses and generates comparative recommendation.
"""

import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from universal_agents import run_universal_analysis
from gemini_utils import call_gemini_pro, get_language_instruction
from telegram_worker import send_telegram_message, resolve_symbol


def run_single_analysis(symbol: str, lang: str) -> dict:
    """Run analysis for a single symbol."""
    try:
        today = date.today().isoformat()
        result = run_universal_analysis(symbol, trade_date=today, lang=lang)
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


def generate_comparison(results: list, lang: str) -> str:
    """Use Gemini Pro to generate comparative analysis."""
    lang_instruction = get_language_instruction(lang, "Write")
    is_de = lang == "de"

    # Build summary of each asset
    summaries = []
    for r in results:
        if r["success"]:
            trade = r["result"].get("trade_decision", {})
            tf = trade.get("timeframes", {})
            summary = f"""
**{r['symbol']}**:
- Signal: {trade.get('signal', 'N/A')}
- Confidence: {trade.get('confidence', 0):.0%}
- Price: ${trade.get('price_usd', 0):,.2f}
- Timeframes: Short={tf.get('short_term', 'N/A')}, Medium={tf.get('medium_term', 'N/A')}, Long={tf.get('long_term', 'N/A')}
- Analysis: {trade.get('detailed_analysis', '')[:400]}
"""
            summaries.append(summary)
        else:
            summaries.append(f"**{r['symbol']}**: Analysis failed - {r.get('error', 'Unknown error')}")

    prompt = f"""You are comparing multiple trading assets for investment recommendation.

## Individual Analyses:
{''.join(summaries)}

## Your Task:
1. Create a comparison table showing key metrics side-by-side
2. Identify which asset(s) offer the best risk/reward
3. Consider correlation (e.g., GOLD and SILVER often move together)
4. Provide a CLEAR final ranking with reasoning

Format your response as:
1. **Comparison Table** (markdown table with Signal, Confidence, Timeframes)
2. **Key Differences** (3-5 bullet points)
3. **Correlation Notes** (if applicable - do they move together?)
4. **Final Recommendation** (RANKED list: 1st choice, 2nd choice, etc. with brief reason)

{lang_instruction}
Keep response under 600 words. Be decisive in your ranking."""

    return call_gemini_pro(prompt, use_search=False)


def format_comparison_result(results: list, comparison: str, lang: str) -> str:
    """Format the full comparison output for Telegram."""
    is_de = lang == "de"

    # Header
    symbols = [r["symbol"] for r in results]
    header = f"""⚖️ *{"Vergleichsanalyse" if is_de else "Comparison Analysis"}*
{" vs ".join(symbols)}
{"─" * 30}
"""

    # Individual summaries
    individual = ""
    for r in results:
        if r["success"]:
            trade = r["result"].get("trade_decision", {})
            signal = trade.get("signal", "N/A")
            emoji = {"LONG": "🟢", "SHORT": "🔴", "HOLD": "🟡", "IGNORE": "⚫"}.get(signal, "⚪")
            conf = trade.get("confidence", 0)
            price = trade.get("price_usd", 0)
            tf = trade.get("timeframes", {})

            individual += f"""
{emoji} *{r['symbol']}*: {signal} ({conf:.0%})
├── ${price:,.2f}
├── KF: {tf.get('short_term', '?')} | MF: {tf.get('medium_term', '?')} | LF: {tf.get('long_term', '?')}
"""
        else:
            individual += f"""
❌ *{r['symbol']}*: {"Analyse fehlgeschlagen" if is_de else "Analysis failed"}
"""

    # Comparison analysis
    comparison_section = f"""
{"─" * 30}
📊 *{"Vergleich & Empfehlung" if is_de else "Comparison & Recommendation"}:*

{comparison}
"""

    return header + individual + comparison_section


def main():
    """Main entry point."""
    symbols_raw = os.environ.get("SYMBOLS", "")
    chat_id = os.environ.get("CHAT_ID")
    lang = os.environ.get("LANG", "de").lower()

    if lang not in ["de", "en"]:
        lang = "de"

    # Parse symbols (space or comma separated)
    raw_symbols = [s.strip() for s in symbols_raw.replace(",", " ").split() if s.strip()]

    print(f"Comparison request: {raw_symbols}")
    print(f"Language: {lang}")

    # Resolve company names to symbols
    symbols = []
    symbol_names = {}
    for raw in raw_symbols:
        symbol, name = resolve_symbol(raw)
        symbols.append(symbol)
        symbol_names[symbol] = name

    if len(symbols) < 2:
        msg = "❌ Mindestens 2 Assets für Vergleich erforderlich.\nBeispiel: /vs GOLD SILVER" if lang == "de" else "❌ At least 2 assets required for comparison.\nExample: /vs GOLD SILVER"
        send_telegram_message(chat_id, msg)
        return 1

    if len(symbols) > 4:
        msg = "❌ Maximal 4 Assets für Vergleich erlaubt.\nBeispiel: /vs GOLD SILVER PLATIN" if lang == "de" else "❌ Maximum 4 assets allowed for comparison.\nExample: /vs GOLD SILVER PLATINUM"
        send_telegram_message(chat_id, msg)
        return 1

    # Send "working" message
    working_msg = f"🔄 {'Analysiere' if lang == 'de' else 'Analyzing'} {', '.join(symbols)}...\n{'Dies kann einige Minuten dauern.' if lang == 'de' else 'This may take a few minutes.'}"
    send_telegram_message(chat_id, working_msg)

    # Run analyses in parallel (with small delay to avoid rate limits)
    print(f"\n{'='*60}")
    print(f"COMPARISON ANALYSIS: {' vs '.join(symbols)}")
    print(f"{'='*60}")

    results = []

    # Use ThreadPoolExecutor for parallel execution
    with ThreadPoolExecutor(max_workers=min(len(symbols), 2)) as executor:
        # Submit all tasks
        futures = {}
        for i, sym in enumerate(symbols):
            if i > 0:
                time.sleep(2)  # Small delay between submissions to avoid rate limits
            futures[executor.submit(run_single_analysis, sym, lang)] = sym

        # Collect results as they complete
        for future in as_completed(futures):
            sym = futures[future]
            try:
                result = future.result()
                results.append(result)
                status = "✓" if result["success"] else "✗"
                print(f"  [{status}] {sym} completed")
            except Exception as e:
                print(f"  [✗] {sym} error: {e}")
                results.append({"symbol": sym, "success": False, "error": str(e)})

    # Sort results back to original order
    results.sort(key=lambda x: symbols.index(x["symbol"]))

    # Check if we have at least 2 successful analyses
    successful = [r for r in results if r["success"]]
    if len(successful) < 2:
        msg = f"❌ {'Nicht genug erfolgreiche Analysen für Vergleich.' if lang == 'de' else 'Not enough successful analyses for comparison.'}"
        send_telegram_message(chat_id, msg)
        return 1

    # Generate comparison
    print("\nGenerating comparative analysis...")
    comparison = generate_comparison(results, lang)

    # Format and send
    message = format_comparison_result(results, comparison, lang)

    success = send_telegram_message(chat_id, message)

    if success:
        print(f"\nComparison sent to chat {chat_id}")
        return 0
    else:
        print("\nFailed to send comparison")
        return 1


if __name__ == "__main__":
    sys.exit(main())

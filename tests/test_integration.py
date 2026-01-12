#!/usr/bin/env python3
"""
Integration tests for Trading Crew.

These tests require:
- GOOGLE_API_KEY environment variable
- Internet connection

Run with: python3 tests/test_integration.py
"""

import os
import sys
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

# Load .env file
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")


def test_gemini_api_connection():
    """Test basic Gemini API connection."""
    from gemini_utils import call_gemini_flash

    print("Testing Gemini API connection...")
    response = call_gemini_flash(
        "Reply with exactly: CONNECTION_OK",
        use_search=False,
        max_retries=2
    )

    assert response and len(response) > 0, "Empty response from API"
    assert "CONNECTION" in response.upper() or "OK" in response.upper(), \
        f"Unexpected response: {response[:100]}"

    print("✅ Gemini API connection: OK")
    return True


def test_gemini_search_grounding():
    """Test Gemini with Google Search."""
    from gemini_utils import call_gemini_flash

    print("Testing Gemini + Google Search...")
    response = call_gemini_flash(
        "What is today's date? Reply in format: YYYY-MM-DD",
        use_search=True,
        max_retries=2
    )

    assert response and len(response) > 0, "Empty response from API"
    # Should contain a date-like pattern
    assert any(c.isdigit() for c in response), f"No date in response: {response[:100]}"

    print("✅ Gemini + Search grounding: OK")
    return True


def test_stock_price_fetch():
    """Test fetching stock price via Gemini Search."""
    from gemini_utils import call_gemini_flash, extract_price_from_text

    print("Testing stock price fetch (AAPL)...")
    response = call_gemini_flash(
        "What is the current stock price of Apple (AAPL)? "
        "Reply with just the price in USD format like: $260.50",
        use_search=True,
        max_retries=2
    )

    price = extract_price_from_text(response)
    assert price is not None, f"Could not extract price from: {response[:200]}"
    assert 100 < price < 500, f"Price {price} seems unrealistic for AAPL"

    print(f"✅ Stock price fetch: OK (AAPL = ${price:.2f})")
    return True


def test_technical_indicators():
    """Test fetching technical indicators."""
    from gemini_utils import call_gemini_flash

    print("Testing technical indicators (AAPL RSI)...")
    response = call_gemini_flash(
        "What is the current RSI (14-day) for Apple stock AAPL? "
        "Reply with just the number between 0 and 100.",
        use_search=True,
        max_retries=2
    )

    # Extract number from response
    import re
    numbers = re.findall(r'\d+\.?\d*', response)
    assert numbers, f"No RSI value found in: {response[:200]}"

    rsi = float(numbers[0])
    assert 0 <= rsi <= 100, f"RSI {rsi} out of valid range"

    print(f"✅ Technical indicators: OK (RSI = {rsi:.1f})")
    return True


def test_commodity_recognition():
    """Test that GOLD/SILVER are recognized as commodities, not stocks."""
    from gemini_utils import call_gemini_flash

    print("Testing commodity recognition (GOLD)...")
    response = call_gemini_flash(
        "What is GOLD in financial markets? Is it a commodity or a stock ticker? "
        "Reply: COMMODITY or STOCK",
        use_search=False,
        max_retries=2
    )

    assert "COMMODITY" in response.upper(), \
        f"GOLD not recognized as commodity: {response[:100]}"

    print("✅ Commodity recognition: OK")
    return True


def test_universal_agents_import():
    """Test that universal_agents can be imported without errors."""
    print("Testing universal_agents import...")

    try:
        from universal_agents import run_universal_analysis, UniversalDebateState
        print("✅ universal_agents import: OK")
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False


def run_all_integration_tests():
    """Run all integration tests."""
    print("\n" + "=" * 60)
    print("Running Integration Tests")
    print("=" * 60 + "\n")

    # Check for API key
    if not os.environ.get("GOOGLE_API_KEY"):
        print("⚠️  GOOGLE_API_KEY not found in environment")
        print("   Set it in .env file or export it")
        return False

    tests = [
        ("API Connection", test_gemini_api_connection),
        ("Search Grounding", test_gemini_search_grounding),
        ("Stock Price", test_stock_price_fetch),
        ("Technical Indicators", test_technical_indicators),
        ("Commodity Recognition", test_commodity_recognition),
        ("Module Import", test_universal_agents_import),
    ]

    results = []
    for name, test_func in tests:
        print(f"\n--- {name} ---")
        try:
            success = test_func()
            results.append((name, success, None))
        except Exception as e:
            print(f"❌ {name}: FAILED - {e}")
            results.append((name, False, str(e)))

    # Summary
    print("\n" + "=" * 60)
    print("Integration Test Results")
    print("=" * 60)

    passed = sum(1 for _, success, _ in results if success)
    failed = len(results) - passed

    for name, success, error in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"  {status}: {name}")
        if error:
            print(f"         Error: {error[:50]}...")

    print(f"\nTotal: {passed}/{len(results)} passed")
    print("=" * 60 + "\n")

    return failed == 0


if __name__ == "__main__":
    success = run_all_integration_tests()
    sys.exit(0 if success else 1)

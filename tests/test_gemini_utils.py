#!/usr/bin/env python3
"""
Unit tests for gemini_utils.py

Run with: python3 -m pytest tests/test_gemini_utils.py -v
Or simply: python3 tests/test_gemini_utils.py
"""

import sys
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from gemini_utils import (
    strip_markdown_code_block,
    parse_json_response,
    extract_price_from_text,
    get_language_instruction,
)


def test_strip_markdown_code_block():
    """Test markdown code block removal."""
    # Test 1: JSON mit Markdown
    result = strip_markdown_code_block('```json\n{"test": 1}\n```')
    assert result == '{"test": 1}', f"Expected JSON, got: {result}"

    # Test 2: Ohne Markdown
    result = strip_markdown_code_block('{"test": 1}')
    assert result == '{"test": 1}', f"Expected unchanged, got: {result}"

    # Test 3: Leerer String
    result = strip_markdown_code_block('')
    assert result == '', f"Expected empty, got: {result}"

    # Test 4: Nur Backticks ohne json
    result = strip_markdown_code_block('```\n{"data": true}\n```')
    assert '{"data": true}' in result or result == '{"data": true}', f"Got: {result}"

    print("✅ strip_markdown_code_block: ALL TESTS PASSED")


def test_parse_json_response():
    """Test JSON parsing from LLM responses."""
    # Test 1: Valides JSON
    result = parse_json_response('{"signal": "LONG"}')
    assert result == {"signal": "LONG"}, f"Expected dict, got: {result}"

    # Test 2: JSON mit Markdown
    result = parse_json_response('```json\n{"signal": "SHORT"}\n```')
    assert result == {"signal": "SHORT"}, f"Expected dict, got: {result}"

    # Test 3: Invalides JSON
    result = parse_json_response('not json at all')
    assert result is None, f"Expected None, got: {result}"

    # Test 4: None Input
    result = parse_json_response(None)
    assert result is None, f"Expected None, got: {result}"

    # Test 5: Empty string
    result = parse_json_response('')
    assert result is None, f"Expected None, got: {result}"

    print("✅ parse_json_response: ALL TESTS PASSED")


def test_extract_price_from_text():
    """Test price extraction from text."""
    # Test 1: USD Format
    result = extract_price_from_text('Price: $260.25')
    assert result == 260.25, f"Expected 260.25, got: {result}"

    # Test 2: Mit Komma
    result = extract_price_from_text('Market cap: $1,234.56')
    assert result == 1234.56, f"Expected 1234.56, got: {result}"

    # Test 3: Ohne Symbol
    result = extract_price_from_text('Current: 100.50')
    assert result == 100.50, f"Expected 100.50, got: {result}"

    # Test 4: Kein Preis
    result = extract_price_from_text('No price here')
    assert result is None, f"Expected None, got: {result}"

    # Test 5: None Input
    result = extract_price_from_text(None)
    assert result is None, f"Expected None, got: {result}"

    # Test 6: Integer price
    result = extract_price_from_text('$2650')
    assert result == 2650.0, f"Expected 2650.0, got: {result}"

    print("✅ extract_price_from_text: ALL TESTS PASSED")


def test_get_language_instruction():
    """Test language instruction generation."""
    # Test 1: German
    result = get_language_instruction('de')
    assert result == 'Respond entirely in German.', f"Got: {result}"

    # Test 2: English
    result = get_language_instruction('en')
    assert result == 'Respond entirely in English.', f"Got: {result}"

    # Test 3: Custom prefix
    result = get_language_instruction('de', prefix='Write')
    assert result == 'Write entirely in German.', f"Got: {result}"

    # Test 4: Unknown language defaults to English
    result = get_language_instruction('fr')
    assert result == 'Respond entirely in English.', f"Got: {result}"

    print("✅ get_language_instruction: ALL TESTS PASSED")


def run_all_tests():
    """Run all unit tests."""
    print("\n" + "=" * 50)
    print("Running gemini_utils.py Unit Tests")
    print("=" * 50 + "\n")

    tests = [
        test_strip_markdown_code_block,
        test_parse_json_response,
        test_extract_price_from_text,
        test_get_language_instruction,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"❌ {test.__name__}: FAILED - {e}")
            failed += 1
        except Exception as e:
            print(f"❌ {test.__name__}: ERROR - {e}")
            failed += 1

    print("\n" + "=" * 50)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 50 + "\n")

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

#!/usr/bin/env python3
"""
Shared utilities for Gemini API calls and response parsing.

This module consolidates common patterns used across commodity_agents.py,
universal_agents.py, and telegram_worker.py to reduce code duplication.
"""

import json
import os
import re
import time
from typing import Optional

from google import genai
from google.genai import types


def get_gemini_client() -> genai.Client:
    """Get configured Gemini client."""
    return genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))


def strip_markdown_code_block(text: str) -> str:
    """
    Remove markdown code block delimiters from text.

    Handles formats like:
    - ```json ... ```
    - ``` ... ```

    Args:
        text: Raw text that may contain markdown code blocks

    Returns:
        Cleaned text with code block delimiters removed
    """
    text = text.strip()

    if text.startswith("```"):
        # Split on ``` and take the content part
        parts = text.split("```")
        if len(parts) >= 2:
            content = parts[1]
            # Remove language identifier (e.g., "json")
            if content.startswith("json"):
                content = content[4:]
            text = content.strip()

    if text.endswith("```"):
        text = text[:-3].strip()

    return text


def parse_json_response(response_text: str) -> Optional[dict]:
    """
    Parse JSON from an LLM response, handling markdown code blocks and surrounding text.

    Args:
        response_text: Raw LLM response that may contain JSON

    Returns:
        Parsed dict or None if parsing fails
    """
    if not response_text:
        return None

    text = strip_markdown_code_block(response_text)

    # Try direct parsing first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find JSON object in text (handles text before/after JSON)
    # Look for first { and last }
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass

    # Try to extract from ```json ... ``` block if present
    if '```json' in response_text:
        try:
            json_block = response_text.split('```json')[1].split('```')[0]
            return json.loads(json_block.strip())
        except (IndexError, json.JSONDecodeError):
            pass

    # Try to extract from ``` ... ``` block
    if '```' in response_text:
        parts = response_text.split('```')
        for part in parts[1::2]:  # Every second part (inside ```)
            part = part.strip()
            if part.startswith('json'):
                part = part[4:].strip()
            if part.startswith('{'):
                try:
                    return json.loads(part)
                except json.JSONDecodeError:
                    continue

    return None


def extract_price_from_text(text: str) -> Optional[float]:
    """
    Extract a price value from text using regex.

    Handles formats like: $100.50, 100.50, $1,234.56

    Args:
        text: Text containing a price

    Returns:
        Extracted price as float or None if not found
    """
    if not text:
        return None

    match = re.search(r'\$?([\d,]+\.?\d*)', text)
    if match:
        return float(match.group(1).replace(",", ""))
    return None


def call_gemini(
    prompt: str,
    model: str = "gemini-3-flash-preview",
    use_search: bool = False,
    max_retries: int = 3,
    retry_delay: int = 5,
) -> str:
    """
    Call Gemini API with optional Google Search grounding and retry logic.

    This is the unified function for all Gemini API calls, replacing:
    - call_gemini_with_search()
    - call_gemini_deep_think()
    - call_gemini_pro_with_search()

    Args:
        prompt: The prompt to send to Gemini
        model: Gemini model name (default: gemini-3-flash-preview)
        use_search: Whether to enable Google Search grounding
        max_retries: Maximum number of retry attempts
        retry_delay: Base delay between retries (uses exponential backoff)

    Returns:
        Response text or empty string if all retries fail
    """
    client = get_gemini_client()

    config = None
    if use_search:
        config = types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())]
        )

    response = None
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=config
            )
            if response and response.text:
                return response.text
        except Exception as e:
            error_str = str(e)
            # Handle rate limiting with exponential backoff
            if "429" in error_str and attempt < max_retries - 1:
                time.sleep(retry_delay * (attempt + 1))
                continue
            # Re-raise non-rate-limit errors on last attempt
            if attempt == max_retries - 1:
                raise

        # Wait before retry on empty response
        if attempt < max_retries - 1:
            time.sleep(2)

    return (response.text if response and response.text else "") or ""


def call_gemini_flash(prompt: str, use_search: bool = True, max_retries: int = 3) -> str:
    """Call Gemini Flash with optional Google Search grounding."""
    return call_gemini(
        prompt=prompt,
        model="gemini-3-flash-preview",
        use_search=use_search,
        max_retries=max_retries,
    )


def call_gemini_pro(prompt: str, use_search: bool = False, max_retries: int = 3) -> str:
    """Call Gemini Pro for deep thinking tasks."""
    return call_gemini(
        prompt=prompt,
        model="gemini-3-pro-preview",
        use_search=use_search,
        max_retries=max_retries,
    )


def get_language_instruction(lang: str, prefix: str = "Respond") -> str:
    """
    Generate language instruction for prompts.

    Args:
        lang: Language code ("en" or "de")
        prefix: Verb prefix (e.g., "Respond", "Write")

    Returns:
        Language instruction string
    """
    if lang == "de":
        return f"{prefix} entirely in German."
    return f"{prefix} entirely in English."

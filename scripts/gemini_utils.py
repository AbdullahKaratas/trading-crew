#!/usr/bin/env python3
"""
Shared utilities for Gemini API calls and response parsing.

This module consolidates common patterns used across commodity_agents.py,
universal_agents.py, and telegram_worker.py to reduce code duplication.
"""

import io
import json
import os
import re
import time
from typing import Optional, List, Union

from google import genai
from google.genai import types
from pydantic import BaseModel, Field


# =============================================================================
# PYDANTIC SCHEMAS FOR STRUCTURED OUTPUT
# =============================================================================

class SupportResistanceZone(BaseModel):
    """A price zone with level and description."""
    level_usd: float = Field(description="Price level in USD")
    description: str = Field(description="Reason for this zone")


class KnockoutStrategy(BaseModel):
    """Knockout certificate strategy parameters."""
    ko_level_usd: float = Field(description="Knockout level in USD")
    distance_pct: float = Field(description="Distance from current price in percent")
    risk: str = Field(description="Risk level: low, medium, or high")


class Strategies(BaseModel):
    """Three risk-based knockout strategies."""
    conservative: KnockoutStrategy = Field(description="Conservative strategy with 15-25% distance")
    moderate: KnockoutStrategy = Field(description="Moderate strategy with 10-15% distance")
    aggressive: KnockoutStrategy = Field(description="Aggressive strategy with 5-10% distance")


class Timeframes(BaseModel):
    """Trading signals for different time horizons."""
    short_term: str = Field(description="Signal for days to weeks: LONG, SHORT, or HOLD")
    medium_term: str = Field(description="Signal for weeks to months: LONG, SHORT, or HOLD")
    long_term: str = Field(description="Signal for months to years: LONG, SHORT, or HOLD")


class TradeDecisionSchema(BaseModel):
    """Complete trade decision output schema."""
    signal: str = Field(description="Main signal: LONG, SHORT, HOLD, or IGNORE")
    confidence: float = Field(description="Confidence level from 0.0 to 1.0")
    unable_to_assess: bool = Field(default=False, description="True if assessment not possible")
    price_usd: float = Field(description="Current price in USD")
    price_eur: float = Field(description="Current price in EUR")
    strategies: Strategies = Field(description="Three knockout strategies")
    support_zones: List[SupportResistanceZone] = Field(description="Key support price zones")
    resistance_zones: List[SupportResistanceZone] = Field(description="Key resistance price zones")
    detailed_analysis: str = Field(description="300-500 word analysis with reasoning")
    timeframes: Timeframes = Field(description="Signals for different time horizons")


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

    def _try_parse(text: str) -> Optional[dict]:
        """Parse JSON and ensure result is a dict."""
        try:
            result = json.loads(text)
            return result if isinstance(result, dict) else None
        except json.JSONDecodeError:
            return None

    text = strip_markdown_code_block(response_text)

    # Try direct parsing first
    result = _try_parse(text)
    if result:
        return result

    # Try to find JSON object in text (handles text before/after JSON)
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1 and end > start:
        result = _try_parse(text[start:end + 1])
        if result:
            return result

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

    return ""


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


def call_gemini_vision(
    prompt: str,
    image: Union[io.BytesIO, bytes],
    model: str = "gemini-3-flash-preview",
    max_retries: int = 3,
    retry_delay: int = 5,
) -> str:
    """
    Call Gemini Vision API with an image for analysis.

    Args:
        prompt: Text prompt describing what to analyze
        image: Image data as BytesIO or bytes (PNG format)
        model: Gemini model name (default: gemini-3-flash-preview)
        max_retries: Maximum number of retry attempts
        retry_delay: Base delay between retries

    Returns:
        Response text or empty string if all retries fail
    """
    client = get_gemini_client()

    # Convert BytesIO to bytes if needed
    if isinstance(image, io.BytesIO):
        image.seek(0)
        img_data = image.read()
    else:
        img_data = image

    # Create image part for Gemini
    image_part = types.Part.from_bytes(data=img_data, mime_type='image/png')
    contents = [prompt, image_part]

    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=model,
                contents=contents,
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
                print(f"  [Vision] Error after {max_retries} attempts: {error_str[:100]}")
                raise

        # Wait before retry on empty response
        if attempt < max_retries - 1:
            time.sleep(2)

    return ""


def call_gemini_json(
    prompt: str,
    model: str = "gemini-3-pro-preview",
    use_search: bool = False,
    max_retries: int = 3,
    schema: Optional[type[BaseModel]] = None,
) -> Optional[dict]:
    """
    Call Gemini with structured JSON output using Pydantic schema.

    Uses Gemini's native structured output feature (response_mime_type + response_schema)
    to guarantee valid JSON that matches the schema. Retries only for API errors.

    Args:
        prompt: The prompt to send
        model: Gemini model to use
        use_search: Whether to enable Google Search grounding
        max_retries: Max attempts for API errors (network, rate limit)
        schema: Pydantic model class for structured output (e.g., TradeDecisionSchema)

    Returns:
        Parsed dict matching the schema, or None if all retries fail
    """
    client = get_gemini_client()

    # Build config with structured output
    config_dict = {}

    if schema:
        # Use Gemini's native structured output
        config_dict["response_mime_type"] = "application/json"
        config_dict["response_schema"] = schema

    if use_search:
        config_dict["tools"] = [types.Tool(google_search=types.GoogleSearch())]

    config = types.GenerateContentConfig(**config_dict) if config_dict else None

    last_error = None
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=config
            )

            if response and response.text:
                # With structured output, response.text is guaranteed valid JSON
                if schema:
                    try:
                        return json.loads(response.text)
                    except json.JSONDecodeError as e:
                        print(f"  Unexpected JSON error (attempt {attempt + 1}): {e}")
                        last_error = e
                else:
                    # Fallback: parse without schema guarantee
                    result = parse_json_response(response.text)
                    if result:
                        return result
                    print(f"  JSON parse failed (attempt {attempt + 1}/{max_retries})")

        except Exception as e:
            last_error = e
            error_str = str(e)

            # Handle rate limiting with exponential backoff
            if "429" in error_str:
                wait_time = 5 * (attempt + 1)
                print(f"  Rate limited, waiting {wait_time}s (attempt {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
                continue

            # Log other errors
            print(f"  API error (attempt {attempt + 1}/{max_retries}): {error_str[:100]}")

        # Wait before retry
        if attempt < max_retries - 1:
            time.sleep(2)

    print(f"  All {max_retries} attempts failed. Last error: {last_error}")
    return None


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

import os
import requests
import pandas as pd
import json
from datetime import datetime, timedelta
from io import StringIO
from threading import Lock
from dotenv import load_dotenv

# Load .env file (override system env vars)
load_dotenv(override=True)

API_BASE_URL = "https://www.alphavantage.co/query"


class AlphaVantageKeyRotator:
    """
    Rotates through multiple Alpha Vantage API keys.
    Tracks rate-limited keys and skips them temporarily.
    """
    _instance = None
    _lock = Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        # Load keys from environment
        keys_str = os.getenv("ALPHA_VANTAGE_API_KEYS", "")
        if keys_str:
            self.keys = [k.strip() for k in keys_str.split(",") if k.strip()]
        else:
            # Fallback to single key
            single_key = os.getenv("ALPHA_VANTAGE_API_KEY", "")
            self.keys = [single_key] if single_key else []

        if not self.keys:
            raise ValueError("No Alpha Vantage API keys configured. Set ALPHA_VANTAGE_API_KEYS or ALPHA_VANTAGE_API_KEY.")

        self.current_index = 0
        self.rate_limited_until = {}  # key -> datetime when it can be used again
        self.request_count = {k: 0 for k in self.keys}
        print(f"[AlphaVantage] Loaded {len(self.keys)} API keys for rotation")

    def get_key(self) -> str:
        """Get the next available API key, skipping rate-limited ones."""
        now = datetime.now()
        attempts = 0

        while attempts < len(self.keys):
            key = self.keys[self.current_index]

            # Check if this key is rate limited
            if key in self.rate_limited_until:
                if now < self.rate_limited_until[key]:
                    # Still rate limited, try next key
                    self.current_index = (self.current_index + 1) % len(self.keys)
                    attempts += 1
                    continue
                else:
                    # Rate limit expired, remove from blocked list
                    del self.rate_limited_until[key]

            # This key is available
            self.request_count[key] += 1
            # Rotate for next call
            self.current_index = (self.current_index + 1) % len(self.keys)
            return key

        # All keys are rate limited
        raise AlphaVantageRateLimitError("All Alpha Vantage API keys are rate limited. Try again later.")

    def mark_rate_limited(self, key: str, block_minutes: int = 60):
        """Mark a key as rate limited for a period of time."""
        self.rate_limited_until[key] = datetime.now() + timedelta(minutes=block_minutes)
        active_keys = len(self.keys) - len(self.rate_limited_until)
        print(f"[AlphaVantage] Key ...{key[-4:]} rate limited. {active_keys}/{len(self.keys)} keys remaining.")

    def get_stats(self) -> dict:
        """Get usage statistics."""
        return {
            "total_keys": len(self.keys),
            "rate_limited": len(self.rate_limited_until),
            "requests_per_key": self.request_count.copy(),
        }


# Global key rotator instance
_key_rotator = None


def get_api_key() -> str:
    """Get an API key using the key rotator."""
    global _key_rotator
    if _key_rotator is None:
        _key_rotator = AlphaVantageKeyRotator()
    return _key_rotator.get_key()


def mark_key_rate_limited(key: str):
    """Mark a key as rate limited."""
    global _key_rotator
    if _key_rotator is not None:
        _key_rotator.mark_rate_limited(key)

def format_datetime_for_api(date_input) -> str:
    """Convert various date formats to YYYYMMDDTHHMM format required by Alpha Vantage API."""
    if isinstance(date_input, str):
        # If already in correct format, return as-is
        if len(date_input) == 13 and 'T' in date_input:
            return date_input
        # Try to parse common date formats
        try:
            dt = datetime.strptime(date_input, "%Y-%m-%d")
            return dt.strftime("%Y%m%dT0000")
        except ValueError:
            try:
                dt = datetime.strptime(date_input, "%Y-%m-%d %H:%M")
                return dt.strftime("%Y%m%dT%H%M")
            except ValueError:
                raise ValueError(f"Unsupported date format: {date_input}")
    elif isinstance(date_input, datetime):
        return date_input.strftime("%Y%m%dT%H%M")
    else:
        raise ValueError(f"Date must be string or datetime object, got {type(date_input)}")

class AlphaVantageRateLimitError(Exception):
    """Exception raised when Alpha Vantage API rate limit is exceeded."""
    pass

def _make_api_request(function_name: str, params: dict) -> dict | str:
    """Helper function to make API requests and handle responses.

    Uses key rotation - automatically tries next key if rate limited.

    Raises:
        AlphaVantageRateLimitError: When ALL API keys are rate limited
    """
    # Get a key from the rotator
    api_key = get_api_key()

    # Create a copy of params to avoid modifying the original
    api_params = params.copy()
    api_params.update({
        "function": function_name,
        "apikey": api_key,
        "source": "trading_agents",
    })

    # Handle entitlement parameter if present in params or global variable
    current_entitlement = globals().get('_current_entitlement')
    entitlement = api_params.get("entitlement") or current_entitlement

    if entitlement:
        api_params["entitlement"] = entitlement
    elif "entitlement" in api_params:
        # Remove entitlement if it's None or empty
        api_params.pop("entitlement", None)

    response = requests.get(API_BASE_URL, params=api_params)
    response.raise_for_status()

    response_text = response.text

    # Check if response is JSON (error responses are typically JSON)
    try:
        response_json = json.loads(response_text)
        # Check for rate limit error
        if "Information" in response_json:
            info_message = response_json["Information"]
            if "rate limit" in info_message.lower() or "api key" in info_message.lower():
                # Mark this key as rate limited
                mark_key_rate_limited(api_key)
                raise AlphaVantageRateLimitError(f"Alpha Vantage rate limit exceeded: {info_message}")
    except json.JSONDecodeError:
        # Response is not JSON (likely CSV data), which is normal
        pass

    return response_text



def _filter_csv_by_date_range(csv_data: str, start_date: str, end_date: str) -> str:
    """
    Filter CSV data to include only rows within the specified date range.

    Args:
        csv_data: CSV string from Alpha Vantage API
        start_date: Start date in yyyy-mm-dd format
        end_date: End date in yyyy-mm-dd format

    Returns:
        Filtered CSV string
    """
    if not csv_data or csv_data.strip() == "":
        return csv_data

    try:
        # Parse CSV data
        df = pd.read_csv(StringIO(csv_data))

        # Assume the first column is the date column (timestamp)
        date_col = df.columns[0]
        df[date_col] = pd.to_datetime(df[date_col])

        # Filter by date range
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)

        filtered_df = df[(df[date_col] >= start_dt) & (df[date_col] <= end_dt)]

        # Convert back to CSV string
        return filtered_df.to_csv(index=False)

    except Exception as e:
        # If filtering fails, return original data with a warning
        print(f"Warning: Failed to filter CSV data by date range: {e}")
        return csv_data

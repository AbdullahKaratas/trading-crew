"""
News and data fetching using Anthropic Claude with Web Search.
Used as fallback when Alpha Vantage rate limit is exceeded.
"""
import anthropic
from .config import get_config


def get_stock_news_openai(query, start_date, end_date):
    """Get stock news using Claude with web search."""
    client = anthropic.Anthropic()  # Uses ANTHROPIC_API_KEY from environment

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",  # Fast and cheap for news lookup
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": f"Search for recent news and developments about {query} from {start_date} to {end_date}. Focus on earnings, analyst ratings, major announcements, and market-moving events. Provide a summary of the most important news.",
            }
        ],
        tools=[{
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": 3
        }]
    )

    # Extract text content from response
    result_text = ""
    for block in response.content:
        if hasattr(block, 'text'):
            result_text += block.text + "\n"

    return result_text.strip() if result_text else f"No news found for {query}"


def get_global_news_openai(curr_date, look_back_days=7, limit=5):
    """Get global market news using Claude with web search."""
    client = anthropic.Anthropic()

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": f"Search for the most important global and macroeconomic news from the past {look_back_days} days (before {curr_date}) that would be relevant for stock trading. Focus on: Fed/central bank decisions, economic indicators, geopolitical events, and market-moving developments. Limit to {limit} key items.",
            }
        ],
        tools=[{
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": 3
        }]
    )

    result_text = ""
    for block in response.content:
        if hasattr(block, 'text'):
            result_text += block.text + "\n"

    return result_text.strip() if result_text else "No global news found"


def get_fundamentals_openai(ticker, curr_date):
    """Get fundamental analysis using Claude with web search."""
    client = anthropic.Anthropic()

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": f"Search for the current fundamental metrics for stock ticker {ticker} as of {curr_date}. Include: P/E ratio, P/S ratio, market cap, revenue growth, earnings, cash flow, and any recent analyst ratings or price targets.",
            }
        ],
        tools=[{
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": 3
        }]
    )

    result_text = ""
    for block in response.content:
        if hasattr(block, 'text'):
            result_text += block.text + "\n"

    return result_text.strip() if result_text else f"No fundamental data found for {ticker}"

from typing import Annotated
from datetime import datetime
from dateutil.relativedelta import relativedelta
from .googlenews_utils import getNewsData


def get_google_news(
    ticker: Annotated[str, "Stock ticker to search news for"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    """
    Get Google News for a stock ticker.

    Signature matches alpha_vantage get_news for seamless fallback.
    """
    query = ticker.replace(" ", "+")

    news_results = getNewsData(query, start_date, end_date)

    news_str = ""

    for news in news_results:
        news_str += (
            f"### {news['title']} (source: {news['source']}) \n\n{news['snippet']}\n\n"
        )

    if len(news_results) == 0:
        return ""

    return f"## {ticker} Google News, from {start_date} to {end_date}:\n\n{news_str}"
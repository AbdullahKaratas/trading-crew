"""Reddit scanner for stock mentions and sentiment."""

import os
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

import structlog

logger = structlog.get_logger()

# Common stock ticker pattern (1-5 uppercase letters)
TICKER_PATTERN = re.compile(r'\b([A-Z]{1,5})\b')

# Words that look like tickers but aren't
TICKER_BLACKLIST = {
    'I', 'A', 'BE', 'BY', 'DO', 'GO', 'HE', 'IF', 'IN', 'IS', 'IT', 'ME', 'MY',
    'NO', 'OF', 'OK', 'ON', 'OR', 'SO', 'TO', 'UP', 'US', 'WE', 'AM', 'AN', 'AS',
    'AT', 'CEO', 'CFO', 'CTO', 'DD', 'EPS', 'ETF', 'FDA', 'FUD', 'GDP', 'IMO',
    'IPO', 'ITM', 'IV', 'LOL', 'MACD', 'NYSE', 'OTM', 'PE', 'PM', 'PT', 'RSI',
    'SEC', 'USA', 'USD', 'WSB', 'YOLO', 'FOR', 'THE', 'AND', 'BUT', 'NOT', 'YOU',
    'ALL', 'CAN', 'HER', 'WAS', 'ONE', 'OUR', 'OUT', 'ARE', 'HAS', 'HIS', 'HOW',
    'ITS', 'MAY', 'NEW', 'NOW', 'OLD', 'SEE', 'WAY', 'WHO', 'BOY', 'DID', 'GET',
    'HIM', 'LET', 'PUT', 'SAY', 'SHE', 'TOO', 'USE', 'OMG', 'WTF', 'BTW', 'IMO',
    'EDIT', 'TLDR', 'AMA', 'TIL', 'PSA', 'FOMO', 'HODL', 'ATH', 'ATL', 'ETA',
    'JUST', 'LIKE', 'THIS', 'THAT', 'WITH', 'FROM', 'HAVE', 'BEEN', 'WILL',
    'WHAT', 'WHEN', 'YOUR', 'THAN', 'THEN', 'THEM', 'THEY', 'SOME', 'INTO',
    'ONLY', 'OVER', 'SUCH', 'TAKE', 'COME', 'MADE', 'FIND', 'LONG', 'DOWN',
    'CALL', 'VERY', 'AFTER', 'MOST', 'ALSO', 'WEEK', 'TIME', 'VERY', 'WHEN',
    'COME', 'THESE', 'KNOW', 'MAKE', 'BACK', 'YEAR', 'WELL', 'EVEN', 'GOOD',
    'ANY', 'BEST', 'FYI', 'IDK', 'NFT', 'AI', 'UK', 'EU', 'TX', 'CA', 'NY',
}

# Subreddits to scan
STOCK_SUBREDDITS = [
    'pennystocks',
    'wallstreetbets',
    'stocks',
    'investing',
    'smallstreetbets',
    'RobinHoodPennyStocks',
    'Shortsqueeze',
    'options',
]


@dataclass
class TickerMention:
    """A stock ticker mention from Reddit."""
    ticker: str
    title: str
    subreddit: str
    score: int
    num_comments: int
    created_utc: datetime
    url: str
    sentiment_hint: str = "neutral"  # Based on keywords


@dataclass
class GemCandidate:
    """A potential gem stock with aggregated data."""
    ticker: str
    mention_count: int
    total_score: int
    total_comments: int
    subreddits: list[str]
    avg_sentiment: str
    momentum_score: float  # How much it's trending
    sample_posts: list[str]


class RedditScanner:
    """
    Scans Reddit for stock ticker mentions.

    Uses PRAW (Python Reddit API Wrapper) when credentials are available,
    falls back to public JSON API (limited) otherwise.
    """

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        user_agent: Optional[str] = None,
    ):
        self.client_id = client_id or os.getenv("REDDIT_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("REDDIT_CLIENT_SECRET")
        self.user_agent = user_agent or os.getenv("REDDIT_USER_AGENT", "trading-crew-scanner/1.0")

        self.reddit = None
        self._init_praw()

    def _init_praw(self) -> None:
        """Initialize PRAW if credentials are available."""
        if self.client_id and self.client_secret:
            try:
                import praw
                self.reddit = praw.Reddit(
                    client_id=self.client_id,
                    client_secret=self.client_secret,
                    user_agent=self.user_agent,
                )
                logger.info("reddit_praw_initialized")
            except ImportError:
                logger.warning("praw_not_installed", hint="pip install praw")
            except Exception as e:
                logger.error("praw_init_failed", error=str(e))
        else:
            logger.info("reddit_no_credentials", fallback="public_json_api")

    def _extract_tickers(self, text: str) -> list[str]:
        """Extract potential stock tickers from text."""
        # Find $TICKER format first (more reliable)
        dollar_tickers = re.findall(r'\$([A-Z]{1,5})\b', text.upper())

        # Then find standalone uppercase words
        raw_tickers = TICKER_PATTERN.findall(text.upper())

        # Filter out blacklisted words
        valid_tickers = [
            t for t in (dollar_tickers + raw_tickers)
            if t not in TICKER_BLACKLIST and len(t) >= 2
        ]

        return list(set(valid_tickers))

    def _analyze_sentiment(self, text: str) -> str:
        """Simple keyword-based sentiment analysis."""
        text_lower = text.lower()

        bullish_keywords = [
            'moon', 'rocket', '🚀', 'buy', 'long', 'calls', 'bullish',
            'undervalued', 'gem', 'hidden', 'squeeze', 'breakout', 'tendies',
            'gains', 'profit', 'up', 'green', 'pumping', 'mooning'
        ]

        bearish_keywords = [
            'sell', 'short', 'puts', 'bearish', 'overvalued', 'dump',
            'crash', 'red', 'loss', 'down', 'avoid', 'scam', 'fraud',
            'bag', 'bagholding', 'rip'
        ]

        bullish_count = sum(1 for kw in bullish_keywords if kw in text_lower)
        bearish_count = sum(1 for kw in bearish_keywords if kw in text_lower)

        if bullish_count > bearish_count + 1:
            return "bullish"
        elif bearish_count > bullish_count + 1:
            return "bearish"
        return "neutral"

    def scan_subreddit_praw(
        self,
        subreddit_name: str,
        limit: int = 100,
        time_filter: str = "day"
    ) -> list[TickerMention]:
        """Scan a subreddit using PRAW API."""
        if not self.reddit:
            return []

        mentions = []
        try:
            subreddit = self.reddit.subreddit(subreddit_name)

            # Get hot and new posts
            for post in subreddit.hot(limit=limit):
                tickers = self._extract_tickers(post.title + " " + (post.selftext or ""))
                for ticker in tickers:
                    mentions.append(TickerMention(
                        ticker=ticker,
                        title=post.title[:200],
                        subreddit=subreddit_name,
                        score=post.score,
                        num_comments=post.num_comments,
                        created_utc=datetime.fromtimestamp(post.created_utc),
                        url=f"https://reddit.com{post.permalink}",
                        sentiment_hint=self._analyze_sentiment(post.title),
                    ))

            logger.info("subreddit_scanned", subreddit=subreddit_name, mentions=len(mentions))

        except Exception as e:
            logger.error("subreddit_scan_failed", subreddit=subreddit_name, error=str(e))

        return mentions

    def scan_subreddit_json(
        self,
        subreddit_name: str,
        limit: int = 25
    ) -> list[TickerMention]:
        """Scan a subreddit using public JSON API (no auth needed, limited)."""
        import requests

        mentions = []
        try:
            url = f"https://www.reddit.com/r/{subreddit_name}/hot.json?limit={limit}"
            headers = {"User-Agent": self.user_agent}

            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()

            for post in data.get("data", {}).get("children", []):
                post_data = post.get("data", {})
                title = post_data.get("title", "")
                selftext = post_data.get("selftext", "")

                tickers = self._extract_tickers(title + " " + selftext)
                for ticker in tickers:
                    mentions.append(TickerMention(
                        ticker=ticker,
                        title=title[:200],
                        subreddit=subreddit_name,
                        score=post_data.get("score", 0),
                        num_comments=post_data.get("num_comments", 0),
                        created_utc=datetime.fromtimestamp(post_data.get("created_utc", 0)),
                        url=f"https://reddit.com{post_data.get('permalink', '')}",
                        sentiment_hint=self._analyze_sentiment(title),
                    ))

            logger.info("subreddit_scanned_json", subreddit=subreddit_name, mentions=len(mentions))

        except Exception as e:
            logger.error("subreddit_json_failed", subreddit=subreddit_name, error=str(e))

        return mentions

    def scan_all_subreddits(
        self,
        subreddits: Optional[list[str]] = None,
        limit_per_sub: int = 50
    ) -> list[TickerMention]:
        """Scan multiple subreddits for ticker mentions."""
        subreddits = subreddits or STOCK_SUBREDDITS
        all_mentions = []

        for sub in subreddits:
            if self.reddit:
                mentions = self.scan_subreddit_praw(sub, limit=limit_per_sub)
            else:
                mentions = self.scan_subreddit_json(sub, limit=min(limit_per_sub, 25))
            all_mentions.extend(mentions)

        return all_mentions

    def aggregate_mentions(
        self,
        mentions: list[TickerMention],
        min_mentions: int = 2
    ) -> list[GemCandidate]:
        """Aggregate mentions into gem candidates."""
        ticker_data: dict[str, dict] = {}

        for mention in mentions:
            ticker = mention.ticker
            if ticker not in ticker_data:
                ticker_data[ticker] = {
                    "mentions": [],
                    "subreddits": set(),
                    "total_score": 0,
                    "total_comments": 0,
                    "sentiments": [],
                    "sample_posts": [],
                }

            data = ticker_data[ticker]
            data["mentions"].append(mention)
            data["subreddits"].add(mention.subreddit)
            data["total_score"] += mention.score
            data["total_comments"] += mention.num_comments
            data["sentiments"].append(mention.sentiment_hint)

            if len(data["sample_posts"]) < 3:
                data["sample_posts"].append(mention.title)

        # Convert to GemCandidates
        candidates = []
        for ticker, data in ticker_data.items():
            mention_count = len(data["mentions"])
            if mention_count < min_mentions:
                continue

            # Calculate average sentiment
            sentiment_counts = Counter(data["sentiments"])
            if sentiment_counts["bullish"] > sentiment_counts["bearish"]:
                avg_sentiment = "bullish"
            elif sentiment_counts["bearish"] > sentiment_counts["bullish"]:
                avg_sentiment = "bearish"
            else:
                avg_sentiment = "neutral"

            # Calculate momentum score (weighted by recency and engagement)
            momentum = (
                mention_count * 10 +
                data["total_score"] * 0.1 +
                data["total_comments"] * 0.5 +
                len(data["subreddits"]) * 20
            )

            candidates.append(GemCandidate(
                ticker=ticker,
                mention_count=mention_count,
                total_score=data["total_score"],
                total_comments=data["total_comments"],
                subreddits=list(data["subreddits"]),
                avg_sentiment=avg_sentiment,
                momentum_score=momentum,
                sample_posts=data["sample_posts"],
            ))

        # Sort by momentum score
        candidates.sort(key=lambda x: x.momentum_score, reverse=True)

        return candidates

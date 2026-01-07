"""GEM Finder - Identifies high-potential penny stocks."""

import os
from dataclasses import dataclass
from typing import Optional

import requests
import structlog
import yfinance as yf

from .reddit_scanner import RedditScanner, GemCandidate, STOCK_SUBREDDITS

logger = structlog.get_logger()


@dataclass
class GemStock:
    """A validated gem stock with full analysis."""
    ticker: str
    name: str
    price: float
    market_cap: float
    volume: int
    avg_volume: int
    volume_spike: float  # Current volume / average volume
    mention_count: int
    momentum_score: float
    sentiment: str
    subreddits: list[str]
    sample_posts: list[str]
    sector: str
    is_penny_stock: bool
    finnhub_buzz: Optional[dict] = None


class GemFinder:
    """
    Finds hidden gem stocks by combining Reddit mentions with market data.

    Filters for:
    - Small/micro cap stocks (< $2B market cap)
    - Volume spikes (unusual activity)
    - Positive sentiment
    - Multiple mentions across subreddits
    """

    def __init__(
        self,
        max_market_cap: float = 2_000_000_000,  # $2B
        min_price: float = 0.10,  # Filter out sub-penny
        max_price: float = 50.00,  # Focus on smaller stocks
        min_volume_spike: float = 1.5,  # 50% above average
        finnhub_api_key: Optional[str] = None,
    ):
        self.max_market_cap = max_market_cap
        self.min_price = min_price
        self.max_price = max_price
        self.min_volume_spike = min_volume_spike
        self.finnhub_api_key = finnhub_api_key or os.getenv("FINNHUB_API_KEY")

        self.reddit_scanner = RedditScanner()

    def get_finnhub_buzz(self, ticker: str) -> Optional[dict]:
        """Get social media buzz from Finnhub."""
        if not self.finnhub_api_key:
            return None

        try:
            url = f"https://finnhub.io/api/v1/stock/social-sentiment"
            params = {
                "symbol": ticker,
                "from": "2024-01-01",
                "token": self.finnhub_api_key,
            }
            response = requests.get(url, params=params, timeout=10)
            if response.ok:
                return response.json()
        except Exception as e:
            logger.warning("finnhub_buzz_failed", ticker=ticker, error=str(e))

        return None

    def get_stock_info(self, ticker: str) -> Optional[dict]:
        """Get stock info from yfinance."""
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            hist = stock.history(period="1mo")

            if hist.empty or not info:
                return None

            # Calculate volume spike
            current_volume = hist["Volume"].iloc[-1] if not hist.empty else 0
            avg_volume = info.get("averageVolume", current_volume) or current_volume
            volume_spike = current_volume / avg_volume if avg_volume > 0 else 1.0

            return {
                "name": info.get("shortName", ticker),
                "price": info.get("regularMarketPrice") or info.get("previousClose", 0),
                "market_cap": info.get("marketCap", 0),
                "volume": int(current_volume),
                "avg_volume": int(avg_volume),
                "volume_spike": volume_spike,
                "sector": info.get("sector", "Unknown"),
            }
        except Exception as e:
            logger.warning("stock_info_failed", ticker=ticker, error=str(e))
            return None

    def scan_reddit(
        self,
        subreddits: Optional[list[str]] = None,
        limit_per_sub: int = 50
    ) -> list[GemCandidate]:
        """Scan Reddit for gem candidates."""
        mentions = self.reddit_scanner.scan_all_subreddits(
            subreddits=subreddits,
            limit_per_sub=limit_per_sub
        )
        return self.reddit_scanner.aggregate_mentions(mentions, min_mentions=2)

    def validate_candidate(self, candidate: GemCandidate) -> Optional[GemStock]:
        """Validate a gem candidate with market data."""
        stock_info = self.get_stock_info(candidate.ticker)

        if not stock_info:
            logger.debug("candidate_no_data", ticker=candidate.ticker)
            return None

        price = stock_info["price"]
        market_cap = stock_info["market_cap"]

        # Apply filters
        if price < self.min_price or price > self.max_price:
            logger.debug("candidate_price_filtered", ticker=candidate.ticker, price=price)
            return None

        if market_cap > self.max_market_cap:
            logger.debug("candidate_cap_filtered", ticker=candidate.ticker, cap=market_cap)
            return None

        # Get Finnhub buzz
        finnhub_buzz = self.get_finnhub_buzz(candidate.ticker)

        return GemStock(
            ticker=candidate.ticker,
            name=stock_info["name"],
            price=price,
            market_cap=market_cap,
            volume=stock_info["volume"],
            avg_volume=stock_info["avg_volume"],
            volume_spike=stock_info["volume_spike"],
            mention_count=candidate.mention_count,
            momentum_score=candidate.momentum_score,
            sentiment=candidate.avg_sentiment,
            subreddits=candidate.subreddits,
            sample_posts=candidate.sample_posts,
            sector=stock_info["sector"],
            is_penny_stock=price < 5.0,
            finnhub_buzz=finnhub_buzz,
        )

    def find_gems(
        self,
        subreddits: Optional[list[str]] = None,
        limit: int = 10,
        require_volume_spike: bool = False,
    ) -> list[GemStock]:
        """
        Find gem stocks from Reddit mentions.

        Args:
            subreddits: Specific subreddits to scan (default: all stock subs)
            limit: Maximum number of gems to return
            require_volume_spike: Only return stocks with volume spike

        Returns:
            List of validated GemStock objects
        """
        logger.info("gem_search_started", subreddits=subreddits or "all")

        # Scan Reddit
        candidates = self.scan_reddit(subreddits=subreddits)
        logger.info("candidates_found", count=len(candidates))

        # Validate each candidate
        gems = []
        for candidate in candidates:
            if len(gems) >= limit * 2:  # Get more than needed for filtering
                break

            gem = self.validate_candidate(candidate)
            if gem:
                if require_volume_spike and gem.volume_spike < self.min_volume_spike:
                    continue
                gems.append(gem)

        # Sort by momentum + volume spike
        gems.sort(key=lambda g: g.momentum_score * (1 + g.volume_spike), reverse=True)

        logger.info("gems_found", count=len(gems[:limit]))
        return gems[:limit]

    def format_gem_message(self, gem: GemStock, lang: str = "de") -> str:
        """Format a gem for Telegram message."""
        if lang == "en":
            sentiment_map = {"bullish": "🟢 Bullish", "bearish": "🔴 Bearish", "neutral": "🟡 Neutral"}
            labels = {
                "price": "Price",
                "market_cap": "Market Cap",
                "volume": "Volume",
                "volume_spike": "Volume Spike",
                "mentions": "Reddit Mentions",
                "sentiment": "Sentiment",
                "subreddits": "Found in",
                "sector": "Sector",
                "sample": "Sample Posts",
            }
        else:
            sentiment_map = {"bullish": "🟢 Bullish", "bearish": "🔴 Bearish", "neutral": "🟡 Neutral"}
            labels = {
                "price": "Kurs",
                "market_cap": "Marktkapital",
                "volume": "Volumen",
                "volume_spike": "Volumen-Spike",
                "mentions": "Reddit Erwähnungen",
                "sentiment": "Sentiment",
                "subreddits": "Gefunden in",
                "sector": "Sektor",
                "sample": "Beispiel-Posts",
            }

        # Format market cap
        cap = gem.market_cap
        if cap >= 1e9:
            cap_str = f"${cap/1e9:.1f}B"
        elif cap >= 1e6:
            cap_str = f"${cap/1e6:.0f}M"
        else:
            cap_str = f"${cap:,.0f}"

        penny_tag = " 💎" if gem.is_penny_stock else ""

        message = f"""
💎 *{gem.ticker}*{penny_tag}
_{gem.name}_

💵 *{labels['price']}:* ${gem.price:.2f}
📊 *{labels['market_cap']}:* {cap_str}
📈 *{labels['volume_spike']}:* {gem.volume_spike:.1f}x
🗣 *{labels['mentions']}:* {gem.mention_count}
{sentiment_map.get(gem.sentiment, "🟡 Neutral")}

*{labels['subreddits']}:* {', '.join(f'r/{s}' for s in gem.subreddits[:3])}
*{labels['sector']}:* {gem.sector}
"""

        if gem.sample_posts:
            message += f"\n*{labels['sample']}:*\n"
            for post in gem.sample_posts[:2]:
                message += f"• _{post[:80]}..._\n"

        message += f"\n📈 [Chart](https://www.tradingview.com/chart/?symbol={gem.ticker})"

        return message.strip()

    def format_gems_summary(self, gems: list[GemStock], lang: str = "de") -> str:
        """Format multiple gems as a summary message."""
        if not gems:
            if lang == "en":
                return "❌ No gems found matching criteria."
            return "❌ Keine Gems gefunden die den Kriterien entsprechen."

        if lang == "en":
            header = "🔥 *GEM SCANNER RESULTS*\n\n"
        else:
            header = "🔥 *GEM SCANNER ERGEBNISSE*\n\n"

        lines = [header]

        for i, gem in enumerate(gems[:5], 1):
            sentiment_emoji = {"bullish": "🟢", "bearish": "🔴", "neutral": "🟡"}.get(gem.sentiment, "🟡")
            penny = "💎" if gem.is_penny_stock else ""

            lines.append(
                f"{i}. *{gem.ticker}* {penny} - ${gem.price:.2f}\n"
                f"   {sentiment_emoji} {gem.mention_count} mentions | "
                f"Vol: {gem.volume_spike:.1f}x | "
                f"Cap: ${gem.market_cap/1e6:.0f}M\n"
            )

        if lang == "en":
            lines.append("\n_Use `/analyze TICKER` for deep analysis_")
        else:
            lines.append("\n_Nutze `/analyze TICKER` für Tiefenanalyse_")

        return "".join(lines)

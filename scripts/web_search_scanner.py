#!/usr/bin/env python3
"""
Web Search GEM Scanner - Finds trending penny stocks via Gemini + Google Search.

Replaces Reddit API with web search for finding trending small-cap stocks.
No API credentials required - uses Gemini's built-in Google Search.
"""

import re
from dataclasses import dataclass
from typing import Optional

import yfinance as yf

from gemini_utils import call_gemini_flash, parse_json_response


@dataclass
class GemStock:
    """A validated gem stock with market data."""
    ticker: str
    name: str
    description: str
    price: float
    market_cap: float
    volume: int
    avg_volume: int
    volume_ratio: float
    change_pct: float
    sector: str
    source: str  # Where it was found (e.g., "Reddit/WSB", "Analyst Pick")


class WebSearchScanner:
    """
    Finds gem stocks using web search instead of Reddit API.

    Uses Gemini + Google Search to find trending penny stocks,
    then validates with yfinance for real market data.
    """

    def __init__(
        self,
        max_market_cap: float = 2_000_000_000,  # $2B
        min_price: float = 0.10,
        max_price: float = 50.00,
    ):
        self.max_market_cap = max_market_cap
        self.min_price = min_price
        self.max_price = max_price

    def search_trending_stocks(self, category: str = "all") -> list[dict]:
        """
        Search for trending stocks using Gemini + Google Search.

        Args:
            category: "all", "wsb", "pennys", "squeeze", "ai", "biotech"

        Returns:
            List of dicts with ticker and description
        """
        # Build search prompt based on category
        if category == "wsb":
            search_focus = "WallStreetBets Reddit most mentioned stocks"
        elif category == "pennys":
            search_focus = "trending penny stocks under $5 Reddit"
        elif category == "squeeze":
            search_focus = "short squeeze stocks Reddit high short interest"
        elif category == "ai":
            search_focus = "AI artificial intelligence penny stocks trending"
        elif category == "biotech":
            search_focus = "biotech penny stocks clinical trials FDA"
        else:
            search_focus = "trending penny stocks Reddit WallStreetBets small cap"

        prompt = f"""Search for {search_focus} in January 2026.

Find 15-20 stock tickers that are currently trending or being discussed.
Focus on small-cap stocks under $2B market cap.

Return ONLY a JSON array (no markdown, no explanation):
[
    {{"ticker": "AAPL", "name": "Apple Inc", "description": "Why it's trending", "source": "Reddit/WSB"}},
    {{"ticker": "NVDA", "name": "NVIDIA", "description": "AI chip leader", "source": "Analyst Pick"}}
]

Include the source where you found each stock (Reddit, analyst report, news, etc.)."""

        response = call_gemini_flash(prompt, use_search=True, max_retries=2)

        if not response:
            return []

        # Parse JSON response
        # Try to find JSON array in response
        try:
            # Look for JSON array pattern
            match = re.search(r'\[[\s\S]*\]', response)
            if match:
                import json
                stocks = json.loads(match.group())
                if isinstance(stocks, list):
                    return stocks
        except Exception as e:
            print(f"  [WebSearch] JSON parse error: {e}")

        return []

    def validate_stock(self, ticker: str, description: str = "", source: str = "") -> Optional[GemStock]:
        """
        Validate a stock ticker with yfinance and apply filters.

        Returns GemStock if it passes filters, None otherwise.
        """
        try:
            stock = yf.Ticker(ticker)
            info = stock.info

            if not info:
                return None

            price = info.get('regularMarketPrice') or info.get('previousClose', 0)
            market_cap = info.get('marketCap', 0)
            volume = info.get('regularMarketVolume', 0)
            avg_volume = info.get('averageVolume', 1) or 1
            change_pct = info.get('regularMarketChangePercent', 0)
            name = info.get('shortName', ticker)
            sector = info.get('sector', 'Unknown')

            # Apply filters
            if not price or price < self.min_price or price > self.max_price:
                return None

            if not market_cap or market_cap > self.max_market_cap:
                return None

            volume_ratio = volume / avg_volume if avg_volume > 0 else 1.0

            return GemStock(
                ticker=ticker,
                name=name,
                description=description,
                price=price,
                market_cap=market_cap,
                volume=int(volume),
                avg_volume=int(avg_volume),
                volume_ratio=volume_ratio,
                change_pct=change_pct,
                sector=sector,
                source=source,
            )

        except Exception as e:
            print(f"  [Validate] {ticker} error: {str(e)[:50]}")
            return None

    def find_gems(
        self,
        category: str = "all",
        limit: int = 10,
    ) -> list[GemStock]:
        """
        Find gem stocks using web search + yfinance validation.

        Args:
            category: "all", "wsb", "pennys", "squeeze", "ai", "biotech"
            limit: Maximum gems to return

        Returns:
            List of validated GemStock objects
        """
        print(f"  [WebSearch] Searching for {category} gems...")

        # Search for trending stocks
        candidates = self.search_trending_stocks(category)
        print(f"  [WebSearch] Found {len(candidates)} candidates")

        # Validate each candidate
        gems = []
        for candidate in candidates:
            ticker = candidate.get('ticker', '').upper().strip()
            if not ticker or len(ticker) > 5:
                continue

            gem = self.validate_stock(
                ticker=ticker,
                description=candidate.get('description', ''),
                source=candidate.get('source', 'Web Search'),
            )

            if gem:
                gems.append(gem)
                print(f"  ✅ {ticker}: ${gem.price:.2f} | ${gem.market_cap/1e6:.0f}M")

            if len(gems) >= limit * 2:  # Get extra for sorting
                break

        # Sort by volume ratio (unusual activity)
        gems.sort(key=lambda g: g.volume_ratio, reverse=True)

        print(f"  [WebSearch] Validated {len(gems[:limit])} gems")
        return gems[:limit]

    def format_gem_message(self, gem: GemStock, lang: str = "de") -> str:
        """Format a single gem for Telegram."""
        # Format market cap
        if gem.market_cap >= 1e9:
            cap_str = f"${gem.market_cap/1e9:.1f}B"
        else:
            cap_str = f"${gem.market_cap/1e6:.0f}M"

        penny_tag = " 💎" if gem.price < 5 else ""
        change_emoji = "📈" if gem.change_pct >= 0 else "📉"

        return f"""
💎 *{gem.ticker}*{penny_tag}
_{gem.name}_

💵 ${gem.price:.2f} {change_emoji} {gem.change_pct:+.1f}%
📊 Cap: {cap_str} | Vol: {gem.volume_ratio:.1f}x
🏷 {gem.sector}
📝 _{gem.description[:100]}..._
🔗 [{gem.source}](https://tradingview.com/chart/?symbol={gem.ticker})
""".strip()

    def format_gems_summary(self, gems: list[GemStock], lang: str = "de") -> str:
        """Format multiple gems as a summary for Telegram."""
        if not gems:
            if lang == "en":
                return "🔍 *GEM SCANNER*\n\nNo gems found matching criteria.\n\nThe scanner searches for:\n• Small cap stocks (< $2B)\n• Trending mentions online\n• Price $0.10 - $50\n\nTry again later!"
            return "🔍 *GEM SCANNER*\n\nKeine Gems gefunden.\n\nDer Scanner sucht nach:\n• Small Cap Aktien (< $2B)\n• Trending Online-Erwähnungen\n• Preis $0.10 - $50\n\nVersuch es später nochmal!"

        if lang == "en":
            header = "🔥 *GEM SCANNER RESULTS*\n"
            header += "_Trending small-cap stocks via web search_\n\n"
        else:
            header = "🔥 *GEM SCANNER ERGEBNISSE*\n"
            header += "_Trending Small-Cap Aktien via Web Search_\n\n"

        lines = [header]

        for i, gem in enumerate(gems[:7], 1):
            # Format market cap
            if gem.market_cap >= 1e9:
                cap_str = f"${gem.market_cap/1e9:.1f}B"
            else:
                cap_str = f"${gem.market_cap/1e6:.0f}M"

            penny = "💎" if gem.price < 5 else "🔹"
            change_emoji = "📈" if gem.change_pct >= 0 else "📉"

            lines.append(
                f"{i}. {penny} *{gem.ticker}* - ${gem.price:.2f} {change_emoji}{gem.change_pct:+.1f}%\n"
                f"   {cap_str} | Vol: {gem.volume_ratio:.1f}x | {gem.sector}\n"
                f"   _{gem.description[:60]}..._\n\n"
            )

        if lang == "en":
            lines.append("_Use `/analyze TICKER` for deep analysis_")
        else:
            lines.append("_Nutze `/analyze TICKER` für Tiefenanalyse_")

        return "".join(lines)


# Convenience function for direct usage
def scan_for_gems(category: str = "all", limit: int = 7, lang: str = "de") -> str:
    """
    Scan for gems and return formatted Telegram message.

    Args:
        category: "all", "wsb", "pennys", "squeeze", "ai", "biotech"
        limit: Max gems to return
        lang: "de" or "en"

    Returns:
        Formatted message for Telegram
    """
    scanner = WebSearchScanner()
    gems = scanner.find_gems(category=category, limit=limit)
    return scanner.format_gems_summary(gems, lang=lang)


if __name__ == "__main__":
    # Test the scanner
    import sys

    category = sys.argv[1] if len(sys.argv) > 1 else "all"
    lang = sys.argv[2] if len(sys.argv) > 2 else "de"

    print(f"\n{'='*50}")
    print(f"GEM SCANNER TEST - Category: {category}")
    print(f"{'='*50}\n")

    result = scan_for_gems(category=category, limit=7, lang=lang)
    print(result)

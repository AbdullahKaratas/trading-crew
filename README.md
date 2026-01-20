# Trading Crew - AI-Powered Trading Analysis

An intelligent trading analysis system using **Multi-Agent AI Debates** powered by Google Gemini. Get actionable trading signals for stocks, commodities, ETFs, and crypto via Telegram.

## How It Works

The system uses a sophisticated multi-agent debate architecture:

```
┌─────────────────────────────────────────────────────────────┐
│                    DATA GATHERING                           │
│         Gemini Flash + Google Search (Real-time)            │
│    Price • Technicals • News • Fundamentals                 │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   CHART GENERATION                          │
│              4-Panel Technical Chart (PNG)                  │
│    Price+SMA • RSI • Volume • CMF/OBV                       │
└─────────────────────────────────────────────────────────────┘
                              │
            ┌─────────────────┴─────────────────┐
            │   Chart sent to ALL 7 AI Agents   │
            └─────────────────┬─────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  INVESTMENT DEBATE                          │
│  ┌─────────────┐    2 Rounds    ┌─────────────┐            │
│  │    BULL     │◄──────────────►│    BEAR     │            │
│  │  + Chart 📊 │                │  + Chart 📊 │            │
│  └─────────────┘                └─────────────┘            │
│                        │                                    │
│                        ▼                                    │
│              ┌─────────────────┐                           │
│              │ INVESTMENT JUDGE│  → LONG / SHORT / HOLD    │
│              │   + Chart 📊    │                           │
│              └─────────────────┘                           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     RISK DEBATE                             │
│  ┌───────┐      ┌─────────┐      ┌─────────┐              │
│  │ RISKY │      │ NEUTRAL │      │  SAFE   │              │
│  │  📊   │      │   📊    │      │   📊    │              │
│  └───────┘      └─────────┘      └─────────┘              │
│                        │                                    │
│                        ▼                                    │
│              ┌─────────────────┐                           │
│              │   RISK JUDGE    │  → Knockout Strategies    │
│              │   + Chart 📊    │  → Entry/Exit Levels      │
│              └─────────────────┘                           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    TELEGRAM BOT                             │
│         📊 Chart Image + 📝 Analysis Text                   │
└─────────────────────────────────────────────────────────────┘
```

## Features

- **Universal Asset Support** - Stocks, Commodities (Gold, Silver), ETFs, Crypto
- **Real-Time Data** - Powered by Gemini + Google Search (no API limits)
- **Chart Vision AI** - Gemini "sees" the chart and recognizes patterns (Head & Shoulders, Golden Cross, etc.)
- **Multi-Agent Debates** - Bull vs Bear + Risk assessment (all agents receive the chart)
- **Knockout Strategies** - Entry zones, stop-loss, take-profit levels
- **Telegram Bot** - Chart image + analysis text sent to your phone
- **Scheduled Analysis** - Daily watchlist analysis via GitHub Actions
- **Multi-Language** - English and German support

### Chart Vision

Every analysis generates a 4-panel technical chart that all AI agents can "see":

| Panel | Indicators | What AI Looks For |
|-------|------------|-------------------|
| **Price** | Candlesticks, SMA 50, SMA 200 | Golden/Death Cross, Trends, Patterns |
| **RSI** | RSI(14), Overbought/Oversold lines | Divergences, Extremes |
| **Volume** | Colored bars (green=bullish) | Confirmation, Climax |
| **Money Flow** | CMF(20), OBV | Accumulation/Distribution |

The chart is sent to Telegram alongside the analysis text.

## Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/AbdullahKaratas/trading-crew.git
cd trading-crew
pip install -r requirements.txt
```

### 2. Get API Keys

| Service | Required | Get it at |
|---------|----------|-----------|
| Google Gemini | Yes | [aistudio.google.com](https://aistudio.google.com/app/apikey) |
| Telegram Bot | Yes | [@BotFather](https://t.me/BotFather) on Telegram |

### 3. Configure Environment

```bash
cp .env.example .env
```

Edit `.env`:
```bash
GOOGLE_API_KEY=your_gemini_api_key
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHI...
TELEGRAM_CHAT_ID=your_chat_id
```

<details>
<summary>How to get Telegram Chat ID</summary>

1. Start your bot (search for it and click "Start")
2. Send any message to the bot
3. Open: `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
4. Find `"chat":{"id": YOUR_CHAT_ID}` in the JSON

</details>

### 4. Run the Bot

```bash
# Interactive mode (recommended)
cd scripts
python telegram_worker.py
```

## Telegram Commands

| Command | Description |
|---------|-------------|
| `/analyze AAPL` | Full analysis for Apple stock |
| `/analyze Apple` | Works with company names too! |
| `/analyze AAPL long` | Force LONG direction (knockout below price) |
| `/analyze AAPL short` | Force SHORT direction (knockout above price) |
| `/analyze GOLD` | Commodity analysis |
| `/analyze AAPL de` | Analysis in German |
| `/vs GOLD SILVER` | Compare 2-4 assets side-by-side |
| `/vs AAPL MSFT GOOGL` | Compare multiple stocks |
| `/help` | Show all commands |

### Example Output

```
LONG Signal: AAPL (Apple Inc.)
Confidence: 78%

Current Price: $260.25

Knockout Strategies:
├─ Conservative: $245.00 (5.9% buffer)
├─ Moderate: $250.00 (3.9% buffer)
└─ Aggressive: $255.00 (2.0% buffer)

Take Profit Zones:
├─ TP1: $270.00 (+3.7%)
├─ TP2: $280.00 (+7.6%)
└─ TP3: $290.00 (+11.4%)

Technical Summary:
RSI: 27.18 (Oversold)
MACD: Bearish but showing reversal signs
Trend: Below 50 SMA, above 200 SMA
```

## Scheduled Analysis

The system can run automatically via GitHub Actions:

1. **Configure GitHub Secrets** (Settings → Secrets → Actions):
   - `GOOGLE_API_KEY`
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`

2. **Edit Watchlist** (`config/watchlist.yaml`):
```yaml
watchlist:
  tech:
    - symbol: AAPL
      name: Apple
      day: monday
    - symbol: NVDA
      name: NVIDIA
      day: tuesday
  commodities:
    - symbol: GOLD
      name: Gold
      day: wednesday
```

3. **Enable Actions** - Runs Mon-Fri at 14:30 CET (pre-market)

## Project Structure

```
trading-crew/
├── scripts/
│   ├── gemini_utils.py       # Gemini API utilities (Flash, Pro, Vision)
│   ├── chart_vision.py       # 4-panel chart generator (Plotly)
│   ├── universal_agents.py   # Multi-agent debate system
│   ├── telegram_worker.py    # /analyze command handler
│   └── comparison_worker.py  # /vs command handler
├── tests/
│   ├── TEST_PROTOCOL.md      # Manual test checklist
│   ├── test_gemini_utils.py  # Unit tests
│   └── test_integration.py   # Integration tests
├── config/
│   ├── watchlist.yaml        # Scheduled analysis watchlist
│   └── settings.yaml         # Bot configuration
└── .github/workflows/
    └── trading_analysis.yml  # GitHub Actions schedule
```

## Testing

```bash
# Run unit tests
python tests/test_gemini_utils.py

# Run integration tests (requires API key)
python tests/test_integration.py
```

## Cost

| Service | Cost |
|---------|------|
| Gemini API | Free tier: 15 RPM, 1500 RPD |
| GitHub Actions | Free: 2000 min/month |
| Telegram | Free |
| **Total** | **$0** (within free tiers) |

For heavy usage, Gemini Pro has very competitive pricing (~$0.001/analysis).

## Disclaimer

```
IMPORTANT: This system is for educational and research purposes only.
It does NOT constitute financial advice.

• Past performance does not guarantee future results
• Trading involves significant risk of loss
• Only invest money you can afford to lose
• Always do your own research

The developers assume no liability for financial losses.
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Run tests: `python tests/test_gemini_utils.py`
4. Submit a pull request

## License

Apache 2.0 - See [LICENSE](LICENSE) for details.

---

**Built with [Claude Code](https://claude.ai/code)** | [Report Issues](https://github.com/AbdullahKaratas/trading-crew/issues)

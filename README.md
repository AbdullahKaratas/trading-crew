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
│                  INVESTMENT DEBATE                          │
│  ┌─────────────┐    2 Rounds    ┌─────────────┐            │
│  │    BULL     │◄──────────────►│    BEAR     │            │
│  │  Researcher │                │  Researcher │            │
│  └─────────────┘                └─────────────┘            │
│                        │                                    │
│                        ▼                                    │
│              ┌─────────────────┐                           │
│              │ INVESTMENT JUDGE│  → LONG / SHORT / HOLD    │
│              │  (Gemini Pro)   │                           │
│              └─────────────────┘                           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     RISK DEBATE                             │
│  ┌───────┐      ┌─────────┐      ┌─────────┐              │
│  │ RISKY │      │ NEUTRAL │      │  SAFE   │              │
│  │Analyst│      │ Analyst │      │ Analyst │              │
│  └───────┘      └─────────┘      └─────────┘              │
│                        │                                    │
│                        ▼                                    │
│              ┌─────────────────┐                           │
│              │   RISK JUDGE    │  → Knockout Strategies    │
│              │  (Gemini Pro)   │  → Entry/Exit Levels      │
│              └─────────────────┘                           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    TELEGRAM BOT                             │
│           Actionable alerts to your phone                   │
└─────────────────────────────────────────────────────────────┘
```

## Features

- **Universal Asset Support** - Stocks, Commodities (Gold, Silver), ETFs, Crypto
- **Real-Time Data** - Powered by Gemini + Google Search (no API limits)
- **Multi-Agent Debates** - Bull vs Bear + Risk assessment
- **Knockout Strategies** - Entry zones, stop-loss, take-profit levels
- **Telegram Bot** - On-demand analysis via commands
- **Scheduled Analysis** - Daily watchlist analysis via GitHub Actions
- **Multi-Language** - English and German support

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
| `/analyze AAPL long` | Force LONG direction (knockout below price) |
| `/analyze AAPL short` | Force SHORT direction (knockout above price) |
| `/analyze GOLD` | Commodity analysis |
| `/analyze AAPL de` | Analysis in German |
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
│   ├── gemini_utils.py       # Centralized Gemini API utilities
│   ├── universal_agents.py   # Multi-agent debate system
│   ├── commodity_agents.py   # Commodity-specific analysis
│   └── telegram_worker.py    # Telegram bot
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

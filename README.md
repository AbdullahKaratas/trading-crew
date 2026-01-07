# Stock Trading Bot - LLM-based Trading Recommendations

An automated trading recommendation system based on Multi-Agent LLM analysis with Claude AI and Gemini. The system analyzes your watchlist daily and sends actionable trading alerts via Telegram.

## What Does the System Do?

The bot runs a comprehensive analysis of your watchlist daily at 14:30 CET (1 hour before US Market Open):

1. **Multi-Agent Analysis** - Different specialized AI agents analyze each ticker:
   - Fundamental Analyst (valuation, financial metrics)
   - Technical Analyst (charts, indicators, levels)
   - Sentiment Analyst (market mood, social signals)
   - News Analyst (breaking news, events)

2. **Bull vs Bear Debate** - Two AI researchers debate the investment:
   - Bull Researcher argues FOR buying
   - Bear Researcher argues AGAINST buying
   - Multiple debate rounds for balanced perspective

3. **Final Decision** - A Trader agent makes the final decision:
   - Signal type (BUY/SELL/HOLD)
   - Entry zone, targets, stop-loss
   - Confidence score
   - Risk management review

4. **Telegram Alerts** - You receive a notification with all details for relevant signals.

```
IMPORTANT DISCLAIMER

This system is for educational and research purposes only.
It does NOT constitute financial advice.

- Past performance does not guarantee future results
- Trading involves significant risk of loss
- Only invest money you can afford to lose
- Consult a financial advisor for real investment decisions

The developers assume no liability for financial losses.
```

## Features

- **Multi-Agent LLM Analysis** with Gemini Flash (fast) and Claude Opus (precise)
- **Bull vs Bear Debate** for balanced perspectives
- **Technical Analysis** with MACD, RSI, Support/Resistance
- **News & Sentiment** integration
- **Risk Management** review for each recommendation
- **Telegram Alerts** with entry, targets, stop-loss
- **Automatic Execution** via GitHub Actions (free)
- **Automatic Fallback** - If Opus credits run out, falls back to Gemini Pro

## Architecture

```
+-----------------------------------------------------+
|           GitHub Actions (14:30 CET)                |
+----------------------+------------------------------+
                       |
                       v
+-----------------------------------------------------+
|              Multi-Agent Analysis                   |
|                                                     |
|  +---------------------------------------------+   |
|  |         ANALYST TEAM (Gemini Flash)         |   |
|  |  - Fundamental  - Technical                 |   |
|  |  - Sentiment    - News                      |   |
|  +---------------------------------------------+   |
|                       |                             |
|                       v                             |
|  +---------------------------------------------+   |
|  |       RESEARCHER TEAM (Gemini Flash)        |   |
|  |         Bull vs Bear Debate                 |   |
|  +---------------------------------------------+   |
|                       |                             |
|                       v                             |
|  +---------------------------------------------+   |
|  |      TRADER + RISK MGMT (Claude Opus)       |   |
|  |       Final Decision + Levels               |   |
|  +---------------------------------------------+   |
+----------------------+------------------------------+
                       |
                       v
+-----------------------------------------------------+
|                  Telegram Bot                       |
|              Alerts to your phone                   |
+-----------------------------------------------------+
```

## Prerequisites

- **Python 3.11+**
- **GitHub Account** (for automatic execution)
- **Telegram Account** (for alerts)
- **API Keys:**
  - Anthropic Claude API (required)
  - Google Gemini API (required)
  - Alpha Vantage (free)

## Setup Guide

### 1. Clone Repository

```bash
git clone https://github.com/YOUR_USERNAME/trading-crew.git
cd trading-crew
```

### 2. Create Python Environment

```bash
# Create virtual environment
python -m venv venv

# Activate
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt
```

### 3. Get API Keys

#### Claude API (required)
1. Go to https://console.anthropic.com
2. Create an account or log in
3. Navigate to "API Keys"
4. Create a new API key
5. Copy the key (starts with `sk-ant-...`)

#### Google Gemini API (required)
1. Go to https://aistudio.google.com/app/apikey
2. Create an API key
3. Copy the key

#### Alpha Vantage (free)
1. Go to https://www.alphavantage.co/support/#api-key
2. Fill out the form
3. You'll receive a free API key immediately
4. Free tier: 25 requests/day (sufficient with caching)

### 4. Create Telegram Bot

```
1. Open Telegram and search for @BotFather
2. Start a chat and send /newbot
3. Choose a name for your bot (e.g., "Stock Trading Alerts")
4. Choose a username (e.g., "my_trading_bot")
5. You'll receive a token - COPY THIS!
   Format: 123456789:ABCdefGHIjklMNOpqrSTUvwxYZ
```

**Get Chat ID:**
```
1. Start your new bot (search for it and click "Start")
2. Send any message to the bot
3. Open in browser:
   https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
4. Find "chat":{"id": YOUR_CHAT_ID} in the JSON
5. The Chat ID is a number (can be negative for groups)
```

### 5. Create Environment File

```bash
# Copy template
cp .env.example .env

# Edit .env and add keys
nano .env  # or vim, code, etc.
```

Fill in the following values:
```bash
ANTHROPIC_API_KEY=sk-ant-api03-xxxxx
GOOGLE_API_KEY=AIzaSyXXXXX
ALPHA_VANTAGE_API_KEY=xxxxx
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrSTUvwxYZ
TELEGRAM_CHAT_ID=123456789
```

### 6. Test Locally

```bash
# Test single stock (without Telegram)
python -m src.main --symbol AAPL --dry-run

# Test all stocks (without Telegram)
python -m src.main --dry-run

# With Telegram (sends real messages!)
python -m src.main --symbol AAPL
```

### 7. Create GitHub Repository

```bash
# Create new repository on GitHub (via web UI)
# Then:
git remote add origin https://github.com/YOUR_USERNAME/trading-crew.git
git branch -M main
git push -u origin main
```

### 8. Configure GitHub Secrets

```
1. Go to your repository on GitHub
2. Settings -> Secrets and variables -> Actions
3. Click "New repository secret"
4. Add the following secrets:

   Name: ANTHROPIC_API_KEY
   Value: sk-ant-api03-xxxxx

   Name: GOOGLE_API_KEY
   Value: AIzaSyXXXXX

   Name: ALPHA_VANTAGE_API_KEY
   Value: xxxxx

   Name: TELEGRAM_BOT_TOKEN
   Value: 123456789:ABCdefGHIjklMNOpqrSTUvwxYZ

   Name: TELEGRAM_CHAT_ID
   Value: 123456789
```

### 9. Enable GitHub Actions

```
1. Go to your repository -> Actions tab
2. Click "I understand my workflows, go ahead and enable them"
3. The workflow runs automatically Mon-Fri at 14:30 CET
```

**Manual Test Run:**
```
1. Actions -> "Daily Trading Analysis"
2. "Run workflow" -> "Run workflow"
3. Optional: Enter symbol for single stock
4. Optional: Enter day override (monday, tuesday, etc.)
```

## Configuration

### Customize Watchlist

Edit `config/watchlist.yaml`:

```yaml
watchlist:
  # Stocks are rotated by day to save API costs
  # Monday stocks
  ai_infrastructure:
    - symbol: NVDA
      name: NVIDIA
      day: monday

  # Tuesday stocks
  semiconductors:
    - symbol: AMD
      name: Advanced Micro Devices
      day: tuesday
```

### Customize Settings

Edit `config/settings.yaml`:

```yaml
trading:
  # Confidence threshold for alerts (0-100)
  min_confidence_for_alert: 65  # Higher = fewer alerts

  # Risk level: conservative, moderate, medium_aggressive, aggressive
  risk_level: medium_aggressive

telegram:
  # Only send alerts with action (no HOLD)
  only_actionable_signals: true

  # Send daily summary
  send_daily_summary: true

llm:
  # More debate rounds = more thorough analysis, but higher cost
  max_debate_rounds: 2

  # Primary model for final decisions
  deep_think_model: "claude-opus-4-5-20251101"

  # Fallback if Opus credits run out
  deep_think_fallback: "gemini-3-pro-preview"
```

## Local Testing

```bash
# Analyze single stock (without Telegram)
python -m src.main --symbol AAPL --dry-run

# Analyze specific day's stocks
python -m src.main --days monday --dry-run

# With debug logging
python -m src.main --symbol AAPL --log-level DEBUG --dry-run

# Run tests
pytest tests/ -v
```

## Interactive Mode (On-Demand Analysis)

Instead of scheduled daily analysis, you can run an interactive Telegram bot that responds to commands:

```bash
# Start interactive bot
python -m src.main --interactive
```

### Available Commands

| Command | Example | Description |
|---------|---------|-------------|
| `/analyze` | `/analyze AAPL` | Analyze a single stock |
| `/analyze` | `/analyze AAPL 5000` | Analyze with budget (EUR) for position sizing |
| `/long` | `/long NVDA 1000` | Long knockout certificate analysis |
| `/short` | `/short TSLA 500` | Short knockout certificate analysis |
| `/compare` | `/compare AAPL MSFT` | Compare two stocks |
| `/portfolio` | `/portfolio AAPL:5000 MSFT:3000` | Set your portfolio (amounts in EUR) |
| `/profile` | `/profile aggressive` | Set risk profile (conservative/moderate/aggressive/yolo) |
| `/risk` | `/risk` | Portfolio risk assessment |
| `/help` | `/help` | Show all commands |

### Risk Profiles

| Profile | Sector Max | Leverage Max | Stop-Loss |
|---------|-----------|--------------|-----------|
| `conservative` | 40% | 2x | 5% |
| `moderate` | 60% | 5x | 8% |
| `aggressive` | 80% | 10x | 15% |
| `yolo` | 100% | 20x | 25% |

### Example Workflow

1. Start the bot: `python -m src.main --interactive`
2. Send `/start` to your Telegram bot
3. Set your risk profile: `/profile aggressive`
4. Set your portfolio: `/portfolio AAPL:5000 NVDA:3000`
5. Check portfolio risk: `/risk`
6. Analyze a new stock: `/analyze MSFT 2000`
7. Get knockout analysis: `/long MSFT 1000`

## Telegram Message Formats

### BUY Signal
```
BUY SIGNAL: AAPL (Apple Inc.)

Price: $185.45
Action: BUY 30-40% of position at current levels

Stop-Loss: $175.00 (-6%)
   Based on recent support level

Targets:
   - $195.00 (+5%): Take 30% profit
   - $210.00 (+13%): Take remaining

Key Events:
   - Earnings report Jan 25
   - Product launch expected Q1

Exit Conditions:
   - Break below $175 support
   - Negative earnings surprise

Recommendation:
Strong technical setup with bullish MACD crossover...

14:30 CET | Pre-Market
```

### Daily Summary
```
DAILY SUMMARY - 01/07/2026

BUY Signals: 2
   - AAPL - BUY 30% at current levels
   - MSFT - Scale in below $400

SELL Signals: 1
   - TSLA - SELL 50% immediately

HOLD: 3 stocks

Top Pick: AAPL
   Strong momentum with clear risk/reward

Next analysis: Tomorrow 14:30 CET
```

## Project Structure

```
trading-crew/
├── README.md                     # This file
├── .env.example                  # API key template
├── .gitignore
├── requirements.txt
│
├── config/
│   ├── watchlist.yaml           # Stock watchlist (by day)
│   └── settings.yaml            # Bot settings
│
├── TradingAgents/               # TradingAgents Framework
│   ├── tradingagents/           # Multi-agent system
│   │   ├── agents/              # Analyst, Researcher, Trader agents
│   │   ├── graph/               # LangGraph workflow
│   │   └── dataflows/           # Data integration
│   └── ...
│
├── src/
│   ├── main.py                  # Entry point
│   ├── analysis/
│   │   └── signals.py           # Signal data classes
│   ├── notifications/
│   │   ├── telegram_bot.py      # Telegram integration
│   │   └── formatters.py        # Message formatting
│   └── utils/
│       ├── logger.py            # Structured logging
│       └── market_hours.py      # US market hours
│
└── .github/
    └── workflows/
        └── trading_analysis.yml  # GitHub Actions cron
```

## Troubleshooting

### "ANTHROPIC_API_KEY not set"
- Check if `.env` file exists
- Check if the key was copied correctly (no spaces)
- For GitHub Actions: Check if secret is correctly configured

### "Telegram connection failed"
- Check bot token (must start with number, then `:`)
- Check chat ID (must be a number)
- Make sure you sent a message to the bot first

### "No data returned for SYMBOL"
- Symbol might not exist or be misspelled
- Some symbols (e.g., `.V` for Venture) might not work
- Verify the symbol on finance.yahoo.com

### "Rate limit exceeded"
- Alpha Vantage free tier: 25 requests/day
- Wait until the next day or upgrade the plan
- Caching is enabled, should normally be sufficient

### GitHub Actions not running
- Check if Actions are enabled (Repository -> Actions)
- Check if secrets are correctly configured
- Check the workflow logs for errors

## Cost Overview

| Service | Cost |
|---------|------|
| GitHub Actions | $0 (2000 min/month free) |
| Claude Opus API | ~$0.50-2/analysis |
| Gemini Flash API | ~$0.01/analysis |
| Alpha Vantage | $0 (free tier) |
| Telegram | $0 |
| **Estimated Total** | **~$30-100/month** |

**Cost Factors:**
- Number of stocks in watchlist
- Number of debate rounds
- Gemini Flash is very cheap
- Opus is used only for final decisions

## Credits

This project is based on the [TradingAgents Framework](https://github.com/TauricResearch/TradingAgents) by TauricResearch.

## License

Apache 2.0 - See LICENSE file for details.

## Support

For questions or issues:
1. Check the troubleshooting section above
2. Look at the GitHub Actions logs
3. Create an issue in the repository

---

**Good luck with your trading!**

*Remember: The system provides recommendations - the final decision is always yours.*

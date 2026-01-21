# CLAUDE.md - Project Guidelines

## LLM Model Requirements

**CRITICAL: This project uses ONLY Google Gemini models.**

| Task | Model |
|------|-------|
| Fast tasks (data gathering, analysts) | `gemini-3-flash-preview` |
| Deep thinking (judges, final decisions) | `gemini-3-pro-preview` |

### Usage

All LLM calls MUST go through `scripts/gemini_utils.py`:

```python
from gemini_utils import call_gemini_flash, call_gemini_pro, call_gemini_vision

# Fast tasks with Google Search
response = call_gemini_flash(prompt, use_search=True)

# Deep thinking without search
response = call_gemini_pro(prompt, use_search=False)

# Vision analysis with chart image
from chart_vision import create_chart_for_analysis
chart_image = create_chart_for_analysis(symbol)  # Returns BytesIO
response = call_gemini_vision(prompt, chart_image)
```

**Do NOT use Claude/Anthropic or OpenAI APIs in this project.**

## Project Structure

```
trading-crew/
├── scripts/
│   ├── gemini_utils.py         # Gemini API (Flash, Pro, Vision)
│   ├── chart_vision.py         # 4-panel chart generator (Plotly)
│   ├── universal_agents.py     # Multi-agent debate system
│   ├── telegram_worker.py      # /analyze command
│   └── comparison_worker.py    # /vs command
├── .github/workflows/
│   ├── telegram_analysis.yml   # /analyze trigger
│   └── telegram_comparison.yml # /vs trigger
├── config/
│   ├── settings.yaml           # Bot config
│   └── watchlist.yaml          # Scheduled symbols
└── TradingAgents/              # Legacy framework
```

## Data Flow

1. Telegram Bot → Supabase Edge Function (external)
2. Edge Function → GitHub Actions (`repository_dispatch`)
3. GitHub Action → Python script
4. Symbol Resolution → Gemini finds yfinance symbol
5. Chart Generation → 4-panel PNG via `chart_vision.py`
6. Multi-Agent Debate → All 7 agents receive chart + text data
7. Chart Image → Telegram via `send_telegram_photo()`
8. Analysis Text → Telegram via `send_telegram_message()`

## Chart Vision

The system generates a 4-panel technical chart for AI analysis:

| Panel | Indicators |
|-------|------------|
| Price | Candlesticks, SMA 50 (orange), SMA 200 (purple) |
| RSI | RSI(14), Overbought (70), Oversold (30) lines |
| Volume | Green (bullish) / Red (bearish) bars |
| Money Flow | CMF(20) area, OBV line |

All 7 agents (Bull, Bear, Investment Judge, Risky, Safe, Neutral, Risk Judge) receive the chart via Gemini Vision API.

## Agent Data Requirements

**CRITICAL: ALL 7 agents must receive ALL gathered data sources.**

Each agent prompt MUST include:
- `state['technical_data']` - Price action, indicators, support/resistance
- `state['news_data']` - News, geopolitics, tariffs, partnerships, product launches
- `state['fundamental_data']` - Financials, macro context, supply/demand
- `state['chart_image']` - 4-panel technical chart (if available)

**Why this matters:**
- Judges only seeing debate summaries lose critical details
- Geopolitical events, tariffs, partnerships get filtered out
- Final analysis becomes too technical/chart-focused
- Important news catalysts are ignored in risk assessment

**Never let an agent make decisions without full context!**

| Agent | technical_data | news_data | fundamental_data | chart_image |
|-------|----------------|-----------|------------------|-------------|
| Bull Analyst | ✅ | ✅ | ✅ | ✅ |
| Bear Analyst | ✅ | ✅ | ✅ | ✅ |
| Investment Judge | ✅ | ✅ | ✅ | ✅ |
| Risky Analyst | ✅ | ✅ | ✅ | ✅ |
| Safe Analyst | ✅ | ✅ | ✅ | ✅ |
| Neutral Analyst | ✅ | ✅ | ✅ | ✅ |
| Risk Judge | ✅ | ✅ | ✅ | ✅ |

## Trade Decision Schema

Key fields in `TRADE_DECISION_SCHEMA`:
- `signal`: LONG | SHORT | HOLD | IGNORE
- `confidence`: 0.0 to 1.0
- `timeframes`: { short_term, medium_term, long_term }
- `strategies`: { conservative, moderate, aggressive }
- `support_zones` / `resistance_zones`
- `detailed_analysis`: Full text reasoning

## Data Integrity

**CRITICAL: NEVER use fake/placeholder data. Users trust our analysis!**

### Forbidden Patterns
```python
# ❌ NEVER DO THIS
recent_low = current_price * 0.95   # Fake!
week_52_high = current_price * 1.20  # Fake!
eur_rate = 0.95                      # Hardcoded!
"confidence": 0.75                   # Example value LLM copies!
```

### Required Patterns
```python
# ✅ Always fetch real data
recent_low = hist["Low"].tail(20).min()           # Real yfinance data
week_52_high = hist_1y["High"].max()              # Real yfinance data
eur_rate = get_eur_usd_rate()                     # Live rate via yfinance/API
"confidence": <float 0.0-1.0 - see guidelines>    # LLM calculates
```

### Data Sources Priority
1. **yfinance** - Stocks, ETFs, Commodities (via futures symbols like `SI=F`, `GC=F`)
2. **Gemini + Google Search** - Fallback for missing data
3. **NEVER** - Hardcoded values or `price * factor` estimates

### Commodity yfinance Symbols
| Commodity | yfinance Symbol |
|-----------|-----------------|
| Silver | `SI=F` |
| Gold | `GC=F` |
| Oil (WTI) | `CL=F` |
| Copper | `HG=F` |

## Coding Standards

- Code comments: English
- User-facing text: German (`de`) and English (`en`) support
- Use `get_language_instruction(lang)` for LLM prompts
- Always use try/except with meaningful errors **and logging** (never bare `except: pass`)
- Telegram: Markdown format, 4000 char limit (auto-split)

## Commands

| Command | Description |
|---------|-------------|
| `/analyze SYMBOL` | Full analysis |
| `/analyze SYMBOL long/short` | Force direction |
| `/analyze SYMBOL de/en` | Language |
| `/vs SYMBOL1 SYMBOL2` | Compare 2-4 assets |

## Error Handling

### JSON Retry Logic
- `call_gemini_json()` automatically retries up to 3x if LLM returns text instead of JSON
- Each retry adds "IMPORTANT: Return ONLY valid JSON" to the prompt
- Used in `risk_judge()` for final trade decisions

### yfinance Fallback
When yfinance fails (e.g., European stocks like `EOAN`):
1. Tries common suffixes: `.DE`, `.L`, `.PA`, `.AS`, `.MI`, `.SW`
2. Falls back to Gemini Search for price AND historical levels (52-week, recent highs/lows)
3. For commodities: Use futures symbols (`SI=F`, `GC=F`) which work with yfinance

## Testing

```bash
# Syntax check
python3 -m py_compile scripts/gemini_utils.py
python3 -m py_compile scripts/chart_vision.py
python3 -m py_compile scripts/universal_agents.py
python3 -m py_compile scripts/telegram_worker.py
python3 -m py_compile scripts/comparison_worker.py
```

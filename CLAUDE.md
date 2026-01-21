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

## Trade Decision Schema

Key fields in `TRADE_DECISION_SCHEMA`:
- `signal`: LONG | SHORT | HOLD | IGNORE
- `confidence`: 0.0 to 1.0
- `timeframes`: { short_term, medium_term, long_term }
- `strategies`: { conservative, moderate, aggressive }
- `support_zones` / `resistance_zones`
- `detailed_analysis`: Full text reasoning

## Coding Standards

- Code comments: English
- User-facing text: German (`de`) and English (`en`) support
- Use `get_language_instruction(lang)` for LLM prompts
- Always use try/except with meaningful errors
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
2. Falls back to Gemini Search for price only
3. Support/resistance values are placeholders - actual values come from LLM analysis

## Testing

```bash
# Syntax check
python3 -m py_compile scripts/gemini_utils.py
python3 -m py_compile scripts/chart_vision.py
python3 -m py_compile scripts/universal_agents.py
python3 -m py_compile scripts/telegram_worker.py
python3 -m py_compile scripts/comparison_worker.py
```

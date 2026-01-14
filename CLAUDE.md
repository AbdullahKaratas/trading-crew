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
from gemini_utils import call_gemini_flash, call_gemini_pro

# Fast tasks with Google Search
response = call_gemini_flash(prompt, use_search=True)

# Deep thinking without search
response = call_gemini_pro(prompt, use_search=False)
```

**Do NOT use Claude/Anthropic or OpenAI APIs in this project.**

## Project Structure

```
trading-crew/
├── scripts/
│   ├── gemini_utils.py         # Gemini API (USE THIS!)
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
4. Python → Gemini API via `gemini_utils.py`
5. Response → Telegram via `send_telegram_message()`

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

## Testing

```bash
# Syntax check
python3 -m py_compile scripts/gemini_utils.py
python3 -m py_compile scripts/universal_agents.py
python3 -m py_compile scripts/telegram_worker.py
python3 -m py_compile scripts/comparison_worker.py
```

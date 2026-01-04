# Stock Trading Bot - LLM-basierte Trading Empfehlungen

Ein automatisiertes Trading-Empfehlungssystem basierend auf Multi-Agent LLM-Analyse mit Claude AI. Das System analysiert täglich eure Watchlist und sendet actionable Trading-Alerts per Telegram.

## Was macht das System?

Der Bot führt täglich um 14:00 CET (1 Stunde vor US Market Open) eine umfassende Analyse eurer Watchlist durch:

1. **Multi-Agent Analyse** - Verschiedene spezialisierte KI-Agenten analysieren jeden Ticker:
   - Fundamental Analyst (Bewertung, Finanzkennzahlen)
   - Technical Analyst (Charts, Indikatoren, Levels)
   - Sentiment Analyst (Marktstimmung, Social Signals)
   - News Analyst (Breaking News, Events)

2. **Bull vs Bear Debate** - Zwei KI-Researcher debattieren über das Investment:
   - Bull Researcher argumentiert FÜR den Kauf
   - Bear Researcher argumentiert GEGEN den Kauf
   - Mehrere Debattenrunden für ausgewogene Perspektive

3. **Finale Entscheidung** - Ein Trader-Agent trifft die finale Entscheidung:
   - Signal-Typ (BUY/SELL/HOLD)
   - Entry Zone, Targets, Stop-Loss
   - Confidence Score
   - Risk Management Review

4. **Telegram Alerts** - Bei relevanten Signalen erhaltet ihr eine Benachrichtigung mit allen Details.

```
WICHTIGER HINWEIS - DISCLAIMER

Dieses System ist nur für Bildungs- und Forschungszwecke.
Es stellt KEINE Finanzberatung dar.

- Vergangene Performance garantiert keine zukünftigen Ergebnisse
- Trading birgt erhebliche Verlustrisiken
- Investiere nur Geld, dessen Verlust du dir leisten kannst
- Konsultiere einen Finanzberater für echte Anlageentscheidungen

Die Entwickler übernehmen keine Haftung für finanzielle Verluste.
```

## Features

- **Multi-Agent LLM Analyse** mit Claude Haiku (schnell) und Opus (präzise)
- **Bull vs Bear Debate** für ausgewogene Perspektiven
- **Technische Analyse** mit MACD, RSI, Support/Resistance
- **News & Sentiment** Integration
- **Risk Management** Review für jede Empfehlung
- **Telegram Alerts** mit Entry, Targets, Stop-Loss
- **Automatische Ausführung** via GitHub Actions (kostenlos)

## Architektur

```
+-----------------------------------------------------+
|           GitHub Actions (14:00 CET)                |
+----------------------+------------------------------+
                       |
                       v
+-----------------------------------------------------+
|              Multi-Agent Analysis                   |
|                                                     |
|  +---------------------------------------------+   |
|  |           ANALYST TEAM (Haiku)              |   |
|  |  - Fundamental  - Technical                 |   |
|  |  - Sentiment    - News                      |   |
|  +---------------------------------------------+   |
|                       |                             |
|                       v                             |
|  +---------------------------------------------+   |
|  |         RESEARCHER TEAM (Haiku)             |   |
|  |       Bull vs Bear Debate                   |   |
|  +---------------------------------------------+   |
|                       |                             |
|                       v                             |
|  +---------------------------------------------+   |
|  |        TRADER + RISK MGMT (Opus)            |   |
|  |         Final Decision + Levels             |   |
|  +---------------------------------------------+   |
+----------------------+------------------------------+
                       |
                       v
+-----------------------------------------------------+
|              Telegram Bot                           |
|          Alerts an euer Handy                       |
+-----------------------------------------------------+
                       |
                       v
+-----------------------------------------------------+
|           Ihr entscheidet + Trade Republic          |
+-----------------------------------------------------+
```

## Voraussetzungen

- **Python 3.11+**
- **GitHub Account** (für automatische Ausführung)
- **Telegram Account** (für Alerts)
- **API Keys:**
  - Anthropic Claude API (erforderlich)
  - Alpha Vantage (kostenlos)

## Setup-Anleitung

### 1. Repository klonen

```bash
git clone https://github.com/DEIN_USERNAME/stock-trading-bot-recommendations.git
cd stock-trading-bot-recommendations
```

### 2. Python Environment erstellen

```bash
# Virtual Environment erstellen
python -m venv venv

# Aktivieren
source venv/bin/activate  # Linux/Mac
# oder
venv\Scripts\activate     # Windows

# Dependencies installieren
pip install -r requirements.txt
```

### 3. API Keys holen

#### Claude API (erforderlich)
1. Gehe zu https://console.anthropic.com
2. Erstelle einen Account oder logge dich ein
3. Navigiere zu "API Keys"
4. Erstelle einen neuen API Key
5. Kopiere den Key (beginnt mit `sk-ant-...`)

#### Alpha Vantage (kostenlos)
1. Gehe zu https://www.alphavantage.co/support/#api-key
2. Fülle das Formular aus
3. Du erhältst sofort einen kostenlosen API Key
4. Free Tier: 25 Requests/Tag (reicht mit Caching)

#### Finnhub (optional, für erweiterte News)
1. Gehe zu https://finnhub.io/register
2. Erstelle einen kostenlosen Account
3. Kopiere den API Key aus dem Dashboard

### 4. Telegram Bot erstellen

```
1. Öffne Telegram und suche nach @BotFather
2. Starte einen Chat und sende /newbot
3. Wähle einen Namen für deinen Bot (z.B. "Stock Trading Alerts")
4. Wähle einen Username (z.B. "mein_trading_bot")
5. Du erhältst einen Token - KOPIERE DIESEN!
   Format: 123456789:ABCdefGHIjklMNOpqrSTUvwxYZ
```

**Chat ID holen:**
```
1. Starte deinen neuen Bot (suche ihn und klicke "Start")
2. Sende eine beliebige Nachricht an den Bot
3. Öffne im Browser:
   https://api.telegram.org/bot<DEIN_TOKEN>/getUpdates
4. Suche im JSON nach "chat":{"id": DEINE_CHAT_ID}
5. Die Chat ID ist eine Zahl (kann negativ sein für Gruppen)
```

### 5. Environment Datei erstellen

```bash
# Template kopieren
cp .env.example .env

# .env bearbeiten und Keys eintragen
nano .env  # oder vim, code, etc.
```

Fülle folgende Werte aus:
```bash
ANTHROPIC_API_KEY=sk-ant-api03-xxxxx
ALPHA_VANTAGE_API_KEY=xxxxx
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrSTUvwxYZ
TELEGRAM_CHAT_ID=123456789
```

### 6. Lokal testen

```bash
# Einzelne Aktie testen (ohne Telegram)
python -m src.main --symbol APLD --dry-run

# Alle Aktien testen (ohne Telegram)
python -m src.main --dry-run

# Mit Telegram (sendet echte Nachrichten!)
python -m src.main --symbol APLD
```

### 7. GitHub Repository erstellen

```bash
# Neues Repository auf GitHub erstellen (via Web UI)
# Dann:
git remote add origin https://github.com/DEIN_USERNAME/stock-trading-bot-recommendations.git
git branch -M main
git push -u origin main
```

### 8. GitHub Secrets konfigurieren

```
1. Gehe zu deinem Repository auf GitHub
2. Settings -> Secrets and variables -> Actions
3. Klicke "New repository secret"
4. Füge folgende Secrets hinzu:

   Name: ANTHROPIC_API_KEY
   Value: sk-ant-api03-xxxxx

   Name: ALPHA_VANTAGE_API_KEY
   Value: xxxxx

   Name: TELEGRAM_BOT_TOKEN
   Value: 123456789:ABCdefGHIjklMNOpqrSTUvwxYZ

   Name: TELEGRAM_CHAT_ID
   Value: 123456789

   (Optional)
   Name: FINNHUB_API_KEY
   Value: xxxxx
```

### 9. GitHub Actions aktivieren

```
1. Gehe zu deinem Repository -> Actions Tab
2. Klicke "I understand my workflows, go ahead and enable them"
3. Der Workflow läuft automatisch Mo-Fr um 14:00 CET
```

**Manueller Test-Run:**
```
1. Actions -> "Daily Trading Analysis"
2. "Run workflow" -> "Run workflow"
3. Optional: Symbol eingeben für einzelne Aktie
```

## Konfiguration

### Watchlist anpassen

Bearbeite `config/watchlist.yaml`:

```yaml
watchlist:
  # Eigene Kategorie hinzufügen
  meine_aktien:
    - symbol: NVDA
      name: NVIDIA
    - symbol: AMD
      name: Advanced Micro Devices

  # Bestehende Kategorie erweitern
  ai_infrastructure:
    - symbol: APLD
      name: Applied Digital
    # Neue Aktie hinzufügen:
    - symbol: CLSK
      name: CleanSpark
```

### Settings anpassen

Bearbeite `config/settings.yaml`:

```yaml
trading:
  # Confidence-Schwelle für Alerts (0-100)
  min_confidence_for_alert: 65  # Höher = weniger Alerts

  # Risiko-Level: conservative, moderate, medium_aggressive, aggressive
  risk_level: medium_aggressive

telegram:
  # Nur Alerts mit Action senden (keine HOLD)
  only_actionable_signals: true

  # Tägliche Zusammenfassung senden
  send_daily_summary: true

llm:
  # Mehr Debate-Runden = gründlichere Analyse, aber mehr Kosten
  max_debate_rounds: 2
```

## Lokales Testing

```bash
# Einzelne Aktie analysieren (ohne Telegram)
python -m src.main --symbol APLD --dry-run

# Alle Aktien analysieren (ohne Telegram)
python -m src.main --dry-run

# Mit Debug-Logging
python -m src.main --symbol APLD --log-level DEBUG --dry-run

# Tests ausführen
pytest tests/ -v

# Tests mit Coverage
pytest tests/ --cov=src --cov-report=html
```

## Telegram Message Formate

### BUY Signal
```
BUY SIGNAL: APLD (Applied Digital)

Preis: $8.45
Entry Zone: $8.30 - $8.50
Target 1: $9.20 (+9%)
Target 2: $10.50 (+24%)
Stop-Loss: $7.80 (-8%)

Confidence: 78%
Risk/Reward: 1:3

Technisch:
- Bullish MACD Crossover
- RSI: 45 (neutral)
- Support: $7.80 | Resistance: $10.50

News: Neuer GPU-Cluster Deal angekündigt
Sentiment: Positiv (0.65)

14:12 CET | Pre-Market
```

### Support Alert
```
SUPPORT ALERT: IREN

Preis nähert sich kritischem Support!

Aktuell: $12.05
Support: $11.80 (-2%)
Resistance: $14.20 (+18%)

Mögliche Aktion:
- Buy Limit bei $11.85 setzen
- Stop-Loss unter $11.50

Confidence: 70%
14:08 CET
```

### Daily Summary
```
DAILY SUMMARY - 02.01.2026

BUY Signals: 2
   - APLD (78%) - AI Infrastructure Momentum
   - RKLB (71%) - Space Sector Breakout

SELL Signals: 1
   - QBTS (72%) - Bearish Divergence

Support Alerts: 1
   - IREN near $11.80

HOLD: 10 Aktien
   - Keine klaren Signale

Top Pick: APLD
   Stärkstes Risk/Reward heute (1:3.0)

Nächste Analyse: Morgen 14:00 CET
```

## Projekt-Struktur

```
stock-trading-bot-recommendations/
├── README.md                     # Diese Datei
├── .env.example                  # Template für API Keys
├── .gitignore
├── requirements.txt
├── pyproject.toml
│
├── config/
│   ├── watchlist.yaml           # Aktien-Watchlist
│   └── settings.yaml            # Bot-Einstellungen
│
├── TradingAgents/               # TradingAgents Framework (geklont)
│   ├── tradingagents/           # Multi-Agent System
│   │   ├── agents/              # Analyst, Researcher, Trader Agents
│   │   ├── graph/               # LangGraph Workflow
│   │   └── dataflows/           # Daten-Integration
│   └── ...
│
├── src/
│   ├── __init__.py
│   ├── main.py                  # Entry Point (nutzt TradingAgents)
│   │
│   ├── analysis/
│   │   ├── __init__.py
│   │   └── signals.py           # Signal-Datenklassen
│   │
│   ├── notifications/
│   │   ├── __init__.py
│   │   ├── telegram_bot.py      # Telegram Integration
│   │   └── formatters.py        # Message Formatting
│   │
│   └── utils/
│       ├── __init__.py
│       ├── logger.py            # Structured Logging
│       └── market_hours.py      # US Market Hours
│
├── tests/
│   └── ...
│
└── .github/
    └── workflows/
        └── trading_analysis.yml  # GitHub Actions Cron
```

**Hinweis:** Das `TradingAgents/` Verzeichnis enthält das Framework von
[TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents).
Wir nutzen es mit Claude statt OpenAI.

## Troubleshooting

### "ANTHROPIC_API_KEY not set"
- Prüfe ob `.env` Datei existiert
- Prüfe ob der Key korrekt kopiert wurde (keine Leerzeichen)
- Bei GitHub Actions: Prüfe ob Secret korrekt angelegt wurde

### "Telegram connection failed"
- Prüfe Bot Token (muss mit Zahl beginnen, dann `:`)
- Prüfe Chat ID (muss eine Zahl sein)
- Stelle sicher, dass du dem Bot eine Nachricht gesendet hast

### "No data returned for SYMBOL"
- Symbol könnte nicht existieren oder falsch geschrieben sein
- Manche Symbole (z.B. `.V` für Venture) funktionieren evtl. nicht
- Prüfe das Symbol auf finance.yahoo.com

### "Rate limit exceeded"
- Alpha Vantage Free Tier: 25 requests/day
- Warte bis zum nächsten Tag oder upgrade den Plan
- Caching ist aktiviert, sollte normalerweise reichen

### GitHub Actions läuft nicht
- Prüfe ob Actions aktiviert sind (Repository -> Actions)
- Prüfe ob Secrets korrekt angelegt sind
- Schaue in die Workflow Logs für Fehler

## Kosten-Übersicht

| Service | Kosten |
|---------|--------|
| GitHub Actions | $0 (2000 min/Monat free) |
| Claude API | ~$5-15/Tag je nach Watchlist-Größe |
| Alpha Vantage | $0 (Free Tier reicht) |
| Telegram | $0 |
| **Geschätzt Total** | **~$150-450/Monat** |

**Kosten-Faktoren:**
- Anzahl Aktien in der Watchlist
- Anzahl Debate-Runden
- Haiku ist günstig (~$0.25/1M input tokens)
- Opus ist teurer (~$15/1M input tokens)

## Weiterentwicklung

Ideen für Erweiterungen:
- [ ] Backtesting der Signale
- [ ] Performance-Tracking Dashboard
- [ ] Intraday-Alerts bei starken Bewegungen
- [ ] Integration mit Trade Republic API (wenn verfügbar)
- [ ] Discord/Slack Integration
- [ ] Web Dashboard für Signal-Historie

## Support

Bei Fragen oder Problemen:
1. Prüfe die Troubleshooting-Sektion oben
2. Schaue in die GitHub Actions Logs
3. Erstelle ein Issue im Repository

---

**Viel Erfolg beim Trading!**

*Remember: Das System gibt Empfehlungen - die finale Entscheidung liegt immer bei euch.*

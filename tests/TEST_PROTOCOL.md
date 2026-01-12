# Trading Crew Test Protocol

## Quick Validation Checklist

### 1. Syntax & Import Tests (Automatisch)
```bash
cd scripts
python3 -m py_compile gemini_utils.py
python3 -m py_compile universal_agents.py
python3 -m py_compile commodity_agents.py
python3 -m py_compile telegram_worker.py
```
**Erwartung:** Keine Fehler

---

## 2. Unit Tests: gemini_utils.py

### 2.1 strip_markdown_code_block()
```python
from gemini_utils import strip_markdown_code_block

# Test 1: JSON mit Markdown
assert strip_markdown_code_block('```json\n{"test": 1}\n```') == '{"test": 1}'

# Test 2: Ohne Markdown
assert strip_markdown_code_block('{"test": 1}') == '{"test": 1}'

# Test 3: Leerer String
assert strip_markdown_code_block('') == ''
```

### 2.2 parse_json_response()
```python
from gemini_utils import parse_json_response

# Test 1: Valides JSON
assert parse_json_response('{"signal": "LONG"}') == {"signal": "LONG"}

# Test 2: JSON mit Markdown
assert parse_json_response('```json\n{"signal": "SHORT"}\n```') == {"signal": "SHORT"}

# Test 3: Invalides JSON
assert parse_json_response('not json') is None

# Test 4: None Input
assert parse_json_response(None) is None
```

### 2.3 extract_price_from_text()
```python
from gemini_utils import extract_price_from_text

# Test 1: USD Format
assert extract_price_from_text('Price: $260.25') == 260.25

# Test 2: Mit Komma
assert extract_price_from_text('Market cap: $1,234.56') == 1234.56

# Test 3: Ohne Symbol
assert extract_price_from_text('Current: 100.50') == 100.50

# Test 4: Kein Preis
assert extract_price_from_text('No price here') is None
```

### 2.4 get_language_instruction()
```python
from gemini_utils import get_language_instruction

assert get_language_instruction('de') == 'Respond entirely in German.'
assert get_language_instruction('en') == 'Respond entirely in English.'
```

---

## 3. Integration Tests: Gemini API

### 3.1 API Connection Test
```python
from gemini_utils import call_gemini_flash

response = call_gemini_flash("Say 'OK' if you can read this.", use_search=False)
assert 'OK' in response or 'ok' in response.lower()
```

### 3.2 Search Grounding Test
```python
from gemini_utils import call_gemini_flash

response = call_gemini_flash(
    "What is the current price of AAPL stock? Just give the number.",
    use_search=True
)
# Should return a price like "$260" or "260.25"
assert '$' in response or any(c.isdigit() for c in response)
```

---

## 4. End-to-End Tests via Telegram

### 4.1 Stock Analysis (US)
```
/analyze AAPL
```
**Erwartung:**
- [ ] Preis ~$260 (aktuell prüfen)
- [ ] RSI-Wert vorhanden (0-100)
- [ ] Signal: LONG/SHORT/HOLD
- [ ] Confidence: 0.0-1.0
- [ ] Knockout-Strategien vorhanden
- [ ] Keine NoneType Errors

### 4.2 Stock Analysis mit Forced Direction
```
/analyze AAPL long
```
**Erwartung:**
- [ ] Signal muss LONG sein
- [ ] Knockout nur unterhalb des Preises

```
/analyze AAPL short
```
**Erwartung:**
- [ ] Signal muss SHORT sein
- [ ] Knockout nur oberhalb des Preises

### 4.3 Commodity Analysis
```
/analyze GOLD
```
**Erwartung:**
- [ ] Preis in USD/oz (~$2,600-2,700)
- [ ] Fundamentale Daten (Supply/Demand)
- [ ] COT-Positionierung erwähnt
- [ ] Signal vorhanden

```
/analyze SILVER
```
**Erwartung:**
- [ ] Preis ~$30/oz
- [ ] Nicht verwechselt mit SVM (Silvercorp Metals)

### 4.4 German Language
```
/analyze AAPL de
```
**Erwartung:**
- [ ] Ausgabe komplett auf Deutsch
- [ ] "Vertrauen" statt "Confidence"
- [ ] "Knockout" Strategien auf Deutsch

### 4.5 Error Handling
```
/analyze INVALIDTICKER123
```
**Erwartung:**
- [ ] Graceful Error (keine Crashes)
- [ ] Sinnvolle Fehlermeldung

---

## 5. Performance Tests

### 5.1 Response Time
| Test | Max Zeit |
|------|----------|
| Stock Analysis | < 90 Sekunden |
| Commodity Analysis | < 90 Sekunden |
| Forced Direction | < 90 Sekunden |

### 5.2 Rate Limit Handling
- Mehrere Analysen hintereinander ausführen
- System sollte bei 429-Errors automatisch retry machen
- Keine Crashes bei Rate Limits

---

## 6. Data Accuracy Tests

### 6.1 Preis-Verifikation
Für jeden Test den Preis mit TradingView vergleichen:
- https://www.tradingview.com/symbols/NASDAQ-AAPL/
- https://www.tradingview.com/symbols/COMEX-GC1!/

**Akzeptable Abweichung:** < 1%

### 6.2 Technische Indikatoren
RSI-Wert mit TradingView vergleichen:
- Daily Timeframe wählen
- RSI(14) vergleichen

**Akzeptable Abweichung:** < 5 Punkte

---

## 7. Regression Tests

Nach jedem Code-Change prüfen:
- [ ] AAPL funktioniert
- [ ] GOLD funktioniert
- [ ] Forced Direction funktioniert
- [ ] Deutsche Sprache funktioniert
- [ ] Keine NoneType Errors

---

## Test Execution Log

| Datum | Test | Ergebnis | Notizen |
|-------|------|----------|---------|
| | | | |

---

## Known Issues

| Issue | Status | Workaround |
|-------|--------|------------|
| Rate Limit bei Free Tier | Erwartet | 60s warten zwischen Tests |
| | | |

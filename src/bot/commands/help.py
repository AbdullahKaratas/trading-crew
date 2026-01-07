"""Help command handler."""


class HelpCommand:
    """
    Handle /help command showing all available commands.
    """

    def execute(self) -> str:
        """Return help text with all commands."""
        return """
🤖 *Trading Analysis Bot - Hilfe*

*ANALYSE COMMANDS:*

`/analyze SYMBOL [budget]`
  Analysiert eine Aktie mit Multi-Agent AI
  _Beispiel: `/analyze AAPL` oder `/analyze AAPL 5000`_

`/a SYMBOL [budget]`
  _Kurzform für /analyze_

`/compare SYMBOL1 SYMBOL2`
  Vergleicht zwei Aktien
  _Beispiel: `/compare AAPL MSFT`_

*KNOCKOUT CERTIFICATES:*

`/long SYMBOL [budget]`
  Long Knockout Analyse (bullish)
  _Beispiel: `/long NVDA 1000`_

`/short SYMBOL [budget]`
  Short Knockout Analyse (bearish)
  _Beispiel: `/short TSLA 500`_

*PORTFOLIO & RISIKO:*

`/portfolio [SYMBOL:BETRAG ...]`
  Zeigt/setzt dein Portfolio (Beträge in EUR)
  _Beispiel: `/portfolio AAPL:5000 MSFT:3000`_

`/p`
  _Kurzform für /portfolio anzeigen_

`/profile [profil]`
  Zeigt/setzt dein Risiko-Profil
  _Profile: conservative, moderate, aggressive, yolo_

`/risk`
  Portfolio-Risiko-Analyse
  _Sektor-Konzentration, Korrelation, Beta, Earnings_

*SONSTIGES:*

`/alerts`
  Zeigt deine Preis-Alerts _(coming soon)_

`/help`
  Diese Hilfe anzeigen

*BEISPIEL WORKFLOW:*
1. `/profile aggressive` - Risiko-Profil setzen
2. `/portfolio AAPL:5000 NVDA:3000` - Portfolio setzen
3. `/risk` - Risiko analysieren
4. `/analyze MSFT 2000` - Neue Aktie prüfen
5. `/long MSFT 1000` - Knockout analysieren

*HINWEIS:*
Alle Analysen sind keine Finanzberatung.
Eigenes Research machen!
"""

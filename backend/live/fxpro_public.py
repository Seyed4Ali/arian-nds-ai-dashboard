"""FxPro public quote adapter.

This adapter reads the public FxPro metals page. It is intended for monitoring/shadow
research only. FxPro labels the website prices as indicative; it is NOT a replacement
for authenticated MT5 ticks when execution-grade data is required.
"""
from __future__ import annotations
import re, time
from dataclasses import dataclass
from datetime import datetime, timezone
import requests

URL = "https://www.fxpro.com/trading/metals"

@dataclass(frozen=True)
class Quote:
    symbol: str
    bid: float
    ask: float
    timestamp_utc: str
    source: str = "FxPro public metals page"
    indicative: bool = True

class FxProPublicQuoteError(RuntimeError):
    pass

class FxProPublicQuote:
    def __init__(self, timeout: float = 10.0, session=None):
        self.timeout = timeout
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": "Arian-NDS-AI/phase5 research client"})

    def get_gold(self) -> Quote:
        r = self.session.get(URL, timeout=self.timeout)
        r.raise_for_status()
        text = re.sub(r"\\s+", " ", r.text)
        # Prefer the market ticker occurrence: GOLD <number> / <number> Trade.
        m = re.search(r"GOLD\s+([0-9]+(?:\.[0-9]+)?)\s*/\s*([0-9]+(?:\.[0-9]+)?)\s+Trade", text, re.I)
        if not m:
            # Fallback to the table row: GOLD SPOT ... bid ask
            m = re.search(r"GOLD\s+SPOT.*?([0-9]+(?:\.[0-9]+)?)\s+([0-9]+(?:\.[0-9]+)?)", text, re.I)
        if not m:
            raise FxProPublicQuoteError("Could not parse GOLD quote from FxPro public page")
        first, second = float(m.group(1)), float(m.group(2))
        if first <= 0 or second <= 0:
            raise FxProPublicQuoteError(f"Invalid GOLD quote: {first}/{second}")
        # FxPro public ticker is displayed as sell / buy.
        ask, bid = first, second
        return Quote("GOLD", bid, ask, datetime.now(timezone.utc).isoformat())


def poll(interval_seconds: float = 5.0, once: bool = False):
    feed = FxProPublicQuote()
    while True:
        q = feed.get_gold()
        print(f"{q.timestamp_utc} {q.symbol} bid={q.bid:.2f} ask={q.ask:.2f} spread={q.ask-q.bid:.2f}")
        if once:
            return q
        time.sleep(interval_seconds)

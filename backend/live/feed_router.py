from __future__ import annotations
from dataclasses import dataclass
from .fxpro_public import FxProPublicQuote, Quote

@dataclass
class FeedStatus:
    connected: bool = False
    source: str = "none"
    last_error: str | None = None
    last_quote: Quote | None = None

class LiveFeedRouter:
    """Phase-5 router: FxPro public quote first; MT5 adapter remains available for VPS."""
    def __init__(self):
        self.fxpro = FxProPublicQuote()
        self.status = FeedStatus()

    def quote(self) -> Quote:
        try:
            q = self.fxpro.get_gold()
            self.status = FeedStatus(True, q.source, None, q)
            return q
        except Exception as exc:
            self.status = FeedStatus(False, "FxPro public metals page", str(exc), None)
            raise

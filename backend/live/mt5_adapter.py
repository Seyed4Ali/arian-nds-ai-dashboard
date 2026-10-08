from __future__ import annotations
import os
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any

@dataclass
class Tick:
    symbol: str
    time: datetime
    bid: float
    ask: float
    last: float
    volume: float = 0.0

class MT5Adapter:
    """Read-only/live-data adapter. It never sends orders in Phase 4."""
    def __init__(self, path: str|None=None, login: int|None=None, password: str|None=None, server: str|None=None):
        self.path = path or os.getenv("MT5_PATH")
        self.login = int(login or os.getenv("MT5_LOGIN", "0"))
        self.password = password if password is not None else os.getenv("MT5_PASSWORD", "")
        self.server = server or os.getenv("MT5_SERVER", "")
        self.mt5 = None
        self.connected = False
        self.last_error = None

    def connect(self) -> bool:
        try:
            import MetaTrader5 as mt5
        except ImportError:
            self.last_error = "MetaTrader5 Python package is not installed. Run: pip install MetaTrader5 on the Windows VPS."
            return False
        self.mt5 = mt5
        kwargs = {}
        if self.login: kwargs["login"] = self.login
        if self.password: kwargs["password"] = self.password
        if self.server: kwargs["server"] = self.server
        if self.path: kwargs["path"] = self.path
        ok = mt5.initialize(**kwargs)
        if not ok:
            self.last_error = str(mt5.last_error())
            self.connected = False
            return False
        self.connected = True
        self.last_error = None
        return True

    def ensure(self) -> bool:
        if self.connected and self.mt5 is not None:
            info = self.mt5.terminal_info()
            if info is not None and getattr(info, "connected", False):
                return True
        return self.connect()

    def symbol_select(self, symbol: str) -> bool:
        if not self.ensure(): return False
        return bool(self.mt5.symbol_select(symbol, True))

    def tick(self, symbol: str) -> Tick|None:
        if not self.symbol_select(symbol): return None
        t = self.mt5.symbol_info_tick(symbol)
        if t is None:
            self.last_error = str(self.mt5.last_error())
            return None
        ts = datetime.fromtimestamp(float(t.time), tz=timezone.utc)
        return Tick(symbol, ts, float(t.bid), float(t.ask), float(getattr(t, "last", 0.0)), float(getattr(t, "volume", 0.0)))

    def rates(self, symbol: str, timeframe: str="M5", count: int=300):
        if not self.symbol_select(symbol): return []
        tf = getattr(self.mt5, f"TIMEFRAME_{timeframe}", None)
        if tf is None: raise ValueError(f"Unsupported MT5 timeframe: {timeframe}")
        rates = self.mt5.copy_rates_from_pos(symbol, tf, 0, count)
        if rates is None: return []
        return rates

    def status(self) -> dict[str, Any]:
        if not self.ensure():
            return {"connected": False, "error": self.last_error}
        ti = self.mt5.terminal_info()
        ai = self.mt5.account_info()
        return {
            "connected": bool(ti and getattr(ti, "connected", False)),
            "terminal": getattr(ti, "name", None),
            "company": getattr(ti, "company", None),
            "server": getattr(ai, "server", self.server) if ai else self.server,
            "login": getattr(ai, "login", self.login) if ai else self.login,
            "trade_allowed": bool(getattr(ti, "trade_allowed", False)) if ti else False,
            "error": self.last_error,
        }

    def shutdown(self):
        if self.mt5 is not None:
            self.mt5.shutdown()
        self.connected = False

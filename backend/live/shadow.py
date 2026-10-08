from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
import json
import sqlite3
import threading
import uuid


@dataclass
class ShadowPosition:
    id: str
    symbol: str
    direction: str
    entry: float
    stop_loss: float
    take_profit: float
    risk_percent: float
    volume: float
    opened_at: str
    current: float
    unrealized_pnl: float
    r_multiple: float
    status: str = "OPEN"


class ShadowBroker:
    def __init__(
        self,
        db_path="data/live_shadow.sqlite",
        starting_balance=1000.0,
        contract_size=100.0,
    ):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        self.db_path = db_path
        self.starting_balance = float(starting_balance)
        self.balance = self.starting_balance
        self.contract_size = float(contract_size)

        self.positions = {}
        self.lock = threading.Lock()

        self._init_db()

    def _conn(self):
        return sqlite3.connect(
            self.db_path,
            check_same_thread=False,
        )

    def _init_db(self):
        c = self._conn()
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS events(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT,
                type TEXT,
                payload TEXT
            )
            """
        )
        c.commit()
        c.close()

    def event(self, typ, payload):
        c = self._conn()
        c.execute(
            "INSERT INTO events(ts,type,payload) VALUES(?,?,?)",
            (
                datetime.now(timezone.utc).isoformat(),
                typ,
                json.dumps(payload, default=str),
            ),
        )
        c.commit()
        c.close()

    def _lots_for_risk(self, entry, stop_loss, risk_percent):
        risk_amount = self.balance * float(risk_percent) / 100.0
        risk_per_lot = (
            abs(float(entry) - float(stop_loss)) * self.contract_size
        )

        if risk_per_lot <= 0:
            return 0.0

        return risk_amount / risk_per_lot

    def open(
        self,
        symbol,
        direction,
        entry,
        sl,
        tp,
        risk_percent,
        volume=None,
    ):
        with self.lock:
            entry = float(entry)
            sl = float(sl)
            tp = float(tp)
            risk_percent = float(risk_percent)

            if volume is None:
                volume = self._lots_for_risk(
                    entry,
                    sl,
                    risk_percent,
                )

            volume = float(volume)

            if volume <= 0:
                raise ValueError(
                    "Cannot open shadow position: calculated volume is zero."
                )

            pid = str(uuid.uuid4())[:8]

            p = ShadowPosition(
                pid,
                symbol,
                direction,
                entry,
                sl,
                tp,
                risk_percent,
                volume,
                datetime.now(timezone.utc).isoformat(),
                entry,
                0.0,
                0.0,
            )

            self.positions[pid] = p
            self.event("SHADOW_OPEN", asdict(p))

            return p

    def update(self, symbol, bid, ask):
        closed = []

        with self.lock:
            for pid, p in list(self.positions.items()):
                if p.symbol != symbol:
                    continue

                px = bid if p.direction == "LONG" else ask
                px = float(px)

                p.current = px

                risk_distance = abs(
                    p.entry - p.stop_loss
                )

                if p.direction == "LONG":
                    pnl = (
                        (px - p.entry)
                        * p.volume
                        * self.contract_size
                    )
                    p.r_multiple = (
                        (px - p.entry) / risk_distance
                        if risk_distance
                        else 0.0
                    )
                else:
                    pnl = (
                        (p.entry - px)
                        * p.volume
                        * self.contract_size
                    )
                    p.r_multiple = (
                        (p.entry - px) / risk_distance
                        if risk_distance
                        else 0.0
                    )

                p.unrealized_pnl = float(pnl)

                hit_sl = (
                    bid <= p.stop_loss
                    if p.direction == "LONG"
                    else ask >= p.stop_loss
                )

                hit_tp = (
                    bid >= p.take_profit
                    if p.direction == "LONG"
                    else ask <= p.take_profit
                )

                if hit_sl or hit_tp:
                    p.status = (
                        "TP"
                        if hit_tp and not hit_sl
                        else "SL"
                    )

                    p.current = float(
                        p.take_profit
                        if p.status == "TP"
                        else p.stop_loss
                    )

                    if p.direction == "LONG":
                        p.unrealized_pnl = (
                            (p.current - p.entry)
                            * p.volume
                            * self.contract_size
                        )
                    else:
                        p.unrealized_pnl = (
                            (p.entry - p.current)
                            * p.volume
                            * self.contract_size
                        )

                    p.r_multiple = (
                        p.unrealized_pnl
                        / (
                            p.risk_percent
                            * 0.01
                            * self.balance
                        )
                        if p.risk_percent > 0 and self.balance > 0
                        else 0.0
                    )

                    self.balance += p.unrealized_pnl

                    self.event(
                        "SHADOW_CLOSE",
                        asdict(p),
                    )

                    closed.append(p)
                    del self.positions[pid]

        return closed

    def snapshot(self):
        with self.lock:
            floating = sum(
                p.unrealized_pnl
                for p in self.positions.values()
            )

            return {
                "starting_balance": self.starting_balance,
                "balance": self.balance,
                "equity": self.balance + floating,
                "floating_pnl": floating,
                "contract_size": self.contract_size,
                "positions": [
                    asdict(p)
                    for p in self.positions.values()
                ],
            }

from __future__ import annotations
import threading, time, os
from dataclasses import asdict
from datetime import datetime, timezone
import pandas as pd
from backend.nds_core import Bar, build_candidate
from ai.features import candidate_features
from ai.decision import BaselineDecisionModel
from .mt5_adapter import MT5Adapter
from .shadow import ShadowBroker

class LiveEngine:
    def __init__(self, config):
        self.cfg=config
        self.symbol=self.cfg["symbols"][0]
        self.tf=self.cfg["timeframes"][0]
        self.adapter=MT5Adapter()
        self.shadow=ShadowBroker(starting_balance=self.cfg["demo"]["starting_balance"])
        self.model=BaselineDecisionModel(min_probability=0.60)
        self.running=False; self.thread=None; self.lock=threading.Lock()
        self.state={"mode":"LIVE_DEMO","real_trading":False,"symbol":self.symbol,"timeframe":self.tf,"connection":{"connected":False},"tick":None,"candidate":None,"features":None,"decision":None,"last_error":None,"updated_at":None}
        self.last_signal_key=None

    def _bars(self):
        raw=self.adapter.rates(self.symbol,self.tf,300)
        bars=[]
        for r in raw:
            bars.append(Bar(datetime.fromtimestamp(int(r["time"]),tz=timezone.utc),float(r["open"]),float(r["high"]),float(r["low"]),float(r["close"])))
        return bars

    def step(self):
        self.state["connection"]=self.adapter.status()
        tick=self.adapter.tick(self.symbol)
        if tick is None:
            self.state["last_error"]=self.adapter.last_error; return
        self.state["tick"]={"symbol":tick.symbol,"time":tick.time.isoformat(),"bid":tick.bid,"ask":tick.ask,"spread":tick.ask-tick.bid,"last":tick.last}
        self.shadow.update(self.symbol,tick.bid,tick.ask)
        bars=self._bars()
        if len(bars)<60: return
        # Exclude the currently-forming bar when constructing a decision.
        closed=bars[:-1] if len(bars)>1 else bars
        c=build_candidate(closed, symbol=self.symbol, timeframe=self.tf,
            min_candles=self.cfg["nds"]["min_correction_candles"], window=self.cfg["nds"]["ha_scan_bars"],
            entry_fib=self.cfg["nds"]["entry_fib"],sl_fib=self.cfg["nds"]["sl_fib"],tp_fib=self.cfg["nds"]["tp_fib"],
            min_cycle_atr_mult=self.cfg["nds"]["min_cycle_atr_mult"],fast_ema=self.cfg["nds"]["fast_ema"],slow_ema=self.cfg["nds"]["slow_ema"],use_trend_filter=self.cfg["nds"]["use_trend_filter"])
        self.state["candidate"]=asdict(c) if c else None
        if not c: self.state["decision"]={"decision":"WAIT","probability":0.0,"expected_r":0.0,"confidence":0.0,"model_version":"baseline-rule-v0"}; return
        f=candidate_features(c,closed); f["spread_price"]=float(tick.ask-tick.bid); f["max_spread_points"]=self.cfg["execution"]["max_spread_points"]
        d=self.model.predict(f); self.state["features"]=f; self.state["decision"]=asdict(d)
        key=f"{c.cycle_id}:{c.direction}:{c.entry:.5f}"
        if d.decision=="TAKE" and key!=self.last_signal_key:
            # Shadow only: never mt5.order_send().
            self.shadow.open(self.symbol,c.direction,tick.ask if c.direction=="LONG" else tick.bid,c.stop_loss,c.take_profit,self.cfg["risk"]["default_percent"],1.0)
            self.last_signal_key=key

    def loop(self):
        while self.running:
            try: self.step()
            except Exception as e: self.state["last_error"]=repr(e)
            self.state["updated_at"]=datetime.now(timezone.utc).isoformat()
            time.sleep(2)

    def start(self):
        if self.running:return
        self.running=True; self.thread=threading.Thread(target=self.loop,daemon=True); self.thread.start()
    def stop(self): self.running=False
    def snapshot(self):
        with self.lock:
            s=dict(self.state); s["shadow"]=self.shadow.snapshot(); return s

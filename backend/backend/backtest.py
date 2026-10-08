from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional, Iterable
import math
import pandas as pd

from .nds_core import Bar, TradeCandidate


def _ha_series_v7(bars_oldest_to_newest: list[Bar], now_idx: int, window: int):
    # Exact conceptual equivalent of v7 FindCycle(1, window,...):
    # real MT5 indices are newest=0; v7 builds k=0 from real nowIdx+window
    # down to nowIdx+1, i.e. oldest -> newest closed bar.
    selected = bars_oldest_to_newest[-(window + 1):-1] if now_idx == 1 else None
    return selected


def find_cycle_v7(closed_bars: list[Bar], min_candles: int = 2, window: int = 60):
    """Mirror v7 FindCycle using only completed bars.

    closed_bars must be oldest -> newest and must NOT include the current open bar.
    The v7 call uses MT5 nowIdx=1, therefore its newest input is shift 1.
    """
    bars = len(closed_bars)
    if bars < min_candles + 3:
        return None
    w = min(window, bars - 1)
    if w < min_candles + 2:
        return None
    data = closed_bars[-w:]
    ha_open, ha_close = [], []
    for k, b in enumerate(data):
        hc = (b.open + b.high + b.low + b.close) / 4.0
        ho = (b.open + b.close) / 2.0 if k == 0 else (ha_open[k-1] + ha_close[k-1]) / 2.0
        ha_open.append(ho); ha_close.append(hc)

    run_color = 0; run_len = 0; last_start = -1; last_color = 0
    for k in range(w):
        color = 1 if ha_close[k] > ha_open[k] else -1
        if color == run_color:
            run_len += 1
        else:
            run_color = color; run_len = 1
        if run_len == min_candles:
            last_start = k - min_candles + 1
            last_color = run_color
    if last_start < 0:
        return None

    # v7: runStartReal = nowIdx + window - lastRunStartK, nowIdx=1.
    # MT5 real index r maps to Python closed index len(closed)-1-r.
    run_start_real = 1 + w - last_start
    run_start_idx = len(closed_bars) - 1 - run_start_real
    prev_real = min(run_start_real + 1, len(closed_bars))
    prev_idx = len(closed_bars) - 1 - prev_real
    prev_idx = max(0, min(len(closed_bars)-1, prev_idx))

    if last_color == -1:
        p0 = closed_bars[prev_idx].high
        p0t = closed_bars[prev_idx].time
        segment = closed_bars[max(0, run_start_idx):]
        p1bar = min(segment, key=lambda x: x.low)
        p1 = p1bar.low; p1t = p1bar.time; long_setup = False
    else:
        p0 = closed_bars[prev_idx].low
        p0t = closed_bars[prev_idx].time
        segment = closed_bars[max(0, run_start_idx):]
        p1bar = max(segment, key=lambda x: x.high)
        p1 = p1bar.high; p1t = p1bar.time; long_setup = True
    return p0, p0t, p1, p1t, long_setup, run_start_real


def atr_v7(closed_bars: list[Bar], period: int = 14) -> Optional[float]:
    # v7 uses shifts 1..period and previous closes shift 2..period+1.
    if len(closed_bars) < period + 1:
        return None
    trs = []
    for i in range(len(closed_bars)-period, len(closed_bars)):
        b = closed_bars[i]
        pc = closed_bars[i-1].close
        trs.append(max(b.high-b.low, abs(b.high-pc), abs(b.low-pc)))
    return sum(trs) / period


def ema_last(values: list[float], period: int) -> Optional[float]:
    if len(values) < period:
        return None
    alpha = 2.0 / (period + 1)
    ema = values[0]
    for x in values[1:]:
        ema = alpha*x + (1-alpha)*ema
    return ema


def build_candidate_v7(closed_bars: list[Bar], symbol='XAUUSD', timeframe='M5',
                       min_candles=2, window=60, entry_fib=.864, sl_fib=1.272,
                       tp_fib=.600, min_cycle_atr_mult=.8, fast_ema=20,
                       slow_ema=50, use_trend_filter=True) -> Optional[TradeCandidate]:
    cyc = find_cycle_v7(closed_bars, min_candles, window)
    a = atr_v7(closed_bars, 14)
    if not cyc or a is None or a <= 0:
        return None
    p0,t0,p1,t1,long_setup,_ = cyc
    cycle_size = abs(p1-p0)
    if cycle_size < a*min_cycle_atr_mult:
        return None
    closes = [b.close for b in closed_bars]
    ef = ema_last(closes[-fast_ema:], fast_ema)
    es = ema_last(closes[-slow_ema:], slow_ema)
    if ef is None or es is None:
        return None
    close_price = closed_bars[-1].close
    trend = (close_price >= es and ef >= es) if long_setup else (close_price <= es and ef <= es)
    if use_trend_filter and not trend:
        return None
    r = cycle_size
    if long_setup:
        entry = p1-r*entry_fib; sl=p1-r*sl_fib; tp=p1-r*tp_fib
    else:
        entry = p1+r*entry_fib; sl=p1+r*sl_fib; tp=p1+r*tp_fib
    return TradeCandidate(symbol, timeframe, closed_bars[-1].time,
        'LONG' if long_setup else 'SHORT', f'{t0.isoformat()}-{t1.isoformat()}',
        p0,p1,t0,t1,cycle_size,entry,sl,tp,a,ef,es,trend,cycle_size/a)


@dataclass
class BacktestConfig:
    starting_balance: float = 1000.0
    risk_percent: float = 0.5
    max_spread_points: float = 80
    point_size: float = 0.01
    commission_per_lot: float = 0.0
    contract_size: float = 100.0
    slippage_points: float = 0.0
    pending_expiry_bars: int = 25
    ambiguous_policy: str = 'worst_case'
    allow_one_position: bool = True


@dataclass
class SimTrade:
    symbol: str
    direction: str
    signal_time: datetime
    entry_time: datetime
    exit_time: Optional[datetime]
    entry: float
    exit: Optional[float]
    sl: float
    tp: float
    lots: float
    risk_amount: float
    pnl: Optional[float]
    r_multiple: Optional[float]
    result: Optional[str]
    entry_reason: str
    bars_held: int = 0
    mfe_r: float = 0.0
    mae_r: float = 0.0


class EventDrivenBacktester:
    def __init__(self, cfg: BacktestConfig):
        self.cfg = cfg
        self.balance = cfg.starting_balance
        self.equity_curve = []
        self.trades: list[SimTrade] = []

    def _lots_for_risk(self, entry, sl, risk_amount):
        risk_per_lot = abs(entry-sl)*self.cfg.contract_size
        return 0.0 if risk_per_lot <= 0 else risk_amount/risk_per_lot

    def _touch(self, bar: Bar, trade: SimTrade):
        if trade.direction == 'LONG':
            sl_hit = bar.low <= trade.sl
            tp_hit = bar.high >= trade.tp
        else:
            sl_hit = bar.high >= trade.sl
            tp_hit = bar.low <= trade.tp
        if sl_hit and tp_hit:
            if self.cfg.ambiguous_policy == 'best_case': return 'TP', trade.tp
            return 'SL', trade.sl
        if tp_hit: return 'TP', trade.tp
        if sl_hit: return 'SL', trade.sl
        return None, None

    def run(self, bars: list[Bar], candidate_builder=build_candidate_v7):
        if len(bars) < 100:
            raise ValueError('Need at least 100 bars for EMA/ATR/cycle warmup.')
        pending = None
        open_trade = None
        last_cycle = None
        for i in range(100, len(bars)):
            bar = bars[i]
            history = bars[:i]  # bar i is the current bar; only prior completed bars are known at decision time.

            # Manage an existing trade with current bar.
            if open_trade:
                outcome, px = self._touch(bar, open_trade)
                open_trade.bars_held += 1
                risk_price = abs(open_trade.entry-open_trade.sl)
                if open_trade.direction == 'LONG':
                    mfe = (bar.high-open_trade.entry)/risk_price if risk_price else 0
                    mae = (bar.low-open_trade.entry)/risk_price if risk_price else 0
                else:
                    mfe = (open_trade.entry-bar.low)/risk_price if risk_price else 0
                    mae = (open_trade.entry-bar.high)/risk_price if risk_price else 0
                open_trade.mfe_r=max(open_trade.mfe_r,mfe); open_trade.mae_r=min(open_trade.mae_r,mae)
                if outcome:
                    open_trade.exit_time=bar.time; open_trade.exit=px
                    direction_mult = 1 if open_trade.direction=='LONG' else -1
                    open_trade.pnl=(px-open_trade.entry)*direction_mult*open_trade.lots*self.cfg.contract_size
                    open_trade.pnl -= self.cfg.commission_per_lot*open_trade.lots
                    open_trade.r_multiple=open_trade.pnl/open_trade.risk_amount if open_trade.risk_amount else 0
                    open_trade.result=outcome
                    self.balance += open_trade.pnl
                    self.trades.append(open_trade); open_trade=None

            # Pending order from prior signal.
            if pending and open_trade is None:
                pending['age'] += 1
                c = pending['candidate']
                if pending['direction']=='LONG': triggered = bar.low <= c.entry
                else: triggered = bar.high >= c.entry
                if triggered:
                    risk_amount=self.balance*self.cfg.risk_percent/100
                    lots=self._lots_for_risk(c.entry,c.stop_loss,risk_amount)
                    if lots > 0:
                        open_trade=SimTrade(c.symbol,c.direction,c.timestamp,bar.time,None,c.entry,c.entry,c.stop_loss,c.take_profit,lots,risk_amount,None,None,None,'PENDING')
                    pending=None
                elif pending['age'] >= self.cfg.pending_expiry_bars:
                    pending=None

            # New signal at current bar open, based strictly on history.
            if open_trade is None and pending is None:
                c = candidate_builder(history)
                if c and c.cycle_id != last_cycle:
                    last_cycle=c.cycle_id
                    # Approximate v7's current tick validation using current bar open as first observable price.
                    px=bar.open
                    valid_market = ((c.direction=='LONG' and px < c.take_profit and px > c.stop_loss and px >= c.entry) or
                                    (c.direction=='SHORT' and px > c.take_profit and px < c.stop_loss and px <= c.entry))
                    risk_amount=self.balance*self.cfg.risk_percent/100
                    lots=self._lots_for_risk(px if valid_market else c.entry,c.stop_loss,risk_amount)
                    if lots > 0:
                        if valid_market:
                            open_trade=SimTrade(c.symbol,c.direction,c.timestamp,bar.time,None,px,px,c.stop_loss,c.take_profit,lots,risk_amount,None,None,None,'MARKET')
                        else:
                            pending={'candidate':c,'direction':c.direction,'age':0}

            self.equity_curve.append({'time':bar.time,'balance':self.balance})
        if open_trade:
            self.trades.append(open_trade)
        return self

    def summary(self):
        closed=[t for t in self.trades if t.pnl is not None]
        pnls=[t.pnl for t in closed]
        rs=[t.r_multiple for t in closed]
        wins=[p for p in pnls if p>0]; losses=[p for p in pnls if p<0]
        eq=pd.Series([x['balance'] for x in self.equity_curve]) if self.equity_curve else pd.Series([self.balance])
        peak=eq.cummax(); dd=(eq-peak)/peak*100
        pf=sum(wins)/abs(sum(losses)) if losses else math.inf
        return {'starting_balance':self.cfg.starting_balance,'ending_balance':self.balance,
                'return_pct':(self.balance/self.cfg.starting_balance-1)*100,
                'trades':len(closed),'win_rate_pct':(len(wins)/len(closed)*100 if closed else 0),
                'profit_factor':pf,'expectancy_r':(sum(rs)/len(rs) if rs else 0),
                'max_drawdown_pct':abs(dd.min()) if len(dd) else 0}

    def trades_df(self): return pd.DataFrame([asdict(t) for t in self.trades])

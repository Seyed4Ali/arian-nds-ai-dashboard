from dataclasses import dataclass, asdict
from datetime import datetime
from math import inf
from typing import List, Optional

@dataclass
class Bar:
    time: datetime
    open: float
    high: float
    low: float
    close: float

@dataclass
class TradeCandidate:
    symbol: str
    timeframe: str
    timestamp: datetime
    direction: str
    cycle_id: str
    point0: float
    point1: float
    point0_time: datetime
    point1_time: datetime
    cycle_size: float
    entry: float
    stop_loss: float
    take_profit: float
    atr: float
    ema_fast: float
    ema_slow: float
    trend_aligned: bool
    cycle_atr_ratio: float


def heikin_ashi(bars: List[Bar]):
    out=[]
    for i,b in enumerate(bars):
        hc=(b.open+b.high+b.low+b.close)/4.0
        ho=(b.open+b.close)/2.0 if i==0 else (out[-1][0]+out[-1][1])/2.0
        out.append((ho,hc))
    return out


def sma_ema(values, period):
    if not values: return None
    alpha=2/(period+1)
    ema=values[0]
    for x in values[1:]: ema=alpha*x+(1-alpha)*ema
    return ema


def atr(bars: List[Bar], period=14):
    if len(bars)<period+1: return None
    trs=[]
    for i in range(1,len(bars)):
        b=bars[i]; pc=bars[i-1].close
        trs.append(max(b.high-b.low, abs(b.high-pc), abs(b.low-pc)))
    return sum(trs[-period:])/period


def find_cycle(bars: List[Bar], min_candles=2, window=60):
    if len(bars)<min_candles+3: return None
    data=bars[-(window+1):] if len(bars)>window+1 else bars[:]
    # Match EA's oldest -> newest HA calculation.
    ha=heikin_ashi(data)
    run_color=0; run_len=0; last_start=None; last_color=None
    for k,(ho,hc) in enumerate(ha):
        color=1 if hc>ho else -1
        if color==run_color: run_len+=1
        else: run_color=color; run_len=1
        if run_len==min_candles:
            last_start=k-min_candles+1; last_color=color
    if last_start is None: return None
    run_start=len(data)-1-last_start
    # run_start is expressed as bars-from-current; map to list index.
    # The EA's real index is reversed; equivalent current data index is len(data)-1-run_start.
    start_idx=len(data)-1-run_start
    prev_idx=max(0,start_idx-1)
    if last_color==-1:
        p0=data[prev_idx].high
        p0t=data[prev_idx].time
        segment=data[start_idx:]
        p1bar=min(segment,key=lambda x:x.low)
        p1=p1bar.low; p1t=p1bar.time; long_setup=False
    else:
        p0=data[prev_idx].low
        p0t=data[prev_idx].time
        segment=data[start_idx:]
        p1bar=max(segment,key=lambda x:x.high)
        p1=p1bar.high; p1t=p1bar.time; long_setup=True
    return p0,p0t,p1,p1t,long_setup


def fib_levels(p0,p1,long_setup,entry_fib=.864,sl_fib=1.272,tp_fib=.600):
    r=abs(p1-p0)
    if long_setup:
        return p1-r*entry_fib, p1-r*sl_fib, p1-r*tp_fib
    return p1+r*entry_fib, p1+r*sl_fib, p1+r*tp_fib


def build_candidate(bars: List[Bar], symbol="XAUUSD", timeframe="M5", min_candles=2, window=60,
                    entry_fib=.864, sl_fib=1.272, tp_fib=.600, min_cycle_atr_mult=.8,
                    fast_ema=20, slow_ema=50, use_trend_filter=True):
    cyc=find_cycle(bars,min_candles,window)
    a=atr(bars,14)
    if not cyc or a is None: return None
    p0,t0,p1,t1,long_setup=cyc
    cycle_size=abs(p1-p0)
    if cycle_size < a*min_cycle_atr_mult: return None
    closes=[b.close for b in bars]
    ef=sma_ema(closes[-fast_ema:],fast_ema)
    es=sma_ema(closes[-slow_ema:],slow_ema)
    trend=(closes[-1]>=es and ef>=es) if long_setup else (closes[-1]<=es and ef<=es)
    if use_trend_filter and not trend: return None
    entry,sl,tp=fib_levels(p0,p1,long_setup,entry_fib,sl_fib,tp_fib)
    return TradeCandidate(symbol,timeframe,bars[-1].time,"LONG" if long_setup else "SHORT",
                          f"{t0.isoformat()}-{t1.isoformat()}",p0,p1,t0,t1,cycle_size,entry,sl,tp,a,ef,es,trend,cycle_size/a)

from __future__ import annotations
from dataclasses import asdict
from typing import Optional
import pandas as pd
from .nds_core import Bar
from .backtest import build_candidate_v7


def bars_from_csv(path: str) -> list[Bar]:
    df=pd.read_csv(path)
    cols={c.lower():c for c in df.columns}
    required=['time','open','high','low','close']
    if not all(c in cols for c in required):
        raise ValueError(f'CSV must contain time, open, high, low, close. Got {list(df.columns)}')
    df=df.sort_values(cols['time']).reset_index(drop=True)
    return [Bar(pd.to_datetime(r[cols['time']]).to_pydatetime(),float(r[cols['open']]),float(r[cols['high']]),float(r[cols['low']]),float(r[cols['close']])) for _,r in df.iterrows()]


def generate_nds_signal_dataset(bars: list[Bar], horizon_bars: int=100):
    rows=[]
    for i in range(100, len(bars)-1):
        history=bars[:i]
        c=build_candidate_v7(history)
        if not c: continue
        future=bars[i:i+horizon_bars]
        entry=c.entry
        tp=c.take_profit; sl=c.stop_loss
        touched_entry=False; outcome=None; resolution_i=None
        for j,b in enumerate(future):
            if not touched_entry:
                touched_entry = (b.low <= entry if c.direction=='LONG' else b.high >= entry)
                if not touched_entry: continue
            sl_hit=(b.low<=sl if c.direction=='LONG' else b.high>=sl)
            tp_hit=(b.high>=tp if c.direction=='LONG' else b.low<=tp)
            if sl_hit and tp_hit:
                outcome='LOSS'  # conservative label
                resolution_i=j; break
            if tp_hit:
                outcome='WIN'; resolution_i=j; break
            if sl_hit:
                outcome='LOSS'; resolution_i=j; break
        if outcome is None:
            continue
        row=asdict(c)
        row.update({'outcome':outcome,'label':1 if outcome=='WIN' else 0,
                    'resolution_bars':resolution_i+1 if resolution_i is not None else None})
        rows.append(row)
    return pd.DataFrame(rows)

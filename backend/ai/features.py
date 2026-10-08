from __future__ import annotations
import math
from dataclasses import asdict
import pandas as pd
from backend.nds_core import Bar, TradeCandidate

FEATURE_COLUMNS = [
    'direction_long','cycle_size','atr','cycle_atr_ratio','ema_fast','ema_slow','trend_aligned',
    'entry_distance_atr','sl_distance_atr','tp_distance_atr','rr','close_to_ema_fast_atr',
    'ema_gap_atr','hour','day_of_week'
]

def candidate_features(c: TradeCandidate, bars: list[Bar]) -> dict:
    last = bars[-1]
    atr = max(c.atr, 1e-12)
    entry_dist = abs(last.close-c.entry)/atr
    sl_dist = abs(c.entry-c.stop_loss)/atr
    tp_dist = abs(c.take_profit-c.entry)/atr
    rr = tp_dist/sl_dist if sl_dist else 0.0
    return {
        'direction_long': int(c.direction == 'LONG'),
        'cycle_size': c.cycle_size,
        'atr': c.atr,
        'cycle_atr_ratio': c.cycle_atr_ratio,
        'ema_fast': c.ema_fast,
        'ema_slow': c.ema_slow,
        'trend_aligned': int(c.trend_aligned),
        'entry_distance_atr': entry_dist,
        'sl_distance_atr': sl_dist,
        'tp_distance_atr': tp_dist,
        'rr': rr,
        'close_to_ema_fast_atr': abs(last.close-c.ema_fast)/atr,
        'ema_gap_atr': abs(c.ema_fast-c.ema_slow)/atr,
        'hour': last.time.hour,
        'day_of_week': last.time.weekday(),
    }

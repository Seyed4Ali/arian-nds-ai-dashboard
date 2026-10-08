from datetime import datetime, timedelta
from backend.backtest import find_cycle_v7, build_candidate_v7, EventDrivenBacktester, BacktestConfig
from backend.nds_core import Bar


def make_bars(n=180):
    out=[]; price=2000.0
    t=datetime(2026,1,1)
    for i in range(n):
        drift=0.8 if i%20<10 else -0.5
        o=price; c=price+drift; h=max(o,c)+1.0; l=min(o,c)-1.0
        out.append(Bar(t,o,h,l,c)); price=c; t+=timedelta(minutes=5)
    return out


def test_v7_cycle_is_deterministic():
    bars=make_bars()
    a=find_cycle_v7(bars[:-1],2,60)
    b=find_cycle_v7(bars[:-1],2,60)
    assert a==b


def test_backtester_runs():
    bars=make_bars()
    bt=EventDrivenBacktester(BacktestConfig())
    bt.run(bars)
    assert len(bt.equity_curve)>0
    assert bt.balance==bt.equity_curve[-1]['balance'] or bt.balance>=0

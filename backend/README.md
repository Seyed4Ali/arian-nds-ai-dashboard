# Arian NDS Adaptive AI — Phase 1

This repository is the first implementation pass of the NDS adaptive-agent architecture.

## Current scope
- v7 is the baseline NDS implementation.
- v6.1 is preserved as a reference baseline.
- Deterministic Heikin-Ashi cycle detection matching the supplied EA logic.
- Fibonacci entry/SL/TP calculation.
- EMA trend filter and ATR cycle-size filter.
- Structured `TradeCandidate` objects.
- Safe configuration with live-real trading disabled.
- Backtest/ML/dashboard modules are scaffolded for the next phases.

## Safety
`LIVE_DEMO_MODE=true` and `LIVE_REAL_TRADING=false` are the intended defaults.
A mobile browser is only the monitoring/control client. MT5 Desktop + the Python backend must run on a VPS/always-on host for continuous live-market operation.

## Phase 2 — Event-driven backtesting
- Exact v7-style cycle reconstruction using completed bars only.
- v7 ATR/EMA filters aligned with the supplied EA.
- Event-driven pending/market demo execution model.
- Conservative same-bar SL/TP ambiguity handling.
- Risk-based position sizing.
- Trade-level MFE/MAE/R tracking.
- Signal dataset generation with TP-before-SL labels.
- CSV input CLI: `python backtesting_cli.py --csv <ohlcv.csv>`.

### Expected OHLCV CSV
Required columns: `time,open,high,low,close`. Optional volume columns are ignored.

### Important
The backtester is deliberately conservative where OHLC data cannot reveal intrabar order. For production validation, use tick/intrabar data and broker-specific symbol specifications.

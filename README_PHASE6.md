# Arian NDS AI — Phase 6

This package contains:
- `frontend/` — GitHub Pages dashboard.
- `backend/` — FastAPI shadow backend + Phase-5 NDS/AI/MT5 code.
- `frontend/.github/workflows/pages.yml` — GitHub Pages deployment workflow.

Important:
- Real trading remains disabled.
- The public FxPro quote is indicative and is for monitoring/shadow research.
- NDS requires closed-candle market data; the public quote alone must not be used to invent NDS signals.
- For execution-grade candles/ticks, run the backend with MT5 on a Windows machine/VPS.

## GitHub Pages
Copy the contents of `frontend/` into the repository root, preserving `.github/workflows/pages.yml`.
Then set GitHub Pages Source to `GitHub Actions`.

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pathlib import Path

from live.config_loader import load_config
from live.engine import LiveEngine
from live.feed_router import LiveFeedRouter

app = FastAPI(title="Arian NDS Adaptive AI", version="0.5.1")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

config = load_config()
engine = LiveEngine(config)
feed_router = LiveFeedRouter()

@app.on_event("startup")
def startup():
    # Engine is deliberately NOT started automatically on a public host.
    # Start it only where MT5 is available.
    pass

@app.on_event("shutdown")
def shutdown():
    engine.stop()
    try:
        engine.adapter.shutdown()
    except Exception:
        pass

@app.get("/health")
def health():
    return {
        "status": "ok",
        "mode": "SHADOW",
        "real_trading": False,
        "engine_running": engine.running,
    }

@app.get("/api/live/quote")
def live_quote():
    try:
        q = feed_router.quote()
        return {
            "ok": True,
            "symbol": q.symbol,
            "bid": q.bid,
            "ask": q.ask,
            "spread": q.ask - q.bid,
            "timestamp_utc": q.timestamp_utc,
            "source": q.source,
            "indicative": q.indicative,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}

@app.get("/api/status")
def status():
    return engine.snapshot()

@app.post("/api/demo/start")
def start_demo():
    engine.start()
    return {"ok": True, "mode": "SHADOW", "real_trading": False}

@app.post("/api/demo/stop")
def stop_demo():
    engine.stop()
    return {"ok": True, "mode": "SHADOW", "running": False, "real_trading": False}

@app.get("/", response_class=HTMLResponse)
def root():
    return HTMLResponse(
        "<html><body><h3>Arian NDS AI API</h3>"
        "<p>Use /health, /api/live/quote and /api/status.</p>"
        "<p>Real trading is permanently disabled in this build.</p></body></html>"
    )

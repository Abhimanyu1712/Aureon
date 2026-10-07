from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.analytics import router as analytics_router
from app.api.backtest import router as backtest_router
from app.api.signals import router as signals_router
from app.ingest.status import get_data_status

app = FastAPI(
    title="Aureon API",
    description="Commodity Derivatives Intelligence for MCX Gold",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://aureon-livid.vercel.app",
],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analytics_router)
app.include_router(signals_router)
app.include_router(backtest_router)

@app.get("/api/health")
def health_check():
    return {"status": "ok", "message": "Aureon API is running"}


@app.get("/api/data/status")
def data_status():
    return get_data_status()

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter

from app.backtest.service import (
    get_benchmark,
    get_equity,
    get_report,
    get_summary,
    get_trades,
)


router = APIRouter(prefix="/api/backtest", tags=["backtest"])
SourceType = Literal["DEMO", "REAL"]


def _response(data: object | None, source_type: SourceType) -> dict:
    return {
        "status": "AVAILABLE" if data is not None else "NO_BACKTEST_DATA",
        "data_type": "DEMO / SYNTHETIC DATA" if source_type == "DEMO" else "REAL/HISTORICAL",
        "data": data,
    }


@router.get("/summary")
def backtest_summary(source_type: SourceType = "DEMO") -> dict:
    return _response(get_summary(source_type), source_type)


@router.get("/trades")
def backtest_trades(source_type: SourceType = "DEMO") -> dict:
    return _response(get_trades(source_type), source_type)


@router.get("/equity")
def backtest_equity(source_type: SourceType = "DEMO") -> dict:
    return _response(get_equity(source_type), source_type)


@router.get("/benchmark")
def backtest_benchmark(source_type: SourceType = "DEMO") -> dict:
    return _response(get_benchmark(source_type), source_type)


@router.get("/report")
def backtest_report(source_type: SourceType = "DEMO") -> dict:
    return _response(get_report(source_type), source_type)
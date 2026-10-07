from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from app.analytics.normalization import get_contract_spec
from app.analytics.signal_service import get_signal_records, supported_signal_statuses


router = APIRouter(prefix="/api/analytics/signals", tags=["signals"])
SourceType = Literal["DEMO", "REAL"]
SignalStatus = Literal[
    "STRONG_RELATIVE_DEVIATION",
    "WATCHLIST",
    "NO_SIGNAL",
    "INSUFFICIENT_HISTORY",
    "INSUFFICIENT_PEERS",
    "INSUFFICIENT_LIQUIDITY",
    "EXPIRY_FILTER_FAILED",
]


def _payload(source_type: SourceType, records: list[dict]) -> dict:
    return {
        "status": "AVAILABLE" if records else "NO_SIGNAL_DATA",
        "data_type": "DEMO" if source_type == "DEMO" else "REAL/HISTORICAL",
        "record_count": len(records),
        "records": records,
    }


def _records(
    source_type: SourceType,
    symbol: str | None,
    trading_date: date | None,
    expiry_date: date | None,
    status: SignalStatus | None,
) -> dict:
    if status is not None and status not in supported_signal_statuses():
        raise HTTPException(status_code=422, detail="Unsupported signal status")
    return _payload(
        source_type,
        get_signal_records(
            source_type=source_type,
            symbol=symbol,
            trading_date=trading_date,
            expiry_date=expiry_date,
            signal_status=status,
        ),
    )


@router.get("")
def all_signals(
    source_type: SourceType = "DEMO",
    date_filter: date | None = Query(default=None, alias="date"),
    expiry_date: date | None = None,
    status: SignalStatus | None = None,
) -> dict:
    return _records(source_type, None, date_filter, expiry_date, status)


@router.get("/{symbol}")
def signals_for_symbol(
    symbol: str,
    source_type: SourceType = "DEMO",
    date_filter: date | None = Query(default=None, alias="date"),
    expiry_date: date | None = None,
    status: SignalStatus | None = None,
) -> dict:
    normalized_symbol = symbol.strip().upper()
    try:
        get_contract_spec(normalized_symbol)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _records(source_type, normalized_symbol, date_filter, expiry_date, status)
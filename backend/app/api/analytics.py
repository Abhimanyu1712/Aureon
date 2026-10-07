from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException

from app.analytics.normalization import get_contract_spec
from app.analytics.service import get_normalized_records, get_relative_value_records


router = APIRouter(prefix="/api/analytics", tags=["analytics"])
SourceType = Literal["DEMO", "REAL"]


def _payload(source_type: SourceType, records: list[dict]) -> dict:
    return {
        "status": "AVAILABLE" if records else "NO_ANALYTICS_DATA",
        "data_type": "DEMO" if source_type == "DEMO" else "REAL/HISTORICAL",
        "record_count": len(records),
        "records": records,
    }


@router.get("/normalized")
def normalized_data(source_type: SourceType = "DEMO") -> dict:
    return _payload(source_type, get_normalized_records(source_type))


@router.get("/relative-value")
def relative_value_data(source_type: SourceType = "DEMO") -> dict:
    return _payload(source_type, get_relative_value_records(source_type))


@router.get("/relative-value/{symbol}")
def relative_value_for_symbol(symbol: str, source_type: SourceType = "DEMO") -> dict:
    normalized_symbol = symbol.strip().upper()
    try:
        get_contract_spec(normalized_symbol)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    records = [
        row
        for row in get_relative_value_records(source_type)
        if row["symbol"] == normalized_symbol
    ]
    return _payload(source_type, records)
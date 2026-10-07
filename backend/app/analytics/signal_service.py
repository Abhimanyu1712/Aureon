from __future__ import annotations

import csv
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from app.analytics.signal_pipeline import ANALYTICS_DIR


NUMERIC_FIELDS = {
    "normalized_price",
    "peer_reference",
    "spread",
    "z_score",
    "volume",
    "open_interest",
}
INTEGER_FIELDS = {"peer_count", "days_to_expiry", "rolling_history_count"}


def get_signal_records(
    *,
    source_type: str = "DEMO",
    symbol: str | None = None,
    trading_date: date | None = None,
    expiry_date: date | None = None,
    signal_status: str | None = None,
) -> list[dict[str, Any]]:
    source_type = source_type.strip().upper()
    if source_type not in {"DEMO", "REAL"}:
        raise ValueError("source_type must be DEMO or REAL")
    records: list[dict[str, Any]] = []
    for path in sorted(ANALYTICS_DIR.glob("*_signals.csv")):
        with path.open("r", encoding="utf-8-sig", newline="") as source:
            for raw in csv.DictReader(source):
                if raw.get("source_type") != source_type:
                    continue
                if symbol and raw.get("symbol") != symbol.strip().upper():
                    continue
                if trading_date and raw.get("trade_date") != trading_date.isoformat():
                    continue
                if expiry_date and raw.get("expiry_date") != expiry_date.isoformat():
                    continue
                if signal_status and raw.get("signal_status") != signal_status:
                    continue
                record: dict[str, Any] = dict(raw)
                for field in NUMERIC_FIELDS:
                    if record.get(field) == "":
                        record[field] = None
                    else:
                        try:
                            value = Decimal(record[field])
                            record[field] = float(value) if value.is_finite() else None
                        except (InvalidOperation, ValueError, TypeError):
                            record[field] = None
                for field in INTEGER_FIELDS:
                    try:
                        record[field] = int(record[field])
                    except (TypeError, ValueError):
                        record[field] = None
                records.append(record)
    return sorted(
        records,
        key=lambda row: (row["trade_date"], row["symbol"], row["expiry_date"]),
    )


def supported_signal_statuses() -> set[str]:
    return {
        "STRONG_RELATIVE_DEVIATION",
        "WATCHLIST",
        "NO_SIGNAL",
        "INSUFFICIENT_HISTORY",
        "INSUFFICIENT_PEERS",
        "INSUFFICIENT_LIQUIDITY",
        "EXPIRY_FILTER_FAILED",
    }
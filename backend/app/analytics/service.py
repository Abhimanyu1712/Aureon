from __future__ import annotations

import csv
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Literal

from app.analytics.normalization import CONTRACT_SPECS
from app.analytics.pipeline import PROJECT_ROOT


AnalyticsKind = Literal["normalized", "relative_value"]
ANALYTICS_DIR = PROJECT_ROOT / "data" / "analytics"
NUMERIC_FIELDS = {
    "close",
    "volume",
    "open_interest",
    "normalized_price_per_gram",
    "purity_adjusted_price_per_gram",
    "normalized_price",
    "peer_reference",
    "spread",
    "rolling_mean",
    "rolling_std",
    "z_score",
}


def read_analytics_records(kind: AnalyticsKind, source_type: str = "DEMO") -> list[dict[str, Any]]:
    normalized_source = source_type.strip().upper()
    if normalized_source not in {"DEMO", "REAL"}:
        raise ValueError("source_type must be DEMO or REAL")
    records: list[dict[str, Any]] = []
    for path in sorted(ANALYTICS_DIR.glob(f"*_{kind}.csv")):
        with path.open("r", encoding="utf-8-sig", newline="") as source:
            for raw in csv.DictReader(source):
                if raw.get("source_type") != normalized_source:
                    continue
                record: dict[str, Any] = dict(raw)
                for field in NUMERIC_FIELDS.intersection(record):
                    value = record[field]
                    if value == "":
                        record[field] = None
                    else:
                        try:
                            record[field] = float(Decimal(value))
                        except (InvalidOperation, ValueError):
                            record[field] = None
                if "peer_count" in record:
                    record["peer_count"] = int(record["peer_count"])
                records.append(record)
    return sorted(
        records,
        key=lambda row: (row["trade_date"], row["symbol"], row["expiry_date"]),
    )


def get_normalized_records(source_type: str = "DEMO") -> list[dict[str, Any]]:
    return read_analytics_records("normalized", source_type)


def get_relative_value_records(source_type: str = "DEMO") -> list[dict[str, Any]]:
    return read_analytics_records("relative_value", source_type)


def supported_symbols() -> set[str]:
    return set(CONTRACT_SPECS)
from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from app.analytics.normalization import normalize_price_to_purity_adjusted_rupees_per_gram
from app.analytics.relative_value import NormalizedObservation, RelativeValuePoint, calculate_relative_value
from app.ingest.schema import make_contract_id


PROJECT_ROOT = Path(__file__).resolve().parents[3]
NORMALIZED_COLUMNS = (
    "symbol",
    "trade_date",
    "expiry_date",
    "contract_id",
    "close",
    "volume",
    "open_interest",
    "normalized_price_per_gram",
    "purity_adjusted_price_per_gram",
    "source_type",
    "source_file",
)
RELATIVE_VALUE_COLUMNS = (
    "symbol",
    "trade_date",
    "expiry_date",
    "contract_id",
    "normalized_price",
    "peer_reference",
    "spread",
    "rolling_mean",
    "rolling_std",
    "z_score",
    "peer_count",
    "analytics_status",
    "source_type",
    "source_file",
)
REQUIRED_PROCESSED_COLUMNS = {
    "symbol",
    "trade_date",
    "expiry_date",
    "contract_id",
    "close",
    "volume",
    "open_interest",
    "source_type",
    "source_file",
}


class AnalyticsInputError(ValueError):
    pass


@dataclass(frozen=True)
class AnalyticsResult:
    source_file: str
    normalized_path: str
    relative_value_path: str
    total_rows: int
    ready_rows: int
    insufficient_peer_rows: int
    insufficient_history_rows: int
    zero_variance_rows: int
    source_types: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _parse_decimal(value: str, field: str, row_number: int) -> Decimal:
    try:
        result = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise AnalyticsInputError(f"Row {row_number}: {field} must be numeric.") from exc
    if not result.is_finite() or result < 0:
        raise AnalyticsInputError(f"Row {row_number}: {field} must be finite and non-negative.")
    return result


def _format_decimal(value: Decimal | None) -> str:
    if value is None:
        return ""
    return format(value, "f")


def _read_observations(input_path: Path) -> list[NormalizedObservation]:
    with input_path.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        headers = set(reader.fieldnames or ())
        missing = REQUIRED_PROCESSED_COLUMNS - headers
        if missing:
            raise AnalyticsInputError(
                "Stage 2 processed CSV is missing columns: " + ", ".join(sorted(missing))
            )
        observations: list[NormalizedObservation] = []
        for row_number, raw in enumerate(reader, start=2):
            try:
                symbol = (raw["symbol"] or "").strip()
                trade_date = date.fromisoformat((raw["trade_date"] or "").strip())
                expiry_date = date.fromisoformat((raw["expiry_date"] or "").strip())
            except (TypeError, ValueError) as exc:
                raise AnalyticsInputError(
                    f"Row {row_number}: symbol, trade_date and expiry_date are required and valid."
                ) from exc

            expected_contract_id = make_contract_id(symbol, expiry_date.isoformat())
            if raw["contract_id"] != expected_contract_id:
                raise AnalyticsInputError(
                    f"Row {row_number}: invalid contract identity; expected {expected_contract_id}."
                )
            source_type = (raw["source_type"] or "").strip().upper()
            if source_type not in {"DEMO", "REAL"}:
                raise AnalyticsInputError(
                    f"Row {row_number}: source_type must be DEMO or REAL."
                )

            close = _parse_decimal(raw["close"] or "", "close", row_number)
            volume = _parse_decimal(raw["volume"] or "", "volume", row_number)
            open_interest = _parse_decimal(raw["open_interest"] or "", "open_interest", row_number)
            try:
                normalized = normalize_price_to_purity_adjusted_rupees_per_gram(symbol, close)
            except ValueError as exc:
                raise AnalyticsInputError(f"Row {row_number}: {exc}") from exc

            observations.append(
                NormalizedObservation(
                    symbol=symbol,
                    trade_date=trade_date,
                    expiry_date=expiry_date,
                    contract_id=expected_contract_id,
                    normalized_price_per_gram=normalized.normalized_price_per_gram,
                    purity_adjusted_price_per_gram=normalized.purity_adjusted_price_per_gram,
                    close=close,
                    volume=volume,
                    open_interest=open_interest,
                    source_type=source_type,
                    source_file=raw["source_file"] or input_path.name,
                )
            )
    if not observations:
        raise AnalyticsInputError("Stage 2 processed CSV contains no data rows.")
    return observations


def _normalized_record(row: NormalizedObservation) -> dict[str, str]:
    return {
        "symbol": row.symbol,
        "trade_date": row.trade_date.isoformat(),
        "expiry_date": row.expiry_date.isoformat(),
        "contract_id": row.contract_id,
        "close": _format_decimal(row.close),
        "volume": _format_decimal(row.volume),
        "open_interest": _format_decimal(row.open_interest),
        "normalized_price_per_gram": _format_decimal(row.normalized_price_per_gram),
        "purity_adjusted_price_per_gram": _format_decimal(row.purity_adjusted_price_per_gram),
        "source_type": row.source_type,
        "source_file": row.source_file,
    }


def _relative_value_record(point: RelativeValuePoint) -> dict[str, str | int]:
    return {
        "symbol": point.symbol,
        "trade_date": point.trade_date.isoformat(),
        "expiry_date": point.expiry_date.isoformat(),
        "contract_id": point.contract_id,
        "normalized_price": _format_decimal(point.normalized_price),
        "peer_reference": _format_decimal(point.peer_reference),
        "spread": _format_decimal(point.spread),
        "rolling_mean": _format_decimal(point.rolling_mean),
        "rolling_std": _format_decimal(point.rolling_std),
        "z_score": _format_decimal(point.z_score),
        "peer_count": point.peer_count,
        "analytics_status": point.analytics_status,
        "source_type": point.source_type,
        "source_file": point.source_file,
    }


def _write_csv(path: Path, columns: tuple[str, ...], rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def run_analytics(
    input_path: str | Path,
    output_dir: str | Path | None = None,
    *,
    rolling_window: int = 5,
    min_periods: int = 3,
    min_peer_count: int = 2,
) -> AnalyticsResult:
    """Read Stage 2 output and write separate normalized and relative-value CSVs."""
    source_path = Path(input_path).expanduser().resolve()
    if not source_path.is_file():
        raise FileNotFoundError(f"Stage 2 processed CSV does not exist: {source_path}")
    observations = _read_observations(source_path)
    relative_points = calculate_relative_value(
        observations,
        rolling_window=rolling_window,
        min_periods=min_periods,
        min_peer_count=min_peer_count,
    )

    destination = (
        Path(output_dir).expanduser().resolve()
        if output_dir is not None
        else PROJECT_ROOT / "data" / "analytics"
    )
    destination.mkdir(parents=True, exist_ok=True)
    normalized_path = destination / f"{source_path.stem}_normalized.csv"
    relative_path = destination / f"{source_path.stem}_relative_value.csv"
    _write_csv(normalized_path, NORMALIZED_COLUMNS, [_normalized_record(row) for row in observations])
    _write_csv(
        relative_path,
        RELATIVE_VALUE_COLUMNS,
        [_relative_value_record(point) for point in relative_points],
    )

    statuses = [point.analytics_status for point in relative_points]
    return AnalyticsResult(
        source_file=source_path.name,
        normalized_path=str(normalized_path),
        relative_value_path=str(relative_path),
        total_rows=len(relative_points),
        ready_rows=statuses.count("READY"),
        insufficient_peer_rows=statuses.count("INSUFFICIENT_PEERS"),
        insufficient_history_rows=statuses.count("INSUFFICIENT_HISTORY"),
        zero_variance_rows=statuses.count("ZERO_VARIANCE"),
        source_types=tuple(sorted({row.source_type for row in observations})),
    )
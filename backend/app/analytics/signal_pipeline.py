from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from app.analytics.pipeline import PROJECT_ROOT
from app.analytics.signals import SignalConfig, SignalEngine, SignalEvidence, SignalResult


ANALYTICS_DIR = PROJECT_ROOT / "data" / "analytics"
SIGNAL_COLUMNS = (
    "symbol",
    "trade_date",
    "expiry_date",
    "contract_id",
    "normalized_price",
    "peer_reference",
    "spread",
    "z_score",
    "peer_count",
    "volume",
    "open_interest",
    "days_to_expiry",
    "rolling_history_count",
    "relative_direction",
    "signal_status",
    "cost_filter_status",
    "analytics_status",
    "source_type",
    "source_file",
    "explanation",
)
JOIN_FIELDS = ("source_type", "symbol", "trade_date", "expiry_date", "contract_id")
DECIMAL_FIELDS = (
    "normalized_price",
    "peer_reference",
    "spread",
    "z_score",
    "volume",
    "open_interest",
)


class SignalInputError(ValueError):
    pass


@dataclass(frozen=True)
class SignalPipelineResult:
    normalized_source: str
    relative_value_source: str
    output_path: str
    total_rows: int
    status_counts: dict[str, int]
    source_types: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def _decimal(value: str | None, field: str, key: tuple[str, ...]) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise SignalInputError(f"Invalid {field} in Stage 3 row {key}.") from exc
    if not result.is_finite():
        raise SignalInputError(f"Non-finite {field} in Stage 3 row {key}.")
    return result


def _key(row: dict[str, str]) -> tuple[str, ...]:
    try:
        return tuple(row[field] for field in JOIN_FIELDS)
    except KeyError as exc:
        raise SignalInputError(f"Stage 3 output is missing join field {exc.args[0]}.") from exc


def _signal_evidence(
    normalized: dict[str, str],
    relative: dict[str, str],
    history_count: int,
) -> SignalEvidence:
    key = _key(relative)
    try:
        trade_date = date.fromisoformat(relative["trade_date"])
        expiry_date = date.fromisoformat(relative["expiry_date"])
        peer_count = int(relative["peer_count"])
        analytics_status = relative["analytics_status"]
    except (KeyError, ValueError) as exc:
        raise SignalInputError(f"Invalid Stage 3 relative-value row {key}.") from exc

    values: dict[str, Decimal | None] = {}
    for field in DECIMAL_FIELDS:
        source_row = relative if field in {"normalized_price", "peer_reference", "spread", "z_score"} else normalized
        values[field] = _decimal(source_row.get(field), field, key)
    if values["normalized_price"] is None:
        raise SignalInputError(f"Stage 3 normalized price is missing for row {key}.")

    return SignalEvidence(
        symbol=relative["symbol"],
        trade_date=trade_date,
        expiry_date=expiry_date,
        contract_id=relative["contract_id"],
        normalized_price=values["normalized_price"],
        peer_reference=values["peer_reference"],
        spread=values["spread"],
        z_score=values["z_score"],
        peer_count=peer_count,
        volume=values["volume"],
        open_interest=values["open_interest"],
        rolling_history_count=history_count,
        analytics_status=analytics_status,
        source_type=relative["source_type"],
        source_file=relative.get("source_file") or normalized.get("source_file", ""),
    )


def _format(value: Decimal | None) -> str:
    return "" if value is None else format(value, "f")


def _record(result: SignalResult) -> dict[str, str | int]:
    return {
        "symbol": result.symbol,
        "trade_date": result.trade_date.isoformat(),
        "expiry_date": result.expiry_date.isoformat(),
        "contract_id": result.contract_id,
        "normalized_price": _format(result.normalized_price),
        "peer_reference": _format(result.peer_reference),
        "spread": _format(result.spread),
        "z_score": _format(result.z_score),
        "peer_count": result.peer_count,
        "volume": _format(result.volume),
        "open_interest": _format(result.open_interest),
        "days_to_expiry": result.days_to_expiry,
        "rolling_history_count": result.rolling_history_count,
        "relative_direction": result.relative_direction,
        "signal_status": result.signal_status,
        "cost_filter_status": result.cost_filter_status,
        "analytics_status": result.analytics_status,
        "source_type": result.source_type,
        "source_file": result.source_file,
        "explanation": result.explanation,
    }


def run_signal_pipeline(
    normalized_path: str | Path,
    relative_value_path: str | Path,
    output_path: str | Path | None = None,
    *,
    config: SignalConfig | None = None,
) -> SignalPipelineResult:
    normalized_file = Path(normalized_path).expanduser().resolve()
    relative_file = Path(relative_value_path).expanduser().resolve()
    if not normalized_file.is_file() or not relative_file.is_file():
        raise FileNotFoundError("Both Stage 3 normalized and relative-value CSVs must exist.")

    normalized_rows = _read_csv(normalized_file)
    relative_rows = _read_csv(relative_file)
    normalized_by_key: dict[tuple[str, ...], dict[str, str]] = {}
    for row in normalized_rows:
        key = _key(row)
        if key in normalized_by_key:
            raise SignalInputError(f"Duplicate Stage 3 normalized row {key}.")
        normalized_by_key[key] = row

    unmatched = set(normalized_by_key)
    indexed_relative: list[tuple[tuple[str, ...], dict[str, str]]] = []
    for row in relative_rows:
        key = _key(row)
        if key not in normalized_by_key:
            raise SignalInputError(f"No matching Stage 3 normalized row for {key}.")
        indexed_relative.append((key, row))
        unmatched.discard(key)
    if unmatched:
        raise SignalInputError(f"Stage 3 relative-value output is missing {len(unmatched)} normalized rows.")
    if not indexed_relative:
        raise SignalInputError("Stage 3 relative-value output contains no rows.")

    indexed_relative.sort(key=lambda pair: (pair[1]["source_type"], pair[1]["contract_id"], pair[1]["trade_date"]))
    engine = SignalEngine(config)
    history: dict[tuple[str, str], list[Decimal]] = {}
    output: list[SignalResult] = []
    for key, relative in indexed_relative:
        normalized = normalized_by_key[key]
        history_key = (relative["source_type"], relative["contract_id"])
        current_spread = _decimal(relative.get("spread"), "spread", key)
        history_count = len(history.get(history_key, []))
        if current_spread is not None:
            history_count = min(history_count + 1, engine.config.rolling_window)
        evidence = _signal_evidence(normalized, relative, history_count)
        result = engine.evaluate(evidence)
        output.append(result)
        spread = evidence.spread
        if spread is not None:
            history.setdefault(history_key, []).append(spread)
            if len(history[history_key]) > engine.config.rolling_window:
                history[history_key].pop(0)

    target_path = (
        Path(output_path).expanduser().resolve()
        if output_path is not None
        else ANALYTICS_DIR / f"{normalized_file.stem.removesuffix('_normalized')}_signals.csv"
    )
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with target_path.open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=SIGNAL_COLUMNS)
        writer.writeheader()
        writer.writerows(_record(result) for result in sorted(output, key=lambda item: (item.trade_date, item.symbol, item.expiry_date)))

    status_counts: dict[str, int] = {}
    for result in output:
        status_counts[result.signal_status] = status_counts.get(result.signal_status, 0) + 1
    return SignalPipelineResult(
        normalized_source=str(normalized_file),
        relative_value_source=str(relative_file),
        output_path=str(target_path),
        total_rows=len(output),
        status_counts=status_counts,
        source_types=tuple(sorted({result.source_type for result in output})),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Classify Stage 3 relative-value observations.")
    parser.add_argument("normalized_csv", help="Stage 3 normalized CSV")
    parser.add_argument("relative_value_csv", help="Stage 3 relative-value CSV")
    parser.add_argument("--output", help="Signals CSV path (default: data/analytics/*_signals.csv)")
    args = parser.parse_args()
    result = run_signal_pipeline(args.normalized_csv, args.relative_value_csv, args.output)
    print(json.dumps(result.to_dict(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
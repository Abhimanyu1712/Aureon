from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.ingest.parse import ParsedRow, parse_row
from app.ingest.schema import (
    OPTION_TYPE_ALIASES,
    PROCESSED_COLUMNS,
    REQUIRED_COLUMNS,
    SOURCE_TYPES,
    STRIKE_ALIASES,
    canonical_column_name,
    make_contract_id,
    normalize_header,
)
from app.ingest.validate import (
    ValidationIssue,
    add_duplicate_issues,
    collect_issues,
    missing_columns_issue,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]


@dataclass
class IngestResult:
    source_file: str
    source_type: str
    processed_path: str
    report_path: str
    total_rows: int
    valid_rows: int
    invalid_rows: int
    issues: list[ValidationIssue]
    invalid_row_details: list[dict[str, Any]]

    @property
    def errors(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "warning"]

    @property
    def is_valid(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_file": self.source_file,
            "source_type": self.source_type,
            "processed_path": self.processed_path,
            "report_path": self.report_path,
            "total_rows": self.total_rows,
            "valid_rows": self.valid_rows,
            "invalid_rows": self.invalid_rows,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "errors": [issue.to_dict() for issue in self.errors],
            "warnings": [issue.to_dict() for issue in self.warnings],
        }


def _source_type_for(path: Path, source_type: str | None) -> str:
    if source_type is not None:
        normalized = source_type.strip().upper()
        if normalized not in SOURCE_TYPES:
            raise ValueError(f"source_type must be one of: {', '.join(SOURCE_TYPES)}")
        return normalized
    try:
        path.resolve().relative_to((PROJECT_ROOT / "data" / "demo").resolve())
        return "DEMO"
    except ValueError:
        return "REAL"


def _canonical_records(
    reader: csv.DictReader,
) -> tuple[list[dict[str, Any]], list[str], str | None, str | None]:
    headers = reader.fieldnames or []
    canonical_headers = [canonical_column_name(header) for header in headers]
    missing = sorted(set(REQUIRED_COLUMNS) - set(canonical_headers))
    option_column = next(
        (header for header in headers if normalize_header(header) in OPTION_TYPE_ALIASES),
        None,
    )
    strike_column = next(
        (header for header in headers if normalize_header(header) in STRIKE_ALIASES),
        None,
    )
    records: list[dict[str, Any]] = []
    for row in reader:
        record: dict[str, Any] = {}
        for header, value in row.items():
            if header is not None:
                record[canonical_column_name(header)] = value
        records.append(record)
    return records, missing, option_column, strike_column


def _processed_record(row: ParsedRow, source_type: str, source_file: str) -> dict[str, Any]:
    assert row.symbol is not None
    assert row.trade_date is not None
    assert row.expiry_date is not None
    return {
        "symbol": row.symbol,
        "trade_date": row.trade_date.isoformat(),
        "expiry_date": row.expiry_date.isoformat(),
        "expiry_raw": row.expiry_raw,
        "contract_id": make_contract_id(row.symbol, row.expiry_date.isoformat()),
        "open": row.open,
        "high": row.high,
        "low": row.low,
        "close": row.close,
        "volume": row.volume,
        "open_interest": row.open_interest,
        "source_type": source_type,
        "source_file": source_file,
    }


def run_ingest(
    input_path: str | Path,
    output_dir: str | Path | None = None,
    source_type: str | None = None,
) -> IngestResult:
    """Parse and validate a CSV without modifying its source file."""
    source_path = Path(input_path).expanduser().resolve()
    if not source_path.is_file():
        raise FileNotFoundError(f"Input CSV does not exist: {source_path}")

    resolved_source_type = _source_type_for(source_path, source_type)
    destination = (
        Path(output_dir).expanduser().resolve()
        if output_dir is not None
        else PROJECT_ROOT / "data" / "processed"
    )
    destination.mkdir(parents=True, exist_ok=True)
    processed_path = destination / f"{source_path.stem}_processed.csv"
    report_path = destination / f"{source_path.stem}_validation.json"

    with source_path.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        records, missing, option_column, strike_column = _canonical_records(reader)
        headers_present = bool(reader.fieldnames)

    parsed_rows = [
        parse_row(
            index,
            record,
            option_type_col=option_column,
            strike_col=strike_column,
        )
        for index, record in enumerate(records, start=2)
    ]
    issues = []
    if missing or not headers_present:
        issues.append(missing_columns_issue(missing or REQUIRED_COLUMNS))
    add_duplicate_issues(parsed_rows)
    issues.extend(collect_issues(parsed_rows))

    valid_parsed_rows = [row for row in parsed_rows if not row.issues]
    invalid_parsed_rows = [row for row in parsed_rows if row.issues]
    with processed_path.open("w", encoding="utf-8", newline="") as processed:
        writer = csv.DictWriter(processed, fieldnames=PROCESSED_COLUMNS)
        writer.writeheader()
        writer.writerows(
            _processed_record(row, resolved_source_type, source_path.name)
            for row in valid_parsed_rows
        )

    invalid_details = [
        {
            "row": row.row_number,
            "values": row.original,
            "issues": [issue.to_dict() for issue in row.issues],
        }
        for row in invalid_parsed_rows
    ]
    result = IngestResult(
        source_file=source_path.name,
        source_type=resolved_source_type,
        processed_path=str(processed_path),
        report_path=str(report_path),
        total_rows=len(parsed_rows),
        valid_rows=len(valid_parsed_rows),
        invalid_rows=len(invalid_parsed_rows),
        issues=issues,
        invalid_row_details=invalid_details,
    )
    report = result.to_dict()
    report["schema_version"] = "2.0.0"
    report["invalid_row_details"] = invalid_details
    report["valid_row_numbers"] = [row.row_number for row in valid_parsed_rows]
    with report_path.open("w", encoding="utf-8", newline="") as output:
        json.dump(report, output, indent=2)
        output.write("\n")
    return result
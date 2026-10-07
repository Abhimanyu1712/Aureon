from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
from typing import Any, Iterable


@dataclass
class ValidationIssue:
    code: str
    severity: str
    message: str
    row: int | None = None
    field: str | None = None
    value: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def missing_columns_issue(missing: Iterable[str]) -> ValidationIssue:
    cols = ", ".join(missing)
    return ValidationIssue(
        code="MISSING_COLUMNS",
        severity="error",
        message=f"Missing required columns: {cols}",
        field="columns",
        value=cols,
    )


def add_duplicate_issues(parsed_rows: list[Any]) -> list[ValidationIssue]:
    """Mark duplicate Symbol+Date+ExpiryDate keys. Does not drop rows."""
    groups: dict[tuple[str, str, str], list[int]] = defaultdict(list)
    for row in parsed_rows:
        key = row.identity_key
        if key is not None:
            groups[key].append(row.row_number)

    extra: list[ValidationIssue] = []
    for key, row_numbers in groups.items():
        if len(row_numbers) < 2:
            continue
        symbol, trade_date, expiry_date = key
        for row in parsed_rows:
            if row.row_number in row_numbers:
                issue = ValidationIssue(
                    code="DUPLICATE_ROW",
                    severity="error",
                    message=(
                        "Duplicate contract-day "
                        f"(Symbol={symbol}, Date={trade_date}, ExpiryDate={expiry_date})."
                    ),
                    row=row.row_number,
                    field="contract_id",
                    value=f"{symbol}|{expiry_date}",
                )
                row.issues.append(issue)
                extra.append(issue)
    return extra


def collect_issues(parsed_rows: list[Any]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for row in parsed_rows:
        issues.extend(row.issues)
    return issues

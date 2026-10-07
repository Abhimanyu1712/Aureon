from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from math import isfinite
from pathlib import Path
from typing import Any

import pandas as pd

from app.ingest.schema import FUTURES_OPTION_TYPE_VALUES
from app.ingest.validate import ValidationIssue

TRADE_DATE_FORMATS = (
    "%Y-%m-%d",
    "%d-%m-%Y",
    "%d/%m/%Y",
    "%Y/%m/%d",
    "%d.%m.%Y",
    "%d-%b-%Y",
    "%d-%b-%y",
    "%d %b %Y",
    "%d%b%Y",
    "%d-%B-%Y",
)

EXPIRY_DATE_FORMATS = (
    "%d%b%Y",
    "%d%b%y",
    "%d-%b-%Y",
    "%d-%b-%y",
    "%d %b %Y",
    "%d-%B-%Y",
    "%Y-%m-%d",
    "%d-%m-%Y",
    "%d/%m/%Y",
)


def _is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and pd.isna(value):
        return True
    if pd.isna(value):
        return True
    return str(value).strip() == ""


def _stringify(value: Any) -> str:
    if _is_blank(value):
        return ""
    text = str(value).strip()
    if text.endswith(".0") and text.replace(".", "", 1).isdigit():
        return text[:-2]
    return text


def parse_trade_date(value: Any) -> date | None:
    if _is_blank(value):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = _stringify(value)
    for fmt in TRADE_DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def parse_expiry_date(value: Any) -> date | None:
    if _is_blank(value):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = _stringify(value).upper().replace(" ", "")
    # 04SEP2026, 4SEP2026
    padded = text
    match = re.fullmatch(r"(\d{1,2})([A-Z]{3})(\d{2,4})", text)
    if match:
        day, mon, year = match.groups()
        padded = f"{int(day):02d}{mon}{year}"
    for candidate in (padded, _stringify(value).upper()):
        for fmt in EXPIRY_DATE_FORMATS:
            try:
                return datetime.strptime(candidate, fmt).date()
            except ValueError:
                continue
    return None


def parse_number(value: Any) -> float | None:
    if _is_blank(value):
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if pd.isna(value) or not isfinite(value):
            return None
        return float(value)
    text = _stringify(value).replace(",", "")
    try:
        number = float(text)
        return number if isfinite(number) else None
    except ValueError:
        return None


def strip_symbol(value: Any) -> str | None:
    if _is_blank(value):
        return None
    symbol = str(value).strip()
    return symbol or None


def is_valid_symbol(value: str | None) -> bool:
    return value is not None and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", value) is not None


def date_from_filename(path: Path) -> date | None:
    match = re.search(r"(\d{8})", path.stem)
    if not match:
        return None
    token = match.group(1)
    for fmt in ("%d%m%Y", "%Y%m%d"):
        try:
            return datetime.strptime(token, fmt).date()
        except ValueError:
            continue
    return None


def is_futures_option_type(value: Any) -> bool:
    if _is_blank(value):
        return True
    return _stringify(value).upper() in FUTURES_OPTION_TYPE_VALUES


def is_option_row(option_type: Any, strike: Any) -> bool:
    if not is_futures_option_type(option_type):
        return True
    if _is_blank(strike):
        return False
    strike_text = _stringify(strike).upper()
    if strike_text in {"0", "0.0", "-", "NA", "N/A"}:
        return False
    parsed = parse_number(strike)
    return parsed is not None and parsed > 0


def _issue(
    code: str,
    message: str,
    row: int,
    field: str,
    value: Any,
) -> ValidationIssue:
    display = "" if _is_blank(value) else _stringify(value)
    return ValidationIssue(
        code=code,
        severity="error",
        message=message,
        row=row,
        field=field,
        value=display,
    )


@dataclass
class ParsedRow:
    row_number: int
    original: dict[str, Any]
    symbol: str | None = None
    trade_date: date | None = None
    expiry_date: date | None = None
    expiry_raw: str | None = None
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    volume: float | None = None
    open_interest: float | None = None
    is_option: bool = False
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def identity_key(self) -> tuple[str, str, str] | None:
        if self.symbol and self.trade_date and self.expiry_date:
            return (self.symbol, self.trade_date.isoformat(), self.expiry_date.isoformat())
        return None


def parse_row(
    row_number: int,
    record: dict[str, Any],
    *,
    option_type_col: str | None = None,
    strike_col: str | None = None,
) -> ParsedRow:
    parsed = ParsedRow(row_number=row_number, original=record)

    raw_symbol = record.get("Symbol")
    parsed.symbol = strip_symbol(raw_symbol)
    if _is_blank(raw_symbol):
        parsed.issues.append(
            _issue("MISSING_VALUE", "Symbol is required.", row_number, "Symbol", raw_symbol)
        )
    elif parsed.symbol is None:
        parsed.issues.append(
            _issue(
                "INVALID_CONTRACT_IDENTITY",
                "Symbol is empty after stripping whitespace.",
                row_number,
                "Symbol",
                raw_symbol,
            )
        )
    elif not is_valid_symbol(parsed.symbol):
        parsed.issues.append(
            _issue(
                "INVALID_SYMBOL",
                "Symbol must contain only letters, numbers, underscores, or hyphens.",
                row_number,
                "Symbol",
                raw_symbol,
            )
        )

    raw_date = record.get("Date")
    parsed.trade_date = parse_trade_date(raw_date)
    if _is_blank(raw_date):
        parsed.issues.append(
            _issue("MISSING_VALUE", "Date is required.", row_number, "Date", raw_date)
        )
    elif parsed.trade_date is None:
        parsed.issues.append(
            _issue("INVALID_DATE", "Date could not be parsed.", row_number, "Date", raw_date)
        )

    raw_expiry = record.get("ExpiryDate")
    parsed.expiry_raw = None if _is_blank(raw_expiry) else _stringify(raw_expiry)
    parsed.expiry_date = parse_expiry_date(raw_expiry)
    if _is_blank(raw_expiry):
        parsed.issues.append(
            _issue(
                "MISSING_VALUE",
                "ExpiryDate is required.",
                row_number,
                "ExpiryDate",
                raw_expiry,
            )
        )
    elif parsed.expiry_date is None:
        parsed.issues.append(
            _issue(
                "INVALID_EXPIRY",
                "ExpiryDate could not be parsed (expected values such as 04SEP2026).",
                row_number,
                "ExpiryDate",
                raw_expiry,
            )
        )
    if not is_valid_symbol(parsed.symbol) or parsed.expiry_date is None:
        parsed.issues.append(
            _issue(
                "INVALID_CONTRACT_IDENTITY",
                "Contract identity requires a non-empty Symbol and a valid ExpiryDate.",
                row_number,
                "ExpiryDate" if parsed.expiry_date is None else "Symbol",
                raw_expiry if parsed.expiry_date is None else raw_symbol,
            )
        )

    option_type = record.get(option_type_col) if option_type_col else None
    strike = record.get(strike_col) if strike_col else None
    parsed.is_option = is_option_row(option_type, strike)
    if parsed.is_option:
        parsed.issues.append(
            _issue(
                "INVALID_CONTRACT_IDENTITY",
                "Options rows cannot use Symbol+ExpiryDate identity; Stage 2 accepts futures only.",
                row_number,
                option_type_col or strike_col or "Option Type",
                option_type if option_type_col else strike,
            )
        )

    for field_name, code, attr, allow_zero in (
        ("Open", "INVALID_PRICE", "open", False),
        ("High", "INVALID_PRICE", "high", False),
        ("Low", "INVALID_PRICE", "low", False),
        ("Close", "INVALID_PRICE", "close", False),
        ("Volume", "INVALID_VOLUME", "volume", True),
        ("OpenInterest", "INVALID_OPEN_INTEREST", "open_interest", True),
    ):
        raw = record.get(field_name)
        if _is_blank(raw):
            parsed.issues.append(
                _issue("MISSING_VALUE", f"{field_name} is required.", row_number, field_name, raw)
            )
            continue
        number = parse_number(raw)
        if number is None:
            parsed.issues.append(
                _issue(code, f"{field_name} is not numeric.", row_number, field_name, raw)
            )
            continue
        if number < 0 or (not allow_zero and number == 0):
            parsed.issues.append(
                _issue(code, f"{field_name} must be a positive number.", row_number, field_name, raw)
            )
            continue
        setattr(parsed, attr, number)

    prices = (parsed.open, parsed.high, parsed.low, parsed.close)
    if all(p is not None for p in prices):
        open_, high, low, close = prices  # type: ignore[misc]
        if high < low:
            parsed.issues.append(
                _issue("INVALID_PRICE", "High is less than Low.", row_number, "High", high)
            )
        if open_ < low or open_ > high:
            parsed.issues.append(
                _issue(
                    "INVALID_PRICE",
                    "Open is outside the High-Low range.",
                    row_number,
                    "Open",
                    open_,
                )
            )
        if close < low or close > high:
            parsed.issues.append(
                _issue(
                    "INVALID_PRICE",
                    "Close is outside the High-Low range.",
                    row_number,
                    "Close",
                    close,
                )
            )

    return parsed

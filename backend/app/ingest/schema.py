REQUIRED_COLUMNS = (
    "Symbol",
    "Date",
    "ExpiryDate",
    "Open",
    "High",
    "Low",
    "Close",
    "Volume",
    "OpenInterest",
)

# Normalized header (lowercase, spaces collapsed) -> canonical name
COLUMN_ALIASES = {
    "symbol": "Symbol",
    "date": "Date",
    "expirydate": "ExpiryDate",
    "expiry date": "ExpiryDate",
    "expiry_date": "ExpiryDate",
    "open": "Open",
    "high": "High",
    "low": "Low",
    "close": "Close",
    "volume": "Volume",
    "traded quantity": "Volume",
    "tradedquantity": "Volume",
    "traded_quantity": "Volume",
    "openinterest": "OpenInterest",
    "open interest": "OpenInterest",
    "open_interest": "OpenInterest",
    "oi": "OpenInterest",
}

OPTION_TYPE_ALIASES = {
    "option type",
    "optiontype",
    "opt type",
    "opttype",
}

STRIKE_ALIASES = {
    "strike price",
    "strikeprice",
    "strike",
}

PROCESSED_COLUMNS = (
    "symbol",
    "trade_date",
    "expiry_date",
    "expiry_raw",
    "contract_id",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "open_interest",
    "source_type",
    "source_file",
)

FORBIDDEN_PROCESSED_COLUMNS = (
    "near_month",
    "nearmonth",
    "continuous",
    "continuous_contract",
    "front_month",
    "rolled",
)

SOURCE_TYPES = ("DEMO", "REAL")
SCHEMA_VERSION = "2.0.0"

FUTURES_OPTION_TYPE_VALUES = {"", "-", "NA", "N/A", "XX", "FUT", "FUTURE", "FUTURES"}


def normalize_header(name: str) -> str:
    cleaned = str(name).replace("\ufeff", "").strip()
    return " ".join(cleaned.lower().split())


def compact_header(normalized: str) -> str:
    return normalized.replace(" ", "").replace("_", "")


def canonical_column_name(name: str) -> str:
    normalized = normalize_header(name)
    if normalized in COLUMN_ALIASES:
        return COLUMN_ALIASES[normalized]
    compact = compact_header(normalized)
    return COLUMN_ALIASES.get(compact, str(name).replace("\ufeff", "").strip())


def make_contract_id(symbol: str, expiry_date_iso: str) -> str:
    return f"{symbol}|{expiry_date_iso}"

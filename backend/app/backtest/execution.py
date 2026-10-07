from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from app.analytics.normalization import get_contract_spec
from app.backtest.config import BacktestConfig
from app.backtest.models import TradeLeg


JOIN_FIELDS = ("source_type", "symbol", "trade_date", "expiry_date", "contract_id")


class BacktestInputError(ValueError):
    pass


@dataclass(frozen=True)
class MarketBar:
    symbol: str
    trade_date: date
    expiry_date: date
    contract_id: str
    normalized_price: Decimal
    volume: Decimal | None
    open_interest: Decimal | None
    source_type: str
    source_file: str

    @property
    def contract_size_grams(self) -> Decimal:
        return get_contract_spec(self.symbol).contract_size_grams


@dataclass(frozen=True)
class BacktestSignal:
    symbol: str
    trade_date: date
    expiry_date: date
    contract_id: str
    normalized_price: Decimal
    peer_reference: Decimal | None
    spread: Decimal | None
    z_score: Decimal | None
    peer_count: int
    volume: Decimal | None
    open_interest: Decimal | None
    days_to_expiry: int
    relative_direction: str
    signal_status: str
    source_type: str
    source_file: str


def _decimal(value: str | None, name: str, row_number: int) -> Decimal:
    try:
        parsed = Decimal(value or "")
    except InvalidOperation as exc:
        raise BacktestInputError(f"Row {row_number}: {name} must be numeric.") from exc
    if not parsed.is_finite():
        raise BacktestInputError(f"Row {row_number}: {name} must be finite.")
    if name in {"normalized price", "Stage 4 normalized price"} and parsed <= 0:
        raise BacktestInputError(f"Row {row_number}: {name} must be positive.")
    return parsed


def _read_csv(path: Path) -> tuple[list[dict[str, str]], set[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        return list(reader), set(reader.fieldnames or ())


def load_backtest_inputs(
    normalized_path: str | Path,
    signals_path: str | Path,
    source_type: str = "DEMO",
) -> tuple[dict[tuple[str, date, str], MarketBar], dict[tuple[str, date, str], BacktestSignal]]:
    normalized_file = Path(normalized_path).expanduser().resolve()
    signal_file = Path(signals_path).expanduser().resolve()
    if not normalized_file.is_file() or not signal_file.is_file():
        raise FileNotFoundError("Stage 3 normalized and Stage 4 signal CSVs must both exist.")
    selected_source = source_type.strip().upper()
    if selected_source not in {"DEMO", "REAL"}:
        raise ValueError("source_type must be DEMO or REAL")

    normalized_rows, normalized_headers = _read_csv(normalized_file)
    signal_rows, signal_headers = _read_csv(signal_file)
    normalized_required = {
        *JOIN_FIELDS,
        "purity_adjusted_price_per_gram",
        "volume",
        "open_interest",
        "source_file",
    }
    signal_required = {
        *JOIN_FIELDS,
        "normalized_price",
        "peer_reference",
        "spread",
        "z_score",
        "peer_count",
        "volume",
        "open_interest",
        "days_to_expiry",
        "relative_direction",
        "signal_status",
        "source_file",
    }
    if missing := normalized_required - normalized_headers:
        raise BacktestInputError("Stage 3 normalized CSV missing: " + ", ".join(sorted(missing)))
    if missing := signal_required - signal_headers:
        raise BacktestInputError("Stage 4 signal CSV missing: " + ", ".join(sorted(missing)))

    bars: dict[tuple[str, date, str], MarketBar] = {}
    for row_number, row in enumerate(normalized_rows, start=2):
        if row["source_type"].upper() != selected_source:
            continue
        try:
            trade_date = date.fromisoformat(row["trade_date"])
            expiry_date = date.fromisoformat(row["expiry_date"])
        except ValueError as exc:
            raise BacktestInputError(f"Stage 3 row {row_number}: invalid dates.") from exc
        symbol = row["symbol"].strip().upper()
        expected_id = f"{symbol}|{expiry_date.isoformat()}"
        if row["contract_id"] != expected_id:
            raise BacktestInputError(f"Stage 3 row {row_number}: invalid contract identity.")
        try:
            bar = MarketBar(
                symbol=symbol,
                trade_date=trade_date,
                expiry_date=expiry_date,
                contract_id=expected_id,
                normalized_price=_decimal(row["purity_adjusted_price_per_gram"], "normalized price", row_number),
                volume=_optional_decimal(row["volume"], "volume", row_number),
                open_interest=_optional_decimal(row["open_interest"], "open interest", row_number),
                source_type=selected_source,
                source_file=row["source_file"],
            )
        except ValueError as exc:
            raise BacktestInputError(f"Stage 3 row {row_number}: unsupported contract symbol {symbol}.") from exc
        key = (bar.contract_id, bar.trade_date, bar.source_type)
        if key in bars:
            raise BacktestInputError(f"Duplicate Stage 3 contract observation: {key}.")
        bars[key] = bar

    signals: dict[tuple[str, date, str], BacktestSignal] = {}
    for row_number, row in enumerate(signal_rows, start=2):
        if row["source_type"].upper() != selected_source:
            continue
        try:
            trade_date = date.fromisoformat(row["trade_date"])
            expiry_date = date.fromisoformat(row["expiry_date"])
            peer_count = int(row["peer_count"])
            days_to_expiry = int(row["days_to_expiry"])
        except ValueError as exc:
            raise BacktestInputError(f"Stage 4 row {row_number}: invalid dates or counts.") from exc
        if days_to_expiry != (expiry_date - trade_date).days:
            raise BacktestInputError(f"Stage 4 row {row_number}: days_to_expiry does not match row dates.")
        symbol = row["symbol"].strip().upper()
        expected_id = f"{symbol}|{expiry_date.isoformat()}"
        if row["contract_id"] != expected_id:
            raise BacktestInputError(f"Stage 4 row {row_number}: invalid contract identity.")
        key = (expected_id, trade_date, selected_source)
        bar = bars.get(key)
        if bar is None:
            raise BacktestInputError(f"Stage 4 row {row_number}: no matching Stage 3 price row.")
        stage4_price = _decimal(row["normalized_price"], "Stage 4 normalized price", row_number)
        if stage4_price != bar.normalized_price:
            raise BacktestInputError(f"Stage 4 row {row_number}: price does not match Stage 3 normalized close.")
        signal = BacktestSignal(
            symbol=symbol,
            trade_date=trade_date,
            expiry_date=expiry_date,
            contract_id=expected_id,
            normalized_price=stage4_price,
            peer_reference=_optional_decimal(row["peer_reference"], "peer reference", row_number),
            spread=_optional_decimal(row["spread"], "spread", row_number),
            z_score=_optional_decimal(row["z_score"], "z-score", row_number),
            peer_count=peer_count,
            volume=_optional_decimal(row["volume"], "volume", row_number),
            open_interest=_optional_decimal(row["open_interest"], "open interest", row_number),
            days_to_expiry=days_to_expiry,
            relative_direction=row["relative_direction"],
            signal_status=row["signal_status"],
            source_type=selected_source,
            source_file=row["source_file"],
        )
        if key in signals:
            raise BacktestInputError(f"Duplicate Stage 4 signal row: {key}.")
        signals[key] = signal
    if not bars or not signals:
        raise BacktestInputError(f"No {selected_source} Stage 3/4 records are available.")
    return bars, signals


def _optional_decimal(value: str | None, name: str, row_number: int) -> Decimal | None:
    if value is None or value == "":
        return None
    return _decimal(value, name, row_number)


def build_trade_legs(
    target: MarketBar,
    peers: list[MarketBar],
    direction: str,
    config: BacktestConfig,
) -> list[TradeLeg]:
    if not peers:
        raise ValueError("A peer basket requires at least one contract.")
    target_side = "LONG" if direction == "CHEAP" else "SHORT"
    peer_side = "SHORT" if direction == "CHEAP" else "LONG"
    target_units = config.per_leg_notional / (
        target.normalized_price * target.contract_size_grams
    )
    target_notional = target_units * target.normalized_price * target.contract_size_grams
    legs = [
        TradeLeg(
            symbol=target.symbol,
            contract_id=target.contract_id,
            expiry_date=target.expiry_date,
            position_side=target_side,
            contract_equivalents=target_units,
            contract_size_grams=target.contract_size_grams,
            entry_price_per_gram=target.normalized_price,
            entry_notional=target_notional,
        )
    ]
    by_symbol: dict[str, list[MarketBar]] = {}
    for peer in peers:
        by_symbol.setdefault(peer.symbol, []).append(peer)
    symbol_notional = config.per_leg_notional / Decimal(len(by_symbol))
    for peer_symbol in sorted(by_symbol):
        symbol_contracts = by_symbol[peer_symbol]
        contract_notional = symbol_notional / Decimal(len(symbol_contracts))
        for peer in sorted(symbol_contracts, key=lambda item: item.contract_id):
            units = contract_notional / (peer.normalized_price * peer.contract_size_grams)
            legs.append(
                TradeLeg(
                    symbol=peer.symbol,
                    contract_id=peer.contract_id,
                    expiry_date=peer.expiry_date,
                    position_side=peer_side,
                    contract_equivalents=units,
                    contract_size_grams=peer.contract_size_grams,
                    entry_price_per_gram=peer.normalized_price,
                    entry_notional=units * peer.normalized_price * peer.contract_size_grams,
                )
            )
    return legs
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any


@dataclass
class TradeLeg:
    symbol: str
    contract_id: str
    expiry_date: date
    position_side: str
    contract_equivalents: Decimal
    contract_size_grams: Decimal
    entry_price_per_gram: Decimal
    exit_price_per_gram: Decimal | None = None
    exit_price_date: date | None = None
    entry_notional: Decimal = Decimal(0)
    exit_notional: Decimal | None = None
    gross_pnl: Decimal | None = None
    entry_cost: Decimal = Decimal(0)
    exit_cost: Decimal | None = None


@dataclass
class Trade:
    trade_id: str
    target_symbol: str
    target_expiry_date: date
    target_contract_id: str
    peer_symbols: tuple[str, ...]
    peer_contract_ids: tuple[str, ...]
    entry_signal_date: date
    entry_date: date
    exit_date: date | None
    entry_z_score: Decimal
    exit_z_score: Decimal | None
    direction: str
    target_entry_price: Decimal
    target_exit_price: Decimal | None
    peer_entry_value: Decimal
    peer_exit_value: Decimal | None
    target_units: Decimal
    peer_units: tuple[Decimal, ...]
    days_held: int | None
    exit_reason: str | None
    target_leg_gross_pnl: Decimal | None
    peer_leg_gross_pnl: Decimal | None
    gross_pnl: Decimal | None
    transaction_cost: Decimal
    net_pnl: Decimal | None
    return_on_capital: Decimal | None
    status: str
    source_type: str
    source_file: str
    legs: list[TradeLeg] = field(default_factory=list)


@dataclass(frozen=True)
class EntryRejection:
    signal_date: date
    symbol: str
    contract_id: str
    direction: str
    z_score: Decimal | None
    entry_rejected_reason: str
    source_type: str


@dataclass(frozen=True)
class EquityPoint:
    date: date
    starting_equity: Decimal
    daily_pnl: Decimal
    daily_cost: Decimal
    daily_net_pnl: Decimal
    ending_equity: Decimal


@dataclass
class BacktestResult:
    dataset_type: str
    dataset_start: date | None
    dataset_end: date | None
    initial_capital: Decimal
    configuration: dict[str, Any]
    trades: list[Trade]
    rejected_entries: list[EntryRejection]
    equity_curve: list[EquityPoint]
    benchmark: dict[str, Any]
    metrics: dict[str, Any]
    data_quality_notes: list[str]
    report: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
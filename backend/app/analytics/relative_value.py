from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from statistics import median
from typing import Iterable


MINIMUM_STANDARD_DEVIATION = Decimal("1e-12")


@dataclass(frozen=True)
class NormalizedObservation:
    symbol: str
    trade_date: date
    expiry_date: date
    contract_id: str
    normalized_price_per_gram: Decimal
    purity_adjusted_price_per_gram: Decimal
    close: Decimal
    volume: Decimal
    open_interest: Decimal
    source_type: str
    source_file: str


@dataclass(frozen=True)
class RelativeValuePoint:
    symbol: str
    trade_date: date
    expiry_date: date
    contract_id: str
    normalized_price: Decimal
    peer_reference: Decimal | None
    spread: Decimal | None
    rolling_mean: Decimal | None
    rolling_std: Decimal | None
    z_score: Decimal | None
    peer_count: int
    analytics_status: str
    source_type: str
    source_file: str


def calculate_relative_value(
    observations: Iterable[NormalizedObservation],
    *,
    rolling_window: int = 5,
    min_periods: int = 3,
    min_peer_count: int = 2,
) -> list[RelativeValuePoint]:
    if rolling_window < 1:
        raise ValueError("rolling_window must be at least 1")
    if min_periods < 2 or min_periods > rolling_window:
        raise ValueError("min_periods must be between 2 and rolling_window")
    if min_peer_count < 1:
        raise ValueError("min_peer_count must be at least 1")

    rows = list(observations)
    seen: set[tuple[str, str, date, date]] = set()
    cohorts: dict[tuple[str, date, int, int], list[NormalizedObservation]] = defaultdict(list)
    for row in rows:
        expected_id = f"{row.symbol}|{row.expiry_date.isoformat()}"
        if row.contract_id != expected_id:
            raise ValueError(f"Invalid contract identity for {row.symbol}: expected {expected_id}")
        if row.source_type not in {"DEMO", "REAL"}:
            raise ValueError(f"Invalid source type for {row.contract_id}: {row.source_type}")
        if not row.purity_adjusted_price_per_gram.is_finite() or row.purity_adjusted_price_per_gram <= 0:
            raise ValueError(f"Invalid normalized price for {row.contract_id}")
        identity = (row.source_type, row.symbol, row.expiry_date, row.trade_date)
        if identity in seen:
            raise ValueError(f"Duplicate contract-day observation: {row.contract_id} on {row.trade_date}")
        seen.add(identity)
        # Product expiries fall on different days; cohort only within the same
        # delivery month, and never combine DEMO with REAL observations.
        cohort = (
            row.source_type,
            row.trade_date,
            row.expiry_date.year,
            row.expiry_date.month,
        )
        cohorts[cohort].append(row)

    provisional: list[dict[str, object]] = []
    for row in rows:
        cohort = (
            row.source_type,
            row.trade_date,
            row.expiry_date.year,
            row.expiry_date.month,
        )
        peers_by_symbol: dict[str, list[Decimal]] = defaultdict(list)
        for candidate in cohorts[cohort]:
            if candidate.symbol != row.symbol:
                peers_by_symbol[candidate.symbol].append(candidate.purity_adjusted_price_per_gram)

        # One value per peer symbol prevents multiple contracts from one product
        # overweighting the reference. Their distinct identities remain output.
        peer_values = [median(values) for values in peers_by_symbol.values()]
        peer_count = len(peer_values)
        peer_reference = median(peer_values) if peer_count >= min_peer_count else None
        spread = (
            row.purity_adjusted_price_per_gram - peer_reference
            if peer_reference is not None
            else None
        )
        provisional.append(
            {
                "row": row,
                "peer_count": peer_count,
                "peer_reference": peer_reference,
                "spread": spread,
            }
        )

    provisional.sort(
        key=lambda item: (
            item["row"].source_type,
            item["row"].contract_id,
            item["row"].trade_date,
        )
    )
    histories: dict[tuple[str, str], deque[Decimal]] = {}
    results: list[RelativeValuePoint] = []
    for item in provisional:
        row = item["row"]
        spread = item["spread"]
        peer_count = item["peer_count"]
        peer_reference = item["peer_reference"]
        rolling_mean = None
        rolling_std = None
        z_score = None

        if spread is None:
            status = "INSUFFICIENT_PEERS"
        else:
            history_key = (row.source_type, row.contract_id)
            history = histories.setdefault(history_key, deque(maxlen=rolling_window))
            history.append(spread)
            if len(history) < min_periods:
                status = "INSUFFICIENT_HISTORY"
            else:
                rolling_mean = sum(history, Decimal(0)) / Decimal(len(history))
                variance = sum(
                    ((value - rolling_mean) ** 2 for value in history),
                    Decimal(0),
                ) / Decimal(len(history))
                rolling_std = variance.sqrt()
                if rolling_std <= MINIMUM_STANDARD_DEVIATION:
                    status = "ZERO_VARIANCE"
                else:
                    z_score = (spread - rolling_mean) / rolling_std
                    status = "READY"

        results.append(
            RelativeValuePoint(
                symbol=row.symbol,
                trade_date=row.trade_date,
                expiry_date=row.expiry_date,
                contract_id=row.contract_id,
                normalized_price=row.purity_adjusted_price_per_gram,
                peer_reference=peer_reference,
                spread=spread,
                rolling_mean=rolling_mean,
                rolling_std=rolling_std,
                z_score=z_score,
                peer_count=peer_count,
                analytics_status=status,
                source_type=row.source_type,
                source_file=row.source_file,
            )
        )
    return sorted(results, key=lambda point: (point.trade_date, point.symbol, point.expiry_date))
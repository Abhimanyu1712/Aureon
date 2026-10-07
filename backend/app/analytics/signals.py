from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Literal


SignalStatus = Literal[
    "STRONG_RELATIVE_DEVIATION",
    "WATCHLIST",
    "NO_SIGNAL",
    "INSUFFICIENT_HISTORY",
    "INSUFFICIENT_PEERS",
    "INSUFFICIENT_LIQUIDITY",
    "EXPIRY_FILTER_FAILED",
]
RelativeDirection = Literal["CHEAP", "EXPENSIVE", "NEUTRAL"]


@dataclass(frozen=True)
class SignalConfig:
    watchlist_z: Decimal = Decimal("1.5")
    strong_deviation_z: Decimal = Decimal("2.0")
    neutral_z: Decimal = Decimal("1e-12")
    minimum_volume: Decimal = Decimal("500")
    minimum_open_interest: Decimal = Decimal("1000")
    minimum_days_to_expiry: int = 5
    minimum_peer_count: int = 2
    minimum_history_count: int = 3
    rolling_window: int = 5

    def __post_init__(self) -> None:
        if self.watchlist_z <= 0 or self.strong_deviation_z < self.watchlist_z:
            raise ValueError("z-score thresholds must satisfy 0 < watchlist_z <= strong_deviation_z")
        if self.neutral_z < 0:
            raise ValueError("neutral_z cannot be negative")
        if self.minimum_volume < 0 or self.minimum_open_interest < 0:
            raise ValueError("liquidity proxy thresholds cannot be negative")
        if self.minimum_days_to_expiry < 0:
            raise ValueError("minimum_days_to_expiry cannot be negative")
        if self.minimum_peer_count < 1 or self.minimum_history_count < 1:
            raise ValueError("minimum peer and history counts must be positive")
        if self.rolling_window < self.minimum_history_count:
            raise ValueError("rolling_window must be at least minimum_history_count")

    @classmethod
    def from_environment(cls) -> SignalConfig:
        def decimal_setting(name: str, default: str) -> Decimal:
            try:
                result = Decimal(os.getenv(name, default))
            except InvalidOperation as exc:
                raise ValueError(f"{name} must be a decimal number") from exc
            if not result.is_finite():
                raise ValueError(f"{name} must be a finite decimal number")
            return result

        def integer_setting(name: str, default: str) -> int:
            try:
                return int(os.getenv(name, default))
            except ValueError as exc:
                raise ValueError(f"{name} must be an integer") from exc

        return cls(
            watchlist_z=decimal_setting("AUREON_SIGNAL_WATCHLIST_Z", "1.5"),
            strong_deviation_z=decimal_setting("AUREON_SIGNAL_STRONG_Z", "2.0"),
            neutral_z=decimal_setting("AUREON_SIGNAL_NEUTRAL_Z", "1e-12"),
            minimum_volume=decimal_setting("AUREON_SIGNAL_MIN_VOLUME", "500"),
            minimum_open_interest=decimal_setting("AUREON_SIGNAL_MIN_OPEN_INTEREST", "1000"),
            minimum_days_to_expiry=integer_setting("AUREON_SIGNAL_MIN_DAYS_TO_EXPIRY", "5"),
            minimum_peer_count=integer_setting("AUREON_SIGNAL_MIN_PEERS", "2"),
            minimum_history_count=integer_setting("AUREON_SIGNAL_MIN_HISTORY", "3"),
            rolling_window=integer_setting("AUREON_SIGNAL_ROLLING_WINDOW", "5"),
        )


@dataclass(frozen=True)
class SignalEvidence:
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
    rolling_history_count: int
    analytics_status: str
    source_type: str
    source_file: str


@dataclass(frozen=True)
class SignalResult:
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
    rolling_history_count: int
    relative_direction: RelativeDirection
    signal_status: SignalStatus
    cost_filter_status: Literal["NOT_APPLIED"]
    analytics_status: str
    source_type: str
    source_file: str
    explanation: str


def _format_value(value: Decimal | None, decimals: int = 2) -> str:
    return "missing" if value is None else f"{value:.{decimals}f}"


class SignalEngine:
    def __init__(self, config: SignalConfig | None = None) -> None:
        self.config = config or SignalConfig.from_environment()

    def evaluate(self, evidence: SignalEvidence) -> SignalResult:
        expected_contract_id = f"{evidence.symbol}|{evidence.expiry_date.isoformat()}"
        if evidence.contract_id != expected_contract_id:
            raise ValueError(f"Invalid contract identity; expected {expected_contract_id}")
        if evidence.peer_count < 0 or evidence.rolling_history_count < 0:
            raise ValueError("peer_count and rolling_history_count cannot be negative")

        days_to_expiry = (evidence.expiry_date - evidence.trade_date).days
        z_score = evidence.z_score
        if z_score is not None and not z_score.is_finite():
            raise ValueError("z_score must be finite when provided")
        if z_score is None or abs(z_score) <= self.config.neutral_z:
            direction: RelativeDirection = "NEUTRAL"
        elif z_score < 0:
            direction = "CHEAP"
        else:
            direction = "EXPENSIVE"

        status, reason = self._classify(evidence, days_to_expiry)
        explanation = self._explain(evidence, days_to_expiry, direction, status, reason)
        return SignalResult(
            symbol=evidence.symbol,
            trade_date=evidence.trade_date,
            expiry_date=evidence.expiry_date,
            contract_id=evidence.contract_id,
            normalized_price=evidence.normalized_price,
            peer_reference=evidence.peer_reference,
            spread=evidence.spread,
            z_score=z_score,
            peer_count=evidence.peer_count,
            volume=evidence.volume,
            open_interest=evidence.open_interest,
            days_to_expiry=days_to_expiry,
            rolling_history_count=evidence.rolling_history_count,
            relative_direction=direction,
            signal_status=status,
            cost_filter_status="NOT_APPLIED",
            analytics_status=evidence.analytics_status,
            source_type=evidence.source_type,
            source_file=evidence.source_file,
            explanation=explanation,
        )

    def _classify(self, evidence: SignalEvidence, days_to_expiry: int) -> tuple[SignalStatus, str]:
        config = self.config
        if evidence.analytics_status == "INSUFFICIENT_PEERS" or evidence.peer_count < config.minimum_peer_count:
            return "INSUFFICIENT_PEERS", "Stage 3 has fewer than the configured minimum peer symbols."
        if (
            evidence.analytics_status != "READY"
            or evidence.z_score is None
            or evidence.rolling_history_count < config.minimum_history_count
        ):
            if evidence.analytics_status == "ZERO_VARIANCE":
                return "INSUFFICIENT_HISTORY", "Stage 3 rolling standard deviation is zero, so no z-score can be classified."
            return "INSUFFICIENT_HISTORY", "Stage 3 has insufficient valid rolling history for a z-score."
        if (
            evidence.volume is None
            or evidence.open_interest is None
            or not evidence.volume.is_finite()
            or not evidence.open_interest.is_finite()
            or evidence.volume < config.minimum_volume
            or evidence.open_interest < config.minimum_open_interest
        ):
            return "INSUFFICIENT_LIQUIDITY", "Volume/open interest are missing or below liquidity proxy thresholds."
        if days_to_expiry < config.minimum_days_to_expiry:
            return "EXPIRY_FILTER_FAILED", "Days remaining are below the configured minimum."

        absolute_z = abs(evidence.z_score)
        if absolute_z >= config.strong_deviation_z:
            return "STRONG_RELATIVE_DEVIATION", "Absolute z-score meets the strong-deviation threshold."
        if absolute_z >= config.watchlist_z:
            return "WATCHLIST", "Absolute z-score meets the watchlist threshold."
        return "NO_SIGNAL", "Absolute z-score is below the watchlist threshold."

    def _explain(
        self,
        evidence: SignalEvidence,
        days_to_expiry: int,
        direction: RelativeDirection,
        status: SignalStatus,
        reason: str,
    ) -> str:
        z_text = _format_value(evidence.z_score)
        volume_text = _format_value(evidence.volume, 0)
        oi_text = _format_value(evidence.open_interest, 0)
        if direction == "CHEAP":
            relation = "below"
        elif direction == "EXPENSIVE":
            relation = "above"
        else:
            relation = "at or near"

        if status == "INSUFFICIENT_PEERS":
            detail = (
                f"{evidence.peer_count} comparable peer symbols are available; "
                f"{self.config.minimum_peer_count} are required."
            )
        elif status == "INSUFFICIENT_HISTORY":
            if evidence.analytics_status == "ZERO_VARIANCE":
                detail = (
                    f"Stage 3 status is ZERO_VARIANCE; "
                    f"{evidence.rolling_history_count} trailing observations are available, "
                    "but dispersion is zero."
                )
            else:
                detail = (
                    f"Stage 3 status is {evidence.analytics_status}; "
                    f"{evidence.rolling_history_count} trailing observations are available and "
                    f"{self.config.minimum_history_count} are required."
                )
        elif status == "INSUFFICIENT_LIQUIDITY":
            detail = (
                f"Liquidity proxy failed: volume {volume_text} (minimum "
                f"{self.config.minimum_volume:g}) and open interest {oi_text} "
                f"(minimum {self.config.minimum_open_interest:g})."
            )
        elif status == "EXPIRY_FILTER_FAILED":
            detail = (
                f"Only {days_to_expiry} days remain until expiry; "
                f"{self.config.minimum_days_to_expiry} are required."
            )
        else:
            detail = (
                f"Volume {volume_text} and open interest {oi_text} pass the configured "
                f"liquidity proxy thresholds; {days_to_expiry} days remain until expiry."
            )

        peer_text = (
            f"peer reference is {_format_value(evidence.peer_reference)} ₹/gram"
            if evidence.peer_reference is not None
            else "peer reference is unavailable"
        )
        z_detail = (
            f"Z-score = {z_text}. {evidence.symbol} is {relation} its peer reference "
            f"on a purity-adjusted ₹/gram basis ({peer_text})."
            if evidence.z_score is not None
            else f"Z-score is unavailable for {evidence.symbol}; {peer_text}."
        )
        return f"{z_detail} {detail} {reason} Transaction costs are not applied."
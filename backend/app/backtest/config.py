from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation


@dataclass(frozen=True)
class BacktestConfig:
    entry_z: Decimal = Decimal("2.0")
    exit_z: Decimal = Decimal("0.5")
    max_holding_days: int = 20
    minimum_volume: Decimal = Decimal("500")
    minimum_open_interest: Decimal = Decimal("1000")
    minimum_days_to_expiry: int = 5
    estimated_cost_rate_per_side: Decimal = Decimal("0.0005")
    initial_capital: Decimal = Decimal("1000000")
    benchmark_symbol: str = "GOLDTEN"

    def __post_init__(self) -> None:
        decimal_values = (
            self.entry_z,
            self.exit_z,
            self.minimum_volume,
            self.minimum_open_interest,
            self.estimated_cost_rate_per_side,
            self.initial_capital,
        )
        if any(not value.is_finite() for value in decimal_values):
            raise ValueError("backtest Decimal configuration values must be finite")
        if self.entry_z <= 0 or self.exit_z < 0 or self.exit_z >= self.entry_z:
            raise ValueError("z thresholds must satisfy 0 <= exit_z < entry_z")
        if self.max_holding_days < 1:
            raise ValueError("max_holding_days must be positive")
        if self.minimum_volume < 0 or self.minimum_open_interest < 0:
            raise ValueError("liquidity proxy thresholds cannot be negative")
        if self.minimum_days_to_expiry < 0:
            raise ValueError("minimum_days_to_expiry cannot be negative")
        if not self.estimated_cost_rate_per_side.is_finite() or self.estimated_cost_rate_per_side < 0:
            raise ValueError("estimated_cost_rate_per_side must be finite and non-negative")
        if not self.initial_capital.is_finite() or self.initial_capital <= 0:
            raise ValueError("initial_capital must be finite and positive")
        if not self.benchmark_symbol.strip():
            raise ValueError("benchmark_symbol is required")

    @property
    def per_leg_notional(self) -> Decimal:
        return self.initial_capital / Decimal(2)

    def to_dict(self) -> dict[str, str | int]:
        return {
            key: str(value) if isinstance(value, Decimal) else value
            for key, value in asdict(self).items()
        }

    @classmethod
    def from_environment(cls) -> BacktestConfig:
        def decimal_setting(name: str, default: str) -> Decimal:
            try:
                value = Decimal(os.getenv(name, default))
            except InvalidOperation as exc:
                raise ValueError(f"{name} must be a decimal number") from exc
            if not value.is_finite():
                raise ValueError(f"{name} must be finite")
            return value

        def integer_setting(name: str, default: str) -> int:
            try:
                return int(os.getenv(name, default))
            except ValueError as exc:
                raise ValueError(f"{name} must be an integer") from exc

        return cls(
            entry_z=decimal_setting("AUREON_BACKTEST_ENTRY_Z", "2.0"),
            exit_z=decimal_setting("AUREON_BACKTEST_EXIT_Z", "0.5"),
            max_holding_days=integer_setting("AUREON_BACKTEST_MAX_HOLDING_DAYS", "20"),
            minimum_volume=decimal_setting("AUREON_BACKTEST_MIN_VOLUME", "500"),
            minimum_open_interest=decimal_setting("AUREON_BACKTEST_MIN_OPEN_INTEREST", "1000"),
            minimum_days_to_expiry=integer_setting("AUREON_BACKTEST_MIN_DAYS_TO_EXPIRY", "5"),
            estimated_cost_rate_per_side=decimal_setting("AUREON_BACKTEST_COST_RATE", "0.0005"),
            initial_capital=decimal_setting("AUREON_BACKTEST_INITIAL_CAPITAL", "1000000"),
            benchmark_symbol=os.getenv("AUREON_BACKTEST_BENCHMARK_SYMBOL", "GOLDTEN").strip().upper(),
        )
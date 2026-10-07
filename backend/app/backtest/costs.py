from __future__ import annotations

from decimal import Decimal

from app.backtest.config import BacktestConfig


def estimated_execution_cost(notional: Decimal, config: BacktestConfig) -> Decimal:
    """Estimate one leg's cost for one fill; the rate is an explicit assumption."""
    return abs(notional) * config.estimated_cost_rate_per_side


def estimated_fill_cost(target_notional: Decimal, peer_notional: Decimal, config: BacktestConfig) -> Decimal:
    """Apply estimated per-side cost to both target and peer legs at one fill."""
    return estimated_execution_cost(target_notional, config) + estimated_execution_cost(
        peer_notional, config
    )
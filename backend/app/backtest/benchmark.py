from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.backtest.config import BacktestConfig
from app.backtest.execution import MarketBar
from app.backtest.models import EquityPoint


def calculate_benchmark(
    bars: dict[tuple[str, date, str], MarketBar],
    equity_curve: list[EquityPoint],
    config: BacktestConfig,
) -> dict[str, object]:
    equity_dates = {point.date for point in equity_curve}
    candidates: dict[str, dict[date, Decimal]] = {}
    for bar in bars.values():
        if bar.symbol == config.benchmark_symbol and bar.trade_date in equity_dates:
            candidates.setdefault(bar.contract_id, {})[bar.trade_date] = bar.normalized_price
    if not candidates:
        return {
            "symbol": config.benchmark_symbol,
            "contract_id": None,
            "start_date": None,
            "end_date": None,
            "benchmark_return": None,
            "strategy_return": None,
            "relative_outperformance": None,
            "status": "INSUFFICIENT_DATA",
            "reason": "No benchmark contract has prices on the backtest dates.",
        }

    full_period_contracts = [
        contract_id
        for contract_id, prices in candidates.items()
        if equity_dates.issubset(prices)
    ]
    if not full_period_contracts:
        return {
            "symbol": config.benchmark_symbol,
            "contract_id": None,
            "start_date": min(equity_dates) if equity_dates else None,
            "end_date": max(equity_dates) if equity_dates else None,
            "benchmark_return": None,
            "strategy_return": None,
            "relative_outperformance": None,
            "status": "INSUFFICIENT_DATA",
            "reason": "No single exact benchmark contract has prices on every backtest date.",
        }

    benchmark_contract = min(full_period_contracts)
    prices = candidates[benchmark_contract]
    common_dates = sorted(prices)
    if len(common_dates) < 2:
        return {
            "symbol": config.benchmark_symbol,
            "contract_id": benchmark_contract,
            "start_date": common_dates[0] if common_dates else None,
            "end_date": common_dates[-1] if common_dates else None,
            "benchmark_return": None,
            "strategy_return": None,
            "relative_outperformance": None,
            "status": "INSUFFICIENT_DATA",
            "reason": "Benchmark requires at least two common daily observations.",
        }

    first_date, last_date = common_dates[0], common_dates[-1]
    benchmark_return = prices[last_date] / prices[first_date] - Decimal(1)
    equity_by_date = {point.date: point for point in equity_curve}
    aligned_start = equity_by_date[first_date].starting_equity
    aligned_end = equity_by_date[last_date].ending_equity
    strategy_return = aligned_end / aligned_start - Decimal(1) if aligned_start > 0 else None
    return {
        "symbol": config.benchmark_symbol,
        "contract_id": benchmark_contract,
        "start_date": first_date,
        "end_date": last_date,
        "benchmark_return": benchmark_return,
        "strategy_return": strategy_return,
        "relative_outperformance": (
            strategy_return - benchmark_return if strategy_return is not None else None
        ),
        "status": "CALCULATED" if strategy_return is not None else "INSUFFICIENT_DATA",
        "assumption": "Single exact normalized contract, no expiry roll; matched observed dates only.",
    }
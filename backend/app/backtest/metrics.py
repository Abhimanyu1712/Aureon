from __future__ import annotations

from decimal import Decimal

from app.backtest.models import EquityPoint, Trade


TRADING_DAYS_PER_YEAR = Decimal("252")
MIN_SHARPE_OBSERVATIONS = 20


def calculate_metrics(
    trades: list[Trade],
    equity_curve: list[EquityPoint],
    initial_capital: Decimal,
) -> dict[str, object]:
    completed = [trade for trade in trades if trade.status == "COMPLETED"]
    wins = [trade for trade in completed if (trade.net_pnl or Decimal(0)) > 0]
    losses = [trade for trade in completed if (trade.net_pnl or Decimal(0)) < 0]
    gross = sum((point.daily_pnl for point in equity_curve), Decimal(0))
    costs = sum((trade.transaction_cost for trade in trades), Decimal(0))
    final_equity = equity_curve[-1].ending_equity if equity_curve else initial_capital
    net = final_equity - initial_capital
    cumulative_return = final_equity / initial_capital - Decimal(1)

    peak = initial_capital
    max_drawdown = Decimal(0)
    for point in equity_curve:
        peak = max(peak, point.ending_equity)
        if peak > 0:
            max_drawdown = max(max_drawdown, (peak - point.ending_equity) / peak)

    daily_returns = [
        point.daily_net_pnl / point.starting_equity
        for point in equity_curve
        if point.starting_equity > 0
    ]
    sharpe: dict[str, object]
    if len(daily_returns) < MIN_SHARPE_OBSERVATIONS:
        sharpe = {
            "value": None,
            "status": "INSUFFICIENT_DATA",
            "observations": len(daily_returns),
            "minimum_observations": MIN_SHARPE_OBSERVATIONS,
        }
    else:
        mean_return = sum(daily_returns, Decimal(0)) / Decimal(len(daily_returns))
        variance = sum(((value - mean_return) ** 2 for value in daily_returns), Decimal(0)) / Decimal(
            len(daily_returns) - 1
        )
        deviation = variance.sqrt()
        if deviation == 0:
            sharpe = {
                "value": None,
                "status": "INSUFFICIENT_DATA",
                "observations": len(daily_returns),
                "reason": "Daily return volatility is zero.",
            }
        else:
            sharpe = {
                "value": mean_return / deviation * TRADING_DAYS_PER_YEAR.sqrt(),
                "status": "CALCULATED",
                "observations": len(daily_returns),
            }

    return {
        "total_trades": len(trades),
        "completed_trades": len(completed),
        "open_trades": sum(trade.status == "OPEN" for trade in trades),
        "winning_trades": len(wins),
        "losing_trades": len(losses),
        "win_rate": Decimal(len(wins)) / Decimal(len(completed)) if completed else None,
        "gross_pnl": gross,
        "transaction_cost": costs,
        "net_pnl": net,
        "average_trade_pnl": (
            sum((trade.net_pnl or Decimal(0) for trade in completed), Decimal(0))
            / Decimal(len(completed))
            if completed
            else None
        ),
        "average_holding_days": (
            Decimal(sum(trade.days_held or 0 for trade in completed)) / Decimal(len(completed))
            if completed
            else None
        ),
        "max_drawdown": max_drawdown,
        "sharpe": sharpe,
        "cumulative_return": cumulative_return,
        "final_equity": final_equity,
        "daily_return_observations": len(daily_returns),
    }
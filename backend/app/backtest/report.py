from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.backtest.models import BacktestResult


def json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [json_safe(item) for item in value]
    if hasattr(value, "__dataclass_fields__"):
        return json_safe(asdict(value))
    return value


def build_report(result: BacktestResult) -> dict[str, Any]:
    return json_safe(
        {
            "dataset_type": result.dataset_type,
            "dataset_start": result.dataset_start,
            "dataset_end": result.dataset_end,
            "initial_capital": result.initial_capital,
            "configuration": result.configuration,
            "trade_count": result.metrics["total_trades"],
            "completed_trades": result.metrics["completed_trades"],
            "win_rate": result.metrics["win_rate"],
            "gross_pnl": result.metrics["gross_pnl"],
            "transaction_cost": result.metrics["transaction_cost"],
            "net_pnl": result.metrics["net_pnl"],
            "max_drawdown": result.metrics["max_drawdown"],
            "sharpe": result.metrics["sharpe"],
            "benchmark_return": result.benchmark["benchmark_return"],
            "strategy_return": result.benchmark["strategy_return"],
            "relative_outperformance": result.benchmark["relative_outperformance"],
            "benchmark": result.benchmark,
            "metrics": result.metrics,
            "rejected_entry_count": len(result.rejected_entries),
            "rejected_entries": result.rejected_entries,
            "open_trades": [trade for trade in result.trades if trade.status == "OPEN"],
            "data_quality_notes": result.data_quality_notes,
        }
    )


def write_report(report: dict[str, Any], path: str | Path) -> Path:
    report_path = Path(path).expanduser().resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report_path
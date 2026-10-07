from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from app.backtest.engine import BacktestConfigPath


BACKTEST_DIR = BacktestConfigPath.default_output_dir()
BacktestSource = Literal["DEMO", "REAL"]


def _reports(source_type: BacktestSource) -> list[tuple[Path, dict[str, Any]]]:
    found: list[tuple[Path, dict[str, Any]]] = []
    if not BACKTEST_DIR.exists():
        return found
    for path in sorted(BACKTEST_DIR.glob("*_backtest_report.json")):
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        dataset_type = str(report.get("dataset_type", ""))
        if source_type == "DEMO" and "DEMO" not in dataset_type:
            continue
        if source_type == "REAL" and "REAL" not in dataset_type:
            continue
        found.append((path, report))
    return found


def get_report(source_type: BacktestSource = "DEMO") -> dict[str, Any] | None:
    reports = _reports(source_type)
    return reports[-1][1] if reports else None


def get_summary(source_type: BacktestSource = "DEMO") -> dict[str, Any] | None:
    report = get_report(source_type)
    if report is None:
        return None
    return {
        key: report.get(key)
        for key in (
            "dataset_type",
            "dataset_start",
            "dataset_end",
            "initial_capital",
            "configuration",
            "trade_count",
            "completed_trades",
            "win_rate",
            "gross_pnl",
            "transaction_cost",
            "net_pnl",
            "max_drawdown",
            "sharpe",
            "benchmark_return",
            "strategy_return",
            "relative_outperformance",
            "data_quality_notes",
        )
    }


def _artifact(source_type: BacktestSource, name: str) -> Any | None:
    reports = _reports(source_type)
    if not reports:
        return None
    report_path, report = reports[-1]
    if not report.get("artifact_paths", {}).get(name):
        return None
    artifact_path = BACKTEST_DIR / f"{report_path.name.removesuffix('_report.json')}_{name}.json"
    try:
        return json.loads(Path(artifact_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def get_trades(source_type: BacktestSource = "DEMO") -> list[dict[str, Any]] | None:
    return _artifact(source_type, "trades")


def get_equity(source_type: BacktestSource = "DEMO") -> list[dict[str, Any]] | None:
    return _artifact(source_type, "equity")


def get_benchmark(source_type: BacktestSource = "DEMO") -> dict[str, Any] | None:
    return _artifact(source_type, "benchmark")
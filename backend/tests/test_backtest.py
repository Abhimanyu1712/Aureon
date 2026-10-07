import csv
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.backtest import BacktestConfig, BacktestEngine, run_backtest
from app.backtest.execution import BacktestSignal, MarketBar
from app.backtest import service as backtest_service
from app.main import app
from app.ingest import run_ingest
from app.analytics.pipeline import run_analytics
from app.analytics.signal_pipeline import run_signal_pipeline


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEMO_CSV = PROJECT_ROOT / "data" / "demo" / "DEMO_SYNTHETIC_MCX_BHAVCOPY.csv"
client = TestClient(app)
TRADE_DATES = [date(2026, 9, day) for day in range(1, 6)]
EXPIRY = date(2026, 9, 30)
CONTRACTS = (
    ("GOLDM", "GOLDM|2026-09-30", Decimal("100")),
    ("GOLDTEN", "GOLDTEN|2026-09-30", Decimal("10")),
    ("GOLDGUINEA", "GOLDGUINEA|2026-09-30", Decimal("8")),
)


def market_data(
    *,
    target_prices=(Decimal("700"), Decimal("700"), Decimal("710"), Decimal("711"), Decimal("711")),
    peer_prices=(Decimal("700"), Decimal("700"), Decimal("700"), Decimal("700"), Decimal("700")),
    expiry=EXPIRY,
    low_volume_days=(),
    missing_peer_days=(),
):
    bars = {}
    for day_index, trading_date in enumerate(TRADE_DATES):
        values = (target_prices[day_index], peer_prices[day_index], peer_prices[day_index])
        for contract_index, ((symbol, _, _), price) in enumerate(zip(CONTRACTS, values)):
            if contract_index > 0 and trading_date.day in missing_peer_days and contract_index == 2:
                continue
            contract_id = f"{symbol}|{expiry.isoformat()}"
            bar = MarketBar(
                symbol=symbol,
                trade_date=trading_date,
                expiry_date=expiry,
                contract_id=contract_id,
                normalized_price=price,
                volume=Decimal("100") if trading_date.day in low_volume_days else Decimal("1000"),
                open_interest=Decimal("2000"),
                source_type="DEMO",
                source_file="SYNTHETIC_TEST_FIXTURE.csv",
            )
            bars[(contract_id, trading_date, "DEMO")] = bar
    return bars


def signal_for(day_index, *, z_score, status, direction, expiry=EXPIRY, days_to_expiry=None, trade_date=None):
    trade_date = TRADE_DATES[day_index] if trade_date is None else trade_date
    contract_id = f"GOLDM|{expiry.isoformat()}"
    return BacktestSignal(
        symbol="GOLDM",
        trade_date=trade_date,
        expiry_date=expiry,
        contract_id=contract_id,
        normalized_price=Decimal("700"),
        peer_reference=Decimal("700"),
        spread=Decimal("0"),
        z_score=z_score,
        peer_count=2,
        volume=Decimal("1000"),
        open_interest=Decimal("2000"),
        days_to_expiry=(expiry - trade_date).days if days_to_expiry is None else days_to_expiry,
        relative_direction=direction,
        signal_status=status,
        source_type="DEMO",
        source_file="SYNTHETIC_TEST_FIXTURE.csv",
    )


def signal_map(*signals):
    return {(item.contract_id, item.trade_date, item.source_type): item for item in signals}


def default_signals(direction="CHEAP", expiry=EXPIRY):
    return signal_map(
        signal_for(0, z_score=Decimal("-2.5") if direction == "CHEAP" else Decimal("2.5"), status="STRONG_RELATIVE_DEVIATION", direction=direction, expiry=expiry),
        signal_for(2, z_score=Decimal("0.2"), status="NO_SIGNAL", direction="NEUTRAL", expiry=expiry),
    )


def settings(**overrides):
    values = {
        "initial_capital": Decimal("1000000"),
        "minimum_volume": Decimal("500"),
        "minimum_open_interest": Decimal("1000"),
        "estimated_cost_rate_per_side": Decimal("0.0005"),
    }
    values.update(overrides)
    return BacktestConfig(**values)


def run_fixture(**kwargs):
    config = kwargs.pop("config", settings())
    bars = kwargs.pop("bars", market_data())
    direction = kwargs.pop("direction", "CHEAP")
    signals = kwargs.pop("signals", default_signals(direction))
    return BacktestEngine(config).run(bars, signals, **kwargs)


def test_entry_uses_next_available_close_and_keeps_exact_contract_legs():
    result = run_fixture()

    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.entry_signal_date == TRADE_DATES[0]
    assert trade.entry_date == TRADE_DATES[1]
    assert trade.target_contract_id == "GOLDM|2026-09-30"
    assert trade.target_entry_price == Decimal("700")
    assert trade.direction == "CHEAP"
    assert len(trade.legs) == 3
    assert trade.legs[0].position_side == "LONG"
    assert all(leg.position_side == "SHORT" for leg in trade.legs[1:])
    assert sum((leg.entry_notional for leg in trade.legs[1:]), Decimal(0)) == trade.legs[0].entry_notional
    assert all("|2026-09-30" in leg.contract_id for leg in trade.legs)


def test_mean_reversion_exit_uses_next_available_close_and_records_both_leg_pnl():
    trade = run_fixture().trades[0]

    assert trade.exit_date == TRADE_DATES[3]
    assert trade.exit_reason == "MEAN_REVERSION"
    assert trade.exit_z_score == Decimal("0.2")
    assert trade.target_leg_gross_pnl is not None and trade.target_leg_gross_pnl > 0
    assert trade.peer_leg_gross_pnl == 0
    assert trade.gross_pnl == trade.target_leg_gross_pnl + trade.peer_leg_gross_pnl
    assert trade.net_pnl == trade.gross_pnl - trade.transaction_cost
    assert trade.status == "COMPLETED"


def test_expensive_direction_builds_short_target_long_peer_legs_and_can_lose():
    result = run_fixture(
        direction="EXPENSIVE",
        bars=market_data(target_prices=(Decimal("700"), Decimal("700"), Decimal("710"), Decimal("711"), Decimal("711"))),
        signals=default_signals("EXPENSIVE"),
    )
    trade = result.trades[0]

    assert trade.legs[0].position_side == "SHORT"
    assert all(leg.position_side == "LONG" for leg in trade.legs[1:])
    assert trade.net_pnl < 0


def test_zero_and_positive_costs_and_both_fills_and_legs_are_accounted():
    zero_cost = run_fixture(config=settings(estimated_cost_rate_per_side=Decimal(0))).trades[0]
    costed = run_fixture().trades[0]

    assert zero_cost.transaction_cost == 0
    assert zero_cost.net_pnl == zero_cost.gross_pnl
    expected_cost = sum((leg.entry_cost + leg.exit_cost for leg in costed.legs), Decimal(0))
    assert costed.transaction_cost == expected_cost
    assert costed.transaction_cost > 0
    assert sum((leg.entry_cost for leg in costed.legs), Decimal(0)) > 0
    assert sum((leg.exit_cost for leg in costed.legs), Decimal(0)) > 0
    assert costed.legs[0].entry_cost > 0 and costed.legs[0].exit_cost > 0
    assert all(leg.entry_cost > 0 and leg.exit_cost > 0 for leg in costed.legs[1:])
    assert costed.net_pnl < costed.gross_pnl


def test_low_entry_liquidity_rejects_trade_and_records_reason():
    result = run_fixture(bars=market_data(low_volume_days=(2,)))

    assert result.trades == []
    assert any(item.entry_rejected_reason == "INSUFFICIENT_LIQUIDITY" for item in result.rejected_entries)


def test_exit_waits_for_joint_liquid_close_after_liquidity_failure():
    result = run_fixture(bars=market_data(low_volume_days=(4,)))

    trade = result.trades[0]
    assert trade.exit_date == TRADE_DATES[4]
    assert trade.exit_reason == "MEAN_REVERSION"
    assert trade.legs[0].exit_price_date == TRADE_DATES[4]


def test_missing_peer_delays_exit_until_joint_observation_returns():
    result = run_fixture(bars=market_data(missing_peer_days=(4,)))

    trade = result.trades[0]
    assert trade.exit_date == TRADE_DATES[4]
    assert trade.exit_reason == "MEAN_REVERSION"


def test_peer_disappearance_queues_peer_unavailable_exit():
    signals = signal_map(
        signal_for(0, z_score=Decimal("-2.5"), status="STRONG_RELATIVE_DEVIATION", direction="CHEAP"),
    )
    result = run_fixture(bars=market_data(missing_peer_days=(3,)), signals=signals)

    assert result.trades[0].exit_date == TRADE_DATES[3]
    assert result.trades[0].exit_reason == "PEER_UNAVAILABLE"


def test_expiry_and_max_holding_period_force_exits():
    expiry = TRADE_DATES[2]
    expiry_result = run_fixture(
        bars=market_data(expiry=expiry),
        signals=default_signals(expiry=expiry),
        config=settings(minimum_days_to_expiry=0),
    )
    max_hold_result = run_fixture(
        signals=signal_map(
            signal_for(0, z_score=Decimal("-2.5"), status="STRONG_RELATIVE_DEVIATION", direction="CHEAP"),
        ),
        config=settings(max_holding_days=1),
    )

    assert expiry_result.trades[0].exit_reason == "EXPIRY"
    assert expiry_result.trades[0].exit_date == expiry
    assert max_hold_result.trades[0].exit_reason == "MAX_HOLDING_PERIOD"
    assert max_hold_result.trades[0].days_held == 1


def test_entry_rechecks_minimum_days_to_expiry_at_next_date_fill():
    expiry = date(2026, 9, 6)
    result = run_fixture(
        bars=market_data(expiry=expiry),
        signals=signal_map(
            signal_for(
                0,
                z_score=Decimal("-2.5"),
                status="STRONG_RELATIVE_DEVIATION",
                direction="CHEAP",
                expiry=expiry,
            )
        ),
        config=settings(minimum_days_to_expiry=5),
    )

    assert result.trades == []
    assert result.rejected_entries[0].entry_rejected_reason == "EXPIRY_FILTER_FAILED"


def test_expiry_with_missing_peer_uses_last_joint_basket_mark():
    expiry = TRADE_DATES[2]
    result = run_fixture(
        bars=market_data(expiry=expiry, missing_peer_days=(expiry.day,)),
        signals=default_signals(expiry=expiry),
        config=settings(minimum_days_to_expiry=0),
    )
    trade = result.trades[0]

    assert trade.exit_reason == "EXPIRY"
    assert trade.exit_date == expiry
    assert {leg.exit_price_date for leg in trade.legs} == {TRADE_DATES[1]}


def test_equity_curve_marks_open_position_and_metrics_are_dynamic():
    result = run_fixture()

    assert [point.date for point in result.equity_curve] == sorted(point.date for point in result.equity_curve)
    assert result.equity_curve[0].ending_equity == result.initial_capital
    assert result.equity_curve[2].daily_pnl != 0
    assert result.metrics["gross_pnl"] == result.trades[0].gross_pnl
    assert result.metrics["transaction_cost"] == result.trades[0].transaction_cost
    assert abs(result.metrics["net_pnl"] - result.trades[0].net_pnl) < Decimal("1e-20")
    assert result.metrics["cumulative_return"] == result.metrics["net_pnl"] / result.initial_capital
    assert result.benchmark["contract_id"] == "GOLDTEN|2026-09-30"
    assert result.benchmark["status"] == "CALCULATED"
    assert result.metrics["sharpe"]["status"] == "INSUFFICIENT_DATA"
    assert result.metrics["sharpe"]["minimum_observations"] == 20


def test_benchmark_is_insufficient_when_no_exact_contract_spans_all_dates():
    bars = market_data()
    del bars[("GOLDTEN|2026-09-30", TRADE_DATES[2], "DEMO")]
    signals = signal_map(
        signal_for(0, z_score=Decimal(0), status="NO_SIGNAL", direction="NEUTRAL"),
    )

    result = BacktestEngine(settings()).run(bars, signals)

    assert result.benchmark["status"] == "INSUFFICIENT_DATA"
    assert result.benchmark["benchmark_return"] is None
    assert result.benchmark["relative_outperformance"] is None


def test_future_rows_do_not_change_earlier_trades_or_equity():
    bars = market_data()
    signals = default_signals()
    base = BacktestEngine(settings()).run(bars, signals)

    future_date = date(2026, 9, 6)
    for symbol, contract_id, _ in CONTRACTS:
        bars[(contract_id, future_date, "DEMO")] = MarketBar(
            symbol=symbol,
            trade_date=future_date,
            expiry_date=EXPIRY,
            contract_id=contract_id,
            normalized_price=Decimal("9999"),
            volume=Decimal("0"),
            open_interest=Decimal("0"),
            source_type="DEMO",
            source_file="SYNTHETIC_TEST_FIXTURE.csv",
        )
    signals[("GOLDM|2026-09-30", future_date, "DEMO")] = signal_for(
        4,
        z_score=Decimal("-9"),
        status="STRONG_RELATIVE_DEVIATION",
        direction="CHEAP",
        trade_date=future_date,
    )
    extended = BacktestEngine(settings()).run(bars, signals)

    assert base.trades == [trade for trade in extended.trades if trade.entry_date <= TRADE_DATES[3]]
    assert base.equity_curve == [point for point in extended.equity_curve if point.date <= TRADE_DATES[4]]


def test_no_future_liquidity_changes_historical_entry_decision():
    base_bars = market_data()
    low_future = market_data(low_volume_days=(4, 5))
    base = BacktestEngine(settings()).run(base_bars, default_signals())
    changed = BacktestEngine(settings()).run(low_future, default_signals())

    assert base.trades[0].entry_date == changed.trades[0].entry_date
    assert base.trades[0].target_entry_price == changed.trades[0].target_entry_price
    assert base.equity_curve[1] == changed.equity_curve[1]


def test_stage4_demo_without_strong_signals_returns_insufficient_metrics_and_no_trades(tmp_path):
    source_bytes = DEMO_CSV.read_bytes()
    stage2 = run_ingest(DEMO_CSV, tmp_path / "processed")
    stage3 = run_analytics(stage2.processed_path, tmp_path / "analytics")
    stage4 = run_signal_pipeline(stage3.normalized_path, stage3.relative_value_path, tmp_path / "analytics" / "demo_signals.csv")
    result = run_backtest(
        stage3.normalized_path,
        stage4.output_path,
        tmp_path / "backtests",
        config=settings(),
    )

    assert DEMO_CSV.read_bytes() == source_bytes
    assert result.dataset_type == "DEMO / SYNTHETIC DATA"
    assert result.trades == []
    assert result.metrics["sharpe"]["status"] == "INSUFFICIENT_DATA"
    assert result.metrics["cumulative_return"] == 0
    assert result.benchmark["status"] == "CALCULATED"
    assert "No Stage 4 strong-deviation entry signal" in " ".join(result.data_quality_notes)
    assert json.loads((tmp_path / "backtests" / "demo_backtest_report.json").read_text())[
        "dataset_type"
    ] == "DEMO / SYNTHETIC DATA"


def test_backtest_api_returns_safe_empty_data_and_generated_report(tmp_path, monkeypatch):
    monkeypatch.setattr(backtest_service, "BACKTEST_DIR", tmp_path)
    empty = client.get("/api/backtest/summary")
    assert empty.status_code == 200
    assert empty.json()["status"] == "NO_BACKTEST_DATA"

    output = tmp_path / "fixture_backtest_report.json"
    output.write_text(
        json.dumps({
            "dataset_type": "DEMO / SYNTHETIC DATA",
            "metrics": {"net_pnl": "0"},
            "artifact_paths": {},
        }),
        encoding="utf-8",
    )
    response = client.get("/api/backtest/report")
    assert response.status_code == 200
    assert response.json()["status"] == "AVAILABLE"
    assert response.json()["data"]["dataset_type"] == "DEMO / SYNTHETIC DATA"


def test_all_backtest_api_views_serve_generated_demo_artifacts(tmp_path, monkeypatch):
    stage2 = run_ingest(DEMO_CSV, tmp_path / "processed")
    stage3 = run_analytics(stage2.processed_path, tmp_path / "analytics")
    stage4 = run_signal_pipeline(
        stage3.normalized_path,
        stage3.relative_value_path,
        tmp_path / "analytics" / "demo_signals.csv",
    )
    run_backtest(
        stage3.normalized_path,
        stage4.output_path,
        tmp_path / "backtests",
        config=settings(),
    )
    monkeypatch.setattr(backtest_service, "BACKTEST_DIR", tmp_path / "backtests")

    responses = {
        endpoint: client.get(f"/api/backtest/{endpoint}")
        for endpoint in ("summary", "trades", "equity", "benchmark", "report")
    }

    assert all(response.status_code == 200 for response in responses.values())
    assert all(response.json()["status"] == "AVAILABLE" for response in responses.values())
    assert responses["summary"].json()["data"]["trade_count"] == 0
    assert responses["trades"].json()["data"] == []
    assert len(responses["equity"].json()["data"]) == 3
    assert responses["benchmark"].json()["data"]["status"] == "CALCULATED"
    assert responses["report"].json()["data"]["dataset_type"] == "DEMO / SYNTHETIC DATA"

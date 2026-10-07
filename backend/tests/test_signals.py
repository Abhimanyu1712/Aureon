import csv
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.analytics import signal_service
from app.analytics.pipeline import run_analytics
from app.analytics.signal_pipeline import run_signal_pipeline
from app.analytics.signals import SignalConfig, SignalEngine, SignalEvidence
from app.ingest import run_ingest
from app.main import app


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEMO_CSV = PROJECT_ROOT / "data" / "demo" / "DEMO_SYNTHETIC_MCX_BHAVCOPY.csv"
client = TestClient(app)


def evidence(
    z_score=Decimal("0"),
    *,
    analytics_status="READY",
    peer_count=3,
    volume=Decimal("800"),
    open_interest=Decimal("2000"),
    trade_date=date(2026, 9, 1),
    expiry_date=date(2026, 9, 30),
    history_count=5,
):
    return SignalEvidence(
        symbol="GOLDTEN",
        trade_date=trade_date,
        expiry_date=expiry_date,
        contract_id=f"GOLDTEN|{expiry_date.isoformat()}",
        normalized_price=Decimal("700"),
        peer_reference=Decimal("700"),
        spread=Decimal("0"),
        z_score=z_score,
        peer_count=peer_count,
        volume=volume,
        open_interest=open_interest,
        rolling_history_count=history_count,
        analytics_status=analytics_status,
        source_type="DEMO",
        source_file="DEMO_SYNTHETIC_MCX_BHAVCOPY.csv",
    )


@pytest.mark.parametrize(
    "z_score,expected",
    [
        ("0", "NO_SIGNAL"),
        ("1.49", "NO_SIGNAL"),
        ("1.50", "WATCHLIST"),
        ("1.99", "WATCHLIST"),
        ("2.00", "STRONG_RELATIVE_DEVIATION"),
        ("-1.50", "WATCHLIST"),
        ("-2.00", "STRONG_RELATIVE_DEVIATION"),
    ],
)
def test_signal_thresholds_are_symmetric_and_boundary_inclusive(z_score, expected):
    result = SignalEngine(SignalConfig()).evaluate(evidence(Decimal(z_score)))

    assert result.signal_status == expected


@pytest.mark.parametrize(
    "z_score,direction",
    [("-0.25", "CHEAP"), ("0.25", "EXPENSIVE"), ("0", "NEUTRAL"), ("1e-13", "NEUTRAL")],
)
def test_relative_direction_uses_z_score_sign(z_score, direction):
    result = SignalEngine(SignalConfig()).evaluate(evidence(Decimal(z_score)))

    assert result.relative_direction == direction


@pytest.mark.parametrize(
    "overrides,expected",
    [
        ({"analytics_status": "INSUFFICIENT_HISTORY", "z_score": Decimal("3")}, "INSUFFICIENT_HISTORY"),
        ({"analytics_status": "INSUFFICIENT_PEERS", "z_score": Decimal("3")}, "INSUFFICIENT_PEERS"),
        ({"peer_count": 1, "z_score": Decimal("3")}, "INSUFFICIENT_PEERS"),
        ({"volume": Decimal("499"), "z_score": Decimal("3")}, "INSUFFICIENT_LIQUIDITY"),
        ({"open_interest": Decimal("999"), "z_score": Decimal("3")}, "INSUFFICIENT_LIQUIDITY"),
        ({"volume": None, "z_score": Decimal("3")}, "INSUFFICIENT_LIQUIDITY"),
        ({"open_interest": None, "z_score": Decimal("3")}, "INSUFFICIENT_LIQUIDITY"),
        ({"expiry_date": date(2026, 9, 5), "z_score": Decimal("3")}, "EXPIRY_FILTER_FAILED"),
    ],
)
def test_rejection_filters_override_z_classification(overrides, expected):
    result = SignalEngine(SignalConfig()).evaluate(evidence(**overrides))

    assert result.signal_status == expected


def test_liquidity_passes_when_both_proxy_values_meet_thresholds():
    result = SignalEngine(SignalConfig()).evaluate(
        evidence(Decimal("1.6"), volume=Decimal("500"), open_interest=Decimal("1000"))
    )

    assert result.signal_status == "WATCHLIST"


def test_days_to_expiry_uses_row_dates_and_boundary_is_inclusive():
    engine = SignalEngine(SignalConfig())
    valid = engine.evaluate(
        evidence(
            Decimal("2"),
            trade_date=date(2026, 9, 1),
            expiry_date=date(2026, 9, 6),
        )
    )
    expired = engine.evaluate(
        evidence(
            Decimal("2"),
            trade_date=date(2026, 9, 7),
            expiry_date=date(2026, 9, 6),
        )
    )

    assert valid.days_to_expiry == 5
    assert valid.signal_status == "STRONG_RELATIVE_DEVIATION"
    assert expired.days_to_expiry == -1
    assert expired.signal_status == "EXPIRY_FILTER_FAILED"


def test_explanation_uses_actual_evidence_and_rejection_reason():
    expensive = SignalEngine(SignalConfig()).evaluate(
        evidence(
            Decimal("2.31"),
            trade_date=date(2026, 9, 1),
            expiry_date=date(2026, 9, 19),
        )
    )
    cheap = SignalEngine(SignalConfig()).evaluate(
        evidence(
            Decimal("-2.31"),
            volume=Decimal("100"),
            trade_date=date(2026, 9, 1),
            expiry_date=date(2026, 9, 19),
        )
    )

    assert "2.31" in expensive.explanation
    assert "above" in expensive.explanation
    assert "18 days remain" in expensive.explanation
    assert "CHEAP" == cheap.relative_direction
    assert "below" in cheap.explanation
    assert "volume 100" in cheap.explanation
    assert "Liquidity proxy failed" in cheap.explanation
    assert "NOT_APPLIED" == expensive.cost_filter_status
    assert "Transaction costs are not applied" in expensive.explanation


def test_bad_contract_identity_and_nonfinite_z_are_rejected():
    engine = SignalEngine(SignalConfig())
    with pytest.raises(ValueError, match="Invalid contract identity"):
        engine.evaluate(
            SignalEvidence(**{**evidence().__dict__, "contract_id": "GOLDTEN|2026-10-30"})
        )
    with pytest.raises(ValueError, match="z_score must be finite"):
        engine.evaluate(evidence(Decimal("Infinity")))


def test_config_can_be_loaded_from_environment(monkeypatch):
    monkeypatch.setenv("AUREON_SIGNAL_WATCHLIST_Z", "1.7")
    monkeypatch.setenv("AUREON_SIGNAL_MIN_VOLUME", "250")
    monkeypatch.setenv("AUREON_SIGNAL_MIN_DAYS_TO_EXPIRY", "7")

    config = SignalConfig.from_environment()

    assert config.watchlist_z == Decimal("1.7")
    assert config.minimum_volume == Decimal("250")
    assert config.minimum_days_to_expiry == 7


def _prepare_demo_signal_output(tmp_path):
    source_bytes = DEMO_CSV.read_bytes()
    stage2 = run_ingest(DEMO_CSV, tmp_path / "processed")
    stage3 = run_analytics(stage2.processed_path, tmp_path / "analytics")
    signals = run_signal_pipeline(
        stage3.normalized_path,
        stage3.relative_value_path,
        tmp_path / "analytics" / "demo_signals.csv",
    )
    assert DEMO_CSV.read_bytes() == source_bytes
    return signals


def test_demo_stage4_pipeline_produces_explained_filtered_results(tmp_path):
    result = _prepare_demo_signal_output(tmp_path)

    assert result.total_rows == 24
    assert result.source_types == ("DEMO",)
    assert result.status_counts["INSUFFICIENT_HISTORY"] == 16
    assert result.status_counts["INSUFFICIENT_LIQUIDITY"] > 0
    assert result.status_counts["EXPIRY_FILTER_FAILED"] > 0
    assert result.status_counts["NO_SIGNAL"] > 0

    with Path(result.output_path).open(newline="", encoding="utf-8") as source:
        rows = list(csv.DictReader(source))
    assert len(rows) == 24
    assert {row["source_type"] for row in rows} == {"DEMO"}
    assert all(row["explanation"] and "Transaction costs are not applied" in row["explanation"] for row in rows)
    assert len({row["contract_id"] for row in rows if row["symbol"] == "GOLDM"}) == 2
    assert all(row["cost_filter_status"] == "NOT_APPLIED" for row in rows)


def test_signal_api_filters_date_status_and_symbol_and_rejects_invalid_symbol(tmp_path, monkeypatch):
    result = _prepare_demo_signal_output(tmp_path)
    monkeypatch.setattr(signal_service, "ANALYTICS_DIR", Path(result.output_path).parent)

    all_signals = client.get("/api/analytics/signals")
    by_date = client.get("/api/analytics/signals?date=2026-09-03")
    by_status = client.get("/api/analytics/signals?status=EXPIRY_FILTER_FAILED")
    by_symbol = client.get("/api/analytics/signals/GOLDM?expiry_date=2026-09-04")

    assert all_signals.status_code == 200
    assert all_signals.json()["data_type"] == "DEMO"
    assert all_signals.json()["record_count"] == 24
    assert by_date.status_code == 200 and by_date.json()["record_count"] == 8
    assert by_status.status_code == 200 and by_status.json()["record_count"] > 0
    assert all(row["signal_status"] == "EXPIRY_FILTER_FAILED" for row in by_status.json()["records"])
    assert by_symbol.status_code == 200
    assert all(row["symbol"] == "GOLDM" for row in by_symbol.json()["records"])
    assert client.get("/api/analytics/signals/SILVER").status_code == 404
    assert client.get("/api/analytics/signals?status=COST_FILTER_FAILED").status_code == 422
    assert client.get("/api/analytics/signals?date=not-a-date").status_code == 422


def test_signal_api_returns_safe_empty_result(tmp_path, monkeypatch):
    monkeypatch.setattr(signal_service, "ANALYTICS_DIR", tmp_path)

    response = client.get("/api/analytics/signals")

    assert response.status_code == 200
    assert response.json() == {
        "status": "NO_SIGNAL_DATA",
        "data_type": "DEMO",
        "record_count": 0,
        "records": [],
    }


def test_future_stage3_rows_do_not_change_prior_signal_results(tmp_path):
    stage2 = run_ingest(DEMO_CSV, tmp_path / "processed")
    stage3 = run_analytics(stage2.processed_path, tmp_path / "analytics")
    normalized_path = Path(stage3.normalized_path)
    relative_path = Path(stage3.relative_value_path)

    def load(path):
        with path.open(newline="", encoding="utf-8") as source:
            return list(csv.DictReader(source))

    def save(path, rows):
        with path.open("w", newline="", encoding="utf-8") as target:
            writer = csv.DictWriter(target, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)

    normalized_rows = load(normalized_path)
    relative_rows = load(relative_path)
    earlier = run_signal_pipeline(
        normalized_path,
        relative_path,
        tmp_path / "earlier_signals.csv",
    )
    old_normalized_count = len(normalized_rows)
    old_relative_count = len(relative_rows)

    future_normalized = [dict(row) for row in normalized_rows if row["trade_date"] == "2026-09-03"]
    future_relative = [dict(row) for row in relative_rows if row["trade_date"] == "2026-09-03"]
    for row in future_normalized + future_relative:
        row["trade_date"] = "2026-09-04"
    save(normalized_path, normalized_rows + future_normalized)
    save(relative_path, relative_rows + future_relative)
    extended = run_signal_pipeline(
        normalized_path,
        relative_path,
        tmp_path / "extended_signals.csv",
    )

    def past_records(path):
        with Path(path).open(newline="", encoding="utf-8") as source:
            return {
                (row["symbol"], row["trade_date"], row["expiry_date"]): row
                for row in csv.DictReader(source)
                if row["trade_date"] <= "2026-09-03"
            }

    assert old_normalized_count == 24
    assert old_relative_count == 24
    assert past_records(earlier.output_path) == past_records(extended.output_path)
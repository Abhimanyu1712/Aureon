import csv
from pathlib import Path
from decimal import Decimal
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.analytics import service as analytics_service
from app.analytics.normalization import (
    CONTRACT_SPECS,
    get_contract_spec,
    normalize_price_to_purity_adjusted_rupees_per_gram,
)
from app.analytics.relative_value import NormalizedObservation, calculate_relative_value
from app.analytics.pipeline import AnalyticsInputError, run_analytics
from app.ingest import run_ingest
from app.main import app


client = TestClient(app)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEMO_CSV = PROJECT_ROOT / "data" / "demo" / "DEMO_SYNTHETIC_MCX_BHAVCOPY.csv"


def test_contract_specifications_match_stage_three_requirements():
    assert set(CONTRACT_SPECS) == {"GOLDM", "GOLDTEN", "GOLDGUINEA", "GOLDPETAL"}
    assert (
        CONTRACT_SPECS["GOLDM"].contract_size_grams,
        CONTRACT_SPECS["GOLDM"].quote_grams,
        CONTRACT_SPECS["GOLDM"].purity_fineness,
    ) == (Decimal("100"), Decimal("10"), 995)
    assert (
        CONTRACT_SPECS["GOLDTEN"].contract_size_grams,
        CONTRACT_SPECS["GOLDTEN"].quote_grams,
        CONTRACT_SPECS["GOLDTEN"].purity_fineness,
    ) == (Decimal("10"), Decimal("10"), 999)
    assert (
        CONTRACT_SPECS["GOLDGUINEA"].contract_size_grams,
        CONTRACT_SPECS["GOLDGUINEA"].quote_grams,
        CONTRACT_SPECS["GOLDGUINEA"].purity_fineness,
    ) == (Decimal("8"), Decimal("8"), 999)
    assert (
        CONTRACT_SPECS["GOLDPETAL"].contract_size_grams,
        CONTRACT_SPECS["GOLDPETAL"].quote_grams,
        CONTRACT_SPECS["GOLDPETAL"].purity_fineness,
    ) == (Decimal("1"), Decimal("1"), 999)
    assert "3rd-5th" in CONTRACT_SPECS["GOLDM"].expiry_rule
    assert "27th-31st" in CONTRACT_SPECS["GOLDPETAL"].expiry_rule


@pytest.mark.parametrize(
    ("symbol", "quote", "expected_per_gram"),
    [
        ("GOLDM", "7031", Decimal("703.1")),
        ("GOLDTEN", "7040", Decimal("704")),
        ("GOLDGUINEA", "5616", Decimal("702")),
        ("GOLDPETAL", "704", Decimal("704")),
    ],
)
def test_normalizes_quote_bases_to_rupees_per_gram(symbol, quote, expected_per_gram):
    result = normalize_price_to_purity_adjusted_rupees_per_gram(symbol, quote)

    assert result.normalized_price_per_gram == expected_per_gram


def test_goldm_purity_adjustment_is_manually_verified_to_six_decimals():
    result = normalize_price_to_purity_adjusted_rupees_per_gram("GOLDM", "7031")

    assert result.purity_adjusted_price_per_gram.quantize(Decimal("0.000001")) == Decimal(
        "705.926533"
    )


@pytest.mark.parametrize("symbol,quote", [("GOLDTEN", "7040"), ("GOLDGUINEA", "5616"), ("GOLDPETAL", "704")])
def test_999_fineness_contracts_need_no_purity_scale(symbol, quote):
    result = normalize_price_to_purity_adjusted_rupees_per_gram(symbol, quote)

    assert result.purity_adjusted_price_per_gram == result.normalized_price_per_gram


def test_symbol_lookup_is_case_insensitive_and_unknown_symbol_fails_clearly():
    assert get_contract_spec(" goldm ").symbol == "GOLDM"
    with pytest.raises(ValueError, match="Unsupported gold contract symbol"):
        get_contract_spec("SILVER")


@pytest.mark.parametrize("price", [None, "", "not-a-price", "NaN", "Infinity", "0", "-1"])
def test_missing_or_invalid_price_is_rejected(price):
    with pytest.raises(ValueError, match="finite positive number"):
        normalize_price_to_purity_adjusted_rupees_per_gram("GOLDM", price)


def observation(symbol, trade_day, expiry_day, price, source_type="DEMO"):
    expiry = date.fromisoformat(expiry_day)
    return NormalizedObservation(
        symbol=symbol,
        trade_date=date.fromisoformat(trade_day),
        expiry_date=expiry,
        contract_id=f"{symbol}|{expiry.isoformat()}",
        normalized_price_per_gram=Decimal(str(price)),
        purity_adjusted_price_per_gram=Decimal(str(price)),
        close=Decimal(str(price)),
        volume=Decimal("1"),
        open_interest=Decimal("1"),
        source_type=source_type,
        source_file="fixture.csv",
    )


def test_peer_median_spread_and_peer_count():
    rows = [
        observation(symbol, "2026-09-01", "2026-09-04", price)
        for symbol, price in [("GOLDM", 10), ("GOLDTEN", 20), ("GOLDGUINEA", 30), ("GOLDPETAL", 40)]
    ]

    result = calculate_relative_value(rows, rolling_window=3, min_periods=3)
    goldm = next(point for point in result if point.symbol == "GOLDM")

    assert goldm.peer_reference == Decimal("30")
    assert goldm.spread == Decimal("-20")
    assert goldm.peer_count == 3


def target_series(target_prices, peer_price=9):
    rows = []
    for day, target_price in enumerate(target_prices, start=1):
        trade_day = f"2026-09-0{day}"
        rows.extend(
            [
                observation("GOLDM", trade_day, "2026-09-04", target_price),
                observation("GOLDTEN", trade_day, "2026-09-30", peer_price),
                observation("GOLDGUINEA", trade_day, "2026-09-29", peer_price),
            ]
        )
    return rows


def test_rolling_mean_population_std_and_z_score():
    result = calculate_relative_value(
        target_series([10, 11, 13]), rolling_window=3, min_periods=3
    )
    goldm = [point for point in result if point.symbol == "GOLDM"][-1]

    assert goldm.spread == Decimal("4")
    assert goldm.rolling_mean == Decimal(7) / Decimal(3)
    expected_std = (14**0.5) / 3
    assert abs(float(goldm.rolling_std) - expected_std) < 1e-12
    assert abs(float(goldm.z_score) - (4 - 7 / 3) / expected_std) < 1e-12
    assert goldm.analytics_status == "READY"


def test_zero_variance_and_insufficient_peers_have_safe_statuses():
    zero_variance = calculate_relative_value(
        target_series([10, 10, 10]), rolling_window=3, min_periods=3
    )
    goldm = [point for point in zero_variance if point.symbol == "GOLDM"][-1]
    assert goldm.analytics_status == "ZERO_VARIANCE"
    assert goldm.rolling_std == 0
    assert goldm.z_score is None

    insufficient = calculate_relative_value(
        [
            observation("GOLDM", "2026-09-01", "2026-09-04", 10),
            observation("GOLDTEN", "2026-09-01", "2026-09-30", 9),
        ],
        rolling_window=3,
        min_periods=3,
    )
    assert {point.analytics_status for point in insufficient} == {"INSUFFICIENT_PEERS"}
    assert all(point.peer_reference is None and point.spread is None for point in insufficient)


def test_different_expiries_stay_distinct_but_share_expiry_month_cohort():
    rows = target_series([10, 11, 13])
    rows.append(observation("GOLDM", "2026-09-01", "2026-09-05", 12))

    result = calculate_relative_value(rows, rolling_window=3, min_periods=3)
    goldm_ids = {point.contract_id for point in result if point.symbol == "GOLDM"}

    assert goldm_ids == {"GOLDM|2026-09-04", "GOLDM|2026-09-05"}
    assert len(result) == len(rows)


def test_peer_comparison_does_not_cross_expiry_month_or_source_type():
    rows = [
        observation("GOLDM", "2026-09-01", "2026-09-04", 10, "DEMO"),
        observation("GOLDTEN", "2026-09-01", "2026-10-30", 9, "DEMO"),
        observation("GOLDGUINEA", "2026-09-01", "2026-10-29", 9, "DEMO"),
        observation("GOLDPETAL", "2026-09-01", "2026-09-30", 9, "REAL"),
    ]

    result = calculate_relative_value(rows, rolling_window=3, min_periods=3)

    assert all(point.analytics_status == "INSUFFICIENT_PEERS" for point in result)
    assert all(point.peer_reference is None for point in result)


def test_future_observations_do_not_change_prior_rolling_statistics():
    historical = target_series([10, 11])
    future_extended = target_series([10, 11, 1000])
    historical_result = calculate_relative_value(
        historical, rolling_window=3, min_periods=2
    )
    extended_result = calculate_relative_value(
        future_extended, rolling_window=3, min_periods=2
    )
    historical_goldm = [point for point in historical_result if point.symbol == "GOLDM"]
    extended_goldm = [point for point in extended_result if point.symbol == "GOLDM"][:2]

    assert [point.rolling_mean for point in historical_goldm] == [
        point.rolling_mean for point in extended_goldm
    ]
    assert [point.z_score for point in historical_goldm] == [
        point.z_score for point in extended_goldm
    ]


def test_stage2_to_stage3_pipeline_preserves_inputs_and_contract_expiries(tmp_path):
    demo_bytes = DEMO_CSV.read_bytes()
    stage2 = run_ingest(DEMO_CSV, tmp_path / "processed")
    stage2_bytes = Path(stage2.processed_path).read_bytes()
    analytics = run_analytics(stage2.processed_path, tmp_path / "analytics")

    assert DEMO_CSV.read_bytes() == demo_bytes
    assert Path(stage2.processed_path).read_bytes() == stage2_bytes
    assert analytics.total_rows == 24
    assert analytics.ready_rows == 8
    assert analytics.insufficient_history_rows == 16
    with Path(analytics.normalized_path).open(newline="", encoding="utf-8") as source:
        normalized = list(csv.DictReader(source))
    with Path(analytics.relative_value_path).open(newline="", encoding="utf-8") as source:
        relative = list(csv.DictReader(source))

    goldm_september = next(
        row for row in normalized
        if row["symbol"] == "GOLDM" and row["trade_date"] == "2026-09-01"
        and row["expiry_date"] == "2026-09-04"
    )
    assert Decimal(goldm_september["normalized_price_per_gram"]) == Decimal("703.1")
    assert Decimal(goldm_september["purity_adjusted_price_per_gram"]).quantize(
        Decimal("0.000001")
    ) == Decimal("705.926533")
    assert len({row["contract_id"] for row in normalized if row["symbol"] == "GOLDM"}) == 2
    assert len(relative) == 24
    assert {row["source_type"] for row in relative} == {"DEMO"}
    assert {row["analytics_status"] for row in relative} == {
        "INSUFFICIENT_HISTORY",
        "READY",
    }


def test_analytics_pipeline_fails_clearly_on_unknown_symbol_or_bad_identity(tmp_path):
    source_path = tmp_path / "unknown.csv"
    with source_path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(
            output,
            fieldnames=[
                "symbol", "trade_date", "expiry_date", "contract_id", "close",
                "volume", "open_interest", "source_type", "source_file",
            ],
        )
        writer.writeheader()
        writer.writerow({
            "symbol": "SILVER", "trade_date": "2026-09-01", "expiry_date": "2026-09-04",
            "contract_id": "SILVER|2026-09-04", "close": "100", "volume": "1",
            "open_interest": "1", "source_type": "DEMO", "source_file": "unknown.csv",
        })

    with pytest.raises(AnalyticsInputError, match="Unsupported gold contract symbol"):
        run_analytics(source_path, tmp_path / "analytics")

    with source_path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(
            output,
            fieldnames=[
                "symbol", "trade_date", "expiry_date", "contract_id", "close",
                "volume", "open_interest", "source_type", "source_file",
            ],
        )
        writer.writeheader()
        writer.writerow({
            "symbol": "GOLDM", "trade_date": "2026-09-01", "expiry_date": "2026-09-04",
            "contract_id": "GOLDM|2026-10-04", "close": "100", "volume": "1",
            "open_interest": "1", "source_type": "DEMO", "source_file": "unknown.csv",
        })
    with pytest.raises(AnalyticsInputError, match="invalid contract identity"):
        run_analytics(source_path, tmp_path / "analytics")


def test_analytics_api_reads_output_and_handles_unknown_symbol(tmp_path, monkeypatch):
    stage2 = run_ingest(DEMO_CSV, tmp_path / "processed")
    run_analytics(stage2.processed_path, tmp_path / "analytics")
    monkeypatch.setattr(analytics_service, "ANALYTICS_DIR", tmp_path / "analytics")

    normalized = client.get("/api/analytics/normalized")
    relative = client.get("/api/analytics/relative-value")
    symbol = client.get("/api/analytics/relative-value/GOLDM")

    assert normalized.status_code == 200
    assert normalized.json()["status"] == "AVAILABLE"
    assert normalized.json()["data_type"] == "DEMO"
    assert normalized.json()["record_count"] == 24
    assert relative.status_code == 200
    assert relative.json()["record_count"] == 24
    assert {row["analytics_status"] for row in relative.json()["records"]} >= {
        "INSUFFICIENT_HISTORY",
        "READY",
    }
    assert symbol.status_code == 200
    assert all(row["symbol"] == "GOLDM" for row in symbol.json()["records"])
    assert client.get("/api/analytics/relative-value/SILVER").status_code == 404
    assert client.get("/api/analytics/normalized?source_type=INVALID").status_code == 422


def test_analytics_api_returns_clear_empty_status(tmp_path, monkeypatch):
    monkeypatch.setattr(analytics_service, "ANALYTICS_DIR", tmp_path)

    response = client.get("/api/analytics/normalized")

    assert response.status_code == 200
    assert response.json() == {
        "status": "NO_ANALYTICS_DATA",
        "data_type": "DEMO",
        "record_count": 0,
        "records": [],
    }
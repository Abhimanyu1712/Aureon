import csv
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.ingest import run_ingest
from app.ingest.schema import PROCESSED_COLUMNS
from app.main import app


client = TestClient(app)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEMO_CSV = PROJECT_ROOT / "data" / "demo" / "DEMO_SYNTHETIC_MCX_BHAVCOPY.csv"
HEADERS = [
    "Symbol",
    "Date",
    "ExpiryDate",
    "Open",
    "High",
    "Low",
    "Close",
    "Volume",
    "OpenInterest",
]
VALID_ROW = ["GOLDM", "2026-09-01", "04SEP2026", "100", "110", "90", "105", "20", "30"]


def write_csv(path: Path, headers: list[str], rows: list[list[str]]) -> Path:
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.writer(output)
        writer.writerow(headers)
        writer.writerows(rows)
    return path


def ingest(tmp_path: Path, rows: list[list[str]], headers: list[str] | None = None):
    path = write_csv(tmp_path / "input.csv", headers or HEADERS, rows)
    return run_ingest(path, tmp_path / "out")


def test_valid_csv_parses_dates_and_writes_processed_output(tmp_path: Path):
    result = ingest(tmp_path, [VALID_ROW])

    assert result.is_valid
    assert result.total_rows == result.valid_rows == 1
    with Path(result.processed_path).open(newline="", encoding="utf-8") as source:
        processed = list(csv.DictReader(source))
    assert list(processed[0]) == list(PROCESSED_COLUMNS)
    assert processed[0]["trade_date"] == "2026-09-01"
    assert processed[0]["expiry_date"] == "2026-09-04"
    assert processed[0]["contract_id"] == "GOLDM|2026-09-04"


def test_missing_required_column_is_reported(tmp_path: Path):
    result = ingest(tmp_path, [VALID_ROW[:-1]], HEADERS[:-1])

    assert any(issue.code == "MISSING_COLUMNS" for issue in result.errors)


def test_missing_value_is_reported_and_row_not_processed(tmp_path: Path):
    row = VALID_ROW.copy()
    row[4] = ""
    result = ingest(tmp_path, [row])

    assert result.invalid_rows == 1
    assert any(issue.code == "MISSING_VALUE" and issue.field == "High" for issue in result.errors)
    assert Path(result.processed_path).read_text(encoding="utf-8").count("\n") == 1


def test_invalid_trading_date_is_reported(tmp_path: Path):
    row = VALID_ROW.copy()
    row[1] = "31-02-2026"
    result = ingest(tmp_path, [row])

    assert any(issue.code == "INVALID_DATE" for issue in result.errors)


def test_invalid_expiry_date_is_reported(tmp_path: Path):
    row = VALID_ROW.copy()
    row[2] = "31FEB2026"
    result = ingest(tmp_path, [row])

    assert any(issue.code == "INVALID_EXPIRY" for issue in result.errors)


@pytest.mark.parametrize("field", ["Open", "High", "Low", "Close"])
def test_invalid_ohlc_is_reported(tmp_path: Path, field: str):
    row = VALID_ROW.copy()
    row[HEADERS.index(field)] = "not-a-price"
    result = ingest(tmp_path, [row])

    assert any(issue.code == "INVALID_PRICE" and issue.field == field for issue in result.errors)


def test_invalid_volume_is_reported(tmp_path: Path):
    row = VALID_ROW.copy()
    row[7] = "-1"
    result = ingest(tmp_path, [row])

    assert any(issue.code == "INVALID_VOLUME" for issue in result.errors)


def test_invalid_open_interest_is_reported(tmp_path: Path):
    row = VALID_ROW.copy()
    row[8] = "NaN"
    result = ingest(tmp_path, [row])

    assert any(issue.code == "INVALID_OPEN_INTEREST" for issue in result.errors)


def test_duplicate_rows_are_reported_without_silent_processing(tmp_path: Path):
    result = ingest(tmp_path, [VALID_ROW, VALID_ROW])

    assert result.invalid_rows == 2
    assert len([issue for issue in result.errors if issue.code == "DUPLICATE_ROW"]) == 2


def test_symbol_whitespace_is_stripped(tmp_path: Path):
    row = VALID_ROW.copy()
    row[0] = "  GOLDM  "
    result = ingest(tmp_path, [row])

    with Path(result.processed_path).open(newline="", encoding="utf-8") as source:
        processed = next(csv.DictReader(source))
    assert processed["symbol"] == "GOLDM"


def test_invalid_symbol_and_contract_identity_are_reported(tmp_path: Path):
    row = VALID_ROW.copy()
    row[0] = "GOLD M"
    result = ingest(tmp_path, [row])

    assert any(issue.code == "INVALID_SYMBOL" for issue in result.errors)
    assert any(issue.code == "INVALID_CONTRACT_IDENTITY" for issue in result.errors)


def test_contract_identity_is_symbol_and_expiry(tmp_path: Path):
    row = VALID_ROW.copy()
    result = ingest(tmp_path, [row])

    with Path(result.processed_path).open(newline="", encoding="utf-8") as source:
        processed = next(csv.DictReader(source))
    assert processed["contract_id"] == "GOLDM|2026-09-04"


def test_multiple_expiries_remain_separate_contracts(tmp_path: Path):
    later_expiry = VALID_ROW.copy()
    later_expiry[2] = "05OCT2026"
    result = ingest(tmp_path, [VALID_ROW, later_expiry])

    with Path(result.processed_path).open(newline="", encoding="utf-8") as source:
        processed = list(csv.DictReader(source))
    assert {row["contract_id"] for row in processed} == {
        "GOLDM|2026-09-04",
        "GOLDM|2026-10-05",
    }


def test_no_near_month_or_continuous_transformation(tmp_path: Path):
    later_expiry = VALID_ROW.copy()
    later_expiry[2] = "05OCT2026"
    result = ingest(tmp_path, [VALID_ROW, later_expiry])

    with Path(result.processed_path).open(newline="", encoding="utf-8") as source:
        processed = list(csv.DictReader(source))
    assert [row["expiry_date"] for row in processed] == ["2026-09-04", "2026-10-05"]
    assert not {"near_month", "continuous", "front_month"}.intersection(processed[0])


def test_demo_dataset_is_labelled_valid_and_contains_required_contracts(tmp_path: Path):
    source_bytes = DEMO_CSV.read_bytes()
    result = run_ingest(DEMO_CSV, tmp_path / "out")

    assert result.is_valid
    assert DEMO_CSV.read_bytes() == source_bytes
    assert result.source_type == "DEMO"
    assert result.valid_rows == 24
    with Path(result.processed_path).open(newline="", encoding="utf-8") as source:
        processed = list(csv.DictReader(source))
    assert {row["symbol"] for row in processed} == {
        "GOLDM",
        "GOLDTEN",
        "GOLDGUINEA",
        "GOLDPETAL",
    }
    assert {row["source_type"] for row in processed} == {"DEMO"}
    assert len({row["trade_date"] for row in processed}) > 1
    assert len({row["expiry_date"] for row in processed}) > 1


def test_invalid_report_preserves_bad_row_details(tmp_path: Path):
    row = VALID_ROW.copy()
    row[3] = "bad"
    result = ingest(tmp_path, [row])
    report = json.loads(Path(result.report_path).read_text(encoding="utf-8"))

    assert report["invalid_rows"] == 1
    assert report["invalid_row_details"][0]["values"]["Open"] == "bad"


def test_data_status_api_reports_demo_data():
    response = client.get("/api/data/status")

    assert response.status_code == 200
    assert response.json()["data_type"] in {"DEMO", "MIXED"}
    assert "DEMO" in response.json()["available_data_types"]


def test_health_api_remains_unchanged():
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "message": "Aureon API is running"}
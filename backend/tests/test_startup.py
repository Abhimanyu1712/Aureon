import json
import shutil
from pathlib import Path

from app.startup import ensure_demo_artifacts


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEMO_CSV = PROJECT_ROOT / "data" / "demo" / "DEMO_SYNTHETIC_MCX_BHAVCOPY.csv"


def test_startup_builds_missing_demo_artifacts_in_clean_data_root(tmp_path: Path):
    demo_dir = tmp_path / "data" / "demo"
    demo_dir.mkdir(parents=True)
    shutil.copyfile(DEMO_CSV, demo_dir / DEMO_CSV.name)

    ensure_demo_artifacts(tmp_path)

    assert (tmp_path / "data" / "processed" / "DEMO_SYNTHETIC_MCX_BHAVCOPY_validation.json").is_file()
    assert (tmp_path / "data" / "analytics" / "DEMO_SYNTHETIC_MCX_BHAVCOPY_processed_normalized.csv").is_file()
    assert (tmp_path / "data" / "analytics" / "DEMO_SYNTHETIC_MCX_BHAVCOPY_processed_relative_value.csv").is_file()
    assert (tmp_path / "data" / "analytics" / "DEMO_SYNTHETIC_MCX_BHAVCOPY_processed_signals.csv").is_file()


def test_startup_is_idempotent_when_demo_artifacts_exist(tmp_path: Path):
    demo_dir = tmp_path / "data" / "demo"
    demo_dir.mkdir(parents=True)
    shutil.copyfile(DEMO_CSV, demo_dir / DEMO_CSV.name)
    ensure_demo_artifacts(tmp_path)
    validation_report = tmp_path / "data" / "processed" / "DEMO_SYNTHETIC_MCX_BHAVCOPY_validation.json"
    before = validation_report.stat().st_mtime_ns

    ensure_demo_artifacts(tmp_path)

    assert validation_report.stat().st_mtime_ns == before


def test_startup_rebuilds_nonempty_but_stale_artifacts(tmp_path: Path):
    demo_dir = tmp_path / "data" / "demo"
    demo_dir.mkdir(parents=True)
    shutil.copyfile(DEMO_CSV, demo_dir / DEMO_CSV.name)
    ensure_demo_artifacts(tmp_path)
    validation_report = tmp_path / "data" / "processed" / "DEMO_SYNTHETIC_MCX_BHAVCOPY_validation.json"
    report = json.loads(validation_report.read_text(encoding="utf-8"))
    report["total_rows"] -= 1
    validation_report.write_text(json.dumps(report), encoding="utf-8")

    ensure_demo_artifacts(tmp_path)

    repaired_report = json.loads(validation_report.read_text(encoding="utf-8"))
    assert repaired_report["total_rows"] == 24
    assert repaired_report["valid_rows"] == 24
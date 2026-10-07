from __future__ import annotations

import csv
import json
from pathlib import Path

from app.analytics.pipeline import run_analytics
from app.analytics.signal_pipeline import run_signal_pipeline
from app.ingest.pipeline import PROJECT_ROOT, run_ingest


def _csv_row_count(path: Path) -> int | None:
    if not path.is_file():
        return None
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        return sum(1 for _ in csv.DictReader(source))


def _demo_artifacts_ready(
    demo_source: Path,
    validation_report: Path,
    processed_csv: Path,
    normalized_csv: Path,
    relative_value_csv: Path,
    signals_csv: Path,
) -> bool:
    try:
        report = json.loads(validation_report.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    source_rows = _csv_row_count(demo_source)
    processed_rows = _csv_row_count(processed_csv)
    normalized_rows = _csv_row_count(normalized_csv)
    relative_value_rows = _csv_row_count(relative_value_csv)
    signal_rows = _csv_row_count(signals_csv)
    valid_rows = int(report.get("valid_rows", 0))
    return all(
        (
            report.get("source_type") == "DEMO",
            source_rows is not None and int(report.get("total_rows", -1)) == source_rows,
            valid_rows > 0 and processed_rows == valid_rows,
            normalized_rows == processed_rows,
            relative_value_rows == normalized_rows,
            signal_rows == relative_value_rows,
        )
    )


def ensure_demo_artifacts(project_root: Path = PROJECT_ROOT) -> None:
    """Generate missing demo artifacts through the existing Stage 2-4 pipelines."""
    demo_source = project_root / "data" / "demo" / "DEMO_SYNTHETIC_MCX_BHAVCOPY.csv"
    processed_dir = project_root / "data" / "processed"
    analytics_dir = project_root / "data" / "analytics"
    processed_csv = processed_dir / "DEMO_SYNTHETIC_MCX_BHAVCOPY_processed.csv"
    validation_report = processed_dir / "DEMO_SYNTHETIC_MCX_BHAVCOPY_validation.json"
    normalized_csv = analytics_dir / "DEMO_SYNTHETIC_MCX_BHAVCOPY_processed_normalized.csv"
    relative_value_csv = analytics_dir / "DEMO_SYNTHETIC_MCX_BHAVCOPY_processed_relative_value.csv"
    signals_csv = analytics_dir / "DEMO_SYNTHETIC_MCX_BHAVCOPY_processed_signals.csv"

    if _demo_artifacts_ready(
        demo_source,
        validation_report,
        processed_csv,
        normalized_csv,
        relative_value_csv,
        signals_csv,
    ):
        return
    if not demo_source.is_file():
        raise FileNotFoundError(
            f"Demo source CSV is unavailable at {demo_source}. "
            "Deploy with the repository root as the Render Root Directory."
        )

    processed_dir.mkdir(parents=True, exist_ok=True)
    analytics_dir.mkdir(parents=True, exist_ok=True)
    ingest_result = run_ingest(demo_source, processed_dir, source_type="DEMO")
    if not ingest_result.is_valid or ingest_result.valid_rows == 0:
        raise RuntimeError("Stage 2 demo ingestion did not produce valid rows.")

    run_analytics(processed_csv, analytics_dir)
    run_signal_pipeline(normalized_csv, relative_value_csv, signals_csv)
    if not _demo_artifacts_ready(
        demo_source,
        validation_report,
        processed_csv,
        normalized_csv,
        relative_value_csv,
        signals_csv,
    ):
        raise RuntimeError("Stage 2-4 demo pipelines did not produce all required artifacts.")
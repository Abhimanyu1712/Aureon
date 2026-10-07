from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.ingest.pipeline import PROJECT_ROOT


def get_data_status() -> dict[str, Any]:
    data_root = PROJECT_ROOT / "data"
    source_types: set[str] = set()
    source_files: list[str] = []
    processed_rows = 0

    for folder_name, source_type in (("demo", "DEMO"), ("raw", "REAL")):
        folder = data_root / folder_name
        for path in sorted(folder.glob("*.csv")) if folder.exists() else []:
            source_types.add(source_type)
            source_files.append(path.relative_to(PROJECT_ROOT).as_posix())

    processed_dir = data_root / "processed"
    for report_path in sorted(processed_dir.glob("*_validation.json")):
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        source_type = report.get("source_type")
        if source_type in {"DEMO", "REAL"}:
            source_types.add(source_type)
        processed_rows += int(report.get("valid_rows", 0))
        processed_file = report.get("processed_path")
        if processed_file:
            processed_path = Path(processed_file).resolve()
            try:
                source_files.append(processed_path.relative_to(PROJECT_ROOT).as_posix())
            except ValueError:
                source_files.append(str(processed_path))

    labels = {
        "DEMO": "DEMO",
        "REAL": "REAL/HISTORICAL",
    }
    available_types = sorted(labels[source_type] for source_type in source_types)
    data_type = (
        available_types[0]
        if len(available_types) == 1
        else "MIXED"
        if available_types
        else "NONE"
    )
    return {
        "available": bool(source_types),
        "data_type": data_type,
        "available_data_types": available_types,
        "source_files": source_files,
        "processed_rows": processed_rows,
    }
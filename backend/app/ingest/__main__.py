from __future__ import annotations

import argparse
import json

from app.ingest.pipeline import run_ingest


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and process an MCX Bhavcopy CSV.")
    parser.add_argument("input_csv", help="Path to the source CSV; it is never modified")
    parser.add_argument(
        "--output-dir",
        help="Output folder (default: repository data/processed)",
    )
    parser.add_argument(
        "--source-type",
        choices=("DEMO", "REAL"),
        help="Data provenance (auto-detected from data/demo when omitted)",
    )
    args = parser.parse_args()
    result = run_ingest(args.input_csv, args.output_dir, args.source_type)
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.is_valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
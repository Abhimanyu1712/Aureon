from __future__ import annotations

import argparse
import json

from app.analytics.pipeline import run_analytics


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Normalize Stage 2 MCX prices and calculate relative-value analytics."
    )
    parser.add_argument("stage2_csv", help="Path to a validated Stage 2 processed CSV")
    parser.add_argument("--output-dir", help="Output folder (default: repository data/analytics)")
    args = parser.parse_args()
    result = run_analytics(args.stage2_csv, args.output_dir)
    print(json.dumps(result.to_dict(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
from __future__ import annotations

import argparse
import json

from app.backtest.engine import run_backtest


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a Stage 4-driven relative-value backtest.")
    parser.add_argument("normalized_csv", help="Stage 3 normalized CSV")
    parser.add_argument("signals_csv", help="Stage 4 signal CSV")
    parser.add_argument("--output-dir", help="Output folder (default: data/backtests)")
    parser.add_argument("--source-type", choices=("DEMO", "REAL"), default="DEMO")
    args = parser.parse_args()
    result = run_backtest(
        args.normalized_csv,
        args.signals_csv,
        args.output_dir,
        source_type=args.source_type,
    )
    print(json.dumps(result.report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
# Stage 2: MCX Bhavcopy Ingestion

Stage 2 provides local CSV parsing and validation only. It does not fetch market data or perform financial normalization or analysis.

## CSV Format

CSV headers are case-insensitive and may have surrounding whitespace. The required fields are:

```text
Symbol,Date,ExpiryDate,Open,High,Low,Close,Volume,OpenInterest
```

`Date` is the trading date. ISO format (`YYYY-MM-DD`) is recommended; common day-first forms such as `DD-MM-YYYY` and `DD/MM/YYYY` are also accepted. `ExpiryDate` is parsed separately and accepts MCX-style dates such as `04SEP2026` as well as common ISO/day-first date forms. Prices must be positive numeric values with internally consistent OHLC bounds. Volume and OpenInterest must be non-negative numeric values. Symbols are trimmed; blank or malformed symbols and invalid contract identities are rejected.

## Contract Identity

A contract is identified by `Symbol + ExpiryDate`; each daily record also retains its trading `Date`. Two expiries of the same symbol remain separate contracts. No near-month selection, rolling, or continuous-series transformation occurs.

## Data Folders and Provenance

- `data/raw/` is for user-supplied source files. Ingestion reads these files without modifying them. Raw files are excluded from Git by default.
- `data/demo/` contains `DEMO_SYNTHETIC_MCX_BHAVCOPY.csv`, deterministic synthetic rows for GOLDM, GOLDTEN, GOLDGUINEA, and GOLDPETAL. These values are fabricated test fixtures, not real MCX prices or historical observations, and must not be used to claim trading performance.
- `data/processed/` receives cleaned valid rows and a JSON validation report. Generated output is excluded from Git by default.

The processed CSV retains normalized trading and expiry dates, original expiry text, contract ID, OHLC, volume, open interest, provenance, and source filename. Invalid rows are excluded from the processed CSV but retained in the report with their original values and row-specific errors; no bad records are silently discarded.

## Run Ingestion

From PowerShell at the repository root:

```powershell
cd backend
.\.venv\Scripts\python.exe -m app.ingest ..\data\demo\DEMO_SYNTHETIC_MCX_BHAVCOPY.csv
```

Use a real source CSV in `data/raw/` in place of the demo path. Provenance is inferred from whether the input is under `data/demo/`; it can be specified explicitly with `--source-type DEMO` or `--source-type REAL`. Optional output folder:

```powershell
.\.venv\Scripts\python.exe -m app.ingest ..\data\raw\bhavcopy.csv --output-dir ..\data\processed
```

The command prints a JSON summary and exits with code `1` when validation errors are found. The report includes counts, errors, warnings, valid row numbers, and invalid rows with their values and issues.

## API and Tests

- `GET /api/health` remains the Stage 1 health check.
- `GET /api/data/status` reports available DEMO and/or REAL/HISTORICAL inputs and processed-row count. `MIXED` means both provenance types are present. No live MCX API or downloader is implemented.

Run the backend test suite from `backend/`:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

## Limitations

This stage accepts futures bhavcopy records with the fields above. It does not normalize contract sizes or quote bases, apply purity adjustments, convert to rupees per gram, construct peer baskets, calculate relative value or z-scores, filter liquidity or expiry trades, include transaction costs, generate signals, backtest, or use machine learning. Validate the source schema and provenance before relying on processed data.
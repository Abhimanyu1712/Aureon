# AUREON: Commodity Derivatives Intelligence

**"See the spread. Understand the risk. Act with evidence."**

Aureon is a full-stack financial analytics platform built for **Hack in Hills '26 (Problem 03 — Commodity Derivatives Intelligence)**. 

This repository implements **Stage 1: Project Foundation**, **Stage 2: MCX daily Bhavcopy ingestion and validation**, **Stage 3: gold contract normalization and relative-value analytics**, **Stage 4: explainable relative-value signal classification**, and **Stage 5: walk-forward backtesting**. It does not download live MCX data, provide financial advice, or execute trades.

## Features
- Python FastAPI Backend structure
- React + TypeScript research dashboard with responsive analytics, signal, contract, and backtest views
- Basic `/api/health` endpoint for connectivity
- CSV ingestion with structured validation reports and a data-status endpoint
- Purity-adjusted ₹/gram normalization and expiry-aware relative-value analytics
- Explainable signal classifications with liquidity-proxy and expiry filters
- Historical relative-value backtesting with P&L, estimated costs and benchmark attribution

## Installation & Setup (Windows)

Ensure you have Python 3.11+ and Node.js installed.

### 1. Backend Setup
Open a terminal (PowerShell) and navigate to the project root:
```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Frontend Setup
Open a second terminal and navigate to the project root:
```powershell
cd frontend
npm install
```

### 3. Running the Application

**Start the Backend:**
```powershell
# From the backend directory with venv activated
uvicorn app.main:app --reload
```

**Start the Frontend:**
```powershell
# From the frontend directory
npm run dev
```

The dashboard will be available at `http://localhost:5173`.

## Stage 2: MCX Bhavcopy Ingestion

The accepted CSV fields and formats, data provenance rules, validation behavior, and limitations are documented in [docs/MCX_INGESTION.md](docs/MCX_INGESTION.md).

From the repository root, run ingestion in PowerShell:

```powershell
cd backend
.\.venv\Scripts\python.exe -m app.ingest ..\data\demo\DEMO_SYNTHETIC_MCX_BHAVCOPY.csv
```

The pipeline writes a cleaned CSV and a JSON validation report under `data/processed/`; it never changes the input file. Run backend tests with:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest
```

## Stage 3: Normalization and Relative Value

Stage 3 consumes Stage 2 processed CSVs, writes derived files under `data/analytics/`, and serves them through read-only analytics endpoints. Specifications, the exact formula, peer cohort assumptions, statuses, and commands are in [docs/STAGE3_ANALYTICS.md](docs/STAGE3_ANALYTICS.md).

```powershell
cd backend
.\.venv\Scripts\python.exe -m app.ingest ..\data\demo\DEMO_SYNTHETIC_MCX_BHAVCOPY.csv
.\.venv\Scripts\python.exe -m app.analytics ..\data\processed\DEMO_SYNTHETIC_MCX_BHAVCOPY_processed.csv
```

The Stage 2 validation report is written directly into `data/processed/`, which is where `/api/data/status` scans for row counts. Stage 3 writes its normalized and relative-value outputs into `data/analytics/`. The API exposes `GET /api/analytics/normalized`, `GET /api/analytics/relative-value`, and `GET /api/analytics/relative-value/{symbol}`. Outputs retain their DEMO or REAL/HISTORICAL provenance; synthetic results are not market observations.

## Stage 4: Signal Classification

Stage 4 consumes Stage 3 normalized and relative-value CSVs; it does not normalize prices again. Thresholds, filter precedence, demo limitations, and API details are documented in [docs/STAGE4_SIGNALS.md](docs/STAGE4_SIGNALS.md). After generating Stage 3 outputs, classify them with:

```powershell
cd backend
.\.venv\Scripts\python.exe -m app.analytics.signal_pipeline ..\data\analytics\DEMO_SYNTHETIC_MCX_BHAVCOPY_processed_normalized.csv ..\data\analytics\DEMO_SYNTHETIC_MCX_BHAVCOPY_processed_relative_value.csv
```

The command writes a separate `*_signals.csv` to `data/analytics/`. Read results from `GET /api/analytics/signals` and `GET /api/analytics/signals/{symbol}`. Classifications are descriptive analytics, not trading recommendations.

## Render Backend Deployment

The repository defines the Render service in [render.yaml](render.yaml). The **Root Directory must be the repository root (`.`)** because the committed demo CSV is stored at `data/demo/`, outside `backend/`.

The Render Blueprint Build Command installs backend requirements and runs the existing Stage 2, Stage 3, and Stage 4 CLI pipelines. These create the ignored files `data/processed/DEMO_SYNTHETIC_MCX_BHAVCOPY_validation.json`, `data/analytics/DEMO_SYNTHETIC_MCX_BHAVCOPY_processed_normalized.csv`, and the corresponding relative-value and signal CSVs before startup. FastAPI startup checks for these artifacts and regenerates them through the same pipeline modules if missing or empty.

For an existing dashboard-managed Render service, set **Root Directory** to `.` and use this Build Command:

```sh
pip install -r backend/requirements.txt && cd backend && python -m app.ingest ../data/demo/DEMO_SYNTHETIC_MCX_BHAVCOPY.csv && python -m app.analytics ../data/processed/DEMO_SYNTHETIC_MCX_BHAVCOPY_processed.csv && python -m app.analytics.signal_pipeline ../data/analytics/DEMO_SYNTHETIC_MCX_BHAVCOPY_processed_normalized.csv ../data/analytics/DEMO_SYNTHETIC_MCX_BHAVCOPY_processed_relative_value.csv
```

Start Command (from repository root):

```sh
cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Generated data remains Git-ignored; do not commit the generated artifacts. Keep Stage 2's default top-level `data/processed/` output because `/api/data/status` scans that directory for validation reports.

## Stage 5: Walk-Forward Backtesting

Stage 5 consumes Stage 3 normalized prices and Stage 4 signal outputs; details and limitations are documented in [docs/STAGE5_BACKTESTING.md](docs/STAGE5_BACKTESTING.md). After generating Stage 3 and Stage 4 output files, run from `backend/`:

```powershell
.\.venv\Scripts\python.exe -m app.backtest ..\data\analytics\DEMO_SYNTHETIC_MCX_BHAVCOPY_processed_normalized.csv ..\data\analytics\DEMO_SYNTHETIC_MCX_BHAVCOPY_processed_signals.csv
```

Machine-readable report, trade ledger, equity curve, and benchmark are written separately under `data/backtests/`. Read them via `GET /api/backtest/summary`, `/trades`, `/equity`, `/benchmark`, and `/report`. Backtest outputs are simulations, not executable fills or recommendations.

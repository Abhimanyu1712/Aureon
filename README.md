# AUREON: Commodity Derivatives Intelligence

**"See the spread. Understand the risk. Act with evidence."**

Aureon is a full-stack financial analytics platform built for **Hack in Hills '26 (Problem 03 — Commodity Derivatives Intelligence)**. 

This repository implements **Stage 1: Project Foundation**, **Stage 2: MCX daily Bhavcopy ingestion and validation**, and **Stage 3: gold contract normalization and relative-value analytics**. It does not download live MCX data or generate trading signals.

## Features
- Python FastAPI Backend structure
- React + Vite Frontend skeleton
- Basic `/api/health` endpoint for connectivity
- CSV ingestion with structured validation reports and a data-status endpoint
- Purity-adjusted ₹/gram normalization and expiry-aware relative-value analytics

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
.\.venv\Scripts\python.exe -m app.ingest ..\data\demo\DEMO_SYNTHETIC_MCX_BHAVCOPY.csv --output-dir ..\data\processed\stage3_demo_input
.\.venv\Scripts\python.exe -m app.analytics ..\data\processed\stage3_demo_input\DEMO_SYNTHETIC_MCX_BHAVCOPY_processed.csv
```

The API exposes `GET /api/analytics/normalized`, `GET /api/analytics/relative-value`, and `GET /api/analytics/relative-value/{symbol}`. Outputs retain their DEMO or REAL/HISTORICAL provenance; synthetic results are not market observations.

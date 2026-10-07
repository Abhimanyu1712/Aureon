# Stage 3: Contract Normalization and Relative Value

Stage 3 derives comparable purity-adjusted prices and descriptive relative-value statistics from validated Stage 2 processed CSVs. Stage 4 consumes these outputs for signal classification; Stage 3 itself does not predict gold prices or create trade signals.

## Contract Specifications

| Symbol | Contract size | Quotation basis | Purity | Expiry rule |
| --- | ---: | ---: | ---: | --- |
| GOLDM | 100 g | ₹ per 10 g | 995 fineness | 3rd-5th day of expiry month |
| GOLDTEN | 10 g | ₹ per 10 g | 999 fineness | 27th-31st day of expiry month |
| GOLDGUINEA | 8 g | ₹ per 8 g | 999 fineness | 27th-31st day of expiry month |
| GOLDPETAL | 1 g | ₹ per 1 g | 999 fineness | 27th-31st day of expiry month |

Unknown symbols and missing, non-numeric, non-finite, zero, or negative close prices fail with a row-specific error. Monetary/unit calculations use Python `Decimal`.

## Normalization Formula

Normalization makes quotation units and fineness explicit. For quoted close $Q$ rupees per quoted $g_q$ grams, contract size $g_c$, contract purity $p$ fineness, and common reference fineness 999:

```text
contract_value_rupees = Q * (g_c / g_q)
normalized_price_per_gram = contract_value_rupees / g_c
purity_adjusted_price_per_gram = normalized_price_per_gram * (999 / p)
```

The first two steps convert from the contract's quotation basis to observed ₹/gram; contract size cancels algebraically but is retained in the calculation to make the contract-value units auditable. The final factor converts the observed price to an equivalent 999-fineness basis. It scales a 995-fineness price upward by `999/995`; 999-fineness contracts are unchanged. It is not a quote for physical fine gold and applies no taxes, fees, location, or other adjustments.

Manual examples:

- GOLDM quoted close ₹7,031 per 10 g: contract value = `7031 * (100 / 10) = ₹70,310`; observed = `₹70,310 / 100 = ₹703.10/g`; 999-basis = `703.10 * (999 / 995) = ₹705.926533/g` (rounded here to six decimals).
- GOLDTEN quoted close ₹7,040 per 10 g: `7040 * (10 / 10) / 10 = ₹704/g`, unchanged at 999 fineness.
- GOLDGUINEA quoted close ₹5,633.60 per 8 g: `5633.60 * (8 / 8) / 8 = ₹704.20/g`, unchanged at 999 fineness.
- GOLDPETAL quoted close ₹704 per 1 g: `704 * (1 / 1) / 1 = ₹704/g`, unchanged at 999 fineness.

The Stage 3 normalized CSV includes `normalized_price_per_gram` before purity adjustment and `purity_adjusted_price_per_gram` on the shared 999 basis.

## Relative-Value Method

Each observation keeps its trading `trade_date`, exact `expiry_date`, and `contract_id = Symbol|ExpiryDate`. Contracts are never rolled, merged, or replaced by a continuous series.

Peer cohorts require the same source type (DEMO is never mixed with REAL), trading date, and expiry calendar month (same year and month). Products have different specified expiry days, so matching exact expiry dates would leave no cross-product peers. This explicitly chosen monthly delivery cohort retains every exact expiry in output; it does not adjust for the different days-to-expiry, so term effects may remain in the spread. The same symbol is excluded from its own peer set. If a symbol has multiple contracts in a cohort, its peer contribution is its within-symbol median so one product cannot overweight the reference; all contracts remain separate output rows.

At least two distinct peer symbols are required. For an eligible observation:

```text
peer_reference = median of peer-symbol median purity-adjusted prices
spread = this contract's purity-adjusted price - peer_reference
rolling_mean = mean of the latest 5 valid spreads for this Symbol+ExpiryDate
rolling_std = population standard deviation of those spreads (ddof=0)
z_score = (current spread - rolling_mean) / rolling_std
```

Rolling observations are processed in ascending trading-date order, include the current and prior valid observations, and never use centered windows or future rows. At least 3 eligible spreads are required before rolling statistics are emitted. A zero or near-zero standard deviation (at most `1e-12`) produces no z-score.

`analytics_status` is one of:

- `INSUFFICIENT_PEERS`: peer reference and spread are null; there are fewer than two distinct peer symbols.
- `INSUFFICIENT_HISTORY`: a peer reference and spread exist, but fewer than three historical/current eligible spreads are available.
- `ZERO_VARIANCE`: rolling mean and standard deviation exist, but z-score is null because the standard deviation is zero or near zero.
- `READY`: peer and rolling statistics, including z-score, are available.

These statuses describe data sufficiency only. A spread or z-score is not a buy/sell recommendation, alert, or expected return.

## Data Provenance and Outputs

- **Observed input:** validated Stage 2 processed rows (`close`, volume, open interest, trading date, expiry date and source metadata). Raw data remains untouched.
- **Derived output:** `data/analytics/` contains separate normalized and relative-value CSVs; Stage 2 processed files are read-only inputs and are not overwritten. Generated analytics output is ignored by Git.
- **Synthetic demo:** `data/demo/DEMO_SYNTHETIC_MCX_BHAVCOPY.csv` is fabricated software-test data only. Its prices are scaled to the specified quotation bases, expiry days follow the listed day ranges, and the added third date provides the minimum rolling history. It is not real MCX market data or historical performance evidence.

## Run Locally on Windows

From the repository root in PowerShell:

```powershell
cd backend
.\.venv\Scripts\python.exe -m app.ingest ..\data\demo\DEMO_SYNTHETIC_MCX_BHAVCOPY.csv --output-dir ..\data\processed\stage3_demo_input
.\.venv\Scripts\python.exe -m app.analytics ..\data\processed\stage3_demo_input\DEMO_SYNTHETIC_MCX_BHAVCOPY_processed.csv
```

The first command creates a separate Stage 2 processed input so an existing Stage 2 output is not replaced. The second writes `*_normalized.csv` and `*_relative_value.csv` under `data/analytics/`. For real/historical data, pass the corresponding validated Stage 2 processed CSV; its provenance remains REAL and is analyzed separately from DEMO.

## Read-Only API

Start FastAPI from `backend/` using `uvicorn app.main:app --reload`:

- `GET /api/analytics/normalized?source_type=DEMO`
- `GET /api/analytics/relative-value?source_type=DEMO`
- `GET /api/analytics/relative-value/GOLDM?source_type=DEMO`

Use `source_type=REAL` for REAL/HISTORICAL output. Endpoints read generated analytics files only; they do not run ingestion, write files, or fetch market data. Before analytics output exists they return `NO_ANALYTICS_DATA` with an empty records array. Unsupported symbols return HTTP 404; invalid source-type query values return HTTP 422. Records with insufficient peers/history remain visible with null derived fields and an explanatory status.

## Deliberate Limitations

There is no expiry-day normalization, tenor/carry adjustment, liquidity or trading filter, quote/tax/cost adjustment, trading signal, alert, backtest, P&L, ML, dashboard, broker integration, or live MCX downloader. The monthly expiry cohort and 999-fineness basis are explicit Stage 3 assumptions, not MCX settlement rules or trading instructions.
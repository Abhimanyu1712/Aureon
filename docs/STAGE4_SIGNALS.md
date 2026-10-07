# Stage 4: Relative-Value Signal Classification

Stage 4 classifies Stage 3 relative-value observations after checking peer/history sufficiency, observable liquidity proxies, and time to the row's contract expiry. Results are descriptive analytics only. They are not financial advice, execution instructions, expected returns, or claims that prices will converge.

## Input and Provenance

Stage 4 requires the Stage 3 `*_normalized.csv` and matching `*_relative_value.csv`. It joins rows by source type, symbol, trading date, exact expiry date, and `contract_id`. It uses Stage 3's existing `normalized_price`, peer reference, spread, z-score, and peer status. It does not recalculate normalization or use any hidden source. The output retains `source_type` and `source_file` for traceability:

```text
raw/processed input -> Stage 2 validation -> Stage 3 normalized and relative-value files
                   -> Stage 4 signal classification -> separate *_signals.csv
```

Raw inputs and Stage 2/3 files are read-only to Stage 4. DEMO and REAL/HISTORICAL records are filtered and classified separately. The synthetic fixture and its derived outputs must not be presented as real market observations.

## Classification Thresholds

Default thresholds are centralized in `SignalConfig` and can be overridden with environment variables:

| Setting | Default | Meaning |
| --- | ---: | --- |
| `AUREON_SIGNAL_WATCHLIST_Z` | 1.5 | Inclusive absolute z-score threshold for `WATCHLIST` |
| `AUREON_SIGNAL_STRONG_Z` | 2.0 | Inclusive absolute z-score threshold for `STRONG_RELATIVE_DEVIATION` |
| `AUREON_SIGNAL_NEUTRAL_Z` | 1e-12 | Values at or below this absolute z-score have `NEUTRAL` direction |
| `AUREON_SIGNAL_MIN_VOLUME` | 500 | Minimum observed daily volume proxy |
| `AUREON_SIGNAL_MIN_OPEN_INTEREST` | 1000 | Minimum observed open-interest proxy |
| `AUREON_SIGNAL_MIN_DAYS_TO_EXPIRY` | 5 | Minimum remaining calendar days for classification |
| `AUREON_SIGNAL_MIN_PEERS` | 2 | Minimum Stage 3 comparable peer-symbol count |
| `AUREON_SIGNAL_MIN_HISTORY` | 3 | Minimum valid trailing spread observations |
| `AUREON_SIGNAL_ROLLING_WINDOW` | 5 | Cap used when reporting available trailing observations |

Set these in the process environment (or copy the documented defaults from `.env.example` to a locally managed environment). The application does not load `.env` files itself. These are configurable analytical demo thresholds, not calibrated market rules.

When no rejection filter applies, classification is deterministic and based on the Stage 3 z-score:

- `abs(z_score) < 1.5`: `NO_SIGNAL`
- `1.5 <= abs(z_score) < 2.0`: `WATCHLIST`
- `abs(z_score) >= 2.0`: `STRONG_RELATIVE_DEVIATION`

The configured values replace the example constants above. No arbitrary confidence score is calculated.

## Filter Precedence and Interpretation

The first applicable state wins, in this order:

1. `INSUFFICIENT_PEERS`: Stage 3 reports insufficient peers or peer count is below the configured minimum.
2. `INSUFFICIENT_HISTORY`: Stage 3 has no usable standardized z-score, or the trailing count is below its configured minimum. Stage 3 `ZERO_VARIANCE` also maps here because no standardized deviation can be classified.
3. `INSUFFICIENT_LIQUIDITY`: volume or open interest is missing, non-finite, or below its configured proxy threshold.
4. `EXPIRY_FILTER_FAILED`: fewer than the configured minimum days remain.
5. Otherwise, apply the z-score classification (`NO_SIGNAL`, `WATCHLIST`, or `STRONG_RELATIVE_DEVIATION`).

Positive z-score direction is `EXPENSIVE` versus the peer reference; negative is `CHEAP`; near-zero or unavailable is `NEUTRAL`. These words describe relative positioning only and do not imply a position or action. Failed filters remain visible with their evidence and generated explanation; a normal classification is not emitted for them.

Volume and OpenInterest are observed bhavcopy fields used only as transparent liquidity proxies. They are not order-book depth, executable liquidity, or a guarantee that a trade can be entered or exited. Missing values fail closed as `INSUFFICIENT_LIQUIDITY`.

Days to expiry is strictly `(ExpiryDate - TradingDate).days`, using each historical row's dates, never the system date. An expired contract yields a negative value and fails the expiry filter. The threshold is a simple calendar-day cutoff; no tender periods, delivery lifecycle rules, or undocumented MCX dates are inferred.

Each explanation is rendered from that row's actual z-score, peer reference, volume, open interest, history count, and days to expiry, plus the applicable filter reason. `cost_filter_status` is always `NOT_APPLIED`: the repository had no documented transaction-cost assumption, so no numeric cost filter is invented. Transaction-cost modelling belongs to later evaluation work.

## Output and API

Run from the repository root in PowerShell after Stage 3 has generated both inputs:

```powershell
cd backend
.\.venv\Scripts\python.exe -m app.analytics.signal_pipeline ..\data\analytics\DEMO_SYNTHETIC_MCX_BHAVCOPY_processed_normalized.csv ..\data\analytics\DEMO_SYNTHETIC_MCX_BHAVCOPY_processed_relative_value.csv
```

The command writes `data/analytics/DEMO_SYNTHETIC_MCX_BHAVCOPY_processed_signals.csv`. Its rows include exact `contract_id`, `trade_date`, `expiry_date`, normalized value, peer reference, spread, z-score, peer count, volume, open interest, `days_to_expiry`, `rolling_history_count`, direction, signal status, cost-filter status, Stage 3 analytics status, provenance, and explanation.

Read-only API endpoints:

- `GET /api/analytics/signals?source_type=DEMO`
- `GET /api/analytics/signals/GOLDM?date=2026-09-03&expiry_date=2026-09-04&status=EXPIRY_FILTER_FAILED`

Optional filters are `source_type` (`DEMO` or `REAL`), `date`, `expiry_date`, and `status`. Unsupported symbols return HTTP 404; malformed dates or unknown status values return HTTP 422. If no signal file exists, the endpoint returns `NO_SIGNAL_DATA` with an empty list. The endpoints do not run calculations, mutate files, or download market data.

The demo uses synthetic prices and contract activity. Its classifications exist to exercise software behavior and are not MCX results, historical performance, or trading recommendations. No alerts, orders, broker links, backtesting, P&L, risk-adjusted performance measures, or ML are implemented. Cost modelling and those later-stage capabilities remain out of scope.
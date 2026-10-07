# Stage 5: Walk-Forward Backtesting

Stage 5 replays Stage 4 signal classifications against Stage 3 normalized prices. It creates historical simulation records only. **Backtest results are historical simulations, not guarantees of future performance.** Synthetic output is labeled `DEMO / SYNTHETIC DATA`; it is not real MCX market evidence.

## Strategy and Information Timing

Only `STRONG_RELATIVE_DEVIATION` Stage 4 rows are considered for entry, and `CHEAP` / `EXPENSIVE` determines the relative-value pair:

- `CHEAP`: long the target contract and short the Stage 3 comparable peer basket.
- `EXPENSIVE`: short the target contract and long the peer basket.

The peer basket is fixed from comparable contracts present on the signal date, in the same expiry month and provenance, excluding the target symbol. The Stage 3 peer count must be represented by distinct available peer symbols. Exact `Symbol|ExpiryDate` IDs are retained for every target and hedge leg. No generic gold identifier, near-month roll, or continuous series is created.

Signals are consumed in ascending trading-date order. An eligible signal observed at date `t` enters at the next joint date with available target and peer observations. Stage 4 z-scores and Stage 3 normalized prices are read as supplied; no future rows are used to recompute them. Liquidity and minimum days-to-expiry are rechecked using the actual next-date fill observations; a signal with only five days remaining can be rejected if the next-date execution would breach the five-day minimum. If the next target/peer joint date is unavailable before expiry, the entry is rejected or remains pending until the dataset ends and is recorded as rejected. Each run allows one open position; overlapping signals are not stacked.

## Simulated Execution and Exits

Daily close is used only as a consistent simulation mark/fill proxy. It is not claimed to be an executable intraday fill. Both entries and ordinary exits use the next joint available trading-date close after the observation. A mean-reversion exit is queued when Stage 4 z-score returns to `abs(z) <= EXIT_Z` (default 0.5), then executed at the next joint close that passes exit liquidity checks.

Other exits are deterministic:

- `EXPIRY`: force liquidation when the earliest expiry among target and peer legs is reached. If any leg has no close on that date, the entire basket exits at its last joint available close on or before expiry; each leg records that quote date. No position is marked using post-expiry prices.
- `MAX_HOLDING_PERIOD`: force liquidation at the configured maximum number of observed trading sessions (default 20).
- `PEER_UNAVAILABLE`: queue an exit when a required peer observation disappears, and execute at the next joint date when the complete basket is observable and passes liquidity checks.

If mean-reversion or peer-unavailable exit is pending but liquidity fails, the position remains open until a joint liquid exit opportunity or an expiry/maximum-hold forced exit. Expiry uses the last joint basket quote; a max-holding exit uses current closes where available and otherwise each leg's last mark. These fallbacks are explicit in each leg's `exit_price_date` and are not presented as guaranteed executable fills.

## Sizing, P&L, and Costs

The target leg receives one half of initial capital as notional. The peer basket receives the other half, divided equally by peer symbol and then by that symbol's exact contracts. Units are fractional contract-equivalents calculated from Stage 3 purity-adjusted ₹/gram price times the Stage 3 contract gram size. This creates a transparent equal-notional pair, not a perfect statistical or deliverable hedge; actual MCX lot increments are unavailable and are not modeled.

For each leg, gross P&L is the signed contract-equivalent quantity times contract grams times the change in normalized price per gram. The ledger records target-leg and peer-leg P&L separately, then gross, cost, net, and return on the configured initial capital. The equity curve marks open positions to the latest available normalized close; entry costs reduce equity on entry, and exit costs reduce equity on exit. Open trades remain open/unrealized at the end of the dataset.

The default cost model is an **estimated 0.0005 (5 basis points) per leg per fill** on absolute notional. It is charged separately on both target and peer legs at entry and exit. This is a transparent placeholder assumption, not verified MCX brokerage, exchange fees, taxes, slippage, or market impact. It can be set to zero for a no-cost scenario or overridden using `AUREON_BACKTEST_COST_RATE`. No precise executable cost claim is made.

Volume and OpenInterest are observable liquidity proxies only, never market depth. Entry is rejected unless all legs at the next joint close meet configured minimum volume and open-interest values. An open trade waits for an eligible joint close unless expiry or max-holding forces an exit.

## Configuration

`BacktestConfig` centralizes the environment-overridable settings (defaults shown):

| Environment variable | Default |
| --- | ---: |
| `AUREON_BACKTEST_ENTRY_Z` | 2.0 |
| `AUREON_BACKTEST_EXIT_Z` | 0.5 |
| `AUREON_BACKTEST_MAX_HOLDING_DAYS` | 20 trading sessions |
| `AUREON_BACKTEST_MIN_VOLUME` | 500 |
| `AUREON_BACKTEST_MIN_OPEN_INTEREST` | 1000 |
| `AUREON_BACKTEST_MIN_DAYS_TO_EXPIRY` | 5 calendar days |
| `AUREON_BACKTEST_COST_RATE` | 0.0005 per leg per fill |
| `AUREON_BACKTEST_INITIAL_CAPITAL` | ₹1,000,000 |
| `AUREON_BACKTEST_BENCHMARK_SYMBOL` | GOLDTEN |

The checked-in `.env.example` documents values, but the process reads environment variables directly and does not load `.env` files automatically. Costs and thresholds are assumptions, not fitted or optimized values.

## Metrics and Benchmark

Trade count, completed/open trades, wins/losses, win rate, gross/net P&L, costs, average completed-trade P&L, holding period, end-of-day maximum drawdown, cumulative equity return, and annualized Sharpe are calculated from the replay. Sharpe uses sample standard deviation and 252 trading sessions per year; it returns `INSUFFICIENT_DATA` until at least 20 daily returns exist, or when observed volatility is zero. Metrics without a valid denominator are `null`, not fabricated.

The benchmark is the configured symbol's single exact contract with normalized prices available on every backtest equity date. It does not roll contracts. If no exact benchmark contract spans the full date set, benchmark return and relative outperformance are `null` with `INSUFFICIENT_DATA`. The default GOLDTEN comparison is one contract only, not a proxy for the entire Indian gold market. Strategy return is aligned to the benchmark's first and last observed dates; relative outperformance is strategy return minus benchmark return. This is attribution context, not evidence of causality.

## Run and API

Generate Stage 3 normalized output and Stage 4 signals first. From `backend/` in PowerShell:

```powershell
.\.venv\Scripts\python.exe -m app.backtest ..\data\analytics\DEMO_SYNTHETIC_MCX_BHAVCOPY_processed_normalized.csv ..\data\analytics\DEMO_SYNTHETIC_MCX_BHAVCOPY_processed_signals.csv
```

Optional arguments: `--output-dir ..\data\backtests\run1` and `--source-type REAL`. Reports are written to `data/backtests/` by default: `*_report.json`, `*_trades.json`, `*_equity.json`, and `*_benchmark.json`. Inputs remain read-only.

Read-only endpoints:

- `GET /api/backtest/summary?source_type=DEMO`
- `GET /api/backtest/trades?source_type=DEMO`
- `GET /api/backtest/equity?source_type=DEMO`
- `GET /api/backtest/benchmark?source_type=DEMO`
- `GET /api/backtest/report?source_type=DEMO`

Before a report is generated, endpoints return `NO_BACKTEST_DATA`. These routes only read generated artifacts; they do not start simulations or access raw input data.

## Data Limitations and Scope

The existing demo contains only three trading dates and no Stage 4 strong-deviation observations. An honest demo run therefore has no entries, zero simulated return, and insufficient observations for Sharpe; it is not extended or altered to manufacture a performance result. Unit tests use separate controlled fixtures to verify wins, losses, entry/exit timing, costs, lifecycle, and filters. Demo report values must always remain labeled synthetic.

The daily close is not an intraday fill, fractional contracts may not be executable, equal notional does not eliminate basis/tenor risk, peer availability and sparse observations limit exits, estimated costs are not market-verified, and three demo dates cannot support performance conclusions. Backtesting here does not establish that a strategy works. No cost calibration, walk-forward optimization, live alerts, P&L attribution beyond the specified legs, broker access, or order execution is added.
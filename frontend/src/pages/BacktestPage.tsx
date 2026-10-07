import { useDashboard } from '../lib/useDashboard';
import { formatCurrency, formatDate, formatInteger, formatNumber, formatPercent, formatSignedCurrency, numericValue } from '../lib/format';
import { DataNotice, EmptyState, ErrorState, LoadingState, PageHeading, SectionTitle, StatusBadge } from '../components/States';
import { MetricTile } from '../components/MetricTile';
import { EquityChart, ReturnComparisonChart } from '../components/Charts';

export function BacktestPage() {
  const { snapshot, loading, refresh } = useDashboard();
  if (!snapshot && loading) return <LoadingState />;
  if (!snapshot) return <ErrorState onRetry={refresh} />;
  const report = snapshot.backtestReport.data?.data ?? null;
  const summary = snapshot.backtestSummary.data?.data ?? null;
  const trades = snapshot.backtestTrades.data?.data ?? null;
  const equity = snapshot.backtestEquity.data?.data ?? null;
  const benchmark = snapshot.backtestBenchmark.data?.data ?? null;
  const config = summary?.configuration ?? report?.configuration ?? null;

  return (
    <div className="page-stack">
      <PageHeading eyebrow="STAGE 05 · HISTORICAL SIMULATION" title="Backtest Lab" description="Walk-forward simulation with explicit execution and cost assumptions." action={<span className="report-window">{summary?.dataset_start && summary.dataset_end ? `${formatDate(summary.dataset_start)} — ${formatDate(summary.dataset_end)}` : 'DATE RANGE N/A'}</span>} />
      {(snapshot.backtestReport.error || !report) ? <ErrorState title="Backtest report unavailable" message={snapshot.backtestReport.error ? 'The report endpoint could not be loaded.' : 'Run the Stage 5 backtest CLI to generate a report.'} onRetry={refresh} /> : <>
        {report.dataset_type.includes('DEMO') && <DataNotice tone="demo"><span className="notice-mark">D</span><span><strong>DEMO / SYNTHETIC DATA</strong><small>Historical simulation only · not real MCX performance evidence.</small></span><span className="notice-source">{summary?.dataset_start ? `${formatDate(summary.dataset_start)} — ${formatDate(summary.dataset_end)}` : 'DATE RANGE N/A'}</span></DataNotice>}

        {snapshot.backtestSummary.error && <div className="inline-warning">Backtest summary unavailable; report detail is still shown.</div>}
        <section className="content-panel config-panel">
          <div className="panel-heading-row"><SectionTitle title="Simulation configuration" meta="Values from the generated Stage 5 report" /><span className="estimated-label">ASSUMPTIONS · NOT EXECUTABLE TERMS</span></div>
          {config ? <div className="config-grid">
            <ConfigValue label="Entry z-score" value={config.entry_z} />
            <ConfigValue label="Exit z-score" value={config.exit_z} />
            <ConfigValue label="Maximum hold" value={config.max_holding_days} suffix="sessions" />
            <ConfigValue label="Minimum volume" value={config.minimum_volume} />
            <ConfigValue label="Minimum open interest" value={config.minimum_open_interest} />
            <ConfigValue label="Minimum expiry window" value={config.minimum_days_to_expiry} suffix="calendar days" />
            <ConfigValue label="Estimated cost / leg / fill" value={config.estimated_cost_rate_per_side} suffix="rate" />
            <ConfigValue label="Initial capital" value={config.initial_capital} currency />
          </div> : <EmptyState title="Configuration unavailable" message="No configuration was returned in the report." />}
        </section>

        <section className="metric-grid backtest-metrics">
          <MetricTile label="Total trades" value={summary ? formatInteger(summary.trade_count) : 'INSUFFICIENT DATA'} note={summary ? `${formatInteger(summary.completed_trades)} completed` : 'Summary unavailable'} />
          <MetricTile label="Win rate" value={summary?.win_rate === null || summary?.win_rate === undefined ? 'INSUFFICIENT DATA' : formatPercent(summary.win_rate)} note="Completed trades only" tone={summary?.win_rate == null ? 'muted' : 'default'} />
          <MetricTile label="Gross P&L" value={summary ? formatCurrency(summary.gross_pnl, 0) : 'INSUFFICIENT DATA'} note="Open positions marked to market" />
          <MetricTile label="Transaction costs" value={summary ? formatCurrency(summary.transaction_cost, 0) : 'INSUFFICIENT DATA'} note="Estimated assumption" />
          <MetricTile label="Net P&L" value={summary ? formatCurrency(summary.net_pnl, 0) : 'INSUFFICIENT DATA'} note="After estimated costs" tone={numericValue(summary?.net_pnl ?? null) === null ? 'muted' : numericValue(summary?.net_pnl ?? null)! > 0 ? 'positive' : 'default'} />
          <MetricTile label="Maximum drawdown" value={summary ? formatPercent(summary.max_drawdown) : 'INSUFFICIENT DATA'} note="End-of-day equity" />
          <MetricTile label="Sharpe" value={summary?.sharpe?.status === 'CALCULATED' ? formatNumber(summary.sharpe.value) : 'INSUFFICIENT DATA'} note={summary?.sharpe?.status === 'CALCULATED' ? `${summary.sharpe.observations ?? '—'} daily observations` : `${summary?.sharpe?.observations ?? 0} / ${summary?.sharpe?.minimum_observations ?? 20} observations`} tone={summary?.sharpe?.status === 'CALCULATED' ? 'default' : 'muted'} />
          <MetricTile label="Strategy return" value={summary ? formatPercent(summary.strategy_return) : 'INSUFFICIENT DATA'} note="Benchmark-aligned dates" />
          <MetricTile label="Benchmark return" value={summary ? formatPercent(summary.benchmark_return) : 'INSUFFICIENT DATA'} note={config?.benchmark_symbol ? `${config.benchmark_symbol} · single exact contract` : 'No configured benchmark'} />
          <MetricTile label="Relative outperformance" value={summary ? formatPercent(summary.relative_outperformance) : 'INSUFFICIENT DATA'} note="Strategy minus benchmark" tone={numericValue(summary?.relative_outperformance ?? null) === null ? 'muted' : numericValue(summary?.relative_outperformance ?? null)! > 0 ? 'positive' : 'negative'} />
        </section>

        <section className="content-panel">
          <div className="panel-heading-row"><SectionTitle title="Equity curve" meta="Ending equity · daily mark-to-market · costs deducted on fill" /><span className="panel-unit-label">STRATEGY EQUITY</span></div>
          {snapshot.backtestEquity.error ? <ErrorState title="Equity data unavailable" onRetry={refresh} /> : loading && !equity ? <LoadingState label="Loading equity observations" /> : <EquityChart rows={equity ?? []} />}
        </section>

        <section className="backtest-lower-grid">
          <div className="content-panel benchmark-panel"><div className="panel-heading-row"><SectionTitle title="Benchmark comparison" meta="Matched date range · exact contract · no roll" /></div>{snapshot.backtestBenchmark.error ? <ErrorState title="Benchmark unavailable" onRetry={refresh} /> : <ReturnComparisonChart benchmark={benchmark} />}<p className="benchmark-caption">Benchmark is a comparison reference, not proof of causality or a proxy for the entire Indian gold market.</p></div>
          <div className="content-panel backtest-notes"><SectionTitle title="Data quality & assumptions" meta="From generated report" />{report.data_quality_notes?.length ? <ul>{report.data_quality_notes.slice(0, 5).map((note, index) => <li key={`${index}-${note}`}>{note}</li>)}</ul> : <EmptyState title="No notes returned" message="Report contains no data-quality notes." />}</div>
        </section>

        <section className="content-panel trade-ledger-panel">
          <div className="panel-heading-row"><SectionTitle title="Trade ledger" meta="Exact target and hedge contracts" /><span className="panel-unit-label">{trades ? `${trades.length} RECORDS` : 'N/A'}</span></div>
          {snapshot.backtestTrades.error ? <ErrorState title="Trade ledger unavailable" onRetry={refresh} /> : trades && trades.length ? <div className="table-scroll"><table className="data-table trades-table"><thead><tr><th>Trade ID</th><th>Target</th><th>Expiry</th><th>Direction</th><th>Entry</th><th>Exit</th><th>Entry z</th><th>Exit z</th><th>Days</th><th>Exit reason</th><th>Gross P&L</th><th>Cost</th><th>Net P&L</th><th>Status</th></tr></thead><tbody>{trades.map((trade) => <tr key={trade.trade_id}><td><code>{trade.trade_id}</code></td><td><strong>{trade.target_symbol}</strong><small className="table-subline">{trade.target_contract_id}</small></td><td>{formatDate(trade.target_expiry_date)}</td><td>{trade.direction}</td><td>{formatDate(trade.entry_date)}</td><td>{formatDate(trade.exit_date)}</td><td className="numeric-cell">{formatNumber(trade.entry_z_score)}</td><td className="numeric-cell">{formatNumber(trade.exit_z_score)}</td><td className="numeric-cell">{trade.days_held ?? '—'}</td><td>{trade.exit_reason ?? 'OPEN'}</td><td className="numeric-cell">{formatSignedCurrency(trade.gross_pnl)}</td><td className="numeric-cell">{formatCurrency(trade.transaction_cost, 0)}</td><td className="numeric-cell">{formatSignedCurrency(trade.net_pnl)}</td><td><StatusBadge status={trade.status} /></td></tr>)}</tbody></table></div> : <EmptyState title="No qualifying trades were generated" message="The current Stage 4 classifications and dataset produced no eligible walk-forward entries." />}
        </section>
      </>}
    </div>
  );
}

function ConfigValue({ label, value, suffix, currency = false }: { label: string; value: string | number | null | undefined; suffix?: string; currency?: boolean }) {
  const display = value === null || value === undefined ? 'INSUFFICIENT DATA' : currency ? formatCurrency(value, 0) : String(value);
  return <div className="config-value"><span>{label}</span><strong>{display}</strong>{suffix && <small>{suffix}</small>}</div>;
}
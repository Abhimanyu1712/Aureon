import { ArrowDownRight, ArrowUpRight, BarChart3, CircleDot, Database, Layers3 } from 'lucide-react';
import { useDashboard } from '../lib/useDashboard';
import { formatCurrency, formatDate, formatInteger, formatPercent, formatShortDate, numericValue } from '../lib/format';
import { NormalizedComparisonChart } from '../components/Charts';
import { DataNotice, EmptyState, ErrorState, LoadingState, PageHeading, SectionTitle, StatusBadge } from '../components/States';
import { MetricTile } from '../components/MetricTile';

export function OverviewPage() {
  const { snapshot, loading, refresh } = useDashboard();
  if (!snapshot && loading) return <LoadingState />;
  if (!snapshot) return <ErrorState onRetry={refresh} />;

  const normalized = snapshot.normalized.data?.records ?? [];
  const signals = snapshot.signals.data?.records ?? [];
  const backtest = snapshot.backtestSummary.data?.data ?? null;
  const benchmark = numericValue(backtest?.benchmark_return ?? null);
  const activeSignals = signals.filter((row) => row.signal_status === 'WATCHLIST' || row.signal_status === 'STRONG_RELATIVE_DEVIATION').length;
  const contractCount = new Set(normalized.map((row) => row.contract_id)).size;
  const dataDates = [...new Set(normalized.map((row) => row.trade_date))].sort();
  const currentContracts = normalized.filter((row) => row.trade_date === dataDates.at(-1));
  const latestRecords = currentContracts.slice(0, 6);

  return (
    <div className="page-stack">
      <PageHeading
        eyebrow="COMMODITY DERIVATIVES INTELLIGENCE"
        title="Market overview"
        description="Normalize. Compare. Explain. Validate."
        action={<div className="overview-date-range"><span>OBSERVATION WINDOW</span><strong>{dataDates.length ? `${formatDate(dataDates[0])} — ${formatDate(dataDates.at(-1))}` : 'INSUFFICIENT DATA'}</strong></div>}
      />

      {snapshot.dataStatus.error && <ErrorState title="Data status unavailable" message="The dashboard could not verify data provenance." onRetry={refresh} />}
      {snapshot.dataStatus.data?.data_type === 'DEMO' && <DataNotice tone="demo"><span className="notice-mark">D</span><span><strong>DEMO / SYNTHETIC DATA</strong><small>Fabricated software-test observations. Not real MCX market evidence.</small></span><span className="notice-source">MCX BHAVCOPY FORMAT</span></DataNotice>}
      {snapshot.dataStatus.data?.data_type === 'MIXED' && <DataNotice tone="warning"><span className="notice-mark">!</span><span><strong>MIXED PROVENANCE</strong><small>DEMO and historical records are returned separately by source.</small></span></DataNotice>}
      {snapshot.dataStatus.data?.data_type === 'NONE' && <DataNotice tone="warning"><span className="notice-mark">!</span><span><strong>NO DATA LOADED</strong><small>Analytics and KPI values will remain unavailable until data exists.</small></span></DataNotice>}

      <section className="metric-grid" aria-label="Aureon overview metrics">
        <MetricTile label="Contracts tracked" value={snapshot.normalized.error ? 'N/A' : formatInteger(normalized.length ? contractCount : snapshot.normalized.data?.record_count ?? 0)} note="Symbol + exact expiry" icon={<Layers3 size={15} />} />
        <MetricTile label="Relative observations" value={snapshot.relativeValue.error ? 'N/A' : formatInteger(snapshot.relativeValue.data?.record_count ?? 0)} note="Stage 3 records" icon={<BarChart3 size={15} />} />
        <MetricTile label="Active classifications" value={snapshot.signals.error ? 'N/A' : formatInteger(activeSignals)} note="Watchlist + strong deviation" icon={<CircleDot size={15} />} />
        <MetricTile label="Backtest trades" value={backtest ? formatInteger(backtest.trade_count) : 'INSUFFICIENT DATA'} note={backtest ? `${formatInteger(backtest.completed_trades)} completed` : 'No report available'} icon={<Database size={15} />} />
        <MetricTile label="Strategy net P&L" value={backtest ? formatCurrency(backtest.net_pnl, 0) : 'INSUFFICIENT DATA'} note="Historical simulation only" tone={numericValue(backtest?.net_pnl ?? null) === null ? 'muted' : numericValue(backtest?.net_pnl ?? null)! > 0 ? 'positive' : 'default'} />
        <MetricTile label="Benchmark return" value={benchmark === null ? 'INSUFFICIENT DATA' : formatPercent(benchmark)} note={backtest?.configuration?.benchmark_symbol ? `${backtest.configuration.benchmark_symbol} · exact contract` : 'No benchmark report'} tone={benchmark === null ? 'muted' : benchmark >= 0 ? 'positive' : 'negative'} />
      </section>

      <section className="content-panel overview-chart-panel">
        <div className="panel-heading-row">
          <SectionTitle title="Normalized contract prices" meta="Purity-adjusted · ₹ per gram · exact expiries remain distinct" />
          <div className="panel-unit-label">999 FINENESS BASIS</div>
        </div>
        {snapshot.normalized.error ? <ErrorState title="Normalized data unavailable" onRetry={refresh} /> : loading && !snapshot.normalized.data ? <LoadingState label="Loading normalized prices" /> : <NormalizedComparisonChart rows={normalized} />}
      </section>

      <section className="overview-lower-grid">
        <div className="content-panel overview-contract-panel">
          <SectionTitle title="Latest contract observations" meta={dataDates.length ? `Trading date · ${formatDate(dataDates.at(-1))}` : 'No dates available'} />
          {snapshot.normalized.error ? <ErrorState title="Contract data unavailable" onRetry={refresh} /> : latestRecords.length ? (
            <div className="table-scroll">
              <table className="data-table compact-table">
                <thead><tr><th>Contract</th><th>Expiry</th><th>Purity-adjusted ₹/g</th><th>Volume</th><th>Open interest</th></tr></thead>
                <tbody>{latestRecords.map((row) => <tr key={row.contract_id}><td><strong>{row.symbol}</strong><small className="table-subline">{row.contract_id}</small></td><td>{formatDate(row.expiry_date)}</td><td className="numeric-cell">{formatCurrency(row.purity_adjusted_price_per_gram)}</td><td className="numeric-cell">{formatInteger(row.volume)}</td><td className="numeric-cell">{formatInteger(row.open_interest)}</td></tr>)}</tbody>
              </table>
            </div>
          ) : <EmptyState title="No normalized data" message="Contract observations will appear here when analytics output is available." />}
        </div>
        <div className="content-panel pulse-panel">
          <SectionTitle title="Classification pulse" meta="Latest available evidence" />
          {snapshot.signals.error ? <ErrorState title="Signals unavailable" onRetry={refresh} /> : signals.length ? (
            <div className="pulse-list">{signals.slice(-5).reverse().map((row) => <div className="pulse-row" key={`${row.contract_id}-${row.trade_date}`}><div><strong>{row.symbol}</strong><small>{row.contract_id} · {formatShortDate(row.trade_date)}</small></div><div className="pulse-right"><StatusBadge status={row.signal_status} /><span>{row.z_score === null ? 'N/A' : `z ${Number(row.z_score).toFixed(2)}`}</span></div></div>)}</div>
          ) : <EmptyState title="No signal records" message="Signal classifications have not been generated." />}
          <div className="pulse-footnote">{activeSignals === 0 && signals.length > 0 ? 'No watchlist or strong relative deviation is present in the current observations.' : 'Counts reflect the available Stage 4 signal file.'}</div>
        </div>
      </section>
      <div className="overview-caption"><ArrowUpRight size={14} /><span>Observed market fields feed derived analytics. No displayed classification is an execution instruction.</span><ArrowDownRight size={14} /></div>
    </div>
  );
}
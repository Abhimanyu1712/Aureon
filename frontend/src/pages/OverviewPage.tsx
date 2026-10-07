import { useDashboard } from '../lib/useDashboard';
import { formatInteger } from '../lib/format';
import { NormalizedComparisonChart } from '../components/Charts';
import { DataNotice, ErrorState, LoadingState, PageHeading, SectionTitle } from '../components/States';
import { MetricTile } from '../components/MetricTile';

export function OverviewPage() {
  const { snapshot, loading, refresh } = useDashboard();
  if (!snapshot && loading) return <LoadingState />;
  if (!snapshot) return <ErrorState onRetry={refresh} />;

  const normalized = snapshot.normalized.data?.records ?? [];
  const signals = snapshot.signals.data?.records ?? [];
  const noSignalCount = signals.filter((row) => row.signal_status === 'NO_SIGNAL').length;
  const contractCount = new Set(normalized.map((row) => row.contract_id)).size;
  const symbols = [...new Set(normalized.map((row) => row.symbol))].sort();
  const monthSymbols = new Map<string, Set<string>>();
  normalized.forEach((row) => {
    const expiryMonth = row.expiry_date.slice(0, 7);
    const present = monthSymbols.get(expiryMonth) ?? new Set<string>();
    present.add(row.symbol);
    monthSymbols.set(expiryMonth, present);
  });
  const chartMonth = [...monthSymbols.entries()]
    .filter(([, present]) => symbols.every((symbol) => present.has(symbol)))
    .map(([month]) => month)
    .sort()
    .at(-1);
  const chartRows = normalized.filter((row) => row.expiry_date.startsWith(chartMonth ?? ''));

  return (
    <div className="page-stack">
      <PageHeading
        eyebrow="AUREON"
        title="Commodity Derivatives Intelligence"
        description="See the spread. Understand the risk. Act with evidence."
        action={<div className="overview-date-range"><span>MARKET OVERVIEW</span><strong>{snapshot.reportDate}</strong></div>}
      />

      {snapshot.dataStatus.error && <ErrorState title="Data status unavailable" message="The dashboard could not verify data provenance." onRetry={refresh} />}
      {snapshot.dataStatus.data?.data_type === 'DEMO' && <DataNotice tone="demo"><span className="notice-mark">D</span><span><strong>DEMO / SYNTHETIC DATA</strong><small>Fabricated software-test observations. Not real MCX market evidence.</small></span><span className="notice-source">MCX BHAVCOPY FORMAT</span></DataNotice>}
      {snapshot.dataStatus.data?.data_type === 'MIXED' && <DataNotice tone="warning"><span className="notice-mark">!</span><span><strong>MIXED PROVENANCE</strong><small>DEMO and historical records are returned separately by source.</small></span></DataNotice>}
      {snapshot.dataStatus.data?.data_type === 'NONE' && <DataNotice tone="warning"><span className="notice-mark">!</span><span><strong>NO DATA LOADED</strong><small>Analytics and KPI values will remain unavailable until data exists.</small></span></DataNotice>}

      <section className="metric-grid overview-kpis" aria-label="Market overview metrics">
        <MetricTile label="Dated contract observations" value={snapshot.normalized.error ? 'N/A' : formatInteger(snapshot.normalized.data?.record_count ?? 0)} note="Stage 3 normalized rows" />
        <MetricTile label="Exact contracts tracked" value={snapshot.normalized.error ? 'N/A' : formatInteger(contractCount)} note="Distinct Symbol + ExpiryDate" />
        <MetricTile label="No Signal" value={snapshot.signals.error ? 'N/A' : formatInteger(noSignalCount)} note="Stage 4 classification rows" />
      </section>

      <section className="content-panel overview-chart-panel">
        <div className="panel-heading-row">
          <SectionTitle title="Normalized gold price" meta={chartMonth ? `₹ / gram · latest common expiry month ${chartMonth}` : '₹ / gram · no common expiry month available'} />
          <div className="panel-unit-label">999 FINENESS BASIS</div>
        </div>
        {snapshot.normalized.error ? <ErrorState title="Normalized data unavailable" onRetry={refresh} /> : loading && !snapshot.normalized.data ? <LoadingState label="Loading normalized prices" /> : <NormalizedComparisonChart rows={chartRows} />}
      </section>
      <div className="overview-chart-caption">Each line uses one exact contract per symbol in the latest expiry month shared across symbols. The contract expiry date remains distinct; no continuous near-month series is constructed.</div>
    </div>
  );
}
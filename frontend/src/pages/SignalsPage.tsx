import { useState } from 'react';
import { FileText, Search } from 'lucide-react';
import { useDashboard } from '../lib/useDashboard';
import { compactContract, formatCurrency, formatDate, formatInteger, formatNumber } from '../lib/format';
import { DirectionBadge, EmptyState, ErrorState, LoadingState, PageHeading, SectionTitle, StatusBadge } from '../components/States';

const SIGNAL_STATUSES = ['NO_SIGNAL', 'WATCHLIST', 'STRONG_RELATIVE_DEVIATION', 'INSUFFICIENT_HISTORY', 'INSUFFICIENT_PEERS', 'INSUFFICIENT_LIQUIDITY', 'EXPIRY_FILTER_FAILED'];

export function SignalsPage() {
  const { snapshot, loading, refresh } = useDashboard();
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [symbolFilter, setSymbolFilter] = useState('ALL');
  const [query, setQuery] = useState('');
  const [selectedKey, setSelectedKey] = useState('');
  if (!snapshot && loading) return <LoadingState />;
  if (!snapshot) return <ErrorState onRetry={refresh} />;

  const records = snapshot.signals.data?.records ?? [];
  const symbols = [...new Set(records.map((row) => row.symbol))].sort();
  const filtered = records.filter((row) => (statusFilter === 'ALL' || row.signal_status === statusFilter)
    && (symbolFilter === 'ALL' || row.symbol === symbolFilter)
    && (!query || `${row.symbol} ${row.contract_id}`.toUpperCase().includes(query.trim().toUpperCase())));
  const selected = filtered.find((row) => `${row.contract_id}|${row.trade_date}` === selectedKey) ?? filtered[0];
  const countForStatus = (status: string) => records.filter((row) => row.signal_status === status).length;

  return (
    <div className="page-stack">
      <PageHeading eyebrow="STAGE 04 · EXPLAINABLE CLASSIFICATION" title="Signal research" description="Review relative direction, filter evidence, and the exact classification rationale." action={<div className="record-count"><span>OBSERVATIONS</span><strong>{snapshot.signals.error ? 'N/A' : snapshot.signals.data?.record_count ?? 0}</strong></div>} />
      {snapshot.signals.error && <ErrorState title="Signal data unavailable" onRetry={refresh} />}
      {snapshot.dataStatus.data?.data_type === 'DEMO' && <div className="signal-demo-line"><span className="demo-led" />DEMO / SYNTHETIC DATA <span>Classifications exercise software behavior; they are not market evidence.</span></div>}

      <section className="status-summary-grid" aria-label="Signal status counts">
        {SIGNAL_STATUSES.map((status) => <div className="status-summary-cell" key={status}><StatusBadge status={status} /><strong>{snapshot.signals.error ? 'N/A' : countForStatus(status)}</strong></div>)}
      </section>

      <div className="signal-layout">
        <section className="content-panel signal-list-panel">
          <div className="panel-heading-row"><SectionTitle title="Classifications" meta="Stage 4 evidence · exact contract expiry retained" /><span className="panel-unit-label">{filtered.length} VISIBLE</span></div>
          <div className="filter-bar signal-filter-bar">
            <label className="search-control"><Search size={15} /><input aria-label="Search signals" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search contract" /></label>
            <label className="filter-control"><span>SYMBOL</span><select value={symbolFilter} onChange={(event) => setSymbolFilter(event.target.value)}><option value="ALL">All symbols</option>{symbols.map((symbol) => <option key={symbol}>{symbol}</option>)}</select></label>
            <label className="filter-control"><span>STATUS</span><select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}><option value="ALL">All statuses</option>{SIGNAL_STATUSES.map((status) => <option key={status} value={status}>{status.replaceAll('_', ' ')}</option>)}</select></label>
          </div>
          {loading && !snapshot.signals.data ? <LoadingState label="Loading signal evidence" /> : filtered.length ? <div className="table-scroll signal-table-scroll"><table className="data-table signal-table"><thead><tr><th>Observation</th><th>Direction</th><th>Z-score</th><th>Peer ref.</th><th>Peers</th><th>Volume / OI</th><th>Expiry</th><th>Status</th></tr></thead><tbody>{filtered.map((row) => {
            const key = `${row.contract_id}|${row.trade_date}`;
            const isSelected = selected && key === `${selected.contract_id}|${selected.trade_date}`;
            return <tr key={key} tabIndex={0} aria-selected={isSelected} className={isSelected ? 'selected-row' : ''} onClick={() => setSelectedKey(key)} onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); setSelectedKey(key); } }}><td><strong>{row.symbol}</strong><small className="table-subline">{compactContract(row.contract_id)} · {formatDate(row.trade_date)}</small></td><td><DirectionBadge direction={row.relative_direction} /></td><td className="numeric-cell">{row.z_score === null ? 'N/A' : formatNumber(row.z_score)}</td><td className="numeric-cell">{formatCurrency(row.peer_reference)}</td><td className="numeric-cell">{row.peer_count}</td><td className="numeric-cell">{formatInteger(row.volume)} <small>/ {formatInteger(row.open_interest)}</small></td><td className="numeric-cell">{row.days_to_expiry}d</td><td><StatusBadge status={row.signal_status} /></td></tr>;
          })}</tbody></table></div> : <EmptyState title={snapshot.signals.error ? 'Signal data unavailable' : 'No matching signal observations'} message={snapshot.signals.error ? 'Retry the API request to reload signal data.' : 'There may be no records for the selected filters.'} />}
        </section>

        <aside className="content-panel signal-detail-panel">
          {selected ? <>
            <div className="signal-detail-heading"><span className="eyebrow">SIGNAL STATUS</span><StatusBadge status={selected.signal_status} /><h2>{selected.symbol}</h2><code>{selected.contract_id}</code></div>
            <div className="signal-evidence-grid">
              <div><span>Relative position</span><DirectionBadge direction={selected.relative_direction} /></div>
              <div><span>Z-score</span><strong>{selected.z_score === null ? 'INSUFFICIENT DATA' : formatNumber(selected.z_score)}</strong></div>
              <div><span>Purity-adjusted price</span><strong>{formatCurrency(selected.normalized_price)} <small>₹/g</small></strong></div>
              <div><span>Peer reference</span><strong>{formatCurrency(selected.peer_reference)} <small>₹/g</small></strong></div>
              <div><span>Volume proxy</span><strong>{formatInteger(selected.volume)}</strong></div>
              <div><span>Open interest proxy</span><strong>{formatInteger(selected.open_interest)}</strong></div>
              <div><span>Comparable peers</span><strong>{selected.peer_count}</strong></div>
              <div><span>Days to expiry</span><strong>{selected.days_to_expiry}</strong></div>
            </div>
            <div className="explanation-block"><div className="explanation-title"><FileText size={15} /><span>WHY THIS WAS CLASSIFIED</span></div><p>{selected.explanation}</p></div>
            <div className="signal-provenance"><span>{selected.source_type} · {formatDate(selected.trade_date)}</span><span>Cost filter: {selected.cost_filter_status}</span></div>
          </> : <EmptyState title="Select a signal" message="Choose an observation to inspect its evidence and backend explanation." />}
        </aside>
      </div>
    </div>
  );
}
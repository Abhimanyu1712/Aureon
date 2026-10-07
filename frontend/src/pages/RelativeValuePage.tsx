import { useDeferredValue, useState } from 'react';
import { ArrowDown, ArrowUp, ArrowUpDown, Search } from 'lucide-react';
import type { Numeric } from '../lib/api';
import { useDashboard } from '../lib/useDashboard';
import { formatCurrency, formatDate, formatInteger, formatNumber, numericValue } from '../lib/format';
import { DirectionBadge, EmptyState, ErrorState, LoadingState, PageHeading, SectionTitle, StatusBadge } from '../components/States';
import { RelativePairChart, ZScoreChart } from '../components/Charts';

type SortKey = 'symbol' | 'expiry_date' | 'normalized_price' | 'peer_reference' | 'spread' | 'z_score' | 'peer_count' | 'volume' | 'open_interest' | 'days_to_expiry' | 'signal_status';
const sortableColumns: { key: SortKey; label: string; numeric?: boolean }[] = [
  { key: 'symbol', label: 'Symbol' },
  { key: 'expiry_date', label: 'Expiry' },
  { key: 'normalized_price', label: 'Normalized ₹/g', numeric: true },
  { key: 'peer_reference', label: 'Peer reference', numeric: true },
  { key: 'spread', label: 'Spread', numeric: true },
  { key: 'z_score', label: 'Z-score', numeric: true },
  { key: 'peer_count', label: 'Peers', numeric: true },
  { key: 'volume', label: 'Volume', numeric: true },
  { key: 'open_interest', label: 'Open interest', numeric: true },
  { key: 'days_to_expiry', label: 'Days to expiry', numeric: true },
  { key: 'signal_status', label: 'Status' },
];

function compareValues(a: string | Numeric | undefined, b: string | Numeric | undefined, numeric: boolean) {
  if (numeric) {
    const left = numericValue(a as Numeric);
    const right = numericValue(b as Numeric);
    if (left === null) return right === null ? 0 : 1;
    if (right === null) return -1;
    return left - right;
  }
  return String(a ?? '').localeCompare(String(b ?? ''));
}

export function RelativeValuePage() {
  const { snapshot, loading, refresh } = useDashboard();
  const [search, setSearch] = useState('');
  const [symbolFilter, setSymbolFilter] = useState('ALL');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [sortKey, setSortKey] = useState<SortKey>('z_score');
  const [ascending, setAscending] = useState(false);
  const [selectedKey, setSelectedKey] = useState('');
  const deferredSearch = useDeferredValue(search.trim().toUpperCase());

  if (!snapshot && loading) return <LoadingState />;
  if (!snapshot) return <ErrorState onRetry={refresh} />;
  const rows = snapshot.relativeValue.data?.records ?? [];
  const signals = snapshot.signals.data?.records ?? [];
  const signalMap = new Map(signals.map((row) => [`${row.contract_id}|${row.trade_date}`, row]));
  const symbols = [...new Set(rows.map((row) => row.symbol))].sort();
  const enriched = rows.map((row) => ({ ...row, stage4: signalMap.get(`${row.contract_id}|${row.trade_date}`) }));
  const filtered = enriched.filter((row) => {
    const signalStatus = row.stage4?.signal_status ?? row.analytics_status;
    return (symbolFilter === 'ALL' || row.symbol === symbolFilter)
      && (statusFilter === 'ALL' || signalStatus === statusFilter)
      && (!deferredSearch || `${row.symbol} ${row.contract_id} ${row.expiry_date}`.toUpperCase().includes(deferredSearch));
  });
  const sorted = [...filtered].sort((left, right) => {
    const signalA = left.stage4?.signal_status ?? left.analytics_status;
    const signalB = right.stage4?.signal_status ?? right.analytics_status;
    const valueA = sortKey === 'signal_status' ? signalA : sortKey === 'volume' || sortKey === 'open_interest' || sortKey === 'days_to_expiry' ? left.stage4?.[sortKey] : left[sortKey];
    const valueB = sortKey === 'signal_status' ? signalB : sortKey === 'volume' || sortKey === 'open_interest' || sortKey === 'days_to_expiry' ? right.stage4?.[sortKey] : right[sortKey];
    const numeric = sortableColumns.find((column) => column.key === sortKey)?.numeric ?? false;
    return compareValues(valueA, valueB, numeric) * (ascending ? 1 : -1);
  });
  const selected = sorted.find((row) => `${row.contract_id}|${row.trade_date}` === selectedKey) ?? sorted[0];
  const selectedHistory = selected ? rows.filter((row) => row.contract_id === selected.contract_id).sort((a, b) => a.trade_date.localeCompare(b.trade_date)) : [];

  function requestSort(key: SortKey) {
    if (key === sortKey) setAscending((current) => !current);
    else { setSortKey(key); setAscending(true); }
  }

  return (
    <div className="page-stack">
      <PageHeading eyebrow="STAGE 03 · PEER COMPARISON" title="Relative Value Scanner" description="Find statistically unusual differences across comparable gold contracts." action={<div className="record-count"><span>OBSERVATIONS</span><strong>{snapshot.relativeValue.error ? 'N/A' : formatInteger(snapshot.relativeValue.data?.record_count ?? 0)}</strong></div>} />
      {snapshot.relativeValue.error && <ErrorState title="Relative-value data unavailable" onRetry={refresh} />}
      {snapshot.signals.error && <div className="inline-warning">Signal enrichments unavailable; showing Stage 3 analytics status.</div>}

      <section className="filter-bar" aria-label="Relative value filters">
        <label className="search-control"><Search size={15} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search symbol or exact contract" aria-label="Search symbol or exact contract" /></label>
        <label className="filter-control"><span>SYMBOL</span><select value={symbolFilter} onChange={(event) => setSymbolFilter(event.target.value)}><option value="ALL">All symbols</option>{symbols.map((symbol) => <option key={symbol}>{symbol}</option>)}</select></label>
        <label className="filter-control"><span>CLASSIFICATION</span><select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}><option value="ALL">All statuses</option>{['STRONG_RELATIVE_DEVIATION', 'WATCHLIST', 'NO_SIGNAL', 'INSUFFICIENT_HISTORY', 'INSUFFICIENT_PEERS', 'INSUFFICIENT_LIQUIDITY', 'EXPIRY_FILTER_FAILED'].map((status) => <option key={status} value={status}>{status.replaceAll('_', ' ')}</option>)}</select></label>
        <span className="filter-result-count">{snapshot.relativeValue.error ? 'N/A' : `${sorted.length} rows`}</span>
      </section>

      <div className="scanner-layout">
        <section className="content-panel scanner-table-panel">
          <div className="panel-heading-row"><SectionTitle title="Comparable contract observations" meta="Select a row to inspect its historical spread context" /><span className="panel-unit-label">₹ / GRAM · 999 FINENESS</span></div>
          {loading && !snapshot.relativeValue.data ? <LoadingState label="Loading relative value observations" /> : sorted.length ? (
            <div className="table-scroll scanner-scroll">
              <table className="data-table scanner-table">
                <thead><tr>{sortableColumns.map((column) => {
                  const SortIcon = sortKey !== column.key ? ArrowUpDown : ascending ? ArrowUp : ArrowDown;
                  return <th key={column.key}><button className="sort-button" onClick={() => requestSort(column.key)} aria-label={`Sort by ${column.label}`}>{column.label}<SortIcon size={12} /></button></th>;
                })}</tr></thead>
                <tbody>{sorted.map((row) => {
                  const key = `${row.contract_id}|${row.trade_date}`;
                  const status = row.stage4?.signal_status ?? row.analytics_status;
                  const selectedRow = selected && `${selected.contract_id}|${selected.trade_date}` === key;
                  return <tr key={key} className={selectedRow ? 'selected-row' : ''} tabIndex={0} aria-selected={selectedRow} onClick={() => setSelectedKey(key)} onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); setSelectedKey(key); } }}>
                    <td><strong>{row.symbol}</strong><small className="table-subline">{formatDate(row.trade_date)}</small></td>
                    <td>{formatDate(row.expiry_date)}</td>
                    <td className="numeric-cell">{formatCurrency(row.normalized_price)}</td>
                    <td className="numeric-cell">{formatCurrency(row.peer_reference)}</td>
                    <td className="numeric-cell">{row.spread === null ? 'N/A' : `${Number(row.spread) > 0 ? '+' : ''}${formatNumber(row.spread)}`}</td>
                    <td className="numeric-cell">{row.z_score === null ? <span className="insufficient-label">INSUFFICIENT DATA</span> : Number(row.z_score).toFixed(2)}</td>
                    <td><DirectionBadge direction={row.stage4?.relative_direction ?? 'NEUTRAL'} /></td>
                    <td className="numeric-cell">{row.peer_count}</td>
                    <td className="numeric-cell">{formatInteger(row.stage4?.volume ?? null)}</td>
                    <td className="numeric-cell">{formatInteger(row.stage4?.open_interest ?? null)}</td>
                    <td className="numeric-cell">{row.stage4?.days_to_expiry ?? 'N/A'}</td>
                    <td><StatusBadge status={status} /></td>
                  </tr>;
                })}</tbody>
              </table>
            </div>
          ) : <EmptyState title={snapshot.relativeValue.error ? 'Relative-value data unavailable' : 'No matching observations'} message={snapshot.relativeValue.error ? 'Retry the API request to reload the scanner.' : 'Adjust filters or run the Stage 3 analytics pipeline.'} />}
        </section>

        <aside className="content-panel scanner-detail-panel">
          {selected ? <>
            <div className="detail-topline"><div><span className="eyebrow">SELECTED CONTRACT</span><h2>{selected.symbol}</h2><code>{selected.contract_id}</code></div><StatusBadge status={selected.stage4?.signal_status ?? selected.analytics_status} /></div>
            <div className="detail-stats-grid">
              <div><span>Trading date</span><strong>{formatDate(selected.trade_date)}</strong></div>
              <div><span>Expiry date</span><strong>{formatDate(selected.expiry_date)}</strong></div>
              <div><span>Contract · ₹/g</span><strong>{formatCurrency(selected.normalized_price)}</strong></div>
              <div><span>Peer reference</span><strong>{formatCurrency(selected.peer_reference)}</strong></div>
            </div>
            <SectionTitle title="Price vs peer reference" meta="Purity-adjusted ₹/gram" />
            <RelativePairChart rows={selectedHistory} />
            <div className="detail-chart-heading"><SectionTitle title="Standardized deviation" meta="Stage 3 rolling z-score" /></div>
            <ZScoreChart rows={selectedHistory} />
            {selected.stage4?.explanation && <div className="evidence-note"><span>STAGE 4 EVIDENCE</span><p>{selected.stage4.explanation}</p></div>}
          </> : <EmptyState title="Select an observation" message="Choose a table row to inspect exact contract history." />}
        </aside>
      </div>
      <div className="page-footnote">Peer cohort: same trading date, provenance, and expiry month. Exact expiries remain separate; cross-tenor effects may remain.</div>
    </div>
  );
}
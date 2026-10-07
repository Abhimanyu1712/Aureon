import { useState } from 'react';
import { ChevronDown, Layers3 } from 'lucide-react';
import { NormalizedComparisonChart } from '../components/Charts';
import { EmptyState, ErrorState, LoadingState, PageHeading, SectionTitle } from '../components/States';
import { useDashboard } from '../lib/useDashboard';
import { CONTRACT_SPECS } from '../lib/contracts';
import { compactContract, formatCurrency, formatDate, formatInteger } from '../lib/format';

export function ContractsPage() {
  const { snapshot, loading, refresh } = useDashboard();
  const [selectedContract, setSelectedContract] = useState('');
  if (!snapshot && loading) return <LoadingState />;
  if (!snapshot) return <ErrorState onRetry={refresh} />;

  const normalized = snapshot.normalized.data?.records ?? [];
  const contractIds = [...new Set(normalized.map((row) => row.contract_id))].sort();
  const activeId = contractIds.includes(selectedContract) ? selectedContract : contractIds[0] ?? '';
  const history = normalized.filter((row) => row.contract_id === activeId).sort((a, b) => a.trade_date.localeCompare(b.trade_date));
  const latest = history.at(-1);
  const spec = latest ? CONTRACT_SPECS[latest.symbol] : null;
  const lifecycle = latest && snapshot.signals.data?.records.find((row) => row.contract_id === latest.contract_id && row.trade_date === latest.trade_date);

  return (
    <div className="page-stack">
      <PageHeading eyebrow="CONTRACT REFERENCE" title="Contract Explorer" description="Inspect observed prices and specifications without merging expiries." action={<div className="record-count"><span>EXACT CONTRACTS</span><strong>{snapshot.normalized.error ? 'N/A' : contractIds.length}</strong></div>} />
      {snapshot.normalized.error && <ErrorState title="Contract data unavailable" onRetry={refresh} />}
      {contractIds.length > 0 && <section className="contract-selector-panel content-panel">
        <div className="selector-copy"><span className="eyebrow">CONTRACT IDENTITY</span><strong>Symbol + ExpiryDate</strong><small>Each expiry is a distinct listed contract; dates are not rolled.</small></div>
        <label className="contract-select-wrap"><span>SELECT EXACT CONTRACT</span><div><Layers3 size={15} /><select value={activeId} onChange={(event) => setSelectedContract(event.target.value)} aria-label="Select exact contract">{contractIds.map((contractId) => <option value={contractId} key={contractId}>{compactContract(contractId)} · {contractId}</option>)}</select><ChevronDown size={14} /></div></label>
      </section>}

      {!snapshot.normalized.error && !contractIds.length && <EmptyState title="No normalized contracts" message="Run the Stage 3 analytics pipeline to populate the contract explorer." />}

      {latest && spec && <>
        <div className="contract-summary-grid">
          <div className="contract-identity-block"><span className="eyebrow">SELECTED CONTRACT</span><h2>{latest.symbol}</h2><code>{latest.contract_id}</code><div className="identity-dates"><span>Trading date<strong>{formatDate(latest.trade_date)}</strong></span><span>Expiry date<strong>{formatDate(latest.expiry_date)}</strong></span></div></div>
          <div className="content-panel specification-panel"><SectionTitle title="Contract specification" meta="Reference from Stage 3 configuration" /><div className="spec-grid"><div><span>Contract size</span><strong>{spec.contract_size_grams} g</strong></div><div><span>Quotation</span><strong>₹ per {spec.quote_grams} g</strong></div><div><span>Purity</span><strong>{spec.purity_fineness} fineness</strong></div><div><span>Expiry rule</span><strong>{spec.expiry_rule}</strong></div></div></div>
        </div>
        <section className="metric-grid contract-metrics">
          <div className="metric-tile"><div className="metric-head"><span>Normalized ₹/gram</span></div><strong>{formatCurrency(latest.normalized_price_per_gram)}</strong><small>Before purity adjustment</small></div>
          <div className="metric-tile"><div className="metric-head"><span>Purity-adjusted ₹/gram</span></div><strong>{formatCurrency(latest.purity_adjusted_price_per_gram)}</strong><small>999-fineness basis</small></div>
          <div className="metric-tile"><div className="metric-head"><span>Volume</span></div><strong>{formatInteger(latest.volume)}</strong><small>Observed daily quantity</small></div>
          <div className="metric-tile"><div className="metric-head"><span>Open interest</span></div><strong>{formatInteger(latest.open_interest)}</strong><small>Observed contracts</small></div>
          <div className="metric-tile"><div className="metric-head"><span>Days to expiry</span></div><strong>{lifecycle ? lifecycle.days_to_expiry : 'N/A'}</strong><small>{lifecycle ? `At ${formatDate(lifecycle.trade_date)}` : 'No matching signal row'}</small></div>
        </section>
        <section className="content-panel">
          <div className="panel-heading-row"><SectionTitle title="Contract price history" meta={`${history.length} observed trading dates · purity-adjusted ₹/gram`} /><span className="panel-unit-label">{latest.source_type}</span></div>
          <NormalizedComparisonChart rows={history} height={300} />
        </section>
        <div className="page-footnote">Chart values are derived from the validated Stage 2 and Stage 3 outputs. Contract close itself is not a normalized comparison unit.</div>
      </>}
    </div>
  );
}
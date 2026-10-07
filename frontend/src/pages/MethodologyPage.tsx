import { ArrowDown, ArrowRight, Database, FileCheck2, FlaskConical, GitCompareArrows, Ruler, ShieldAlert, Signal, Timer } from 'lucide-react';
import { PageHeading, DataNotice, SectionTitle } from '../components/States';
import { CONTRACT_SPECS } from '../lib/contracts';
import { useDashboard } from '../lib/useDashboard';

const stages = [
  { label: 'MCX Bhavcopy', icon: Database, detail: 'Observed daily contract fields' },
  { label: 'Validation', icon: FileCheck2, detail: 'Schema, values, duplicate checks' },
  { label: 'Contract identity', icon: GitCompareArrows, detail: 'Symbol + exact ExpiryDate' },
  { label: 'Normalization', icon: Ruler, detail: 'Purity-adjusted ₹/gram' },
  { label: 'Peer comparison', icon: GitCompareArrows, detail: 'Same date and expiry month' },
  { label: 'Z-score', icon: Signal, detail: 'Trailing, current-inclusive window' },
  { label: 'Liquidity + expiry', icon: Timer, detail: 'Volume/OI proxies and days left' },
  { label: 'Signal classification', icon: ShieldAlert, detail: 'Evidence status, no advice' },
  { label: 'Walk-forward simulation', icon: FlaskConical, detail: 'Next-date close assumptions' },
  { label: 'Trader-facing intelligence', icon: ArrowRight, detail: 'Research context, not instructions' },
];

export function MethodologyPage() {
  const { snapshot } = useDashboard();
  const status = snapshot?.dataStatus.data;
  const dataMode = status?.data_type === 'DEMO' ? 'DEMO / SYNTHETIC' : status?.data_type === 'REAL/HISTORICAL' ? 'REAL / HISTORICAL' : status?.data_type === 'MIXED' ? 'MIXED PROVENANCE' : status?.data_type === 'NONE' ? 'NO DATA LOADED' : 'STATUS UNAVAILABLE';

  return (
    <div className="page-stack methodology-page">
      <PageHeading eyebrow="MODEL TRANSPARENCY" title="Methodology" description="How observed contract records become comparable research evidence." />
      {status?.data_type === 'DEMO' && <DataNotice tone="demo"><span className="notice-mark">D</span><span><strong>DATA MODE · {dataMode}</strong><small>Synthetic observations are not real MCX prices, history, or performance.</small></span><span className="notice-source">SOURCE FILE · {status.source_files.find((file) => file.includes('data/demo/'))?.split('/').at(-1) ?? 'SYNTHETIC FIXTURE'}</span></DataNotice>}
      <section className="content-panel pipeline-panel"><div className="panel-heading-row"><SectionTitle title="Aureon research pipeline" meta="Observed input → derived evidence → historical simulation" /></div><div className="method-pipeline">{stages.map((stage, index) => { const Icon = stage.icon; return <div className="pipeline-step" key={stage.label}><div className="pipeline-step-head"><span className="pipeline-index">{String(index + 1).padStart(2, '0')}</span><Icon size={17} /></div><strong>{stage.label}</strong><small>{stage.detail}</small>{index < stages.length - 1 && <ArrowRight className="pipeline-arrow" size={15} />}</div>; })}</div><div className="pipeline-footer"><ArrowDown size={14} /><span>Raw and processed records are not overwritten by analytics or backtesting.</span></div></section>

      <section className="content-panel methodology-spec-panel"><div className="panel-heading-row"><SectionTitle title="Gold contract specifications" meta="Reference values used for Stage 3 normalization" /></div><div className="table-scroll"><table className="data-table"><thead><tr><th>Symbol</th><th>Contract size</th><th>Quotation basis</th><th>Purity</th><th>Expiry rule</th></tr></thead><tbody>{Object.entries(CONTRACT_SPECS).map(([symbol, spec]) => <tr key={symbol}><td><strong>{symbol}</strong></td><td>{spec.contract_size_grams} g</td><td>₹ per {spec.quote_grams} g</td><td>{spec.purity_fineness} fineness</td><td>{spec.expiry_rule}</td></tr>)}</tbody></table></div><p className="method-note">Purity-adjusted price = observed ₹/gram × (999 / contract fineness). Relative-value comparisons retain exact expiry identities and do not create a continuous series.</p></section>

      <div className="methodology-grid">
        <MethodCard number="01" title="Data provenance" body="Observed bhavcopy rows pass Stage 2 validation. Stage 3 normalization and peer values are derived outputs; Stage 4 classifications and Stage 5 simulations remain labeled by their input source. The UI does not fetch live MCX data." />
        <MethodCard number="02" title="Relative value" body="Stage 3 compares same-date, same-source contracts in the same expiry month. Peer reference is the median across distinct peer symbols. Spread is contract purity-adjusted ₹/gram minus that reference." />
        <MethodCard number="03" title="Standardization" body="The z-score uses rolling spread statistics through the current observation only. Early rows, missing peers, or zero variance remain explicitly insufficient rather than being interpolated." />
        <MethodCard number="04" title="Liquidity proxy" body="Daily Volume and OpenInterest are observable activity fields. They are not order-book depth, executable liquidity, or a guarantee that a position can be entered or exited." />
        <MethodCard number="05" title="Contract lifecycle" body="Days to expiry is ExpiryDate minus the row’s TradingDate. No tender-period calendar or undisclosed lifecycle date is inferred." />
        <MethodCard number="06" title="Signal classification" body="Stage 4 prioritizes peer/history sufficiency, liquidity proxies, and the expiry filter before classifying a z-score. Cheap/expensive indicates relative position only, never an instruction." />
        <MethodCard number="07" title="Walk-forward backtest" body="Stage 5 consumes Stage 4 strong-deviation rows. Entries and ordinary exits use the next joint available daily close. Open positions are marked to available closes; daily close is not an intraday fill." />
        <MethodCard number="08" title="Transaction costs" body="The backtest uses a configurable estimated per-leg, per-fill notional rate. It is an explicit placeholder, not verified MCX brokerage, taxes, exchange fees, slippage, or impact." />
        <MethodCard number="09" title="Benchmark" body="Returns compare against one exact normalized GOLDTEN contract available on every backtest date, without rolling. It is a reference series, not the entire Indian gold market or proof of causality." />
        <MethodCard number="10" title="Limitations" body="The current synthetic sample is only three dates with no strong Stage 4 entry, so it produces no trades and cannot support a Sharpe estimate. Synthetic output is not real market evidence; simulation is not a future-performance guarantee." />
      </div>
      <div className="methodology-disclaimer">AUREON IS A RESEARCH INTERFACE · Observations and simulations are not financial advice or executable market instructions.</div>
    </div>
  );
}

function MethodCard({ number, title, body }: { number: string; title: string; body: string }) {
  return <article className="method-card"><span>{number}</span><div><h3>{title}</h3><p>{body}</p></div></article>;
}
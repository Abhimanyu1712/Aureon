import { AlertTriangle, LoaderCircle, RotateCw } from 'lucide-react';
import type { ReactNode } from 'react';

export function PageHeading({ eyebrow, title, description, action }: { eyebrow: string; title: string; description: string; action?: ReactNode }) {
  return (
    <div className="page-heading">
      <div>
        <div className="eyebrow">{eyebrow}</div>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {action && <div className="page-heading-action">{action}</div>}
    </div>
  );
}

export function LoadingState({ label = 'Loading market intelligence' }: { label?: string }) {
  return <div className="state-panel loading-state"><LoaderCircle className="spin" size={18} /><span>{label}</span><div className="loading-rule" /></div>;
}

export function ErrorState({ title = 'Data unavailable', message = 'Backend unavailable. Start the Aureon API to load market intelligence.', onRetry }: { title?: string; message?: string; onRetry: () => void }) {
  return (
    <div className="state-panel error-state">
      <AlertTriangle size={18} />
      <div><strong>{title}</strong><span>{message}</span></div>
      <button className="button button-quiet" type="button" onClick={onRetry}><RotateCw size={14} />Retry</button>
    </div>
  );
}

export function EmptyState({ title, message }: { title: string; message: string }) {
  return <div className="state-panel empty-state"><span className="empty-mark" /><strong>{title}</strong><span>{message}</span></div>;
}

export function DataNotice({ children, tone = 'neutral' }: { children: ReactNode; tone?: 'neutral' | 'demo' | 'warning' }) {
  return <div className={`data-notice data-notice-${tone}`}>{children}</div>;
}

export function SectionTitle({ title, meta, action }: { title: string; meta?: string; action?: ReactNode }) {
  return <div className="section-title"><div><h2>{title}</h2>{meta && <span>{meta}</span>}</div>{action}</div>;
}

export function StatusBadge({ status }: { status: string | null | undefined }) {
  if (!status) return <span className="status-badge status-muted">N/A</span>;
  const tone = status.includes('STRONG') ? 'strong' : status === 'WATCHLIST' ? 'watch' : status === 'NO_SIGNAL' ? 'quiet' : status.includes('INSUFFICIENT') ? 'insufficient' : status.includes('EXPIRY') ? 'expiry' : 'quiet';
  const label = status.replaceAll('_', ' ');
  return <span className={`status-badge status-${tone}`}>{label}</span>;
}

export function DirectionBadge({ direction }: { direction: string | null | undefined }) {
  const tone = direction === 'CHEAP' ? 'cheap' : direction === 'EXPENSIVE' ? 'expensive' : 'neutral';
  return <span className={`direction-badge direction-${tone}`}>{direction ?? 'NEUTRAL'}</span>;
}
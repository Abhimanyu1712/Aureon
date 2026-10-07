import type { ReactNode } from 'react';

export function MetricTile({ label, value, note, tone = 'default', icon }: { label: string; value: string; note?: string; tone?: 'default' | 'positive' | 'negative' | 'muted'; icon?: ReactNode }) {
  return (
    <div className={`metric-tile metric-${tone}`}>
      <div className="metric-head"><span>{label}</span>{icon && <span className="metric-icon">{icon}</span>}</div>
      <strong>{value}</strong>
      {note && <small>{note}</small>}
    </div>
  );
}
import { useId } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { BenchmarkRecord, EquityRecord, NormalizedRecord, RelativeValueRecord } from '../lib/api';
import { compactContract, formatCurrency, formatNumber, formatPercent, formatShortDate, numericValue } from '../lib/format';
import { EmptyState } from './States';

const SERIES_COLORS = ['#d6b46d', '#79b7a9', '#d68578', '#96a9c0', '#c5a1cb', '#91b878', '#d48d4d', '#8ab9c9'];

function ChartFrame({ children, className = '', height }: { children: React.ReactNode; className?: string; height?: number }) {
  return <div className={`chart-frame ${className}`} style={height ? { height } : undefined}><ResponsiveContainer width="100%" height="100%">{children}</ResponsiveContainer></div>;
}

const axisProps = { tick: { fill: '#899491', fontSize: 11 }, axisLine: { stroke: '#303837' }, tickLine: false };
const tooltipProps = { contentStyle: { background: '#1b2120', border: '1px solid #39413e', borderRadius: 4, color: '#e7ebe7', fontSize: 12 }, itemStyle: { color: '#e7ebe7' }, labelStyle: { color: '#aeb8b3', marginBottom: 5 } };

export function NormalizedComparisonChart({ rows, height = 310 }: { rows: NormalizedRecord[]; height?: number }) {
  const gradientId = useId().replaceAll(':', '');
  const contractIds = [...new Set(rows.map((row) => row.contract_id))].sort();
  if (!rows.length) return <EmptyState title="No normalized observations" message="Normalized contract prices will appear when analytics data is available." />;
  const dates = [...new Set(rows.map((row) => row.trade_date))].sort();
  const series = contractIds.map((contractId, index) => ({ key: `series${index}`, contractId, label: compactContract(contractId), color: SERIES_COLORS[index % SERIES_COLORS.length] }));
  const chartData = dates.map((tradingDate) => {
    const point: Record<string, string | number | null> = { date: tradingDate };
    rows.filter((row) => row.trade_date === tradingDate).forEach((row) => {
      const index = contractIds.indexOf(row.contract_id);
      point[`series${index}`] = numericValue(row.purity_adjusted_price_per_gram);
    });
    return point;
  });
  return (
    <ChartFrame className="normalized-chart" height={height}>
      <LineChart data={chartData} margin={{ top: 12, right: 14, left: 2, bottom: 2 }}>
        <defs><linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#d6b46d" stopOpacity={0.12} /><stop offset="100%" stopColor="#d6b46d" stopOpacity={0} /></linearGradient></defs>
        <CartesianGrid stroke="#29312f" strokeDasharray="3 6" vertical={false} />
        <XAxis dataKey="date" tickFormatter={formatShortDate} minTickGap={28} {...axisProps} />
        <YAxis tickFormatter={(value) => `₹${Math.round(Number(value))}`} width={66} domain={['auto', 'auto']} {...axisProps} />
        <Tooltip {...tooltipProps} labelFormatter={(value) => formatShortDate(String(value))} formatter={(value) => [formatCurrency(value as number | string), '999-fineness ₹/gram']} />
        <Legend verticalAlign="bottom" align="left" height={38} iconType="plainline" wrapperStyle={{ color: '#aab4af', fontSize: 11, paddingTop: 10 }} />
        {series.map((item) => <Line key={item.key} type="monotone" dataKey={item.key} name={item.label} stroke={item.color} strokeWidth={2} dot={{ r: 2.5, strokeWidth: 0, fill: item.color }} activeDot={{ r: 4 }} connectNulls={false} />)}
      </LineChart>
    </ChartFrame>
  );
}

export function RelativePairChart({ rows }: { rows: RelativeValueRecord[] }) {
  if (!rows.length) return <EmptyState title="No contract observations" message="Select a contract with normalized and peer-reference data." />;
  const chartData = [...rows].sort((a, b) => a.trade_date.localeCompare(b.trade_date)).map((row) => ({ ...row, dateLabel: formatShortDate(row.trade_date), normalized: numericValue(row.normalized_price), peer: numericValue(row.peer_reference) }));
  return (
    <ChartFrame className="detail-chart">
      <LineChart data={chartData} margin={{ top: 10, right: 12, left: 0, bottom: 2 }}>
        <CartesianGrid stroke="#29312f" strokeDasharray="3 6" vertical={false} />
        <XAxis dataKey="dateLabel" minTickGap={22} {...axisProps} />
        <YAxis tickFormatter={(value) => `₹${Math.round(Number(value))}`} width={64} domain={['auto', 'auto']} {...axisProps} />
        <Tooltip {...tooltipProps} formatter={(value, name) => [formatCurrency(value as number | string), name === 'normalized' ? 'Purity-adjusted price' : 'Peer reference']} />
        <Legend verticalAlign="bottom" align="left" height={30} iconType="plainline" wrapperStyle={{ color: '#aab4af', fontSize: 11 }} />
        <Line type="monotone" dataKey="normalized" name="Contract · ₹/g" stroke="#d6b46d" strokeWidth={2} dot={{ r: 3, fill: '#d6b46d' }} connectNulls={false} />
        <Line type="monotone" dataKey="peer" name="Peer reference · ₹/g" stroke="#79b7a9" strokeWidth={2} strokeDasharray="5 4" dot={false} connectNulls={false} />
      </LineChart>
    </ChartFrame>
  );
}

export function ZScoreChart({ rows }: { rows: RelativeValueRecord[] }) {
  const points = [...rows].filter((row) => numericValue(row.z_score) !== null).sort((a, b) => a.trade_date.localeCompare(b.trade_date));
  if (points.length < 2) return <EmptyState title="Not enough historical observations" message="A z-score history needs at least two dated observations for this exact contract." />;
  const chartData = points.map((row) => ({ dateLabel: formatShortDate(row.trade_date), z: numericValue(row.z_score) }));
  return (
    <ChartFrame className="z-chart">
      <LineChart data={chartData} margin={{ top: 10, right: 12, left: 0, bottom: 2 }}>
        <CartesianGrid stroke="#29312f" strokeDasharray="3 6" vertical={false} />
        <XAxis dataKey="dateLabel" {...axisProps} />
        <YAxis width={42} domain={['auto', 'auto']} tickFormatter={(value) => Number(value).toFixed(1)} {...axisProps} />
        <ReferenceLine y={0} stroke="#74807b" />
        <Tooltip {...tooltipProps} formatter={(value) => [formatNumber(value as number), 'Z-score']} />
        <Line type="monotone" dataKey="z" name="Z-score" stroke="#d68578" strokeWidth={2} dot={{ r: 3, fill: '#d68578' }} connectNulls={false} />
      </LineChart>
    </ChartFrame>
  );
}

export function EquityChart({ rows }: { rows: EquityRecord[] }) {
  if (!rows.length) return <EmptyState title="No equity observations" message="Equity points are available after a backtest report is generated." />;
  const data = rows.map((row) => ({ dateLabel: formatShortDate(row.date), date: row.date, equity: numericValue(row.ending_equity) }));
  return (
    <ChartFrame className="equity-chart">
      <LineChart data={data} margin={{ top: 14, right: 14, left: 0, bottom: 2 }}>
        <CartesianGrid stroke="#29312f" strokeDasharray="3 6" vertical={false} />
        <XAxis dataKey="dateLabel" minTickGap={26} {...axisProps} />
        <YAxis width={90} tickFormatter={(value) => `₹${new Intl.NumberFormat('en-IN', { notation: 'compact', maximumFractionDigits: 1 }).format(Number(value))}`} domain={['auto', 'auto']} {...axisProps} />
        <Tooltip {...tooltipProps} formatter={(value) => [formatCurrency(value as number | string), 'Strategy equity']} />
        <Line type="monotone" dataKey="equity" name="Strategy equity" stroke="#d6b46d" strokeWidth={2.5} dot={{ r: 3, fill: '#d6b46d' }} connectNulls={false} />
      </LineChart>
    </ChartFrame>
  );
}

export function ReturnComparisonChart({ benchmark }: { benchmark: BenchmarkRecord | null }) {
  const benchmarkReturn = numericValue(benchmark?.benchmark_return ?? null);
  const strategyReturn = numericValue(benchmark?.strategy_return ?? null);
  if (!benchmark || benchmark.status !== 'CALCULATED' || benchmarkReturn === null || strategyReturn === null) {
    return <EmptyState title="Benchmark unavailable" message={benchmark?.reason ?? 'A single exact benchmark contract must cover the full backtest date range.'} />;
  }
  const data = [
    { name: 'Strategy', returnValue: strategyReturn },
    { name: benchmark.symbol, returnValue: benchmarkReturn },
  ];
  return (
    <ChartFrame className="return-chart">
      <BarChart data={data} margin={{ top: 12, right: 12, left: 0, bottom: 2 }}>
        <CartesianGrid stroke="#29312f" strokeDasharray="3 6" vertical={false} />
        <XAxis dataKey="name" {...axisProps} />
        <YAxis width={55} tickFormatter={(value) => `${(Number(value) * 100).toFixed(1)}%`} {...axisProps} />
        <ReferenceLine y={0} stroke="#74807b" />
        <Tooltip {...tooltipProps} formatter={(value) => [formatPercent(value as number), 'Return']} />
        <Bar dataKey="returnValue" name="Return" fill="#79b7a9" radius={[2, 2, 0, 0]} maxBarSize={46} />
      </BarChart>
    </ChartFrame>
  );
}
export type Numeric = number | string | null;
export type SourceType = 'DEMO' | 'REAL';

export type Resource<T> = {
  data: T | null;
  error: string | null;
};

export type ListResponse<T> = {
  status: string;
  data_type: string;
  record_count: number;
  records: T[];
};

export type DataResponse<T> = {
  status: string;
  data_type: string;
  data: T | null;
};

export type HealthResponse = { status: string; message: string };

export type DataStatus = {
  available: boolean;
  data_type: 'DEMO' | 'REAL/HISTORICAL' | 'MIXED' | 'NONE';
  available_data_types: string[];
  source_files: string[];
  processed_rows: number;
};

export type NormalizedRecord = {
  symbol: string;
  trade_date: string;
  expiry_date: string;
  contract_id: string;
  close: Numeric;
  volume: Numeric;
  open_interest: Numeric;
  normalized_price_per_gram: Numeric;
  purity_adjusted_price_per_gram: Numeric;
  source_type: string;
  source_file: string;
};

export type RelativeValueRecord = {
  symbol: string;
  trade_date: string;
  expiry_date: string;
  contract_id: string;
  normalized_price: Numeric;
  peer_reference: Numeric;
  spread: Numeric;
  rolling_mean: Numeric;
  rolling_std: Numeric;
  z_score: Numeric;
  peer_count: number;
  analytics_status: string;
  source_type: string;
  source_file: string;
};

export type SignalRecord = {
  symbol: string;
  trade_date: string;
  expiry_date: string;
  contract_id: string;
  normalized_price: Numeric;
  peer_reference: Numeric;
  spread: Numeric;
  z_score: Numeric;
  peer_count: number;
  volume: Numeric;
  open_interest: Numeric;
  days_to_expiry: number;
  rolling_history_count: number;
  relative_direction: 'CHEAP' | 'EXPENSIVE' | 'NEUTRAL';
  signal_status: string;
  cost_filter_status: string;
  analytics_status: string;
  source_type: string;
  source_file: string;
  explanation: string;
};

export type BacktestConfig = {
  entry_z: Numeric;
  exit_z: Numeric;
  max_holding_days: number;
  minimum_volume: Numeric;
  minimum_open_interest: Numeric;
  minimum_days_to_expiry: number;
  estimated_cost_rate_per_side: Numeric;
  initial_capital: Numeric;
  benchmark_symbol: string;
};

export type BacktestSummary = {
  dataset_type: string;
  dataset_start: string | null;
  dataset_end: string | null;
  initial_capital: Numeric;
  configuration: BacktestConfig;
  trade_count: number;
  completed_trades: number;
  win_rate: Numeric;
  gross_pnl: Numeric;
  transaction_cost: Numeric;
  net_pnl: Numeric;
  max_drawdown: Numeric;
  sharpe: { value: Numeric; status: string; observations?: number; minimum_observations?: number; reason?: string };
  benchmark_return: Numeric;
  strategy_return: Numeric;
  relative_outperformance: Numeric;
  data_quality_notes: string[];
};

export type TradeLeg = {
  symbol: string;
  contract_id: string;
  expiry_date: string;
  position_side: 'LONG' | 'SHORT';
  contract_equivalents: Numeric;
  contract_size_grams: Numeric;
  entry_price_per_gram: Numeric;
  exit_price_per_gram: Numeric;
  exit_price_date: string | null;
  entry_notional: Numeric;
  exit_notional: Numeric;
  gross_pnl: Numeric;
  entry_cost: Numeric;
  exit_cost: Numeric;
};

export type TradeRecord = {
  trade_id: string;
  target_symbol: string;
  target_expiry_date: string;
  target_contract_id: string;
  peer_symbols: string[];
  peer_contract_ids: string[];
  entry_signal_date: string;
  entry_date: string;
  exit_date: string | null;
  entry_z_score: Numeric;
  exit_z_score: Numeric;
  direction: 'CHEAP' | 'EXPENSIVE';
  target_entry_price: Numeric;
  target_exit_price: Numeric;
  peer_entry_value: Numeric;
  peer_exit_value: Numeric;
  target_units: Numeric;
  peer_units: Numeric[];
  days_held: number | null;
  exit_reason: string | null;
  target_leg_gross_pnl: Numeric;
  peer_leg_gross_pnl: Numeric;
  gross_pnl: Numeric;
  transaction_cost: Numeric;
  net_pnl: Numeric;
  return_on_capital: Numeric;
  status: string;
  source_type: string;
  source_file: string;
  legs: TradeLeg[];
};

export type EquityRecord = {
  date: string;
  starting_equity: Numeric;
  daily_pnl: Numeric;
  daily_cost: Numeric;
  daily_net_pnl: Numeric;
  ending_equity: Numeric;
};

export type BenchmarkRecord = {
  symbol: string;
  contract_id: string | null;
  start_date: string | null;
  end_date: string | null;
  benchmark_return: Numeric;
  strategy_return: Numeric;
  relative_outperformance: Numeric;
  status: string;
  assumption?: string;
  reason?: string;
};

export type BacktestReport = BacktestSummary & {
  benchmark: BenchmarkRecord;
  metrics: Record<string, unknown>;
  rejected_entry_count: number;
  data_quality_notes: string[];
};

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api';

async function requestJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) {
    throw new Error(`Request failed (${response.status})`);
  }
  return (await response.json()) as T;
}

const withSource = (path: string, sourceType: SourceType) =>
  `${path}?source_type=${sourceType}`;

export const api = {
  getHealth: () => requestJson<HealthResponse>(`/health`),
  getDataStatus: () => requestJson<DataStatus>(`/data/status`),
  getNormalized: (sourceType: SourceType = 'DEMO') =>
    requestJson<ListResponse<NormalizedRecord>>(withSource('/analytics/normalized', sourceType)),
  getRelativeValue: (sourceType: SourceType = 'DEMO') =>
    requestJson<ListResponse<RelativeValueRecord>>(withSource('/analytics/relative-value', sourceType)),
  getSignals: (sourceType: SourceType = 'DEMO') =>
    requestJson<ListResponse<SignalRecord>>(withSource('/analytics/signals', sourceType)),
  getBacktestSummary: (sourceType: SourceType = 'DEMO') =>
    requestJson<DataResponse<BacktestSummary>>(withSource('/backtest/summary', sourceType)),
  getBacktestTrades: (sourceType: SourceType = 'DEMO') =>
    requestJson<DataResponse<TradeRecord[]>>(withSource('/backtest/trades', sourceType)),
  getBacktestEquity: (sourceType: SourceType = 'DEMO') =>
    requestJson<DataResponse<EquityRecord[]>>(withSource('/backtest/equity', sourceType)),
  getBacktestBenchmark: (sourceType: SourceType = 'DEMO') =>
    requestJson<DataResponse<BenchmarkRecord>>(withSource('/backtest/benchmark', sourceType)),
  getBacktestReport: (sourceType: SourceType = 'DEMO') =>
    requestJson<DataResponse<BacktestReport>>(withSource('/backtest/report', sourceType)),
};
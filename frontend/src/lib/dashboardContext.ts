import { createContext } from 'react';
import type { DataResponse, DataStatus, HealthResponse, ListResponse, NormalizedRecord, RelativeValueRecord, Resource, SignalRecord, BacktestSummary, TradeRecord, EquityRecord, BenchmarkRecord, BacktestReport } from './api';

export type DashboardSnapshot = {
  reportDate: string;
  health: Resource<HealthResponse>;
  dataStatus: Resource<DataStatus>;
  normalized: Resource<ListResponse<NormalizedRecord>>;
  relativeValue: Resource<ListResponse<RelativeValueRecord>>;
  signals: Resource<ListResponse<SignalRecord>>;
  backtestSummary: Resource<DataResponse<BacktestSummary>>;
  backtestTrades: Resource<DataResponse<TradeRecord[]>>;
  backtestEquity: Resource<DataResponse<EquityRecord[]>>;
  backtestBenchmark: Resource<DataResponse<BenchmarkRecord>>;
  backtestReport: Resource<DataResponse<BacktestReport>>;
};

export type DashboardContextValue = {
  snapshot: DashboardSnapshot | null;
  loading: boolean;
  refreshing: boolean;
  refresh: () => void;
};

export const DashboardContext = createContext<DashboardContextValue | null>(null);
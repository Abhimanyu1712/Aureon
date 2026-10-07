import { startTransition, useEffect, useState, type ReactNode } from 'react';
import { api, type Resource } from './api';
import { DashboardContext, type DashboardSnapshot } from './dashboardContext';

async function resource<T>(load: () => Promise<T>): Promise<Resource<T>> {
  try {
    return { data: await load(), error: null };
  } catch (error) {
    return {
      data: null,
      error: error instanceof Error ? error.message : 'Backend unavailable',
    };
  }
}

export function DashboardProvider({ children }: { children: ReactNode }) {
  const [snapshot, setSnapshot] = useState<DashboardSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    let current = true;

    Promise.all([
      resource(api.getHealth),
      resource(api.getDataStatus),
      resource(() => api.getNormalized()),
      resource(() => api.getRelativeValue()),
      resource(() => api.getSignals()),
      resource(() => api.getBacktestSummary()),
      resource(() => api.getBacktestTrades()),
      resource(() => api.getBacktestEquity()),
      resource(() => api.getBacktestBenchmark()),
      resource(() => api.getBacktestReport()),
    ]).then(([health, dataStatus, normalized, relativeValue, signals, backtestSummary, backtestTrades, backtestEquity, backtestBenchmark, backtestReport]) => {
      if (!current) return;
      startTransition(() => {
        setSnapshot({ health, dataStatus, normalized, relativeValue, signals, backtestSummary, backtestTrades, backtestEquity, backtestBenchmark, backtestReport });
        setLoading(false);
        setRefreshing(false);
      });
    });

    return () => { current = false; };
  }, [revision]);

  const refresh = () => {
    setRefreshing(true);
    setRevision((value) => value + 1);
  };

  return <DashboardContext.Provider value={{ snapshot, loading, refreshing, refresh }}>{children}</DashboardContext.Provider>;
}
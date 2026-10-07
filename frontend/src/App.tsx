import { lazy, Suspense } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AppShell } from './components/AppShell';
import { DashboardProvider } from './lib/dashboard';

const OverviewPage = lazy(() => import('./pages/OverviewPage').then((module) => ({ default: module.OverviewPage })));
const RelativeValuePage = lazy(() => import('./pages/RelativeValuePage').then((module) => ({ default: module.RelativeValuePage })));
const ContractsPage = lazy(() => import('./pages/ContractsPage').then((module) => ({ default: module.ContractsPage })));
const SignalsPage = lazy(() => import('./pages/SignalsPage').then((module) => ({ default: module.SignalsPage })));
const BacktestPage = lazy(() => import('./pages/BacktestPage').then((module) => ({ default: module.BacktestPage })));
const MethodologyPage = lazy(() => import('./pages/MethodologyPage').then((module) => ({ default: module.MethodologyPage })));

function RouteLoading() {
  return <div className="route-loading"><span className="route-loading-mark" /><span>Loading research view</span></div>;
}

function App() {
  return (
    <BrowserRouter>
      <DashboardProvider>
        <Suspense fallback={<RouteLoading />}>
          <Routes>
            <Route element={<AppShell />}>
              <Route index element={<OverviewPage />} />
              <Route path="relative-value" element={<RelativeValuePage />} />
              <Route path="contracts" element={<ContractsPage />} />
              <Route path="signals" element={<SignalsPage />} />
              <Route path="backtest" element={<BacktestPage />} />
              <Route path="methodology" element={<MethodologyPage />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Routes>
        </Suspense>
      </DashboardProvider>
    </BrowserRouter>
  );
}

export default App;

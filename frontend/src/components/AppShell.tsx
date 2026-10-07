import { useState } from 'react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';
import { Activity, BarChart3, BookOpen, Boxes, FlaskConical, Menu, RefreshCw, Radio, X } from 'lucide-react';
import { useDashboard } from '../lib/useDashboard';

const navigation = [
  { label: 'Overview', path: '/', icon: Activity, end: true },
  { label: 'Relative Value', path: '/relative-value', icon: BarChart3 },
  { label: 'Contracts', path: '/contracts', icon: Boxes },
  { label: 'Signals', path: '/signals', icon: Radio },
  { label: 'Backtest Lab', path: '/backtest', icon: FlaskConical },
  { label: 'Methodology', path: '/methodology', icon: BookOpen },
];

function currentLabel(pathname: string) {
  return navigation.find((item) => item.path === pathname)?.label ?? navigation.find((item) => item.path !== '/' && pathname.startsWith(item.path))?.label ?? 'Overview';
}

export function AppShell() {
  const { snapshot, loading, refreshing, refresh } = useDashboard();
  const { pathname } = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);
  const mode = snapshot?.dataStatus.data?.data_type;
  const backendDown = !loading && (!snapshot?.health.data || snapshot.health.data.status !== 'ok');
  const dataLabel = mode === 'DEMO' || mode === 'MIXED' ? 'DEMO DATA' : mode === 'REAL/HISTORICAL' ? 'HISTORICAL' : mode === 'NONE' ? 'NO DATA' : 'CHECKING';

  return (
    <div className="app-frame">
      {mobileOpen && <button className="mobile-scrim" aria-label="Close navigation" onClick={() => setMobileOpen(false)} />}
      <aside className={`sidebar ${mobileOpen ? 'sidebar-open' : ''}`}>
        <div className="brand-lockup">
          <div className="brand-mark"><span /><span /><span /></div>
          <div><strong>AUREON</strong><small>COMMODITY INTELLIGENCE</small></div>
          <button className="icon-button sidebar-close" aria-label="Close navigation" onClick={() => setMobileOpen(false)}><X size={17} /></button>
        </div>
        <div className="sidebar-label">RESEARCH</div>
        <nav className="primary-nav" aria-label="Main navigation">
          {navigation.map(({ label, path, icon: Icon, end }) => (
            <NavLink key={path} to={path} end={end} onClick={() => setMobileOpen(false)} className={({ isActive }) => `nav-link ${isActive ? 'nav-link-active' : ''}`}>
              <Icon size={17} strokeWidth={1.8} /><span>{label}</span>{label === 'Signals' && snapshot?.signals.data && <small>{snapshot.signals.data.record_count}</small>}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="sidebar-source-label">DATA PROVENANCE</div>
          <div className={`sidebar-mode ${dataLabel.includes('DEMO') ? 'sidebar-mode-demo' : ''}`}><span className="mode-indicator" /><span>{dataLabel}</span></div>
          <p>MCX daily bhavcopy<br />Normalized · compared · simulated</p>
          <div className="sidebar-version"><span>STAGE 06</span><span>RESEARCH BUILD</span></div>
        </div>
      </aside>

      <div className="workspace">
        <header className="topbar">
          <button className="icon-button menu-trigger" aria-label="Open navigation" onClick={() => setMobileOpen(true)}><Menu size={18} /></button>
          <div className="breadcrumb"><span>Workspace</span><span className="breadcrumb-divider">/</span><strong>{currentLabel(pathname)}</strong></div>
          <div className="topbar-right">
            <div className={`connection-state ${backendDown ? 'connection-down' : ''}`}><span className="connection-dot" />{backendDown ? 'Backend unavailable' : loading ? 'Connecting' : 'API connected'}</div>
            <button className={`icon-button refresh-button ${refreshing ? 'refreshing' : ''}`} aria-label="Refresh dashboard data" title="Refresh data" onClick={refresh}><RefreshCw size={16} /></button>
          </div>
        </header>

        {backendDown && <div className="global-error"><span>Backend unavailable</span><span>Start the Aureon API to load market intelligence.</span><button type="button" onClick={refresh}>Retry</button></div>}
        <main className="main-content"><Outlet /></main>
        <footer className="app-footer"><span>AUREON · RESEARCH TERMINAL</span><span>Analytical observations only · Not investment advice</span></footer>
      </div>
    </div>
  );
}
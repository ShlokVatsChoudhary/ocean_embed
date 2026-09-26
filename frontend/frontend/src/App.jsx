import { useEffect, useState } from 'react';
import Hero from './components/Hero';
import ExploreView from './views/ExploreView';
import AnalyzeView from './views/AnalyzeView';
import ValidateView from './views/ValidateView';
import { AlertBanner } from './components/controls';
import { getAnomalyAlerts, MODEL_VERSION, LAST_UPDATE, prettyDate, isBackendEnabled, getApiBase } from './api/oceanembed';

export default function App() {
  const [showHero, setShowHero] = useState(true);
  const [view, setView] = useState('explore');
  const [date, setDate] = useState('2020-01-15');
  const [depth, setDepth] = useState(100);
  const [selected, setSelected] = useState({ lat: 12.0, lon: 68.0 });
  const [bannerOff, setBannerOff] = useState(false);
  const [alerts, setAlerts] = useState([]);

  useEffect(() => {
    let dead = false;
    getAnomalyAlerts().then((a) => { if (!dead) setAlerts(a); }).catch(() => {});
    return () => { dead = true; };
  }, []);

  const jumpToAlert = (a) => {
    setDate(a.date); setDepth(a.depth);
    setSelected({ lat: a.lat, lon: a.lon });
    setView('explore');
  };

  if (showHero) {
    return <Hero onEnter={(v) => { setView(v); setShowHero(false); }} />;
  }

  return (
    <div className="app">
      <header className="topbar">
        <button className="brand brand-link" onClick={() => setShowHero(true)} aria-label="Back to front page">
          <span className="brand-icon" aria-hidden="true">≋</span>
          <span className="brand-name">OceanEmbed</span>
          <span className="brand-sub">subsurface temperature explorer</span>
        </button>
        <nav className="nav">
          {['explore', 'analyze', 'validate'].map((v) => (
            <button key={v} className={view === v ? 'nav-pill active' : 'nav-pill'} onClick={() => setView(v)}>
              {v[0].toUpperCase() + v.slice(1)}
            </button>
          ))}
        </nav>
      </header>
      {!bannerOff && (
        <AlertBanner alerts={alerts} onJump={jumpToAlert} onDismiss={() => setBannerOff(true)} />
      )}
      <main className="content">
        {view === 'explore' && <ExploreView date={date} setDate={setDate} depth={depth} setDepth={setDepth} selected={selected} setSelected={setSelected} />}
        {view === 'analyze' && <AnalyzeView date={date} setDate={setDate} depth={depth} setDepth={setDepth} selected={selected} setSelected={setSelected} />}
        {view === 'validate' && <ValidateView date={date} setDate={setDate} depth={depth} setDepth={setDepth} selected={selected} setSelected={setSelected} />}
      </main>
      <footer className="statusbar">
        <span>Last data update: {prettyDate(LAST_UPDATE)}</span>
        <span>Model: {MODEL_VERSION}</span>
        <span>Data: {isBackendEnabled() ? `backend ${getApiBase()}` : 'local mock'}</span>
        <span>Domain: 5°N–30°N, 45°E–105°E · daily · 0.25° · depths 0–1000 m</span>
      </footer>
    </div>
  );
}

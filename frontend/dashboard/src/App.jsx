import { useEffect, useState } from 'react';
import Hero from './components/Hero';
import AltHero from './components/AltHero';
import ExploreView from './views/ExploreView';
import AnalyzeView from './views/AnalyzeView';
import ValidateView from './views/ValidateView';
import { AlertBanner } from './components/controls';
import { getAnomalyAlerts, getMetadata, MODEL_VERSION, prettyDate, getSupportedDates } from './api/oceanembed';
import './alt.css';

// The alternative "Instrument" look is opt-in via ?ui=alt so the default
// experience is byte-for-byte what it always was. src/alt.css does all the
// work; this flag only flips a class on <body> and picks the matching hero.
const PARAMS = typeof window !== 'undefined'
  ? new URLSearchParams(window.location.search)
  : new URLSearchParams();
const ALT = PARAMS.get('ui') === 'alt';
// ?view=explore|analyze|validate deep-links straight into the dashboard.
const START_VIEW = ['explore', 'analyze', 'validate'].includes(PARAMS.get('view'))
  ? PARAMS.get('view')
  : null;

export default function App() {
  const [showHero, setShowHero] = useState(!START_VIEW);
  const [view, setView] = useState(START_VIEW || 'explore');
  const [date, setDate] = useState('2020-01-01');
  const [depth, setDepth] = useState(100);
  const [selected, setSelected] = useState({ lat: 12.0, lon: 68.0 });
  const [bannerOff, setBannerOff] = useState(false);
  const [alerts, setAlerts] = useState([]);
  const [meta, setMeta] = useState(null);
  const [dates, setDates] = useState([]);

  useEffect(() => {
    document.body.classList.toggle('alt-theme', ALT);
    return () => document.body.classList.remove('alt-theme');
  }, []);

  useEffect(() => {
    let dead = false;
    getAnomalyAlerts().then((a) => { if (!dead) setAlerts(a); }).catch(() => {});
    getMetadata().then((m) => { if (!dead) setMeta(m); }).catch(() => {});
    getSupportedDates().then((d) => {
      if (dead) return;
      setDates(d);
      // Open on a date the backend actually has rather than a hard-coded one.
      if (d.length && !d.includes(date)) setDate(d[0]);
    }).catch(() => {});
    return () => { dead = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const jumpToAlert = (a) => {
    setDate(a.date); setDepth(a.depth);
    setSelected({ lat: a.lat, lon: a.lon });
    setView('explore');
  };

  if (showHero) {
    return ALT
      ? <AltHero onEnter={(v) => { setView(v); setShowHero(false); }} />
      : <Hero onEnter={(v) => { setView(v); setShowHero(false); }} />;
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
        <span>Model dates: {dates.length ? `${prettyDate(dates[0])} – ${prettyDate(dates[dates.length - 1])}` : 'unavailable'}</span>
        <span>Model: {MODEL_VERSION}{meta?.modelParameterCount ? ` · ${meta.modelParameterCount.toLocaleString()} params` : ''}</span>
        <span>Domain: 5°N–30°N · 45°E–105°E</span>
        <span>Resolution: 0.25°</span>
        <span>Depth: 0–1000 m</span>
        <span title={meta?.glorysProvenance || ''}>Reference (GLORYS): {meta?.glorysStatus ?? 'unknown'}</span>
        <span title={meta?.argoProvenance || ''}>Validation (ARGO): {meta?.argoStatus ?? 'unknown'}</span>
        <a className="theme-swap" href={ALT ? './' : './?ui=alt'} title="Switch between the two designs">
          {ALT ? '⇄ Editorial look' : '⇄ Instrument look'}
        </a>
      </footer>
    </div>
  );
}

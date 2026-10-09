// Hero: the front page shown before entering the dashboard. Layout and
// copy mirror the approved "Editorial" concept — serif headline, an
// illustrative vertical-profile chart, and a mono spec strip along the base.
export default function Hero({ onEnter }) {
  return (
    <div className="hero-page">
      <header className="hero-topbar">
        <div className="brand">
          <span className="brand-icon" aria-hidden="true">≋</span>
          <span className="brand-name">OceanEmbed</span>
        </div>
        <nav className="hero-nav">
          <button className="hero-nav-link" onClick={() => onEnter('explore')}>Explore</button>
          <button className="hero-nav-link" onClick={() => onEnter('analyze')}>Analyze</button>
          <button className="hero-nav-link" onClick={() => onEnter('validate')}>Validate</button>
        </nav>
      </header>

      <div className="hero-content">
        <div className="hero-copy">
          <div className="hero-eyebrow">North Indian Ocean · 2004–2024</div>
          <h1 className="hero-headline">A field guide to the water beneath the surface</h1>
          <p className="hero-sub">
            OceanEmbed reconstructs subsurface temperature from satellite and float observations,
            then checks its own reasoning against GLORYS reanalysis and ARGO profiles at every depth.
          </p>
          <div className="hero-actions">
            <button className="btn" onClick={() => onEnter('explore')}>Open the explorer</button>
            <button className="hero-link" onClick={() => onEnter('validate')}>Read the methodology</button>
          </div>
        </div>

        <div className="hero-visual">
          <div className="hero-chart-card">
            <div className="hero-chart-caption">Vertical temperature profile — illustrative</div>
            <svg viewBox="0 0 240 340" width="100%" height="260" role="img" aria-label="Illustrative vertical temperature profile">
              <line x1="30" y1="10" x2="30" y2="310" stroke="var(--rule)" />
              <line x1="30" y1="310" x2="230" y2="310" stroke="var(--rule)" />
              <path d="M 120 10 C 128 70, 132 110, 150 150 S 200 230, 210 300" fill="none" stroke="var(--ink)" strokeWidth="2.5" />
              <path d="M 105 10 C 112 80, 118 130, 145 175 S 195 250, 205 300" fill="none" stroke="var(--amber-border)" strokeWidth="1.6" strokeDasharray="5 4" />
              <text x="8" y="16" fontFamily="IBM Plex Mono" fontSize="10" fill="var(--text-faint)">0 m</text>
              <text x="2" y="305" fontFamily="IBM Plex Mono" fontSize="10" fill="var(--text-faint)">1000 m</text>
            </svg>
            <div className="hero-legend">
              <span className="hero-legend-item"><span className="hero-swatch" style={{ background: 'var(--ink)' }} />OceanEmbed</span>
              <span className="hero-legend-item"><span className="hero-swatch" style={{ background: 'var(--amber-border)' }} />GLORYS</span>
            </div>
          </div>
        </div>
      </div>

      <footer className="hero-footer">
        <span>5°N–30°N, 45°E–105°E</span>
        <span className="hero-footer-rule">0.25° grid</span>
        <span>0–1000 m</span>
      </footer>
    </div>
  );
}

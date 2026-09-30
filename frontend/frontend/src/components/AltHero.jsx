// AltHero: the front page for the alternative "Instrument" look.
//
// Same job as Hero.jsx — explain the project and route into the dashboard —
// but built for the dark theme: luminous profile plot, an inline spec strip,
// and the three numbers a reviewer actually wants. Uses only the theme
// tokens, so it needs no new values of its own.

const DEPTH_TICKS = [0, 100, 200, 300, 500, 700, 1000];

export default function AltHero({ onEnter }) {
  return (
    <div className="hero-page">
      <header className="hero-topbar">
        <div className="brand">
          <span className="brand-icon" aria-hidden="true">≋</span>
          <span className="brand-name">OceanEmbed</span>
          <span className="brand-sub">subsurface temperature · NIO</span>
        </div>
        <nav className="hero-nav">
          <button className="hero-nav-link" onClick={() => onEnter('explore')}>Explore</button>
          <button className="hero-nav-link" onClick={() => onEnter('analyze')}>Analyze</button>
          <button className="hero-nav-link" onClick={() => onEnter('validate')}>Validate</button>
        </nav>
      </header>

      <div className="hero-content">
        <div className="hero-copy">
          <div className="hero-eyebrow">North Indian Ocean · 0–1000 m · daily</div>
          <h1 className="hero-headline">
            The ocean keeps its heat <em>below</em> the surface
          </h1>
          <p className="hero-sub">
            A satellite-only neural network reconstructs the full temperature column —
            the reservoir that decides whether a Bay of Bengal depression becomes a
            super-cyclone — then scores itself against GLORYS reanalysis and ARGO
            floats at every depth.
          </p>

          <div className="hero-actions">
            <button className="btn" onClick={() => onEnter('explore')}>Open the explorer</button>
            <button className="hero-link" onClick={() => onEnter('validate')}>How it is validated</button>
          </div>

          <div className="alt-rule" />

          <div className="alt-stats">
            <div className="alt-stat"><b>0.25°</b><span>Daily grid</span></div>
            <div className="alt-stat"><b>15</b><span>Depth levels, 0–1000 m</span></div>
            <div className="alt-stat"><b>1.64 M</b><span>Trained parameters</span></div>
          </div>
        </div>

        <div className="hero-visual">
          <div className="hero-chart-card">
            <div className="hero-chart-caption">Temperature vs depth · illustrative</div>
            <svg
              viewBox="0 0 260 340"
              width="100%"
              height="286"
              role="img"
              aria-label="Illustrative vertical temperature profile"
              style={{ display: 'block' }}
            >
              <defs>
                <linearGradient id="altFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="var(--ink)" stopOpacity="0.30" />
                  <stop offset="100%" stopColor="var(--ink)" stopOpacity="0.02" />
                </linearGradient>
                <linearGradient id="altGlow" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="var(--ink)" stopOpacity="0.9" />
                  <stop offset="100%" stopColor="var(--ink)" stopOpacity="0.15" />
                </linearGradient>
              </defs>

              {/* depth gridlines + labels */}
              {DEPTH_TICKS.map((d) => {
                const y = 14 + (d / 1000) * 292;
                return (
                  <g key={d}>
                    <line x1="46" y1={y} x2="244" y2={y} stroke="var(--canvas-grid)" strokeWidth="1" />
                    <text
                      x="40" y={y + 3.5} textAnchor="end"
                      fontFamily="var(--font-mono)" fontSize="9.5" fill="var(--text-faint)"
                    >
                      {d}
                    </text>
                  </g>
                );
              })}

              {/* 26 °C isotherm — the cyclone-fuel threshold */}
              <line x1="200" y1="14" x2="200" y2="306" stroke="var(--chart-bias)" strokeWidth="1" strokeDasharray="3 4" opacity="0.55" />
              <text x="204" y="26" fontFamily="var(--font-mono)" fontSize="9" fill="var(--chart-bias)" opacity="0.85">
                26 °C
              </text>

              {/* model column */}
              <path
                d="M 236 14 C 228 46, 214 74, 196 104 C 172 142, 140 176, 120 214 C 104 244, 100 274, 100 300 L 100 306 L 244 306 L 244 14 Z"
                fill="url(#altFill)"
              />
              <path
                d="M 236 14 C 228 46, 214 74, 196 104 C 172 142, 140 176, 120 214 C 104 244, 100 274, 100 300"
                fill="none" stroke="var(--ink)" strokeWidth="2.6" strokeLinecap="round"
              />

              {/* reference column */}
              <path
                d="M 240 14 C 232 52, 220 84, 204 116 C 182 154, 152 186, 134 222 C 120 250, 116 278, 116 302"
                fill="none" stroke="var(--chart-glorys)" strokeWidth="1.5" strokeDasharray="6 4"
                opacity="0.8" strokeLinecap="round"
              />

              {/* the two levels worth calling out */}
              <circle cx="196" cy="104" r="4" fill="var(--ink)" />
              <circle cx="196" cy="104" r="8" fill="none" stroke="var(--ink)" strokeWidth="1" opacity="0.35" />
              <text x="52" y="100" fontFamily="var(--font-mono)" fontSize="9.5" fill="var(--ink)">
                100 m · drawn by the model
              </text>
              <text x="52" y="113" fontFamily="var(--font-mono)" fontSize="9" fill="var(--text-faint)">
                never seen by a satellite
              </text>

              <line x1="46" y1="306" x2="244" y2="306" stroke="var(--rule-strong)" strokeWidth="1" />
              <text x="8" y="306" fontFamily="var(--font-mono)" fontSize="9.5" fill="var(--text-faint)">m</text>
            </svg>

            <div className="hero-legend">
              <span className="hero-legend-item">
                <span className="hero-swatch" style={{ background: 'var(--ink)' }} />OceanEmbed
              </span>
              <span className="hero-legend-item">
                <span className="hero-swatch" style={{ background: 'var(--chart-glorys)' }} />GLORYS reference
              </span>
            </div>
          </div>
        </div>
      </div>

      <footer className="hero-footer">
        <span>5°N–30°N · 45°E–105°E</span>
        <span className="hero-footer-rule">0.25° grid</span>
        <span>0–1000 m</span>
      </footer>
    </div>
  );
}

import { useConsole, fmt } from '../state';
import { STANDARD_DEPTHS, HAZARD_VARIABLES } from '../api/oceanembed';
import { seqStops, CAT_COLOURS, CAT_LABELS } from '../lib/ramp';

// Left rail: every control that changes what the map shows.
export default function Controls() {
  const c = useConsole();
  const isTemp = c.variable === 'temperature';

  // Coverage per depth is derived from the volume already in memory, so this
  // costs no extra request and can never disagree with what the map is showing.
  const tempCoverage = STANDARD_DEPTHS
    .filter((d) => c.volume[d])
    .map((d) => ({ depth: d, share: c.volume[d].stats.validCount / c.volume[d].stats.totalCount }));

  return (
    <aside className="rail">
      <section className="panel">
        <header><h2>Layer</h2></header>
        <div className="body">
          <div className="grp">
            <label>Field</label>
            <div className="stack">
              <button
                className={isTemp ? 'opt on' : 'opt'}
                onClick={() => c.setVariable('temperature')}
              >
                Temperature<span className="tick">●</span>
              </button>
              {HAZARD_VARIABLES.map((v) => (
                <button
                  key={v.id}
                  className={!isTemp && c.activeHazard === v.id ? 'opt on' : 'opt'}
                  onClick={() => { c.setHazardVar(v.id); c.setVariable(v.id); }}
                  title={v.label}
                >
                  {v.id === 'thermocline_depth' ? 'Thermocline depth' : v.label.split(' (')[0]}
                  <span className="tick">●</span>
                </button>
              ))}
            </div>
          </div>

          {isTemp && (
            <div className="grp">
              <label>Depth — {c.depth} m</label>
              <input
                type="range"
                min={0}
                max={STANDARD_DEPTHS.length - 1}
                step={1}
                value={Math.max(0, STANDARD_DEPTHS.indexOf(c.depth))}
                onChange={(e) => c.setDepth(STANDARD_DEPTHS[Number(e.target.value)])}
                aria-label="Depth"
              />
              <div className="chips" style={{ marginTop: 7 }}>
                {[0, 50, 100, 200, 500, 1000].map((d) => (
                  <button key={d} className={c.depth === d ? 'chip on' : 'chip'} onClick={() => c.setDepth(d)}>{d}</button>
                ))}
              </div>
            </div>
          )}

          <div className="grp">
            <label>Display</label>
            <label className="toggle">
              <input type="checkbox" checked={c.compare} onChange={(e) => c.setCompare(e.target.checked)} />
              GLORYS reference on the profile
            </label>
            <label className="toggle" style={{ marginTop: 6 }}>
              <input type="checkbox" checked={c.showCoverage} onChange={(e) => c.setShowCoverage(e.target.checked)} />
              Mark cells with no value
            </label>
          </div>
        </div>
      </section>

      <section className="panel">
        <header><h2>Legend</h2><span className="sub">{isTemp ? '°C' : c.hazardInfo.unit}</span></header>
        <div className="body">
          {c.variable === 'tchp' ? (
            <>
              <div className="legend-cat" style={{ marginTop: 0, flexDirection: 'column', gap: 5 }}>
                {CAT_LABELS.map((l, i) => (
                  <span key={l}><span className="swatch-box" style={{ background: CAT_COLOURS[i] }} />{l}</span>
                ))}
              </div>
              <div className="legend-cap" style={{ marginTop: 8 }}>kJ/cm² over the 0–1000 m column</div>
            </>
          ) : (
            <>
              <div className="legend-bar">
                <span className="end">{isTemp ? 'cold' : 'low'}</span>
                <span className="legend-strip">
                  {(isTemp ? seqStops(28) : seqStops(28)).map((col, i) => <div key={i} style={{ background: col }} />)}
                </span>
                <span className="end r">{isTemp ? 'warm' : 'high'}</span>
              </div>
              <div className="legend-cap">{isTemp ? 'Temperature scale held fixed across depths' : `Scale: ${c.hazardInfo.label}`}</div>
            </>
          )}

          <div className="swatch-list" style={{ marginTop: 12 }}>
            <div className="swatch-row"><span className="swatch-line" style={{ background: 'var(--accent)' }} />OceanEmbed</div>
            <div className="swatch-row"><span className="swatch-line" style={{ background: 'var(--ok)', opacity: 0.9 }} />GLORYS reference</div>
            <div className="swatch-row"><span className="swatch-box" style={{ background: 'var(--warn)', borderRadius: 9 }} />ARGO float position</div>
            <div className="swatch-row"><span className="swatch-box" style={{ background: 'var(--line)' }} />Land / no value</div>
          </div>
        </div>
      </section>

      <section className="panel">
        <header><h2>Coverage</h2><span className="sub">share of grid cells with a value</span></header>
        <div className="body">
          {tempCoverage.length ? (
            <>
              <svg viewBox={`0 0 ${COV_W} ${COV_H}`} width="100%" height={COV_H} role="img" aria-label="Coverage against depth">
                {tempCoverage.map((p, i) => {
                  const x = 4 + (i / Math.max(1, tempCoverage.length - 1)) * (COV_W - 10);
                  const y = COV_H - 6 - p.share * (COV_H - 16);
                  return <circle key={p.depth} cx={x} cy={y} r="2.3" fill="var(--accent)" opacity="0.85" />;
                })}
                <polyline
                  fill="none"
                  stroke="var(--accent)"
                  strokeWidth="1.4"
                  points={tempCoverage.map((p, i) => {
                    const x = 4 + (i / Math.max(1, tempCoverage.length - 1)) * (COV_W - 10);
                    const y = COV_H - 6 - p.share * (COV_H - 16);
                    return `${x},${y}`;
                  }).join(' ')}
                />
                <line x1="4" y1={COV_H - 6} x2={COV_W - 6} y2={COV_H - 6} stroke="var(--line-lit)" strokeWidth="1" />
                <text x="4" y={COV_H - 1} fontSize="8.5" fontFamily="var(--mono)" fill="var(--faint)">0 m</text>
                <text x={COV_W - 6} y={COV_H - 1} textAnchor="end" fontSize="8.5" fontFamily="var(--mono)" fill="var(--faint)">1000 m</text>
              </svg>
              <div className="legend-cap">
                Surface {fmt.pct(tempCoverage[0].share)} → 1000 m {fmt.pct(tempCoverage[tempCoverage.length - 1].share)}.
                Loss with depth is the model's own skill limit, not a plotting choice.
              </div>
            </>
          ) : (
            <div className="empty">Coverage unavailable until the volume loads.</div>
          )}
        </div>
      </section>

      {c.alerts.length > 0 && (
        <section className="panel">
          <header><h2>Model − ARGO watch</h2><span className="sub">{c.alerts.length} flagged</span></header>
          <div className="body">
            <div className="alerts">
              {c.alerts.slice(0, 5).map((a, i) => (
                <button
                  key={`${a.lat}-${a.lon}-${a.depth}-${a.date}-${i}`}
                  className="alert"
                  onClick={() => { c.setDepth(a.depth); c.setSelection({ lat: a.lat, lon: a.lon }); c.setVariable('temperature'); }}
                  title="Move the cursor to this cell"
                >
                  <span className={`dir ${a.direction}`}>{a.direction}</span>
                  <span className="where">{fmt.ll(a.lat, a.lon)} · {a.depth} m</span>
                  <span className="amt">{a.difference > 0 ? '+' : ''}{fmt.num(a.difference, 1)} °C</span>
                </button>
              ))}
            </div>
            <div className="note">
              Largest model-versus-ARGO differences. A diagnostic, not an operational hazard warning.
            </div>
          </div>
        </section>
      )}

      <section className="panel">
        <header><h2>Provenance</h2></header>
        <div className="body">
          <div className="note">
            ARGO floats: <b>{fmt.int(c.floats.length)}</b> positions on {fmt.date(c.date)}.
            ARGO is an independent check and is never used in training.
          </div>
        </div>
      </section>
    </aside>
  );
}

const COV_W = 200;
const COV_H = 62;

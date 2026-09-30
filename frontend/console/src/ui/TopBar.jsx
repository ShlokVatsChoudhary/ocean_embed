import { useConsole, fmt } from '../state';

const WEEK = ['S', 'M', 'T', 'W', 'T', 'F', 'S'];

// Top bar: the day strip is the only navigation, because there is only one screen.
export default function TopBar({ onValidate, onSwitchTheme }) {
  const c = useConsole();
  const idx = c.dates.indexOf(c.date);

  const hazardMetric = c.hazardSummary?.metrics?.find((m) => m.variable === 'tchp');
  const temp = c.volume[c.depth];

  return (
    <header className="topbar">
      <div className="mark">
        <span className="mark-glyph" aria-hidden="true">≋</span>
        <span className="mark-name">OceanEmbed</span>
        <span className="mark-tag">Console</span>
      </div>

      <div className="dayline" role="group" aria-label="Model day">
        <button className="day" onClick={() => c.stepDay(-1)} disabled={idx <= 0} aria-label="Previous day">◀</button>
        {c.dates.map((d) => (
          <button
            key={d}
            className={d === c.date ? 'day on' : 'day'}
            onClick={() => c.setDate(d)}
            title={fmt.date(d)}
          >
            {WEEK[new Date(`${d}T00:00:00`).getDay()]} {d.slice(8)}
          </button>
        ))}
        <button className="day" onClick={() => c.stepDay(1)} disabled={idx < 0 || idx >= c.dates.length - 1} aria-label="Next day">▶</button>
      </div>

      <div className="grow" />

      {temp && (
        <span className="pill" title="Cells with a finite value at the current depth">
          coverage <b>{fmt.pct(temp.stats.validCount / temp.stats.totalCount)}</b>
        </span>
      )}
      {hazardMetric && (
        <span className="pill" title="Median cyclone heat potential over the served cells">
          median TCHP <b>{fmt.num(hazardMetric.median, 1)}</b> kJ/cm²
        </span>
      )}

      <button className="ghost" onClick={onValidate}>Validation</button>
      <button className="ghost" onClick={onSwitchTheme} title="Back to the original interface">⇄ Original</button>
    </header>
  );
}

// Bottom bar: provenance, not decoration. Every claim links to its source string.
export function StatusBar() {
  const c = useConsole();
  const m = c.meta;
  return (
    <footer className="statusbar">
      <span>Model <b>{fmt.version}</b>{m?.modelParameterCount ? <> · <b>{fmt.int(m.modelParameterCount)}</b> params</> : null}</span>
      <span>Days <b>{c.dates.length ? `${c.dates[0]} → ${c.dates[c.dates.length - 1]}` : 'unavailable'}</b></span>
      <span>Grid <b>0.25°</b> · 101 × 241 · 15 levels 0–1000 m</span>
      <span title={m?.glorysProvenance || ''}>Reference (GLORYS) <b>{m?.glorysStatus ?? 'unknown'}</b></span>
      <span title={m?.argoProvenance || ''}>Independent (ARGO) <b>{m?.argoStatus ?? 'unavailable'}</b></span>
      {c.argoTime?.argoDate && (
        <span>ARGO matched <b>{c.argoTime.argoDate}</b> ({c.argoTime.timeOffsetDays > 0 ? '+' : ''}{c.argoTime.timeOffsetDays} d)</span>
      )}
      <span style={{ marginLeft: 'auto', borderRight: 'none' }}>
        <b>ARGO is evaluation only</b> — never a training input
      </span>
    </footer>
  );
}

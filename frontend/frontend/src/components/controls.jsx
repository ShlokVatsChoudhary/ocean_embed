import { STANDARD_DEPTHS } from '../api/oceanembed';

export function DepthSlider({ depth, onChange }) {
  const idx = STANDARD_DEPTHS.indexOf(depth);
  return (
    <div className="ctl-row">
      <label>Depth</label>
      <input
        type="range" min={0} max={STANDARD_DEPTHS.length - 1} step={1}
        value={idx >= 0 ? idx : 0}
        onChange={(e) => onChange(STANDARD_DEPTHS[Number(e.target.value)])}
        style={{ flex: 1 }}
        aria-label="Depth selector"
      />
      <strong className="depth-readout">{depth} m</strong>
    </div>
  );
}

export function DateControl({ date, onChange, min = '2020-01-01', max = '2020-02-15' }) {
  const step = (n) => {
    const d = new Date(date + 'T00:00:00');
    d.setDate(d.getDate() + n);
    onChange(d.toISOString().slice(0, 10));
  };
  return (
    <div className="ctl-row">
      <label>Date</label>
      <button className="btn" onClick={() => step(-1)} aria-label="Previous day">◀</button>
      <input type="date" value={date} min={min} max={max} onChange={(e) => e.target.value && onChange(e.target.value)} />
      <button className="btn" onClick={() => step(1)} aria-label="Next day">▶</button>
    </div>
  );
}

export function CompareModeSwitch({ mode, onChange }) {
  const opts = [
    ['model', 'OceanEmbed'],
    ['glorys', 'vs GLORYS'],
    ['diff', 'Difference'],
  ];
  return (
    <div className="seg" role="tablist" aria-label="Compare mode">
      {opts.map(([v, l]) => (
        <button key={v} className={mode === v ? 'seg-btn active' : 'seg-btn'} onClick={() => onChange(v)}>{l}</button>
      ))}
    </div>
  );
}

export function SkillMetricCard({ label, value, unit = '' }) {
  return (
    <div className="metric-tile">
      <div className="metric-label">{label}</div>
      <div className="metric-value">{value}<span className="metric-unit">{unit}</span></div>
    </div>
  );
}

export function AlertBanner({ alerts, onJump, onDismiss }) {
  if (!alerts || alerts.length === 0) return null;
  return (
    <div className="alert-banner">
      <span className="alert-dot" />
      <button className="alert-text" onClick={() => onJump(alerts[0])} title="Jump to anomaly location">
        {alerts[0].text} — {alerts[0].date}. Click to inspect.
      </button>
      <button className="btn small" onClick={onDismiss}>Dismiss</button>
    </div>
  );
}

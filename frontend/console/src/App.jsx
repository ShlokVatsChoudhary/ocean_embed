import { useEffect, useMemo, useState } from 'react';
import { ConsoleContext, useConsoleState, fmt } from './state';
import MapPanel from './panels/MapPanel';
import SectionPanel from './panels/SectionPanel';
import Controls from './ui/Controls';
import Readout from './ui/Readout';
import TopBar, { StatusBar } from './ui/TopBar';
import ValidationDrawer from './ui/ValidationDrawer';
import { unionRange, seqStops, divStops, CAT_COLOURS, CAT_LABELS } from './lib/ramp';
import { STANDARD_DEPTHS } from './api/oceanembed';

export default function App() {
  const state = useConsoleState();
  const [drawer, setDrawer] = useState(() =>
    typeof window !== 'undefined' && new URLSearchParams(window.location.search).get('drawer') === 'validation');
  const [showFloats, setShowFloats] = useState(true);

  // One temperature range across the whole loaded volume, so changing depth does
  // not silently rescale the colours underneath the user.
  const tempRange = useMemo(
    () => unionRange(STANDARD_DEPTHS.map((d) => state.volume[d])) ?? { min: 10, max: 32 },
    [state.volume],
  );

  const hazardField = state.hazards[state.activeHazard] ?? null;
  const hazardRange = useMemo(
    () => (hazardField ? { min: hazardField.stats.min, max: hazardField.stats.max } : null),
    [hazardField],
  );

  const isCat = state.isHazard && state.activeHazard === 'tchp';
  const modelField = state.isHazard ? hazardField : state.volume[state.depth] ?? null;
  const refField = !state.isHazard ? state.reference[state.depth] ?? null : null;
  const difference = state.mapMode === 'difference' && !state.isHazard;

  // The difference is computed only where both fields have a value, and the range is
  // made symmetric about zero so equal cold and warm errors look equal.
  const diffField = useMemo(() => {
    if (!difference || !modelField || !refField) return null;
    const values = modelField.values.map((row, i) => row.map((v, j) => {
      const r = refField.values?.[i]?.[j];
      if (v === null || v === undefined || r === null || r === undefined) return null;
      return Number(v) - Number(r);
    }));
    let peak = 0;
    const coverage = [];
    values.forEach((row) => {
      coverage.push(row.map((v) => (v === null ? 0 : 1)));
      row.forEach((v) => { if (v !== null) peak = Math.max(peak, Math.abs(v)); });
    });
    return {
      ...modelField, values, coverage,
      stats: { ...modelField.stats, min: -peak, max: peak },
    };
  }, [difference, modelField, refField]);

  const field = difference ? diffField : modelField;
  const mode = isCat ? 'cat' : difference ? 'div' : 'seq';
  const range = difference ? (diffField ? { min: diffField.stats.min, max: diffField.stats.max } : { min: -2.5, max: 2.5 })
    : state.isHazard ? hazardRange : tempRange;
  const unit = state.isHazard ? state.hazardInfo.unit : '°C';

  // Keyboard: arrows move depth and day, which is how this gets used in practice.
  useEffect(() => {
    const onKey = (e) => {
      if (e.target && e.target.matches && e.target.matches('input, textarea, select')) return;
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        if (!state.isHazard) { e.preventDefault(); state.stepDepth(e.key === 'ArrowDown' ? 1 : -1); }
      } else if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
        e.preventDefault(); state.stepDay(e.key === 'ArrowRight' ? 1 : -1);
      } else if (e.key === 'Escape') {
        setDrawer(false);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [state]);

  const markers = showFloats ? state.floats.map((f) => ({ lat: f.lat, lon: f.lon })) : [];
  const pending = state.isHazard ? state.loading.hazards : state.loading.volume;
  const served = field ? field.stats.validCount / field.stats.totalCount : null;

  return (
    <ConsoleContext.Provider value={state}>
      <div className="console">
        <TopBar
          onValidate={() => setDrawer(true)}
          onSwitchTheme={() => { window.location.href = '/'; }}
        />

        {state.failed.volume && !Object.keys(state.volume).length && (
          <div className="banner">
            <span>
              No data from the backend at {fmt.base()}. The console reports nothing rather than
              showing placeholder numbers.
            </span>
            <button onClick={() => window.location.reload()}>Retry</button>
          </div>
        )}

        <div className="workspace">
          <Controls />

          <div className="col-centre">
            <section className="panel">
              <header>
                <h2>{state.isHazard ? state.hazardInfo.label : 'Temperature field'}</h2>
                <span className="sub">{fmt.date(state.date)} · {state.isHazard ? unit : `${state.depth} m`}</span>
                <div className="chips" style={{ marginLeft: 10 }}>
                  {!state.isHazard && (
                    <>
                      <button
                        className={state.mapMode === 'field' ? 'chip on' : 'chip'}
                        onClick={() => state.setMapMode('field')}
                      >
                        Model
                      </button>
                      <button
                        className={state.mapMode === 'difference' ? 'chip on' : 'chip'}
                        onClick={() => state.setMapMode('difference')}
                        title="Model minus the reference field it was trained against"
                      >
                        Model − reference
                      </button>
                    </>
                  )}
                  <button className={showFloats ? 'chip on' : 'chip'} onClick={() => setShowFloats((v) => !v)}>
                    ARGO floats
                  </button>
                  <button className={state.showCoverage ? 'chip on' : 'chip'} onClick={() => state.setShowCoverage((v) => !v)}>
                    Missing cells
                  </button>
                </div>
                <span className="sub" style={{ marginLeft: 8 }}>
                  {field ? `${fmt.int(field.stats.validCount)} cells` : '—'}
                </span>
              </header>
              {pending && <div className="bar indet"><i /></div>}
              <div className="canvas-wrap">
                <MapPanel
                  field={field}
                  mode={mode}
                  range={range}
                  unit={unit}
                  decimals={state.isHazard ? 1 : 2}
                  markers={markers}
                  selected={state.selection}
                  onSelect={state.setSelection}
                  showCoverage={state.showCoverage}
                  catLabels={state.hazardVar === 'tchp' ? hazardField?.categoryLabels : null}
                />
                {!field && !state.failed.volume && (
                  <div className="empty" style={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center' }}>
                    <span><span className="spin" /> &nbsp;loading the {state.isHazard ? state.hazardInfo.label : `${state.depth} m`} field…</span>
                  </div>
                )}
                {!field && state.failed.volume && (
                  <div className="empty" style={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center' }}>
                    Backend unavailable — nothing to draw.
                  </div>
                )}
                {difference && !diffField && (
                  <div className="empty" style={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center' }}>
                    <span><span className="spin" /> &nbsp;loading the reference field…</span>
                  </div>
                )}
              </div>
              <Legend mode={mode} range={range} unit={unit} served={served} isHazard={state.isHazard} />
              {difference && (
                <div className="caveat">
                  The reference field is the model&apos;s own training target on these dates, so this
                  difference is in-sample and optimistic. It is a debugging view, not validation —
                  independent evidence comes from ARGO in the Validation drawer.
                </div>
              )}
            </section>

            <section className="panel">
              <header>
                <h2>Temperature section along {state.selection.lat.toFixed(2)}°N</h2>
                <span className="sub">
                  depth × longitude · click to move the cursor
                  {state.isHazard ? ' · always temperature: it is what every hazard layer is derived from' : ''}
                </span>
              </header>
              <div className="canvas-wrap">
                <SectionPanel
                  volume={state.volume}
                  lat={state.selection.lat}
                  range={tempRange}
                  lon={state.selection.lon}
                  onSelect={(lon) => state.setSelection((s) => ({ ...s, lon }))}
                />
              </div>
            </section>
          </div>

          <Readout />
        </div>

        <StatusBar />
      </div>

      {drawer && <ValidationDrawer onClose={() => setDrawer(false)} />}
    </ConsoleContext.Provider>
  );
}

function Legend({ mode, range, unit, served, isHazard }) {
  if (mode === 'div') {
    const stops = divStops(40);
    return (
      <div className="legend">
        <div className="legend-bar">
          <span className="end">{(range?.min ?? -2.5).toFixed(2)}</span>
          <span className="legend-strip">
            {stops.map((col, i) => <div key={i} style={{ background: col }} />)}
          </span>
          <span className="end r">+{(range?.max ?? 2.5).toFixed(2)}</span>
        </div>
        <div className="legend-cap">
          Model minus reference, °C · symmetric about zero · {served === null ? '—' : fmt.pct(served)} of grid cells served
        </div>
      </div>
    );
  }
  if (mode === 'cat') {
    return (
      <div className="legend">
        <div className="legend-cat">
          {CAT_LABELS.map((l, i) => (
            <span key={l}><span className="swatch-box" style={{ background: CAT_COLOURS[i] }} />{l}</span>
          ))}
        </div>
        <div className="legend-cap">
          Cyclone heat potential, {unit} · {served === null ? '—' : fmt.pct(served)} of grid cells served
        </div>
      </div>
    );
  }
  const stops = seqStops(40);
  const lo = range ? range.min : 0;
  const hi = range ? range.max : 1;
  return (
    <div className="legend">
      <div className="legend-bar">
        <span className="end">{lo.toFixed(1)}</span>
        <span className="legend-strip">
          {stops.map((col, i) => <div key={i} style={{ background: col }} />)}
        </span>
        <span className="end r">{hi.toFixed(1)}</span>
      </div>
      <div className="legend-cap">
        {unit} · {served === null ? '—' : fmt.pct(served)} of grid cells served
        {!isHazard && ' · range fixed across all depths so colour is comparable'}
      </div>
    </div>
  );
}


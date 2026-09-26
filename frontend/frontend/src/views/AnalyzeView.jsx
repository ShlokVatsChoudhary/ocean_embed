import { useEffect, useMemo, useState } from 'react';
import MapHeatmap from '../components/MapHeatmap';
import { DepthSlider, DateControl } from '../components/controls';
import { VerticalProfileChart } from '../components/charts';
import { getTemperatureField, getVerticalProfile, getArgoFloats, prettyDate } from '../api/oceanembed';

function diffField(a, b) {
  return { ...a, values: a.values.map((row, i) => row.map((v, j) => +(v - b.values[i][j]).toFixed(3))), stats: { min: -2.5, max: 2.5 }, source: 'difference' };
}
function anomalyField(a, baseline) {
  return { ...a, values: a.values.map((row) => row.map((v) => +(v - baseline).toFixed(3))), stats: { min: -3, max: 3 }, source: 'anomaly' };
}

export default function AnalyzeView({ date, setDate, depth, setDepth, selected, setSelected }) {
  const [anomalyMode, setAnomalyMode] = useState(false);
  const [baseline, setBaseline] = useState('jan-clim');
  const [modelF, setModelF] = useState(null);
  const [glorysF, setGlorysF] = useState(null);
  const [fieldError, setFieldError] = useState(null);
  const [fieldLoading, setFieldLoading] = useState(true);
  const [floats, setFloats] = useState([]);
  const [profile, setProfile] = useState(null);
  const [profileError, setProfileError] = useState(null);

  useEffect(() => {
    let dead = false;
    setFieldLoading(true); setFieldError(null);
    Promise.all([
      getTemperatureField({ date, depth }),
      getTemperatureField({ date, depth, source: 'glorys' }),
      getArgoFloats({ date }),
    ]).then(([m, g, f]) => {
      if (dead) return;
      setModelF(m); setGlorysF(g); setFloats(f); setFieldLoading(false);
    }).catch((e) => { if (!dead) { setFieldError(e.message); setFieldLoading(false); } });
    return () => { dead = true; };
  }, [date, depth]);

  useEffect(() => {
    let dead = false;
    setProfileError(null);
    getVerticalProfile({ date, lat: selected.lat, lon: selected.lon })
      .then((p) => { if (!dead) setProfile(p); })
      .catch((e) => { if (!dead) setProfileError(e.message); });
    return () => { dead = true; };
  }, [date, selected]);

  const diffF = useMemo(() => (modelF && glorysF ? diffField(modelF, glorysF) : null), [modelF, glorysF]);
  const range = useMemo(() => {
    if (!modelF || !glorysF) return null;
    const lo = Math.min(modelF.stats.min, glorysF.stats.min);
    const hi = Math.max(modelF.stats.max, glorysF.stats.max);
    return { min: Math.floor(lo), max: Math.ceil(hi) };
  }, [modelF, glorysF]);
  const anomF = useMemo(
    () => (modelF ? anomalyField(modelF, baseline === 'jan-clim' ? 26.5 - depth * 0.012 : 25.0 - depth * 0.01) : null),
    [modelF, baseline, depth]
  );
  const markers = floats.map((f) => ({ lat: f.lat, lon: f.lon, kind: 'argo' }));

  const loadFloat = (id) => {
    const f = floats.find((x) => x.id === id);
    if (f) setSelected({ lat: f.lat, lon: f.lon });
  };

  return (
    <div>
      <section className="panel">
        <h2>Side-by-side comparison — {depth}m, {prettyDate(date)}</h2>
        <div className="map-controls">
          <DateControl date={date} onChange={setDate} />
        </div>
        <DepthSlider depth={depth} onChange={setDepth} />
        <div style={{ display: 'flex', gap: 12, alignItems: 'center', margin: '8px 0' }}>
          <label className="check">
            <input type="checkbox" checked={anomalyMode} onChange={(e) => setAnomalyMode(e.target.checked)} />
            Anomaly mode (experimental)
          </label>
          {anomalyMode && (
            <select value={baseline} onChange={(e) => setBaseline(e.target.value)} aria-label="Baseline selector">
              <option value="jan-clim">Baseline: January climatology</option>
              <option value="annual">Baseline: Annual mean</option>
            </select>
          )}
        </div>
        {anomalyMode && (
          <div className="notice">
            Experimental anomaly view — only as good as its baseline climatology. Not validated; use for pattern
            inspection only. Baseline: {baseline === 'jan-clim' ? 'January climatology' : 'Annual mean'} (mock).
          </div>
        )}
        {fieldLoading && <div className="loading">Loading comparison fields…</div>}
        {fieldError && <div className="error-box">Failed to load fields: {fieldError}</div>}
        {!fieldLoading && !fieldError && anomalyMode && anomF && (
          <div className="tri-grid">
            <div><h4>OceanEmbed anomaly</h4><MapHeatmap field={anomF} mode="diverging" fixedRange={{ min: -3, max: 3 }} markers={markers} selected={selected} onSelect={setSelected} height={320} /></div>
          </div>
        )}
        {!fieldLoading && !fieldError && !anomalyMode && modelF && glorysF && diffF && (
          <div className="tri-grid">
            <div><h4>OceanEmbed</h4><MapHeatmap field={modelF} fixedRange={range} markers={markers} selected={selected} onSelect={setSelected} height={320} /></div>
            <div><h4>GLORYS</h4><MapHeatmap field={glorysF} fixedRange={range} markers={markers} selected={selected} onSelect={setSelected} height={320} /></div>
            <div><h4>Difference (model − GLORYS)</h4><MapHeatmap field={diffF} mode="diverging" fixedRange={{ min: -2.5, max: 2.5 }} selected={selected} onSelect={setSelected} height={320} /></div>
          </div>
        )}
        <div className="muted small">● black dots = ARGO float profiles available on {prettyDate(date)} — click a float ID below or the map to load its profile.</div>
      </section>
      <div className="explore-grid" style={{ marginTop: 12 }}>
        <section className="panel">
          <h3>ARGO floats — {prettyDate(date)} ({floats.length})</h3>
          <div className="float-list">
            {floats.map((f) => (
              <button key={f.id} className="btn small" onClick={() => loadFloat(f.id)} title={`Load ${f.id}`}>
                {f.id} · {f.lat}°N {f.lon}°E
              </button>
            ))}
          </div>
        </section>
        <aside className="panel">
          <h3>Vertical profile — {selected.lat}°N, {selected.lon}°E</h3>
          {profileError && <div className="error-box">Failed to load profile: {profileError}</div>}
          {!profile && !profileError && <div className="loading">Loading profile…</div>}
          {profile && <VerticalProfileChart profile={profile} height={340} />}
        </aside>
      </div>
    </div>
  );
}

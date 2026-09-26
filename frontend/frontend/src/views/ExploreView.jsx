import { useEffect, useMemo, useRef, useState } from 'react';
import MapHeatmap from '../components/MapHeatmap';
import { DepthSlider, DateControl, CompareModeSwitch, SkillMetricCard } from '../components/controls';
import { VerticalProfileChart } from '../components/charts';
import { getTemperatureField, getTemperatureRange, getVerticalProfile, getSkillMetrics, prettyDate, addDaysStr } from '../api/oceanembed';

function diffField(a, b) {
  return {
    ...a,
    values: a.values.map((row, i) => row.map((v, j) => +(v - b.values[i][j]).toFixed(3))),
    stats: { min: -2.5, max: 2.5 },
    source: 'difference',
  };
}

export default function ExploreView({ date, setDate, depth, setDepth, selected, setSelected }) {
  const [mode, setMode] = useState('model');
  const [showConf, setShowConf] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [buffering, setBuffering] = useState(false);
  const [frameIdx, setFrameIdx] = useState(0);
  const [loopDates, setLoopDates] = useState([]);
  const [modelF, setModelF] = useState(null);
  const [glorysF, setGlorysF] = useState(null);
  const [fieldError, setFieldError] = useState(null);
  const [fieldLoading, setFieldLoading] = useState(true);
  const [profile, setProfile] = useState(null);
  const [profileError, setProfileError] = useState(null);
  const [skill, setSkill] = useState(null);
  const cacheRef = useRef(new Map());
  const timer = useRef(null);

  const effDate = playing && loopDates.length > 0 ? loopDates[frameIdx] : date;
  const cacheKey = (d, dep, src) => `${d}|${dep}|${src}`;

  async function loadField(d, dep, src, cancelled) {
    const key = cacheKey(d, dep, src);
    if (cacheRef.current.has(key)) return cacheRef.current.get(key);
    const f = await getTemperatureField({ date: d, depth: dep, source: src });
    cacheRef.current.set(key, f);
    if (cacheRef.current.size > 200) {
      const first = cacheRef.current.keys().next().value;
      cacheRef.current.delete(first);
    }
    return cancelled?.() ? null : f;
  }

  // Field fetch (cache-aware so loop playback never refetches a frame).
  useEffect(() => {
    let dead = false;
    setFieldLoading(true); setFieldError(null);
    Promise.all([loadField(effDate, depth, 'oceanembed', () => dead), loadField(effDate, depth, 'glorys', () => dead)])
      .then(([m, g]) => {
        if (dead || !m || !g) return;
        setModelF(m); setGlorysF(g); setFieldLoading(false);
      })
      .catch((e) => { if (!dead) { setFieldError(e.message); setFieldLoading(false); } });
    return () => { dead = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [effDate, depth]);

  // Profile fetch.
  useEffect(() => {
    let dead = false;
    setProfileError(null);
    getVerticalProfile({ date: effDate, lat: selected.lat, lon: selected.lon })
      .then((p) => { if (!dead) setProfile(p); })
      .catch((e) => { if (!dead) setProfileError(e.message); });
    return () => { dead = true; };
  }, [effDate, selected]);

  // Skill metrics (fetched once; row picked per depth).
  useEffect(() => {
    let dead = false;
    getSkillMetrics().then((all) => {
      if (dead) return;
      setSkill(all.find((m) => m.depth === depth) ?? null);
    }).catch(() => { if (!dead) setSkill(null); });
    return () => { dead = true; };
  }, [depth]);

  const stop = () => { setPlaying(false); clearInterval(timer.current); };

  const startLoop = async () => {
    stop();
    setBuffering(true);
    const start = addDaysStr(date, -29);
    try {
      // Prefetch all 30 frames (range endpoint when available, else parallel)
      // into the frame cache so playback is stutter-free against a backend.
      const frames = await getTemperatureRange({ start, end: date, depth, source: 'oceanembed' });
      frames.forEach(({ date: d, field }) => cacheRef.current.set(cacheKey(d, depth, 'oceanembed'), field));
      const glo = await getTemperatureRange({ start, end: date, depth, source: 'glorys' });
      glo.forEach(({ date: d, field }) => cacheRef.current.set(cacheKey(d, depth, 'glorys'), field));
      setLoopDates(frames.map((f) => f.date));
      setFrameIdx(0);
      setPlaying(true);
      let i = 0;
      timer.current = setInterval(() => {
        i += 1;
        if (i > 29) { stop(); return; }
        setFrameIdx(i);
      }, 350);
    } finally {
      setBuffering(false);
    }
  };

  useEffect(() => () => clearInterval(timer.current), []);

  const shown = useMemo(() => {
    if (!modelF || !glorysF) return null;
    if (mode === 'glorys') return glorysF;
    if (mode === 'diff') return diffField(modelF, glorysF);
    return modelF;
  }, [mode, modelF, glorysF]);
  const range = useMemo(() => {
    if (!modelF || !glorysF) return null;
    const lo = Math.min(modelF.stats.min, glorysF.stats.min);
    const hi = Math.max(modelF.stats.max, glorysF.stats.max);
    return { min: Math.floor(lo), max: Math.ceil(hi) };
  }, [modelF, glorysF]);

  return (
    <div className="explore-grid">
      <section className="panel map-panel">
        <h2>Temperature at {depth}m — North Indian Ocean, {prettyDate(effDate)}</h2>
        <div className="map-controls">
          <DateControl date={date} onChange={(d) => { stop(); setDate(d); }} />
          <CompareModeSwitch mode={mode} onChange={setMode} />
        </div>
        {fieldLoading && !shown && <div className="loading">Loading temperature field…</div>}
        {fieldError && <div className="error-box">Failed to load field: {fieldError} <button className="btn small" onClick={() => { cacheRef.current.clear(); stop(); setDate(date); }}>Retry</button></div>}
        {shown && (
          <MapHeatmap
            field={shown}
            mode={mode === 'diff' ? 'diverging' : 'sequential'}
            fixedRange={mode === 'diff' ? { min: -2.5, max: 2.5 } : range}
            selected={selected} showConfidence={showConf} onSelect={setSelected}
          />
        )}
        <DepthSlider depth={depth} onChange={(d) => { stop(); setDepth(d); }} />
        <div className="map-controls">
          {playing
            ? <button className="btn" onClick={stop}>⏸ Pause loop ({loopDates[frameIdx] ? prettyDate(loopDates[frameIdx]) : ''})</button>
            : <button className="btn" onClick={startLoop} disabled={buffering}>{buffering ? 'Buffering 30-day loop…' : '▶ Play 30-day loop'}</button>}
          <label className="check">
            <input type="checkbox" checked={showConf} onChange={(e) => setShowConf(e.target.checked)} />
            Confidence shading (dim = high uncertainty)
          </label>
        </div>
        <div className="muted small">
          {mode === 'model' && 'Showing OceanEmbed reconstruction.'}
          {mode === 'glorys' && 'Showing GLORYS reference field.'}
          {mode === 'diff' && 'Showing OceanEmbed − GLORYS (diverging scale, centered on zero).'}
          {' '}Click map to select a profile location.
        </div>
      </section>
      <aside className="panel side-panel">
        <h3>Vertical profile — {selected.lat}°N, {selected.lon}°E</h3>
        {profileError && <div className="error-box">Failed to load profile: {profileError}</div>}
        {!profile && !profileError && <div className="loading">Loading profile…</div>}
        {profile && <VerticalProfileChart profile={profile} />}
        <h3>Skill at {depth}m</h3>
        <div className="metric-row">
          <SkillMetricCard label="RMSE" value={skill ? skill.rmse.toFixed(2) : '…'} unit=" °C" />
          <SkillMetricCard label="Correlation" value={skill ? skill.correlation.toFixed(3) : '…'} unit="" />
          <SkillMetricCard label="Bias" value={skill ? skill.bias.toFixed(2) : '…'} unit=" °C" />
        </div>
        <div className="muted small">Trust context from independent validation — see Validate view for full table.</div>
      </aside>
    </div>
  );
}

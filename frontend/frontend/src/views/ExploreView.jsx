import { useEffect, useMemo, useRef, useState } from 'react';
import MapHeatmap from '../components/MapHeatmap';
import { DepthSlider, DateControl, CompareModeSwitch, SkillMetricCard } from '../components/controls';
import { VerticalProfileChart } from '../components/charts';
import { getTemperatureField, getVerticalProfile, getSkillMetrics, getComparison, prettyDate, getSupportedDates } from '../api/oceanembed';

export default function ExploreView({ date, setDate, depth, setDepth, selected, setSelected }) {
  const [mode, setMode] = useState('model');
  const [showCoverage, setShowCoverage] = useState(false);
  const [loopDateList, setLoopDateList] = useState([]);
  const [playing, setPlaying] = useState(false);
  const [buffering, setBuffering] = useState(false);
  const [frameIdx, setFrameIdx] = useState(0);
  const [loopDates, setLoopDates] = useState([]);
  const [modelF, setModelF] = useState(null);
  const [fieldError, setFieldError] = useState(null);
  const [fieldLoading, setFieldLoading] = useState(true);
  const [profile, setProfile] = useState(null);
  const [profileError, setProfileError] = useState(null);
  const [skill, setSkill] = useState(null);
  const [comparison, setComparison] = useState(null);
  const [comparisonError, setComparisonError] = useState(null);
  const [comparisonLoading, setComparisonLoading] = useState(false);
  const cacheRef = useRef(new Map());
  const timer = useRef(null);

  const effDate = playing && loopDates.length > 0 ? loopDates[frameIdx] : date;
  const cacheKey = (d, dep, src) => `${d}|${dep}|${src}`;

  async function loadField(d, dep, cancelled) {
    const key = cacheKey(d, dep, 'oceanembed');
    if (cacheRef.current.has(key)) return cacheRef.current.get(key);
    const f = await getTemperatureField({ date: d, depth: dep });
    cacheRef.current.set(key, f);
    if (cacheRef.current.size > 200) {
      const first = cacheRef.current.keys().next().value;
      cacheRef.current.delete(first);
    }
    return cancelled?.() ? null : f;
  }

  useEffect(() => {
    let dead = false;
    setFieldLoading(true); setFieldError(null);
    loadField(effDate, depth, () => dead)
      .then((m) => {
        if (dead) return;
        setModelF(m);
        setFieldLoading(false);
      })
      .catch((e) => { if (!dead) { setFieldError(e.message); setFieldLoading(false); } });
    return () => { dead = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [effDate, depth]);

  useEffect(() => {
    let dead = false;
    setProfileError(null);
    getVerticalProfile({ date: effDate, lat: selected.lat, lon: selected.lon })
      .then((p) => { if (!dead) setProfile(p); })
      .catch((e) => { if (!dead) setProfileError(e.message); });
    return () => { dead = true; };
  }, [effDate, selected]);

  useEffect(() => {
    let dead = false;
    setComparison(null); setComparisonError(null); setComparisonLoading(true);
    const hasSelection = selected && Number.isFinite(selected.lat) && Number.isFinite(selected.lon);
    if (!hasSelection) {
      setComparisonLoading(false);
      return () => { dead = true; };
    }
    getComparison({ latitude: selected.lat, longitude: selected.lon, date: effDate, depth })
      .then((c) => { if (!dead) setComparison(c); })
      .catch((e) => { if (!dead) setComparisonError(e.message); })
      .finally(() => { if (!dead) setComparisonLoading(false); });
    return () => { dead = true; };
  }, [effDate, depth, selected]);

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
    try {
      const frames = [];
      const candidates = loopDateList.length ? loopDateList : await getSupportedDates();
      for (const iso of candidates) {
        const field = await getTemperatureField({ date: iso, depth });
        if (field) {
          cacheRef.current.set(cacheKey(iso, depth, 'oceanembed'), field);
          frames.push(iso);
        }
      }
      setLoopDates(frames);
      setFrameIdx(0);
      setPlaying(frames.length > 1);
      let i = 0;
      timer.current = setInterval(() => {
        i += 1;
        if (i >= frames.length) { stop(); return; }
        setFrameIdx(i);
      }, 350);
    } finally {
      setBuffering(false);
    }
  };

  useEffect(() => () => clearInterval(timer.current), []);

  // The backend is authoritative for which dates the model covers.
  useEffect(() => {
    let dead = false;
    getSupportedDates().then((dates) => { if (!dead) setLoopDateList(dates); }).catch(() => {});
    return () => { dead = true; };
  }, []);

  const shown = mode === 'model' ? modelF : null;
  const range = useMemo(() => {
    if (!modelF) return null;
    return { min: Math.floor(modelF.stats.min), max: Math.ceil(modelF.stats.max) };
  }, [modelF]);
  const hasSelection = selected && Number.isFinite(selected.lat) && Number.isFinite(selected.lon);
  const comparisonMode = mode !== 'model';
  const fieldUnavailableMessage = mode === 'glorys'
    ? 'GLORYS field data is not available in the current backend contract.'
    : mode === 'diff'
      ? 'Difference field data is not available in the current backend contract.'
      : null;

  return (
    <div className="explore-grid">
      <section className="panel map-panel">
        <h2>Temperature at {depth}m — North Indian Ocean, {prettyDate(effDate)}</h2>
        <div className="map-controls">
          <DateControl date={date} onChange={(d) => { stop(); setDate(d); }} />
          <CompareModeSwitch mode={mode} onChange={setMode} />
        </div>
        {fieldError && <div className="error-box">Failed to load field: {fieldError} <button className="btn small" onClick={() => { cacheRef.current.clear(); stop(); setDate(date); }}>Retry</button></div>}
        <div className="visualization-shell">
          {mode === 'model' && shown ? (
            <MapHeatmap
              field={shown}
              mode='sequential'
              fixedRange={range}
              selected={selected} showCoverage={showCoverage} onSelect={setSelected}
            />
          ) : mode !== 'model' ? (
            <div className="loading-panel" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#5d6b7a', fontWeight: 600 }}>
              {fieldUnavailableMessage}
            </div>
          ) : (
            <div className="loading-panel" />
          )}
          {fieldLoading && mode === 'model' && <div className="loading-overlay"><span>Updating visualization…</span></div>}
        </div>
        <DepthSlider depth={depth} onChange={(d) => { stop(); setDepth(d); }} />
        <div className="map-controls">
          {playing
            ? <button className="btn" onClick={stop}>⏸ Pause animation</button>
            : <button className="btn" onClick={startLoop} disabled={buffering}>{buffering ? 'Buffering…' : `▶ Animate ${loopDateList.length || 7} days`}</button>}
          <label className="check">
            <input type="checkbox" checked={showCoverage} onChange={(e) => setShowCoverage(e.target.checked)} />
            Show coverage (dim = no model value)
          </label>
        </div>
        <div className="muted small">
          {mode === 'model' && 'Showing OceanEmbed reconstruction.'}
          {mode === 'glorys' && 'Showing selected-point GLORYS comparison.'}
          {mode === 'diff' && 'Showing selected-point difference at the chosen location.'}
          {' '}Click map to select a profile location.
        </div>
        {comparisonMode && (
          <div className="comparison-card">
            <div className="comparison-head">
              <span>{mode === 'glorys' ? 'Selected location comparison' : 'Difference at selected location'}</span>
              <strong>{hasSelection ? `${selected.lat.toFixed(2)}°N, ${selected.lon.toFixed(2)}°E` : 'Click the map to select a location.'}</strong>
            </div>
            {!hasSelection && <div className="notice">Click the map to select a location.</div>}
            {hasSelection && comparisonLoading && <div className="notice">Loading comparison…</div>}
            {hasSelection && comparisonError && !comparisonLoading && <div className="notice">The comparison service could not be reached. No values are shown rather than substitutes.</div>}
            {hasSelection && !comparisonError && !comparisonLoading && !comparison && <div className="notice">No comparison payload for this location, depth and date.</div>}
            {hasSelection && comparison && comparison.state === 'model_unavailable' && (
              <div className="notice">
                <strong>OceanEmbed prediction unavailable</strong> at this location, depth and date.
                No fallback scientific value is shown.
              </div>
            )}
            {hasSelection && comparison && comparison.state === 'model_only' && (
              <div className="notice">
                <strong>GLORYS reference unavailable</strong> at this location, depth and date. This is a
                legitimate missing reference, not an error.
              </div>
            )}
            {hasSelection && comparison && comparison.offset_degrees > 1 && (
              <div className="notice" style={{ borderLeft: '3px solid #b45309' }}>
                <strong>Not a local value.</strong> This is a shelf-sea location, so the nearest cell
                with a complete 0–1000 m column is {comparison.offset_degrees.toFixed(2)}° away
                ({comparison.grid_latitude.toFixed(2)}°N, {comparison.grid_longitude.toFixed(2)}°E).
                Read this number as representative of that cell, not of your clicked point.
              </div>
            )}
            {hasSelection && comparison && comparison.state !== 'model_unavailable' && (
              <div className="comparison-grid">
                <div className="comparison-stat">
                  <span>Requested location</span>
                  <strong>{comparison.requested_latitude.toFixed(2)}°N, {comparison.requested_longitude.toFixed(2)}°E</strong>
                </div>
                <div className="comparison-stat">
                  <span>Value read from grid cell</span>
                  <strong>
                    {comparison.grid_latitude == null
                      ? 'Not reported'
                      : `${comparison.grid_latitude.toFixed(2)}°N, ${comparison.grid_longitude.toFixed(2)}°E`}
                  </strong>
                  <div className="muted small" style={{ marginTop: 4 }}>
                    {comparison.grid_latitude == null
                      ? 'The model did not report a grid point for this request.'
                      : comparison.offset_degrees > 0
                        ? `Nearest cell to the request (${comparison.nearest_grid_latitude.toFixed(2)}°N, ${comparison.nearest_grid_longitude.toFixed(2)}°E) has no complete 0–1000 m column, so the value comes from ${comparison.offset_degrees.toFixed(2)}° away.`
                        : comparison.snappedToGrid
                          ? `Nearest ${comparison.grid_resolution_degrees}° cell.`
                          : `On the ${comparison.grid_resolution_degrees}° grid.`}
                  </div>
                </div>
                <div className="comparison-stat">
                  <span>Date</span>
                  <strong>{prettyDate(comparison.date)}</strong>
                </div>
                <div className="comparison-stat">
                  <span>Depth</span>
                  <strong>{comparison.depth.toFixed(0)} m</strong>
                </div>
                <div className="comparison-stat">
                  <span>OceanEmbed temperature</span>
                  <strong>{comparison.oceanembed_temperature == null ? 'Unavailable' : `${Number(comparison.oceanembed_temperature).toFixed(2)} °C`}</strong>
                </div>
                <div className="comparison-stat">
                  <span>{comparison.glorys_status === 'bundled_sample' ? 'Reference sample' : 'GLORYS temperature'}</span>
                  <strong>{comparison.glorys_temperature == null ? 'Unavailable' : `${Number(comparison.glorys_temperature).toFixed(2)} °C`}</strong>
                  {comparison.glorys_status === 'bundled_sample' && (
                    <div className="muted small" style={{ marginTop: 4 }}>Bundled/reference sample</div>
                  )}
                </div>
                <div className="comparison-stat highlight">
                  <span>{mode === 'glorys' ? 'Difference' : 'Selected-point difference'}</span>
                  <strong>{comparison.difference == null ? 'Unavailable' : `${Number(comparison.difference).toFixed(2)} °C`}</strong>
                </div>
              </div>
            )}
          </div>
        )}
      </section>
      <aside className="panel side-panel">
        <h3>Vertical profile — {hasSelection ? `${selected.lat}°N, ${selected.lon}°E` : 'No location selected'}</h3>
        {profileError && <div className="error-box">Profile unavailable for this location.</div>}
        <div className="visualization-shell profile-shell">
          {profile ? <VerticalProfileChart profile={profile} /> : <div className="loading-panel" />}
          {!profile && !profileError && <div className="loading-overlay"><span>Updating profile…</span></div>}
        </div>
        {profile && profile.glorys && profile.glorys.some((v) => v !== null) && (
          <div className="muted small" style={{ marginTop: 8 }}>GLORYS profile available for this location.</div>
        )}
        {!profile && !profileError && <div className="notice">Click the map to select a location.</div>}
        {hasSelection && profileError && <div className="notice">GLORYS profile unavailable for this location.</div>}
        <h3>Skill at {depth}m</h3>
        {skill ? (
          <div className="metric-row">
            <SkillMetricCard label="RMSE" value={skill.rmse.toFixed(2)} unit=" °C" />
            <SkillMetricCard label="Correlation" value={skill.correlation.toFixed(3)} unit="" />
            <SkillMetricCard label="Bias" value={skill.bias.toFixed(2)} unit=" °C" />
          </div>
        ) : (
          <div className="notice">Validation metrics available in Validate.</div>
        )}
        <div className="muted small">Trust context from independent validation — see Validate view for full table.</div>
      </aside>
    </div>
  );
}

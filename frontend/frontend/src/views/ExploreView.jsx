import { useEffect, useMemo, useRef, useState } from 'react';
import MapHeatmap from '../components/MapHeatmap';
import { DepthSlider, DateControl, CompareModeSwitch, SkillMetricCard } from '../components/controls';
import { VerticalProfileChart } from '../components/charts';
import {
  getTemperatureField, getVerticalProfile, getSkillMetrics, getComparison, prettyDate,
  getSupportedDates, getHazardField, getHazardSummary, HAZARD_VARIABLES, hazardVariableInfo,
} from '../api/oceanembed';

export default function ExploreView({ date, setDate, depth, setDepth, selected, setSelected }) {
  const [mode, setMode] = useState('model');
  const [showCoverage, setShowCoverage] = useState(false);
  const [loopDateList, setLoopDateList] = useState([]);
  const [playing, setPlaying] = useState(false);
  const [buffering, setBuffering] = useState(false);
  const [frameIdx, setFrameIdx] = useState(0);
  const [loopDates, setLoopDates] = useState([]);
  const [modelF, setModelF] = useState(null);
  const [hazardVar, setHazardVar] = useState('tchp');
  const [hazardF, setHazardF] = useState(null);
  const [hazardError, setHazardError] = useState(null);
  const [hazardLoading, setHazardLoading] = useState(false);
  const [hazardSummary, setHazardSummary] = useState(null);
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

  // Cyclone-risk diagnostics. Depth-integrated, so this does not depend on `depth`.
  // A null cell means the column was too shallow to integrate safely -- it is shown as
  // blank, never as a low value, because a low TCHP beside a coast would read as low risk.
  useEffect(() => {
    if (mode !== 'hazard') return undefined;
    let dead = false;
    setHazardLoading(true); setHazardError(null);
    getHazardField({ date: effDate, variable: hazardVar })
      .then((f) => { if (!dead) { setHazardF(f); setHazardLoading(false); } })
      .catch((e) => { if (!dead) { setHazardError(e.message); setHazardLoading(false); } });
    return () => { dead = true; };
  }, [effDate, hazardVar, mode]);

  useEffect(() => {
    if (mode !== 'hazard') return undefined;
    let dead = false;
    getHazardSummary({ date: effDate })
      .then((s) => { if (!dead) setHazardSummary(s); })
      .catch(() => { if (!dead) setHazardSummary(null); });
    return () => { dead = true; };
  }, [effDate, mode]);

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

  const hazardInfo = hazardVariableInfo(hazardVar);
  const shown = mode === 'hazard' ? hazardF : mode === 'model' ? modelF : null;
  const range = useMemo(() => {
    if (mode === 'hazard') {
      if (!hazardF) return null;
      // TCHP has a meaningful physical scale and fixed category breaks, so pin it rather
      // than autoscaling per day -- otherwise two days cannot be compared by eye.
      if (hazardVar === 'tchp') return { min: 0, max: 100 };
      return { min: Math.floor(hazardF.stats.min), max: Math.ceil(hazardF.stats.max) };
    }
    if (!modelF) return null;
    return { min: Math.floor(modelF.stats.min), max: Math.ceil(modelF.stats.max) };
  }, [modelF, hazardF, mode, hazardVar]);
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
        <h2>
          {mode === 'hazard'
            ? `${hazardInfo.label} — North Indian Ocean, ${prettyDate(effDate)}`
            : `Temperature at ${depth}m — North Indian Ocean, ${prettyDate(effDate)}`}
        </h2>
        <div className="map-controls">
          <DateControl date={date} onChange={(d) => { stop(); setDate(d); }} />
          <CompareModeSwitch mode={mode} onChange={setMode} />
        </div>
        {mode === 'hazard' && (
          <div className="map-controls">
            <label className="muted small" htmlFor="hazard-var">Diagnostic</label>
            <select
              id="hazard-var"
              className="select"
              value={hazardVar}
              onChange={(e) => setHazardVar(e.target.value)}
            >
              {HAZARD_VARIABLES.map((v) => (
                <option key={v.id} value={v.id}>{v.label} ({v.unit})</option>
              ))}
            </select>
          </div>
        )}
        {fieldError && <div className="error-box">Failed to load field: {fieldError} <button className="btn small" onClick={() => { cacheRef.current.clear(); stop(); setDate(date); }}>Retry</button></div>}
        <div className="visualization-shell">
          {(mode === 'model' || mode === 'hazard') && shown ? (
            <MapHeatmap
              field={shown}
              mode='sequential'
              fixedRange={range}
              selected={selected} showCoverage={showCoverage} onSelect={setSelected}
            />
          ) : mode === 'hazard' ? (
            <div className="loading-panel" />
          ) : mode !== 'model' ? (
            <div className="loading-panel" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#5d6b7a', fontWeight: 600 }}>
              {fieldUnavailableMessage}
            </div>
          ) : (
            <div className="loading-panel" />
          )}
          {(fieldLoading || hazardLoading) && (mode === 'model' || mode === 'hazard') && (
            <div className="loading-overlay"><span>Updating visualization…</span></div>
          )}
        </div>
        {mode === 'hazard'
          ? (
            <div className="notice" style={{ marginTop: 8 }}>
              {hazardInfo.label} is integrated over the full 0&#8211;1000 m column, so the depth
              slider does not apply. Switch back to OceanEmbed to choose a depth.
            </div>
          )
          : <DepthSlider depth={depth} onChange={(d) => { stop(); setDepth(d); }} />}
        {hazardError && mode === 'hazard' && (
          <div className="error-box">Failed to load the cyclone diagnostics: {hazardError}</div>
        )}
        {mode === 'hazard' && hazardSummary && hazardSummary.status !== 'available' && (
          <div className="notice">
            Cyclone diagnostics are unavailable for this date. No values are shown rather than substitutes.
          </div>
        )}
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
          {mode === 'hazard' && 'Showing a cyclone-relevant diagnostic derived from the reconstruction.'}
          {mode === 'glorys' && 'Showing selected-point GLORYS comparison.'}
          {mode === 'diff' && 'Showing selected-point difference at the chosen location.'}
          {' '}Click map to select a profile location.
        </div>
        {mode === 'hazard' && hazardSummary && hazardSummary.status === 'available' && (
          <div className="comparison-card">
            <div className="comparison-head">
              <span>Cyclone-relevant counts for {prettyDate(hazardSummary.date)}</span>
              <strong>{(hazardSummary.coverage * 100).toFixed(1)}% of grid cells</strong>
            </div>
            <div className="comparison-grid">
              <div className="comparison-stat">
                <span>Favourable for intensification</span>
                <strong>{hazardSummary.favourableCells.toLocaleString()}</strong>
                <div className="muted small" style={{ marginTop: 4 }}>cells with TCHP &#8805; 50 kJ/cm&#178;</div>
              </div>
              <div className="comparison-stat highlight">
                <span>Rapid-intensification potential</span>
                <strong>{hazardSummary.rapidIntensificationCells.toLocaleString()}</strong>
                <div className="muted small" style={{ marginTop: 4 }}>cells with TCHP &#8805; 80 kJ/cm&#178;</div>
              </div>
              <div className="comparison-stat">
                <span>Median TCHP</span>
                <strong>
                  {(() => {
                    const t = hazardSummary.metrics.find((m) => m.variable === 'tchp');
                    return t && t.median != null ? `${t.median.toFixed(1)} kJ/cm\u00b2` : 'Unavailable';
                  })()}
                </strong>
              </div>
              <div className="comparison-stat">
                <span>Cells with a value</span>
                <strong>{hazardSummary.validCells.toLocaleString()} / {hazardSummary.totalCells.toLocaleString()}</strong>
                <div className="muted small" style={{ marginTop: 4 }}>
                  columns shallower than {hazardSummary.minValidDepthM}m are excluded
                </div>
              </div>
            </div>
            {hazardF && hazardF.caveat && (
              <div className="notice" style={{ marginTop: 8 }}>
                <strong>Diagnostic, not an operational hazard forecast.</strong> {hazardF.caveat}
              </div>
            )}
          </div>
        )}
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
            <SkillMetricCard label="RMSE" value={skill.rmse == null ? '—' : skill.rmse.toFixed(2)} unit=" °C" />
            <SkillMetricCard label="Correlation" value={skill.correlation == null ? '—' : skill.correlation.toFixed(3)} unit="" />
            <SkillMetricCard label="Bias" value={skill.bias == null ? '—' : skill.bias.toFixed(2)} unit=" °C" />
          </div>
        ) : (
          <div className="notice">Validation metrics available in Validate.</div>
        )}
        <div className="muted small">Trust context from independent validation — see Validate view for full table.</div>
      </aside>
    </div>
  );
}

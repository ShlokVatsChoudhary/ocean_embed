import { useEffect, useMemo, useState } from 'react';
import MapHeatmap from '../components/MapHeatmap';
import { DepthSlider, DateControl, SkillMetricCard } from '../components/controls';
import { DepthPerformanceChart, ArgoScatter } from '../components/charts';
import { getTemperatureField, getComparison, getSkillMetrics, getArgoFloats, getArgoValidationSummary, getArgoScatter, getArgoTimeInfo, prettyDate } from '../api/oceanembed';

export default function ValidateView({ date, setDate, depth, setDepth, selected, setSelected }) {
  const [sortKey, setSortKey] = useState('depth');
  const [sortAsc, setSortAsc] = useState(true);
  const [metrics, setMetrics] = useState([]);
  const [metricsError, setMetricsError] = useState(null);
  const [modelF, setModelF] = useState(null);
  const [fieldError, setFieldError] = useState(null);
  const [fieldLoading, setFieldLoading] = useState(true);
  const [floats, setFloats] = useState([]);
  const [summary, setSummary] = useState(null);
  const [scatter, setScatter] = useState([]);
  const [argoTime, setArgoTime] = useState(null);
  const [glorysPoint, setGlorysPoint] = useState(null);

  useEffect(() => {
    let dead = false;
    getSkillMetrics()
      .then((m) => { if (!dead) setMetrics(m); })
      .catch((e) => { if (!dead) setMetricsError(e.message); });
    getArgoValidationSummary().then((s) => { if (!dead) setSummary(s); }).catch(() => {});
    getArgoScatter().then((p) => { if (!dead) setScatter(p); }).catch(() => {});
    return () => { dead = true; };
  }, []);

  // ARGO is a 10-day analysis, so report which analysis time each model date maps to.
  useEffect(() => {
    let dead = false;
    getArgoTimeInfo({ date }).then((t) => { if (!dead) setArgoTime(t); }).catch(() => {});
    return () => { dead = true; };
  }, [date]);

  useEffect(() => {
    let dead = false;
    setFieldLoading(true); setFieldError(null);
    Promise.all([
      getTemperatureField({ date, depth }),
      getArgoFloats({ date }),
    ]).then(([m, f]) => {
      if (dead) return;
      setModelF(m);
      setFloats(f);
      setFieldLoading(false);
    }).catch((e) => { if (!dead) { setFieldError(e.message); setFieldLoading(false); } });
    return () => { dead = true; };
  }, [date, depth]);

  // Point comparison against GLORYS for the currently selected location.
  useEffect(() => {
    if (!selected || !Number.isFinite(selected.lat) || !Number.isFinite(selected.lon)) {
      setGlorysPoint(null);
      return;
    }
    let dead = false;
    getComparison({ latitude: selected.lat, longitude: selected.lon, date, depth })
      .then((c) => { if (!dead) setGlorysPoint(c); })
      .catch(() => { if (!dead) setGlorysPoint(null); });
    return () => { dead = true; };
  }, [selected, date, depth]);

  const sorted = useMemo(() => {
    const arr = [...metrics];
    arr.sort((a, b) => (sortAsc ? a[sortKey] - b[sortKey] : b[sortKey] - a[sortKey]));
    return arr;
  }, [metrics, sortKey, sortAsc]);
  // A stable colour scale so the prediction and ARGO-overlay panels below are comparable.
  const range = useMemo(() => {
    if (!modelF) return null;
    return { min: Math.floor(modelF.stats.min), max: Math.ceil(modelF.stats.max) };
  }, [modelF]);
  // The ARGO reference is a 1-degree product upsampled onto the 0.25-degree grid, so there
  // can be ~9,000 observed cells. Drawing every one is slow and visually solid, so thin them
  // out for the map while still reporting the true count.
  const markers = useMemo(() => {
    const MAX_MARKERS = 900;
    const step = Math.max(1, Math.ceil(floats.length / MAX_MARKERS));
    return floats.filter((_, i) => i % step === 0).map((f) => ({ lat: f.lat, lon: f.lon, kind: 'argo' }));
  }, [floats]);

  const th = (key, label) => (
    <th><button className="th-sort" onClick={() => { if (sortKey === key) setSortAsc(!sortAsc); else { setSortKey(key); setSortAsc(true); } }}>
      {label} {sortKey === key ? (sortAsc ? '▲' : '▼') : ''}
    </button></th>
  );

  return (
    <div>
      <section className="panel">
        <h2>Skill metrics by depth (ARGO — independent, never used in training)</h2>
        {metricsError && <div className="error-box">Failed to load skill metrics: {metricsError}</div>}
        {metrics.length === 0 && !metricsError && <div className="loading">Loading skill metrics…</div>}
        {metrics.length > 0 && (
          <div className="table-wrap">
            <table className="skill-table">
              <thead><tr><th>Depth (m)</th>{th('rmse', 'RMSE (°C)')}{th('mae', 'MAE (°C)')}{th('bias', 'Bias (°C)')}{th('correlation', 'Correlation')}</tr></thead>
              <tbody>
                {sorted.map((m) => (
                  <tr key={m.depth} className={m.depth === depth ? 'row-hl' : ''}>
                    <td>{m.depth}</td>
                    <td>{m.rmse == null ? '—' : m.rmse.toFixed(3)}</td>
                    <td>{m.mae == null ? '—' : m.mae.toFixed(3)}</td>
                    <td>{m.bias == null ? '—' : m.bias.toFixed(3)}</td>
                    <td>{m.correlation == null ? '—' : m.correlation.toFixed(3)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
      <div className="explore-grid" style={{ marginTop: 12 }}>
        <section className="panel">
          <h3>Depth-wise performance</h3>
          {metrics.length > 0 ? <DepthPerformanceChart metrics={metrics} /> : <div className="loading">Loading…</div>}
          <div className="muted small">RMSE typically grows through the thermocline and at depth — check the table for exact values.</div>
        </section>
        <aside className="panel">
          <h3>ARGO validation summary</h3>
          {summary ? (
            <>
              <div className="metric-row">
                <SkillMetricCard label="ARGO profiles" value={summary.nProfiles == null ? 'Unavailable' : summary.nProfiles.toLocaleString()} />
                <SkillMetricCard label="Mean |error|" value={summary.meanError == null ? 'Unavailable' : summary.meanError.toFixed(2)} unit={summary.meanError == null ? '' : ' °C'} />
                <SkillMetricCard label="Correlation" value={summary.correlation == null ? 'Unavailable' : summary.correlation.toFixed(3)} />
              </div>
              <div className="metric-row">
                <SkillMetricCard label="RMSE (all depths)" value={summary.rmse == null ? 'Unavailable' : summary.rmse.toFixed(2)} unit={summary.rmse == null ? '' : ' °C'} />
                <SkillMetricCard label="Observations" value={summary.nObservations == null ? 'Unavailable' : summary.nObservations.toLocaleString()} />
              </div>
              <div className="muted small">Date range: {summary.dateRange}</div>
              {summary.referenceKind && <div className="muted small">Reference type: {summary.referenceKind.replace(/_/g, ' ')}</div>}
              {argoTime?.timeOffsetDays != null && (
                <div className="muted small">
                  Nearest ARGO analysis: {argoTime.argoDate} ({argoTime.timeOffsetDays >= 0 ? '+' : ''}{argoTime.timeOffsetDays} days)
                </div>
              )}
              {summary.caveat && <div className="notice small">{summary.caveat}</div>}
            </>
          ) : (
            <div className="notice">Validation metrics are not available yet.</div>
          )}
          <h3 style={{ marginTop: 12 }}>Predicted vs observed</h3>
          {scatter.length > 0 ? <ArgoScatter points={scatter} /> : <div className="loading">Loading…</div>}
        </aside>
      </div>
      <section className="panel" style={{ marginTop: 12 }}>
        <h2>Spatial error maps — {depth}m, {prettyDate(date)}</h2>
        <div className="map-controls">
          <DateControl date={date} onChange={setDate} />
        </div>
        <DepthSlider depth={depth} onChange={setDepth} />
        {fieldLoading && <div className="loading">Loading error maps…</div>}
        {fieldError && <div className="error-box">Failed to load fields: {fieldError}</div>}
        {!fieldLoading && !fieldError && modelF && (
          <div className="quad-grid">
            <div><h4>Prediction (OceanEmbed)</h4><MapHeatmap field={modelF} fixedRange={range} selected={selected} onSelect={setSelected} height={280} /></div>
            <div>
              <h4>GLORYS reference (selected point)</h4>
              {glorysPoint ? (
                <>
                  <div className="metric-row">
                    <SkillMetricCard label="OceanEmbed" value={glorysPoint.oceanembed_temperature == null ? '—' : glorysPoint.oceanembed_temperature.toFixed(2)} unit={glorysPoint.oceanembed_temperature == null ? '' : ' °C'} />
                    <SkillMetricCard label="GLORYS" value={glorysPoint.glorys_temperature == null ? '—' : glorysPoint.glorys_temperature.toFixed(2)} unit={glorysPoint.glorys_temperature == null ? '' : ' °C'} />
                    <SkillMetricCard label="Difference" value={glorysPoint.difference == null ? '—' : glorysPoint.difference.toFixed(2)} unit={glorysPoint.difference == null ? '' : ' °C'} />
                  </div>
                  <div className="muted small">At {glorysPoint.latitude.toFixed(2)}°N, {glorysPoint.longitude.toFixed(2)}°E · {glorysPoint.depth}m · {prettyDate(glorysPoint.date)}</div>
                  <div className="muted small">{glorysPoint.glorys_provenance}</div>
                </>
              ) : (
                <div className="notice">Select a point on the map to read the model-versus-GLORYS comparison. A full gridded GLORYS field is not exposed by the API.</div>
              )}
            </div>
            <div>
              <h4>Difference</h4>
              <div className="notice">
                A gridded difference map needs a gridded reference. The API exposes GLORYS at a point
                (shown alongside) and ARGO on a 1° analysis grid, so differences are reported per
                observation rather than as a full field.
              </div>
            </div>
            <div>
              <h4>ARGO overlay ({markers.length} observed cells)</h4>
              <MapHeatmap field={modelF} fixedRange={range} markers={markers} selected={selected} onSelect={setSelected} showCoverage height={280} />
              <div className="muted small">Markers are ARGO analysis cells, not individual floats: the bundled reference is a 1° gridded product.</div>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}

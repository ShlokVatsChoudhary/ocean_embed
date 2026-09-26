import { useEffect, useMemo, useState } from 'react';
import MapHeatmap from '../components/MapHeatmap';
import { DepthSlider, DateControl, SkillMetricCard } from '../components/controls';
import { DepthPerformanceChart, ArgoScatter } from '../components/charts';
import { getTemperatureField, getSkillMetrics, getArgoFloats, getArgoValidationSummary, getArgoScatter, prettyDate } from '../api/oceanembed';

function diffField(a, b) {
  return { ...a, values: a.values.map((row, i) => row.map((v, j) => +(v - b.values[i][j]).toFixed(3))), stats: { min: -2.5, max: 2.5 }, source: 'error' };
}

export default function ValidateView({ date, setDate, depth, setDepth, selected, setSelected }) {
  const [sortKey, setSortKey] = useState('depth');
  const [sortAsc, setSortAsc] = useState(true);
  const [metrics, setMetrics] = useState([]);
  const [metricsError, setMetricsError] = useState(null);
  const [modelF, setModelF] = useState(null);
  const [glorysF, setGlorysF] = useState(null);
  const [fieldError, setFieldError] = useState(null);
  const [fieldLoading, setFieldLoading] = useState(true);
  const [floats, setFloats] = useState([]);
  const [summary, setSummary] = useState(null);
  const [scatter, setScatter] = useState([]);

  useEffect(() => {
    let dead = false;
    getSkillMetrics()
      .then((m) => { if (!dead) setMetrics(m); })
      .catch((e) => { if (!dead) setMetricsError(e.message); });
    getArgoValidationSummary().then((s) => { if (!dead) setSummary(s); }).catch(() => {});
    getArgoScatter().then((p) => { if (!dead) setScatter(p); }).catch(() => {});
    return () => { dead = true; };
  }, []);

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

  const sorted = useMemo(() => {
    const arr = [...metrics];
    arr.sort((a, b) => (sortAsc ? a[sortKey] - b[sortKey] : b[sortKey] - a[sortKey]));
    return arr;
  }, [metrics, sortKey, sortAsc]);
  const diffF = useMemo(() => (modelF && glorysF ? diffField(modelF, glorysF) : null), [modelF, glorysF]);
  const range = useMemo(() => {
    if (!modelF || !glorysF) return null;
    const lo = Math.min(modelF.stats.min, glorysF.stats.min);
    const hi = Math.max(modelF.stats.max, glorysF.stats.max);
    return { min: Math.floor(lo), max: Math.ceil(hi) };
  }, [modelF, glorysF]);
  const markers = floats.map((f) => ({ lat: f.lat, lon: f.lon, kind: 'argo' }));

  const th = (key, label) => (
    <th><button className="th-sort" onClick={() => { if (sortKey === key) setSortAsc(!sortAsc); else { setSortKey(key); setSortAsc(true); } }}>
      {label} {sortKey === key ? (sortAsc ? '▲' : '▼') : ''}
    </button></th>
  );

  return (
    <div>
      <section className="panel">
        <h2>Skill metrics by depth (vs independent reference)</h2>
        {metricsError && <div className="error-box">Failed to load skill metrics: {metricsError}</div>}
        {metrics.length === 0 && !metricsError && <div className="loading">Loading skill metrics…</div>}
        {metrics.length > 0 && (
          <div className="table-wrap">
            <table className="skill-table">
              <thead><tr><th>Depth (m)</th>{th('rmse', 'RMSE (°C)')}{th('mae', 'MAE (°C)')}{th('bias', 'Bias (°C)')}{th('correlation', 'Correlation')}</tr></thead>
              <tbody>
                {sorted.map((m) => (
                  <tr key={m.depth} className={m.depth === depth ? 'row-hl' : ''}>
                    <td>{m.depth}</td><td>{m.rmse.toFixed(3)}</td><td>{m.mae.toFixed(3)}</td><td>{m.bias.toFixed(3)}</td><td>{m.correlation.toFixed(3)}</td>
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
          <div className="metric-row">
            <SkillMetricCard label="ARGO profiles" value={summary ? summary.nProfiles.toLocaleString() : '…'} />
            <SkillMetricCard label="Mean |error|" value={summary ? summary.meanError.toFixed(2) : '…'} unit=" °C" />
            <SkillMetricCard label="Correlation" value={summary ? summary.correlation.toFixed(3) : '…'} />
          </div>
          <div className="muted small">Date range: {summary ? summary.dateRange : '…'}</div>
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
        {!fieldLoading && !fieldError && modelF && glorysF && diffF && (
          <div className="quad-grid">
            <div><h4>Prediction (OceanEmbed)</h4><MapHeatmap field={modelF} fixedRange={range} selected={selected} onSelect={setSelected} height={280} /></div>
            <div><h4>GLORYS reference</h4><MapHeatmap field={glorysF} fixedRange={range} selected={selected} onSelect={setSelected} height={280} /></div>
            <div><h4>Error (model − GLORYS)</h4><MapHeatmap field={diffF} mode="diverging" fixedRange={{ min: -2.5, max: 2.5 }} selected={selected} onSelect={setSelected} height={280} /></div>
            <div><h4>ARGO overlay</h4><MapHeatmap field={modelF} fixedRange={range} markers={markers} selected={selected} onSelect={setSelected} height={280} /></div>
          </div>
        )}
      </section>
    </div>
  );
}

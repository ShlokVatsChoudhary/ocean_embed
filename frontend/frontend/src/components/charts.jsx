import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, ScatterChart, Scatter, ReferenceLine } from 'recharts';

// Legend sits on top so it can never collide with the x-axis title at the bottom.
// Axis titles get explicit offsets (dy/dx) plus matching chart margins.
const TOP_LEGEND = { verticalAlign: 'top', align: 'center', wrapperStyle: { fontSize: 12, paddingBottom: 4 } };
const TICK = { fontSize: 11 };

// VerticalProfileChart: temperature (x) vs depth (y, 0 top). Series: model, argo, glorys.
export function VerticalProfileChart({ profile, showGlorys = true, height = 380 }) {
  if (!profile) return <div className="muted">No profile.</div>;
  const data = profile.depths.map((d, i) => ({
    depth: d,
    OceanEmbed: profile.oceanembed[i],
    ...(showGlorys ? { GLORYS: profile.glorys[i] } : {}),
    ...(profile.argo ? { ARGO: profile.argo[i] } : {}),
  }));
  return (
    <div>
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={data} layout="vertical" margin={{ top: 24, right: 20, bottom: 36, left: 36 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis
            type="number" domain={['auto', 'auto']} tick={TICK}
            label={{ value: 'Temperature (°C)', position: 'bottom', offset: 18, fontSize: 12 }}
          />
          <YAxis
            type="number" dataKey="depth" reversed domain={[0, 1000]} tick={TICK}
            label={{ value: 'Depth (m)', angle: -90, position: 'left', offset: 12, fontSize: 12 }}
          />
          <Tooltip formatter={(v) => [`${v} °C`]} labelFormatter={(d) => `${d} m`} />
          <Legend {...TOP_LEGEND} />
          <Line type="monotone" dataKey="OceanEmbed" stroke="#0b5fff" strokeWidth={2.5} dot={{ r: 3 }} connectNulls />
          {showGlorys && <Line type="monotone" dataKey="GLORYS" stroke="#0a8a3c" strokeWidth={1.8} strokeDasharray="6 3" dot={false} connectNulls />}
          {profile.argo && <Line type="monotone" dataKey="ARGO" stroke="#d62728" strokeWidth={1.8} strokeDasharray="2 3" dot={{ r: 3 }} connectNulls />}
        </LineChart>
      </ResponsiveContainer>
      {!profile.argo && <div className="muted small">No ARGO profile at this location/date — showing model + GLORYS only.</div>}
    </div>
  );
}

export function DepthPerformanceChart({ metrics }) {
  const data = metrics.map((m) => ({ depth: m.depth, RMSE: m.rmse, Bias: Math.abs(m.bias) }));
  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={data} margin={{ top: 24, right: 20, bottom: 36, left: 36 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis
          dataKey="depth" tick={TICK}
          label={{ value: 'Depth (m)', position: 'bottom', offset: 18, fontSize: 12 }}
        />
        <YAxis
          tick={TICK}
          label={{ value: 'Error (°C)', angle: -90, position: 'left', offset: 12, fontSize: 12 }}
        />
        <Tooltip />
        <Legend {...TOP_LEGEND} />
        <Line type="monotone" dataKey="RMSE" stroke="#d62728" strokeWidth={2} dot={{ r: 3 }} />
        <Line type="monotone" dataKey="Bias" stroke="#ff7f0e" strokeWidth={2} strokeDasharray="5 3" dot={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}

export function ArgoScatter({ points }) {
  const min = Math.floor(Math.min(...points.map((p) => Math.min(p.obs, p.pred))));
  const max = Math.ceil(Math.max(...points.map((p) => Math.max(p.obs, p.pred))));
  return (
    <ResponsiveContainer width="100%" height={300}>
      <ScatterChart margin={{ top: 24, right: 20, bottom: 36, left: 36 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis
          type="number" dataKey="obs" name="Observed" domain={[min, max]} tick={TICK}
          label={{ value: 'ARGO observed (°C)', position: 'bottom', offset: 18, fontSize: 12 }}
        />
        <YAxis
          type="number" dataKey="pred" name="Predicted" domain={[min, max]} tick={TICK}
          label={{ value: 'Predicted (°C)', angle: -90, position: 'left', offset: 12, fontSize: 12 }}
        />
        <Tooltip cursor={{ strokeDasharray: '3 3' }} />
        <Legend {...TOP_LEGEND} />
        <Scatter name="Pred vs Obs" data={points} fill="#0b5fff" opacity={0.55} />
        <ReferenceLine segment={[{ x: min, y: min }, { x: max, y: max }]} stroke="#333" strokeDasharray="5 4" label={{ value: '1:1', fontSize: 11, position: 'insideTopRight' }} />
      </ScatterChart>
    </ResponsiveContainer>
  );
}

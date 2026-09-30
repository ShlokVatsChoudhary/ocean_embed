import { useValidation, fmt } from '../state';

// Validation drawer. The console does not ask the user to visit a separate tab
// for the evidence; it slides in over whatever they were looking at.
export default function ValidationDrawer({ onClose }) {
  const { data, loading } = useValidation();
  const s = data?.summary;
  const perDepth = data?.perDepth ?? [];
  const scatter = data?.scatter ?? [];

  const worst = perDepth.reduce((a, m) => (m.rmse !== null && (!a || m.rmse > a.rmse) ? m : a), null);

  return (
    <>
      <div className="scrim" onClick={onClose} />
      <div className="drawer" role="dialog" aria-modal="true" aria-label="Validation against independent ARGO">
        <header>
          <h2>Validation</h2>
          <span className="pill"><span className={`dot ${s?.status === 'available' ? 'ok' : 'warn'}`} />{s?.status ?? 'loading'}</span>
          <button className="ghost" style={{ marginLeft: 'auto' }} onClick={onClose}>Close</button>
        </header>

        <div className="body">
          {loading && <div className="empty"><span className="spin" /> &nbsp;Running the model over the validation window…</div>}

          {!loading && s && (
            <>
              <div className="tiles" style={{ marginBottom: 14 }}>
                <div className="tile"><span>All depths RMSE</span><b>{fmt.num(s.rmse, 3)}<i>°C</i></b></div>
                <div className="tile"><span>Correlation</span><b>{fmt.num(s.correlation, 3)}</b></div>
                <div className="tile"><span>Mean error</span><b>{fmt.num(s.meanError, 3)}<i>°C</i></b></div>
                <div className="tile"><span>Observations</span><b>{fmt.int(s.nObservations)}</b></div>
              </div>

              <div className="kv" style={{ marginBottom: 12 }}>
                <dt>Window</dt><dd>{s.dateRange}</dd>
                <dt>Reference</dt><dd>{s.reference}</dd>
                <dt>Reference kind</dt><dd>{s.referenceKind || '—'}</dd>
                <dt>Model</dt><dd>{s.modelVersion}</dd>
              </div>

              {s.provenance && <div className="note" style={{ marginBottom: 10 }}>{s.provenance}</div>}
              {s.caveat && <div className="note warn" style={{ marginBottom: 14 }}>{s.caveat}</div>}

              <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 6 }}>
                <span className="tag">per depth</span>
                {worst && <span style={{ fontSize: 11.5, color: 'var(--dim)' }}>
                  largest error {fmt.num(worst.rmse, 2)} °C at {worst.depth} m — the thermocline, as physics predicts
                </span>}
              </div>

              <table className="grid">
                <thead>
                  <tr>
                    <th>Depth (m)</th><th>RMSE</th><th>MAE</th><th>Bias</th><th>Corr</th><th>n</th>
                  </tr>
                </thead>
                <tbody>
                  {perDepth.map((m) => (
                    <tr key={m.depth}>
                      <td>{m.depth}</td>
                      <td className="lit">{fmt.num(m.rmse, 3)}</td>
                      <td>{fmt.num(m.mae, 3)}</td>
                      <td style={{ color: m.bias < 0 ? 'var(--blue)' : 'var(--warn)' }}>{fmt.num(m.bias, 3)}</td>
                      <td>{fmt.num(m.correlation, 3)}</td>
                      <td>{fmt.int(m.n)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>

              <ScatterPlot points={scatter} />

              <div className="note" style={{ marginTop: 14 }}>
                The model is scored against a <b>1° ten-day ARGO analysis</b>, not its own training
                target, and ARGO is never used in training. The raw pair count overstates the
                independent sample: at 1° there are roughly 600 independent locations in this domain.
              </div>
            </>
          )}

          {!loading && !s && (
            <div className="empty">Validation endpoint unavailable. The console shows nothing rather than a placeholder number.</div>
          )}
        </div>
      </div>
    </>
  );
}

function ScatterPlot({ points }) {
  if (!points?.length) return null;
  const W = 300, H = 190, pad = 26;
  const vals = points.flatMap((p) => [p.obs, p.pred]).filter((v) => Number.isFinite(v));
  if (!vals.length) return null;
  const lo = Math.min(...vals);
  const hi = Math.max(...vals);
  const xOf = (v) => pad + ((v - lo) / Math.max(1e-9, hi - lo)) * (W - pad - 8);
  const yOf = (v) => H - pad - ((v - lo) / Math.max(1e-9, hi - lo)) * (H - pad - 10);

  return (
    <div style={{ marginTop: 16 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 4 }}>
        <span className="tag grey">model vs ARGO</span>
        <span style={{ fontSize: 11.5, color: 'var(--dim)' }}>{points.length} sampled pairs</span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H} role="img" aria-label="Predicted against observed scatter">
        <rect x={pad} y={10} width={W - pad - 8} height={H - pad - 10} fill="var(--sunk)" stroke="var(--line)" />
        <line x1={xOf(lo)} y1={yOf(lo)} x2={xOf(hi)} y2={yOf(hi)} stroke="var(--faint)" strokeWidth="1" strokeDasharray="4 3" />
        {points.map((p, i) => (
          <circle key={i} cx={xOf(p.obs)} cy={yOf(p.pred)} r="2.1" fill="var(--accent)" opacity="0.5" />
        ))}
        <text x={pad} y="8" fontSize="9" fontFamily="var(--mono)" fill="var(--faint)">predicted</text>
        <text x={W - 10} y={H - 6} fontSize="9" textAnchor="end" fontFamily="var(--mono)" fill="var(--faint)">observed °C</text>
      </svg>
    </div>
  );
}

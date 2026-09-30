import { STANDARD_DEPTHS } from '../api/oceanembed';

// A hand-rolled SVG profile so the console keeps zero chart dependencies and can
// draw the depth axis on the same even-band scale as the section panel.
//
// Depth increases to the right, temperature to the left — the orientation
// physical oceanographers actually read, and the opposite of the original
// dashboard's chart.

const TICKS = [0, 50, 100, 200, 300, 500, 700, 1000];

export default function ProfileChart({ depths, model, glorys, depthCursor = null, height = 168 }) {
  const W = 300;
  const H = height;
  const padL = 30, padR = 8, padT = 8, padB = 20;
  const plotW = W - padL - padR;
  const plotH = H - padT - padB;

  const finite = [...(model || []), ...(glorys || [])].filter((v) => v !== null && v !== undefined && Number.isFinite(Number(v)));
  if (!depths?.length || !finite.length) {
    return <div className="empty">Select a point on the map to read its column.</div>;
  }
  const lo = Math.min(...finite);
  const hi = Math.max(...finite);
  const pad = Math.max(0.6, (hi - lo) * 0.08);
  const tmin = lo - pad;
  const tmax = hi + pad;

  const xOf = (t) => padL + ((t - tmin) / Math.max(1e-9, tmax - tmin)) * plotW;
  const yOf = (d) => {
    const i = STANDARD_DEPTHS.indexOf(d);
    const band = i < 0 ? STANDARD_DEPTHS.length - 1 : i;
    return padT + (band / (STANDARD_DEPTHS.length - 1)) * plotH;
  };

  const path = (vals) => {
    let out = '';
    let started = false;
    depths.forEach((d, k) => {
      const v = vals?.[k];
      if (v === null || v === undefined || !Number.isFinite(Number(v))) { started = false; return; }
      out += `${started ? 'L' : 'M'}${xOf(Number(v)).toFixed(2)},${yOf(d).toFixed(2)} `;
      started = true;
    });
    return out.trim();
  };

  const modelPath = path(model);
  const glorysPath = glorys ? path(glorys) : '';

  // The 26 °C isotherm is the cyclone-fuel threshold, worth drawing whenever it is in range.
  const show26 = tmin <= 26 && tmax >= 26;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H} role="img" aria-label="Temperature against depth">
      {TICKS.map((d) => (
        <g key={d}>
          <line x1={padL} y1={yOf(d)} x2={W - padR} y2={yOf(d)} stroke="var(--line)" strokeWidth="1" />
          <text x={padL - 5} y={yOf(d) + 3} textAnchor="end" fontSize="9" fontFamily="var(--mono)" fill="var(--faint)">{d}</text>
        </g>
      ))}

      {[tmin + (tmax - tmin) * 0.25, tmin + (tmax - tmin) * 0.5, tmin + (tmax - tmin) * 0.75].map((t, i) => (
        <g key={i}>
          <line x1={xOf(t)} y1={padT} x2={xOf(t)} y2={padT + plotH} stroke="var(--line)" strokeWidth="1" opacity="0.5" />
          <text x={xOf(t)} y={H - 6} textAnchor="middle" fontSize="9" fontFamily="var(--mono)" fill="var(--faint)">{t.toFixed(1)}</text>
        </g>
      ))}

      {show26 && (
        <>
          <line x1={xOf(26)} y1={padT} x2={xOf(26)} y2={padT + plotH} stroke="var(--warn)" strokeWidth="1" strokeDasharray="3 3" opacity="0.6" />
          <text x={xOf(26) + 3} y={padT + 9} fontSize="8.5" fontFamily="var(--mono)" fill="var(--warn)" opacity="0.9">26°C</text>
        </>
      )}

      {glorysPath && <path d={glorysPath} fill="none" stroke="var(--ok)" strokeWidth="1.5" strokeDasharray="5 3" strokeLinecap="round" />}
      {modelPath && <path d={modelPath} fill="none" stroke="var(--accent)" strokeWidth="2.2" strokeLinecap="round" />}

      {depthCursor !== null && STANDARD_DEPTHS.includes(depthCursor) && (
        <>
          <line x1={padL} y1={yOf(depthCursor)} x2={W - padR} y2={yOf(depthCursor)} stroke="var(--text)" strokeWidth="1" opacity="0.28" />
          {(() => {
            const k = depths.indexOf(depthCursor);
            const v = k >= 0 ? model?.[k] : null;
            if (v === null || v === undefined || !Number.isFinite(Number(v))) return null;
            return <circle cx={xOf(Number(v))} cy={yOf(depthCursor)} r="3.4" fill="var(--accent)" stroke="var(--panel)" strokeWidth="1.5" />;
          })()}
        </>
      )}

      <line x1={padL} y1={padT} x2={padL} y2={padT + plotH} stroke="var(--line-lit)" strokeWidth="1" />
      <text x={padL} y={H - 6} fontSize="9" fontFamily="var(--mono)" fill="var(--faint)">°C</text>
    </svg>
  );
}

// Colour ramps + canvas theme tokens for the console.
//
// These are tuned for a dark ground: the cold end of the temperature ramp stays
// clearly above the panel background so a 2 °C difference near 17 °C is still
// visible, which the original light-blue ramp was not.

export const TOKENS = {
  land: '#0b1620',
  coast: '#2c4a5e',
  grid: 'rgba(120, 175, 205, 0.13)',
  gridMajor: 'rgba(120, 175, 205, 0.22)',
  label: '#6f8ea3',
  labelMajor: '#8fb0c6',
  bg: '#060e17',
  missing: '#0a1723',
  hover: '#ffffff',
  select: '#2fe0c0',
  argo: '#ffb020',
  argoRing: '#04121a',
  font: '11px ui-monospace, "SF Mono", Menlo, monospace',
  fontBold: '600 11px ui-monospace, "SF Mono", Menlo, monospace',
};

// Cold -> hot, readable on a dark panel.
export const SEQ = [
  [0.00, [11, 43, 82]],
  [0.14, [21, 96, 168]],
  [0.30, [47, 159, 208]],
  [0.45, [95, 211, 208]],
  [0.58, [168, 230, 160]],
  [0.72, [255, 224, 102]],
  [0.86, [255, 159, 69]],
  [1.00, [255, 77, 77]],
];

// Difference: the zero band is close to the panel colour so "no difference"
// genuinely disappears instead of glowing.
export const DIV = [
  [0.00, [42, 157, 255]],
  [0.34, [27, 95, 158]],
  [0.50, [18, 30, 40]],
  [0.66, [168, 84, 31]],
  [1.00, [255, 107, 61]],
];

export function rampColor(stops, t) {
  const x = Math.min(1, Math.max(0, Number.isFinite(t) ? t : 0));
  for (let i = 1; i < stops.length; i++) {
    if (x <= stops[i][0]) {
      const [t0, c0] = stops[i - 1];
      const [t1, c1] = stops[i];
      const f = (x - t0) / Math.max(1e-9, t1 - t0);
      return `rgb(${Math.round(c0[0] + (c1[0] - c0[0]) * f)},${Math.round(c0[1] + (c1[1] - c0[1]) * f)},${Math.round(c0[2] + (c1[2] - c0[2]) * f)})`;
    }
  }
  const c = stops[stops.length - 1][1];
  return `rgb(${c[0]},${c[1]},${c[2]})`;
}

export const seqColor = (t) => rampColor(SEQ, t);
export const divColor = (t) => rampColor(DIV, t);

export const seqStops = (n = 40) => Array.from({ length: n }, (_, i) => seqColor(i / (n - 1)));
export const divStops = (n = 40) => Array.from({ length: n }, (_, i) => divColor(i / (n - 1)));

// Discrete cyclone-fuel categories, pale -> hot. Matches the backend breaks
// [30, 50, 80] kJ/cm² so the legend can never disagree with the payload.
export const CAT_COLOURS = ['#1d4a6b', '#2f8fb5', '#ffb020', '#ff4d4d'];
export const CAT_LABELS = ['< 30 low', '30–50 moderate', '50–80 favourable', '> 80 rapid'];

export function catIndex(v, breaks = [30, 50, 80]) {
  // `Number(null) === 0` and `Number('') === 0`, so a missing value would land in the
  // lowest band and be painted as "low risk". A cell with no data must never be
  // rendered as a safe one, so reject those explicitly before coercing.
  if (v === null || v === undefined || v === '') return -1;
  if (!Number.isFinite(Number(v))) return -1;
  const x = Number(v);
  let i = 0;
  while (i < breaks.length && x >= breaks[i]) i += 1;
  return i;
}

// Global range across a set of fields so colours stay stable while scrubbing,
// instead of rescaling on every slice (which makes depth changes unreadable).
export function unionRange(fields) {
  let lo = Infinity;
  let hi = -Infinity;
  fields.forEach((f) => {
    if (!f || !f.stats) return;
    if (Number.isFinite(f.stats.min)) lo = Math.min(lo, f.stats.min);
    if (Number.isFinite(f.stats.max)) hi = Math.max(hi, f.stats.max);
  });
  if (!Number.isFinite(lo) || !Number.isFinite(hi) || hi <= lo) return null;
  return { min: lo, max: hi };
}

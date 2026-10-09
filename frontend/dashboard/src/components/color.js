// Shared color ramps. Sequential cold->warm; diverging blue-white-red centered on 0.

// The canvas renderer paints with colours it cannot get from CSS directly, so it
// resolves the theme tokens once per repaint. Fallbacks mirror the values in
// index.css :root, which means this returns exactly the old hard-coded colours
// unless a theme scope (e.g. src/alt.css) has re-declared them.
export function readTokens(el) {
  const fallback = {
    bg: '#f4f6f8', empty: '#eef2f7', dim: 'rgba(20, 25, 35, 0.42)',
    hatch: 'rgba(255, 255, 255, 0.35)', grid: 'rgba(255, 255, 255, 0.4)',
    axis: '#33414f', marker: '#111111', markerAlert: '#ff3b30',
    markerRing: '#ffffff', focus: '#000000', font: 'system-ui',
  };
  if (typeof window === 'undefined' || !el) return fallback;
  const cs = window.getComputedStyle(el);
  const get = (name, fb) => (cs.getPropertyValue(name) || '').trim() || fb;
  return {
    bg: get('--canvas-bg', fallback.bg),
    empty: get('--canvas-empty', fallback.empty),
    dim: get('--canvas-dim', fallback.dim),
    hatch: get('--canvas-hatch', fallback.hatch),
    grid: get('--canvas-grid', fallback.grid),
    axis: get('--canvas-axis', fallback.axis),
    marker: get('--canvas-marker', fallback.marker),
    markerAlert: get('--canvas-marker-alert', fallback.markerAlert),
    markerRing: get('--canvas-marker-ring', fallback.markerRing),
    focus: get('--canvas-focus', fallback.focus),
    font: get('--font-ui', fallback.font),
  };
}

export function seqColor(t) {
  // t in [0,1]; dark blue -> blue -> cyan -> yellow -> red
  const stops = [
    [0.0, [49, 54, 149]], [0.25, [69, 117, 180]], [0.45, [116, 173, 209]],
    [0.6, [171, 217, 233]], [0.72, [255, 255, 191]], [0.84, [253, 174, 97]],
    [0.93, [244, 109, 67]], [1.0, [165, 0, 38]],
  ];
  return ramp(stops, t);
}
export function divColor(t) {
  // t in [0,1] mapped from [-maxAbs, +maxAbs]
  const stops = [
    [0.0, [49, 54, 149]], [0.3, [69, 117, 180]], [0.45, [171, 217, 233]],
    [0.5, [245, 245, 245]], [0.55, [253, 174, 97]], [0.7, [244, 109, 67]], [1.0, [165, 0, 38]],
  ];
  return ramp(stops, t);
}
function ramp(stops, t) {
  const x = Math.min(1, Math.max(0, t));
  for (let i = 1; i < stops.length; i++) {
    if (x <= stops[i][0]) {
      const [t0, c0] = stops[i - 1], [t1, c1] = stops[i];
      const f = (x - t0) / Math.max(1e-9, t1 - t0);
      return `rgb(${Math.round(c0[0] + (c1[0] - c0[0]) * f)},${Math.round(c0[1] + (c1[1] - c0[1]) * f)},${Math.round(c0[2] + (c1[2] - c0[2]) * f)})`;
    }
  }
  const c = stops[stops.length - 1][1];
  return `rgb(${c[0]},${c[1]},${c[2]})`;
}

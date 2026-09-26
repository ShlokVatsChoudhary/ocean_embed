// Shared color ramps. Sequential cold->warm; diverging blue-white-red centered on 0.
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

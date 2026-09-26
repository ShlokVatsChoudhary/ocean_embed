// OceanEmbed data layer — async, backend-ready with local mock fallback.
//
// How it works:
// - Set VITE_API_BASE (see .env.example) to point at the FastAPI backend.
//   When set, every function below tries the backend first and maps the
//   response into the stable UI shapes. On any network/HTTP/mapping error it
//   logs a warning and falls back to the local mock generator, so the UI
//   keeps working while the backend is still a scaffold.
// - When VITE_API_BASE is unset, mocks are used directly (current behaviour).
// - UI shapes are STABLE — components never touch raw backend JSON:
//     field   -> { lats, lons, values, confidence, stats, date, depth, source }
//     profile -> { depths, oceanembed, glorys, argo|null, lat, lon, date }
//     skill   -> [{ depth, rmse, mae, bias, correlation }]
//     floats  -> [{ lat, lon, id }]
//     alerts  -> [{ lat, lon, depth, date, severity, text }]
//
// Proposed backend contract (FastAPI):
//   GET {base}/api/fields?date=YYYY-MM-DD&depth=100&source=oceanembed|glorys
//   GET {base}/api/fields/range?start=..&end=..&depth=..&source=.. -> { fields: [{ date, ...field }] }
//   GET {base}/api/profiles?date=..&lat=..&lon=..
//   GET {base}/api/skill
//   GET {base}/api/argo?date=..
//   GET {base}/api/alerts
//   GET {base}/api/validation/summary, GET {base}/api/validation/scatter?n=..

export const STANDARD_DEPTHS = [0, 10, 20, 30, 50, 75, 100, 125, 150, 200, 300, 500, 700, 850, 1000];
export const BBOX = { latMin: 5, latMax: 30, lonMin: 45, lonMax: 105 };
export const GRID = { nLat: 50, nLon: 60 };
export const MODEL_VERSION = 'oceanembed-v0.3-mock';
export const LAST_UPDATE = '2020-02-15';

const API_BASE = (import.meta.env.VITE_API_BASE || '').replace(/\/$/, '');
export const isBackendEnabled = () => API_BASE.length > 0;
export const getApiBase = () => API_BASE;

async function getJSON(path, params = {}, timeoutMs = 12000) {
  const qs = new URLSearchParams(Object.fromEntries(
    Object.entries(params).filter(([, v]) => v !== undefined && v !== null).map(([k, v]) => [k, String(v)])
  )).toString();
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(`${API_BASE}${path}?${qs}`, { signal: ctrl.signal });
    if (!res.ok) throw new Error(`HTTP ${res.status} from ${path}`);
    return await res.json();
  } finally {
    clearTimeout(t);
  }
}

// --- tolerant normalizers: accept camelCase or snake_case, flat or 2D values ---
function toNum(x, fallback = 0) {
  const n = Number(x);
  return Number.isFinite(n) ? n : fallback;
}

function normalizeField(raw, { date, depth, source }) {
  if (!raw || typeof raw !== 'object') throw new Error('bad field payload');
  const lats = raw.lats ?? raw.lat ?? raw.latitudes;
  const lons = raw.lons ?? raw.lon ?? raw.longitudes;
  let values = raw.values ?? raw.temperature ?? raw.data;
  let confidence = raw.confidence ?? raw.uncertainty ?? null;
  if (!Array.isArray(lats) || !Array.isArray(lons) || !Array.isArray(values)) {
    throw new Error('field payload missing lats/lons/values');
  }
  const nLat = lats.length, nLon = lons.length;
  if (!Array.isArray(values[0])) {
    // flat row-major array -> reshape
    if (values.length !== nLat * nLon) throw new Error('field values size mismatch');
    const grid = [];
    for (let i = 0; i < nLat; i++) grid.push(values.slice(i * nLon, (i + 1) * nLon).map((v) => toNum(v)));
    values = grid;
  } else {
    values = values.map((row) => row.map((v) => toNum(v)));
  }
  if (confidence && !Array.isArray(confidence[0]) && Array.isArray(confidence)) {
    const grid = [];
    for (let i = 0; i < nLat; i++) grid.push(confidence.slice(i * nLon, (i + 1) * nLon).map((v) => toNum(v, 1)));
    confidence = grid;
  }
  if (!confidence) confidence = values.map((row) => row.map(() => 1));
  let min = Infinity, max = -Infinity;
  values.forEach((row) => row.forEach((v) => { if (v < min) min = v; if (v > max) max = v; }));
  const stats = raw.stats ?? { min, max };
  return { lats, lons, values, confidence, stats, date, depth, source };
}

function normalizeProfile(raw, { date, lat, lon }) {
  if (!raw || typeof raw !== 'object') throw new Error('bad profile payload');
  const depths = raw.depths ?? raw.depth ?? STANDARD_DEPTHS;
  const pick = (...keys) => { for (const k of keys) if (Array.isArray(raw[k])) return raw[k]; return null; };
  const oceanembed = pick('oceanembed', 'model', 'prediction', 'reconstruction');
  const glorys = pick('glorys', 'reference');
  let argo = pick('argo', 'observed', 'insitu', 'in_situ');
  if (!oceanembed) throw new Error('profile payload missing model series');
  if (argo && argo.every((v) => v === null)) argo = null;
  return { depths, oceanembed, glorys: glorys ?? [...oceanembed], argo, lat, lon, date };
}

function normalizeSkillList(raw) {
  const arr = Array.isArray(raw) ? raw : raw.metrics ?? raw.skill ?? [];
  if (!Array.isArray(arr)) throw new Error('bad skill payload');
  return arr.map((m) => ({
    depth: toNum(m.depth),
    rmse: toNum(m.rmse),
    mae: toNum(m.mae ?? m.rmse * 0.75),
    bias: toNum(m.bias),
    correlation: toNum(m.correlation ?? m.corr, 1),
  }));
}

function normalizeFloats(raw) {
  const arr = Array.isArray(raw) ? raw : raw.floats ?? raw.profiles ?? [];
  if (!Array.isArray(arr)) throw new Error('bad argo payload');
  return arr.map((f, i) => ({
    lat: toNum(f.lat ?? f.latitude),
    lon: toNum(f.lon ?? f.lng ?? f.longitude),
    id: String(f.id ?? f.wmo ?? `ARGO-${i + 1}`),
  }));
}

function normalizeAlerts(raw) {
  const arr = Array.isArray(raw) ? raw : raw.alerts ?? [];
  if (!Array.isArray(arr)) throw new Error('bad alerts payload');
  return arr.map((a) => ({
    lat: toNum(a.lat), lon: toNum(a.lon), depth: toNum(a.depth),
    date: String(a.date), severity: String(a.severity ?? 'watch'),
    text: String(a.text ?? a.message ?? 'Anomaly detected'),
  }));
}

// ============================ mock generators ============================
// (unchanged behaviour — used when no backend is configured or as fallback)

function hashStr(s) {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}
function mulberry32(seed) {
  let a = seed >>> 0;
  return function () {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
export function fmtDate(d) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}
export function parseDate(s) {
  const [y, m, d] = s.split('-').map(Number);
  return new Date(y, m - 1, d);
}
export function prettyDate(s) {
  const d = parseDate(s);
  return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
}
export function addDaysStr(s, n) {
  const d = parseDate(s);
  d.setDate(d.getDate() + n);
  return fmtDate(d);
}
export function dateRangeStr(start, end) {
  const out = [];
  let d = parseDate(start);
  const stop = parseDate(end);
  while (d <= stop) { out.push(fmtDate(d)); d = new Date(d.getTime() + 86400000); }
  return out;
}

function meanTemp(depth) {
  return 4.2 + 24.6 * Math.exp(-depth / 170) + 1.1 * Math.exp(-depth / 700);
}

function spatialAnomaly(lat, lon, depth, rngEddy, dayPhase) {
  const arabianWarm = 1.6 * Math.exp(-(((lat - 14) ** 2) / 60 + ((lon - 62) ** 2) / 120));
  const bayWarm = 1.3 * Math.exp(-(((lat - 18) ** 2) / 70 + ((lon - 89) ** 2) / 140));
  const latGrad = -0.09 * (lat - 15);
  const eddy = 1.4 * Math.sin((lon * 0.55 + dayPhase) * 1.0) * Math.cos(lat * 0.5 - dayPhase * 0.7)
    + 0.7 * Math.sin(lon * 1.3 - lat * 0.9 + dayPhase * 1.7);
  const depthDamp = Math.exp(-depth / 450);
  return (arabianWarm + bayWarm + latGrad) * (0.35 + 0.65 * depthDamp) + eddy * depthDamp * 0.8;
}

function gridAxes() {
  const { nLat, nLon } = GRID;
  const lats = Array.from({ length: nLat }, (_, i) => BBOX.latMax - (i * (BBOX.latMax - BBOX.latMin)) / (nLat - 1));
  const lons = Array.from({ length: nLon }, (_, j) => BBOX.lonMin + (j * (BBOX.lonMax - BBOX.lonMin)) / (nLon - 1));
  return { lats, lons };
}

function mockTemperatureField({ date, depth, source = 'oceanembed' }) {
  const { lats, lons } = gridAxes();
  const seed = hashStr(`${date}|${depth}|${source}`);
  const rng = mulberry32(seed);
  const dayPhase = (hashStr(date) % 365) / 365 * Math.PI * 2;
  const cn = 7, cm = 8;
  const lattice = Array.from({ length: cn }, () => Array.from({ length: cm }, () => rng() * 2 - 1));
  const noiseAt = (fi, fj) => {
    const x = (fj / (GRID.nLon - 1)) * (cm - 1), y = (fi / (GRID.nLat - 1)) * (cn - 1);
    const x0 = Math.floor(x), y0 = Math.floor(y);
    const x1 = Math.min(cm - 1, x0 + 1), y1 = Math.min(cn - 1, y0 + 1);
    const tx = x - x0, ty = y - y0;
    return (lattice[y0][x0] * (1 - tx) + lattice[y0][x1] * tx) * (1 - ty)
      + (lattice[y1][x0] * (1 - tx) + lattice[y1][x1] * tx) * ty;
  };
  const bias = source === 'glorys' ? 0.12 + 0.0004 * depth : 0;
  const values = [];
  const confidence = [];
  let min = Infinity, max = -Infinity;
  for (let i = 0; i < GRID.nLat; i++) {
    const row = [], crow = [];
    for (let j = 0; j < GRID.nLon; j++) {
      const lat = lats[i], lon = lons[j];
      const t = meanTemp(depth)
        + spatialAnomaly(lat, lon, depth, rng, dayPhase)
        + noiseAt(i, j) * (0.5 + 0.35 * Math.exp(-depth / 300))
        + bias;
      row.push(+t.toFixed(3));
      const c = Math.min(1, Math.max(0.15,
        0.94 - depth / 1600
        - 0.1 * (lat < 10 ? 1 : 0) - 0.08 * Math.abs(noiseAt(i, j))));
      crow.push(+c.toFixed(3));
      if (t < min) min = t; if (t > max) max = t;
    }
    values.push(row); confidence.push(crow);
  }
  return { lats, lons, values, confidence, stats: { min: +min.toFixed(2), max: +max.toFixed(2) }, date, depth, source };
}

export function nearestIndex(arr, v) {
  let bi = 0, bd = Infinity;
  arr.forEach((a, i) => { const d = Math.abs(a - v); if (d < bd) { bd = d; bi = i; } });
  return bi;
}

function mockVerticalProfile({ date, lat, lon }) {
  const rng = mulberry32(hashStr(`prof|${date}|${lat.toFixed(2)}|${lon.toFixed(2)}`));
  const dayPhase = (hashStr(date) % 365) / 365 * Math.PI * 2;
  const hasArgo = rng() > 0.45;
  const oceanembed = [], glorys = [], argo = [];
  STANDARD_DEPTHS.forEach((d) => {
    const base = meanTemp(d) + spatialAnomaly(lat, lon, d, rng, dayPhase);
    const oe = base + (rng() - 0.5) * 0.3;
    const gl = base + 0.12 + (rng() - 0.5) * 0.25;
    oceanembed.push(+oe.toFixed(3));
    glorys.push(+gl.toFixed(3));
    argo.push(hasArgo ? +(base + (rng() - 0.5) * 0.5).toFixed(3) : null);
  });
  return { depths: [...STANDARD_DEPTHS], oceanembed, glorys, argo: hasArgo ? argo : null, lat, lon, date };
}

function mockSkillMetrics() {
  return STANDARD_DEPTHS.map((d, i) => {
    const rng = mulberry32(hashStr(`skill|${d}`));
    const rmse = +(0.28 + 0.0016 * d + 0.35 * Math.exp(-((d - 125) ** 2) / 12000) + rng() * 0.04).toFixed(3);
    const mae = +(rmse * (0.72 + rng() * 0.06)).toFixed(3);
    const bias = +(((rng() - 0.42) * 0.22).toFixed(3));
    const correlation = +(Math.min(0.995, 0.985 - d / 9000 - i * 0.0012 - rng() * 0.004).toFixed(3));
    return { depth: d, rmse, mae, bias, correlation };
  });
}

function mockArgoFloats({ date }) {
  const rng = mulberry32(hashStr(`argo|${date}`));
  const n = 14 + Math.floor(rng() * 6);
  const floats = [];
  for (let k = 0; k < n; k++) {
    const lat = +(BBOX.latMin + 1 + rng() * (BBOX.latMax - BBOX.latMin - 2)).toFixed(2);
    const lon = +(BBOX.lonMin + 1 + rng() * (BBOX.lonMax - BBOX.lonMin - 2)).toFixed(2);
    floats.push({ lat, lon, id: `ARGO-${date.slice(5).replace('-', '')}-${String(k + 1).padStart(2, '0')}` });
  }
  return floats;
}

function mockAnomalyAlerts() {
  return [
    { lat: 12.0, lon: 68.0, depth: 100, date: '2020-01-15', severity: 'watch', text: 'Marine heatwave watch — warm anomaly detected near 12°N, 68°E at 100m' },
    { lat: 19.5, lon: 88.0, depth: 50, date: '2020-01-15', severity: 'advisory', text: 'Warm anomaly advisory — Bay of Bengal near 19.5°N, 88°E at 50m' },
  ];
}

function mockArgoValidationSummary() {
  return { nProfiles: 18432, dateRange: 'Jan 2020 – Dec 2023', meanError: 0.42, rmse: 0.61, correlation: 0.967 };
}

function mockArgoScatter(n = 220) {
  const rng = mulberry32(hashStr('scatter|argo'));
  const pts = [];
  for (let k = 0; k < n; k++) {
    const depth = STANDARD_DEPTHS[Math.floor(rng() * STANDARD_DEPTHS.length)];
    const obs = meanTemp(depth) + (rng() - 0.5) * 8;
    const pred = obs + (rng() - 0.45) * 1.4;
    pts.push({ obs: +obs.toFixed(2), pred: +pred.toFixed(2), depth });
  }
  return pts;
}

// ============================ public async API ============================
// Backend-first, mock fallback. All return Promises.

async function withFallback(label, fn, mock) {
  if (!isBackendEnabled()) return mock();
  try {
    return await fn();
  } catch (e) {
    console.warn(`[oceanembed] backend ${label} failed, using mock fallback:`, e.message);
    return mock();
  }
}

export async function getTemperatureField({ date, depth, source = 'oceanembed' } = {}) {
  return withFallback('getTemperatureField',
    async () => normalizeField(await getJSON('/api/fields', { date, depth, source }), { date, depth, source }),
    () => mockTemperatureField({ date, depth, source }));
}

export async function getVerticalProfile({ date, lat, lon } = {}) {
  return withFallback('getVerticalProfile',
    async () => normalizeProfile(await getJSON('/api/profiles', { date, lat, lon }), { date, lat, lon }),
    () => mockVerticalProfile({ date, lat, lon }));
}

export async function getSkillMetrics() {
  return withFallback('getSkillMetrics',
    async () => normalizeSkillList(await getJSON('/api/skill')),
    () => mockSkillMetrics());
}

export async function getArgoFloats({ date } = {}) {
  return withFallback('getArgoFloats',
    async () => normalizeFloats(await getJSON('/api/argo', { date })),
    () => mockArgoFloats({ date }));
}

export async function getAnomalyAlerts() {
  return withFallback('getAnomalyAlerts',
    async () => normalizeAlerts(await getJSON('/api/alerts')),
    () => mockAnomalyAlerts());
}

export async function getArgoValidationSummary() {
  return withFallback('getArgoValidationSummary',
    async () => {
      const raw = await getJSON('/api/validation/summary');
      return {
        nProfiles: toNum(raw.nProfiles ?? raw.n_profiles ?? raw.count, 0),
        dateRange: String(raw.dateRange ?? raw.date_range ?? ''),
        meanError: toNum(raw.meanError ?? raw.mean_error),
        rmse: toNum(raw.rmse),
        correlation: toNum(raw.correlation, 1),
      };
    },
    () => mockArgoValidationSummary());
}

export async function getArgoScatter(n = 220) {
  return withFallback('getArgoScatter',
    async () => {
      const raw = await getJSON('/api/validation/scatter', { n });
      const arr = Array.isArray(raw) ? raw : raw.points ?? [];
      return arr.map((p) => ({ obs: toNum(p.obs ?? p.observed), pred: toNum(p.pred ?? p.predicted), depth: toNum(p.depth) }));
    },
    () => mockArgoScatter(n));
}

// Range fetch for loop playback. Prefers a dedicated range endpoint; falls
// back to parallel single-field requests (backend or mock). Returns
// [{ date, field }] in chronological order.
export async function getTemperatureRange({ start, end, depth, source = 'oceanembed' } = {}) {
  const dates = dateRangeStr(start, end);
  if (isBackendEnabled()) {
    try {
      const raw = await getJSON('/api/fields/range', { start, end, depth, source }, 30000);
      const list = Array.isArray(raw) ? raw : raw.fields ?? [];
      if (list.length > 0) {
        return list.map((item) => {
          const d = String(item.date ?? item.day);
          return { date: d, field: normalizeField(item.field ?? item, { date: d, depth, source }) };
        });
      }
    } catch (e) {
      console.warn('[oceanembed] range endpoint unavailable, falling back to parallel fetch:', e.message);
    }
  }
  const fields = await Promise.all(dates.map((d) => getTemperatureField({ date: d, depth, source })));
  return dates.map((d, i) => ({ date: d, field: fields[i] }));
}

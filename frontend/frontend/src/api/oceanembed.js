// OceanEmbed frontend API adapter for the canonical FastAPI contracts.
//
// The backend is the source of truth for request/response shapes. The frontend keeps
// its existing UI-facing shapes, but it now maps directly to the backend contracts that
// were intentionally designed first: /api/metadata, /api/temperature, /api/profile,
// /api/comparison, and /api/validation.
//
// When the backend has not implemented real scientific data yet, the frontend keeps the
// state explicitly empty/unavailable instead of inventing values.

export const STANDARD_DEPTHS = [0.0, 5.0, 10.0, 20.0, 30.0, 50.0, 75.0, 100.0, 125.0, 150.0, 200.0, 300.0, 500.0, 700.0, 1000.0];
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

function hasUsableTemperatureValues(values) {
  if (!Array.isArray(values) || values.length === 0) return false;
  return values.some((row) => {
    if (Array.isArray(row)) {
      return row.some((v) => v !== null && v !== undefined && Number.isFinite(Number(v)));
    }
    return row !== null && row !== undefined && Number.isFinite(Number(row));
  });
}

function normalizeField(raw, { date, depth, source }) {
  if (!raw || typeof raw !== 'object') return null;

  const values = Array.isArray(raw.values) ? raw.values : [];
  if (!hasUsableTemperatureValues(values)) return null;

  const normalized = values.map((row) => {
    if (!Array.isArray(row)) return [Number.isFinite(Number(row)) ? Number(row) : null];
    return row.map((v) => (v !== null && v !== undefined && Number.isFinite(Number(v)) ? Number(v) : null));
  });

  const confidence = [];
  const stats = { min: Infinity, max: -Infinity };
  normalized.forEach((row) => {
    row.forEach((v) => {
      if (v === null) return;
      if (v < stats.min) stats.min = v;
      if (v > stats.max) stats.max = v;
    });
    confidence.push(row.map(() => null));
  });
  if (!Number.isFinite(stats.min)) return null;

  return { lats: [], lons: [], values: normalized, confidence, stats: { min: stats.min, max: stats.max }, date, depth, source };
}

function normalizeProfile(raw, { date, lat, lon }) {
  if (!raw || typeof raw !== 'object') return null;
  const profileList = Array.isArray(raw.profile) ? raw.profile : [];
  if (profileList.length === 0) return null;

  const depths = profileList.map((p) => toNum(p.depth));
  const oceanembed = profileList.map((p) => (p.temperature !== null && p.temperature !== undefined && Number.isFinite(Number(p.temperature)) ? Number(p.temperature) : null));
  const glorys = Array(depths.length).fill(null);
  const argo = null;
  if (!oceanembed.some((v) => v !== null)) return null;

  return { depths, oceanembed, glorys, argo, lat, lon, date };
}

function normalizeSkillList(raw) {
  const arr = Array.isArray(raw) ? raw : raw?.metrics ?? raw?.skill ?? [];
  if (!Array.isArray(arr)) return [];
  return arr.map((m) => ({
    depth: toNum(m.depth),
    rmse: toNum(m.rmse),
    mae: toNum(m.mae ?? m.rmse * 0.75),
    bias: toNum(m.bias),
    correlation: toNum(m.correlation ?? m.corr, 1),
  }));
}

function normalizeFloats(raw) {
  const arr = Array.isArray(raw) ? raw : raw?.floats ?? raw?.profiles ?? [];
  if (!Array.isArray(arr)) return [];
  return arr.map((f, i) => ({
    lat: toNum(f.lat ?? f.latitude),
    lon: toNum(f.lon ?? f.lng ?? f.longitude),
    id: String(f.id ?? f.wmo ?? `ARGO-${i + 1}`),
  }));
}

function normalizeAlerts(raw) {
  const arr = Array.isArray(raw) ? raw : raw?.alerts ?? [];
  if (!Array.isArray(arr)) return [];
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
// Canonical backend contracts only. Empty/unavailable states are explicit.

async function fetchBackend(label, path, params = {}, timeoutMs = 12000) {
  if (!isBackendEnabled()) return null;
  try {
    return await getJSON(path, params, timeoutMs);
  } catch (e) {
    console.warn(`[oceanembed] backend ${label} unavailable:`, e.message);
    return null;
  }
}

export async function getTemperatureField({ date, depth, source = 'oceanembed' } = {}) {
  const raw = await fetchBackend('getTemperatureField', '/api/temperature', { date, depth });
  if (!raw) return null;
  return normalizeField(raw, { date, depth, source });
}

export async function getVerticalProfile({ date, lat, lon } = {}) {
  const raw = await fetchBackend('getVerticalProfile', '/api/profile', { date, latitude: lat, longitude: lon });
  if (!raw) return null;
  return normalizeProfile(raw, { date, lat, lon });
}

export async function getComparison({ latitude, longitude, date, depth } = {}) {
  const raw = await fetchBackend('getComparison', '/api/comparison', { latitude, longitude, date, depth });
  if (!raw) return null;
  const hasRealValues = raw.oceanembed_temperature !== null && raw.oceanembed_temperature !== undefined
    && raw.glorys_temperature !== null && raw.glorys_temperature !== undefined;
  if (!hasRealValues) return null;
  return {
    latitude: toNum(raw.latitude),
    longitude: toNum(raw.longitude),
    date: String(raw.date ?? date),
    depth: toNum(raw.depth ?? depth),
    oceanembed_temperature: toNum(raw.oceanembed_temperature),
    glorys_temperature: toNum(raw.glorys_temperature),
    difference: toNum(raw.difference),
    unit: String(raw.unit ?? 'degC'),
  };
}

export async function getSkillMetrics() {
  return [];
}

export async function getArgoFloats({ date } = {}) {
  return [];
}

export async function getAnomalyAlerts() {
  return [];
}

export async function getArgoValidationSummary() {
  return {
    nProfiles: 0,
    dateRange: 'Unavailable',
    meanError: null,
    rmse: null,
    correlation: null,
  };
}

export async function getArgoScatter(n = 220) {
  return [];
}

export async function getTemperatureRange({ start, end, depth, source = 'oceanembed' } = {}) {
  const dates = dateRangeStr(start, end);
  const fields = [];
  for (const d of dates) {
    const field = await getTemperatureField({ date: d, depth, source });
    if (field) fields.push({ date: d, field });
  }
  return fields;
}

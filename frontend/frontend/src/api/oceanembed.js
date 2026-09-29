// OceanEmbed frontend API adapter for the canonical FastAPI contracts.
//
// The backend is the source of truth for request/response shapes:
// /api/metadata, /api/temperature, /api/temperature/coverage, /api/profile,
// /api/comparison, /api/validation, /api/argo/floats and /api/argo/alerts.
//
// There are no mock generators. When the backend is unreachable or a dataset is
// unavailable, these functions return an explicit empty/unavailable value so the UI can
// say "unavailable" instead of showing invented numbers.

export const STANDARD_DEPTHS = [0.0, 5.0, 10.0, 20.0, 30.0, 50.0, 75.0, 100.0, 125.0, 150.0, 200.0, 300.0, 500.0, 700.0, 1000.0];
export const BBOX = { latMin: 5, latMax: 30, lonMin: 45, lonMax: 105 };
export const GRID = { nLat: 101, nLon: 241 };
export const MODEL_VERSION = 'oceanembed-v0.3-real';

//: Fallback list, used only until /api/metadata answers. The backend is authoritative.
export const SUPPORTED_DATES = ['2020-01-01', '2020-01-02', '2020-01-03', '2020-01-04', '2020-01-05', '2020-01-06', '2020-01-07'];
export const LAST_UPDATE = SUPPORTED_DATES[SUPPORTED_DATES.length - 1];

const API_BASE = (import.meta.env.VITE_API_BASE || '').replace(/\/$/, '');
export const isBackendEnabled = () => API_BASE.length > 0;
export const getApiBase = () => API_BASE;

async function getJSON(path, params = {}, timeoutMs = 30000) {
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

async function fetchBackend(label, path, params = {}, timeoutMs = 30000) {
  if (!isBackendEnabled()) return null;
  try {
    return await getJSON(path, params, timeoutMs);
  } catch (e) {
    console.warn(`[oceanembed] backend ${label} unavailable:`, e.message);
    return null;
  }
}

// ---------------------------------- helpers
function toNum(x, fallback = 0) {
  const n = Number(x);
  return Number.isFinite(n) ? n : fallback;
}

function numOrNull(x) {
  if (x === null || x === undefined || x === '') return null;
  const n = Number(x);
  return Number.isFinite(n) ? n : null;
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
export function nearestIndex(arr, v) {
  let bi = 0, bd = Infinity;
  arr.forEach((a, i) => { const d = Math.abs(a - v); if (d < bd) { bd = d; bi = i; } });
  return bi;
}

// -------------------------------- normalizers
//
// Convention: every field is returned NORTH-UP — lats[0] is the northernmost row and
// values[0] is that same row. The backend grid runs south-to-north, so rows are reversed
// here. MapHeatmap draws row 0 at the top, and the ARGO/GLORYS accessors index with
// north-up latitudes, so this keeps all three consistent.

function normalizeField(raw, { date, depth, source }) {
  if (!raw || typeof raw !== 'object') return null;

  const values = Array.isArray(raw.values) ? raw.values : [];
  if (values.length === 0) return null;

  const bounds = raw.metadata && typeof raw.metadata === 'object' ? raw.metadata.bounds ?? {} : {};
  const latMin = Number.isFinite(Number(bounds.latitude_min)) ? Number(bounds.latitude_min) : BBOX.latMin;
  const latMax = Number.isFinite(Number(bounds.latitude_max)) ? Number(bounds.latitude_max) : BBOX.latMax;
  const lonMin = Number.isFinite(Number(bounds.longitude_min)) ? Number(bounds.longitude_min) : BBOX.lonMin;
  const lonMax = Number.isFinite(Number(bounds.longitude_max)) ? Number(bounds.longitude_max) : BBOX.lonMax;

  const stepLat = 0.25;
  const stepLon = 0.25;
  const latCount = Math.round((latMax - latMin) / stepLat) + 1;
  const lonCount = Math.round((lonMax - lonMin) / stepLon) + 1;

  // Backend rows ascend from latMin; render row 0 as the north edge.
  const lats = Array.from({ length: latCount }, (_, i) => Number((latMax - i * stepLat).toFixed(4)));
  const lons = Array.from({ length: lonCount }, (_, j) => Number((lonMin + j * stepLon).toFixed(4)));

  const southUp = values.map((row) => {
    if (!Array.isArray(row)) {
      return [numOrNull(row)];
    }
    return row.map((v) => numOrNull(v));
  });
  const normalized = southUp.slice().reverse();

  // Coverage: 1 where the value is finite, 0 where the model has nothing (land, shallower
  // than the sea floor, or outside the reference mask). This is a data-availability mask,
  // not a statistical confidence score.
  const coverage = normalized.map((row) => row.map((v) => (v !== null ? 1 : 0)));

  const finite = [];
  normalized.forEach((row) => row.forEach((v) => { if (v !== null) finite.push(v); }));
  const stats = finite.length > 0
    ? { min: Math.min(...finite), max: Math.max(...finite), validCount: finite.length, totalCount: latCount * lonCount }
    : { min: 0, max: 0, validCount: 0, totalCount: latCount * lonCount };

  return { lats, lons, values: normalized, coverage, stats, date, depth, source };
}

function normalizeProfile(raw, { date, lat, lon }) {
  if (!raw || typeof raw !== 'object') return null;
  const profileList = Array.isArray(raw.profile) ? raw.profile : [];
  if (profileList.length === 0) return null;

  const depths = profileList.map((p) => toNum(p.depth));
  const oceanembed = profileList.map((p) => numOrNull(p.temperature));
  if (!oceanembed.some((v) => v !== null)) return null;

  return { depths, oceanembed, glorys: Array(depths.length).fill(null), argo: null, lat, lon, date };
}

// ------------------------------ metadata / dates

let metadataCache = null;

export async function getMetadata() {
  if (metadataCache) return metadataCache;
  const raw = await fetchBackend('getMetadata', '/api/metadata');
  if (!raw) return null;
  metadataCache = {
    datasetName: String(raw.dataset_name ?? 'OceanEmbed'),
    availableDates: Array.isArray(raw.available_dates) ? raw.available_dates.map(String) : SUPPORTED_DATES,
    availableDepths: Array.isArray(raw.available_depths) ? raw.available_depths.map(Number) : STANDARD_DEPTHS,
    glorysStatus: String(raw.glorys_status ?? 'unknown'),
    glorysProvenance: String(raw.glorys_provenance ?? ''),
    argoStatus: String(raw.argo_status ?? 'unavailable'),
    argoProvenance: String(raw.argo_provenance ?? ''),
    argoAvailableDates: Array.isArray(raw.argo_available_dates) ? raw.argo_available_dates.map(String) : [],
    modelParameterCount: numOrNull(raw.model_parameter_count),
  };
  return metadataCache;
}

/** Model dates from the backend, falling back to the known window. */
export async function getSupportedDates() {
  const meta = await getMetadata();
  return meta?.availableDates?.length ? meta.availableDates : SUPPORTED_DATES;
}

/** Latest model date, used for the header. */
export async function getLastUpdate() {
  const dates = await getSupportedDates();
  return dates[dates.length - 1] ?? LAST_UPDATE;
}

// ----------------------------------- fields

export async function getTemperatureField({ date, depth, source = 'oceanembed' } = {}) {
  const raw = await fetchBackend('getTemperatureField', '/api/temperature', { date, depth });
  if (!raw) return null;
  return normalizeField(raw, { date, depth, source });
}

/** Fraction of grid cells with a finite value, straight from the backend. */
export async function getCoverage({ date, depth } = {}) {
  const raw = await fetchBackend('getCoverage', '/api/temperature/coverage', { date, depth });
  if (!raw) return null;
  return {
    date: String(raw.date ?? date),
    depth: toNum(raw.depth ?? depth),
    validCells: toNum(raw.valid_cells),
    totalCells: toNum(raw.total_cells),
    coverage: numOrNull(raw.coverage),
  };
}

export async function getVerticalProfile({ date, lat, lon } = {}) {
  const raw = await fetchBackend('getVerticalProfile', '/api/profile', { date, latitude: lat, longitude: lon });
  if (!raw) return null;
  return normalizeProfile(raw, { date, lat, lon });
}

export async function getComparison({ latitude, longitude, date, depth } = {}) {
  const raw = await fetchBackend('getComparison', '/api/comparison', { latitude, longitude, date, depth });
  if (!raw || typeof raw !== 'object') return null;

  const oceanembedTemperature = numOrNull(raw.oceanembed_temperature);
  const glorysTemperature = numOrNull(raw.glorys_temperature);
  let difference = numOrNull(raw.difference);
  if (difference === null && oceanembedTemperature !== null && glorysTemperature !== null) {
    difference = oceanembedTemperature - glorysTemperature;
  }

  const hasUsefulPayload = [
    oceanembedTemperature,
    glorysTemperature,
    difference,
    raw.glorys_status,
    raw.glorys_provenance,
  ].some((value) => value !== null && value !== undefined && value !== '');

  if (!hasUsefulPayload) return null;

  // State A/B/C per the interface contract. `state` drives the presentation so a missing
  // reference (model_only) is never shown as a failure, and a missing model (model_unavailable)
  // never gets a fabricated number.
  let state = String(raw.state ?? '');
  if (!['model_and_reference', 'model_only', 'model_unavailable'].includes(state)) {
    state = oceanembedTemperature === null
      ? 'model_unavailable'
      : glorysTemperature === null ? 'model_only' : 'model_and_reference';
  }

  const gridLat = numOrNull(raw.grid_latitude);
  const gridLon = numOrNull(raw.grid_longitude);
  const reqLat = toNum(raw.requested_latitude ?? raw.latitude ?? latitude);
  const reqLon = toNum(raw.requested_longitude ?? raw.longitude ?? longitude);
  const snapped = gridLat !== null && gridLon !== null
    && (Math.abs(gridLat - reqLat) > 1e-6 || Math.abs(gridLon - reqLon) > 1e-6);

  return {
    latitude: toNum(raw.latitude ?? latitude),
    longitude: toNum(raw.longitude ?? longitude),
    requested_latitude: reqLat,
    requested_longitude: reqLon,
    grid_latitude: gridLat,
    grid_longitude: gridLon,
    nearest_grid_latitude: numOrNull(raw.nearest_grid_latitude),
    nearest_grid_longitude: numOrNull(raw.nearest_grid_longitude),
    // Distance in degrees between the requested cell and the cell the value came from. A
    // non-zero offset means the requested cell has no complete 0-1000 m column.
    offset_degrees: numOrNull(raw.offset_degrees) ?? 0,
    snappedToGrid: snapped,
    grid_resolution_degrees: numOrNull(raw.grid_resolution_degrees) ?? 0.25,
    date: String(raw.date ?? date),
    depth: toNum(raw.depth ?? depth),
    oceanembed_temperature: oceanembedTemperature,
    glorys_temperature: glorysTemperature,
    difference,
    glorys_status: String(raw.glorys_status ?? 'unknown'),
    glorys_provenance: String(raw.glorys_provenance ?? 'Reference source unavailable'),
    unit: String(raw.unit ?? 'degC'),
    state,
    state_message: String(raw.state_message ?? ''),
  };
}

// ------------------------ ARGO validation (real observations)

let validationCache = null;
let validationInFlight = null;

/**
 * Fetch the ARGO validation payload once and reuse it.
 *
 * The validation endpoint runs the model over the whole window, so it is slow relative to
 * the other calls. Caching it keeps the three consumers below to a single request.
 */
async function loadValidation() {
  if (validationCache) return validationCache;
  if (!validationInFlight) {
    validationInFlight = fetchBackend('getValidation', '/api/validation', {}, 120000)
      .then((raw) => {
        validationCache = raw;
        validationInFlight = null;
        return raw;
      })
      .catch(() => { validationInFlight = null; return null; });
  }
  return validationInFlight;
}

/** Per-depth ARGO validation metrics. RMSE/MAE/bias are °C, correlation is unitless. */
export async function getSkillMetrics() {
  const raw = await loadValidation();
  const perDepth = Array.isArray(raw?.per_depth) ? raw.per_depth : [];
  return perDepth.map((m) => ({
    depth: toNum(m.depth),
    rmse: numOrNull(m.rmse),
    mae: numOrNull(m.mae),
    bias: numOrNull(m.bias),
    correlation: numOrNull(m.correlation),
    n: toNum(m.n),
  }));
}

export async function getArgoValidationSummary() {
  const raw = await loadValidation();
  const summary = raw?.summary ?? {};
  const metrics = raw?.metrics ?? {};
  return {
    status: String(summary.status ?? 'unavailable'),
    provenance: String(summary.provenance ?? raw?.provenance ?? ''),
    reference: String(summary.reference ?? 'ARGO'),
    referenceKind: String(summary.reference_kind ?? raw?.reference_kind ?? ''),
    nProfiles: numOrNull(summary.n_profiles),
    nObservations: numOrNull(summary.n_observations ?? metrics.n_observations),
    meanError: numOrNull(summary.mean_error ?? metrics.mae),
    rmse: numOrNull(metrics.rmse),
    correlation: numOrNull(summary.correlation ?? metrics.correlation),
    dateRange: String(summary.date_range || 'Unavailable'),
    modelVersion: String(summary.model_version ?? MODEL_VERSION),
    caveat: String(summary.caveat ?? ''),
  };
}

export async function getArgoScatter(n = 220) {
  const raw = await loadValidation();
  const points = Array.isArray(raw?.scatter) ? raw.scatter : [];
  return points.slice(0, n).map((p) => ({
    obs: toNum(p.observed),
    pred: toNum(p.predicted),
    depth: toNum(p.depth),
  }));
}

export async function getArgoFloats({ date } = {}) {
  const raw = await fetchBackend('getArgoFloats', '/api/argo/floats', { date });
  const floats = Array.isArray(raw?.floats) ? raw.floats : [];
  return floats.map((f) => ({
    id: String(f.id),
    lat: toNum(f.lat),
    lon: toNum(f.lon),
    nLevels: toNum(f.n_levels),
    depthMin: numOrNull(f.depth_min),
    depthMax: numOrNull(f.depth_max),
    kind: 'argo',
  }));
}

/** ARGO time-matching details, so the UI can show the analysis date and its offset. */
export async function getArgoTimeInfo({ date } = {}) {
  const raw = await fetchBackend('getArgoFloats', '/api/argo/floats', { date });
  if (!raw) return null;
  return {
    status: String(raw.status ?? 'unavailable'),
    provenance: String(raw.provenance ?? ''),
    argoDate: raw.argo_date ? String(raw.argo_date) : null,
    timeOffsetDays: numOrNull(raw.time_offset_days),
  };
}

export async function getAnomalyAlerts() {
  const raw = await fetchBackend('getAnomalyAlerts', '/api/argo/alerts', {});
  const alerts = Array.isArray(raw?.alerts) ? raw.alerts : [];
  return alerts.map((a) => ({
    lat: toNum(a.lat),
    lon: toNum(a.lon),
    depth: toNum(a.depth),
    date: String(a.date ?? ''),
    difference: numOrNull(a.difference),
    direction: String(a.direction ?? ''),
    text: String(a.message ?? 'Large model-versus-ARGO difference'),
    severity: 'watch',
  }));
}

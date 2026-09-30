import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import {
  STANDARD_DEPTHS, getMetadata, getSupportedDates, getAnomalyAlerts,
  getTemperatureField, getReferenceField, getComparison, getArgoValidationSummary,
  getSkillMetrics, getArgoScatter, getArgoFloats, getArgoTimeInfo,
  getHazardField, getHazardSummary, getVerticalProfile,
  hazardVariableInfo, HAZARD_VARIABLES, prettyDate, isBackendEnabled, getApiBase,
  MODEL_VERSION,
} from './api/oceanembed';

// ---------------------------------------------------------------- data layer
//
// Every panel reads the same two objects. `volume` holds one grid per standard
// depth, so scrubbing the depth slider costs nothing after the first load; the
// hazard object holds one grid per hazard variable for the selected day.
//
//   volume  { [depth]: field }
//   hazards { [variable]: field }

export function useOcean() {
  const [dates, setDates] = useState([]);
  const [date, setDate] = useState('2020-01-01');
  const [meta, setMeta] = useState(null);
  const [volume, setVolume] = useState({});
  const [hazards, setHazards] = useState({});
  const [hazardSummary, setHazardSummary] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState({ volume: false, hazards: false });
  const [failed, setFailed] = useState({ volume: false, hazards: false });

  // Separate generation counters per fetch family. A shared counter would let the
  // hazard refetch invalidate an in-flight volume load, which leaves the UI stuck on
  // its loading state and the volume permanently empty.
  const volumeRun = useRef(0);
  const hazardRun = useRef(0);

  // metadata + dates + alerts, once
  useEffect(() => {
    let dead = false;
    getMetadata().then((m) => { if (!dead) setMeta(m); }).catch(() => {});
    getSupportedDates().then((d) => {
      if (dead || !d.length) return;
      setDates(d);
      setDate((cur) => (d.includes(cur) ? cur : d[0]));
    }).catch(() => {});
    return () => { dead = true; };
  }, []);

  // The whole depth volume for the selected day, fetched in parallel.
  // Depths are progressive: the surface lands first and paints immediately.
  useEffect(() => {
    if (!date) return undefined;
    const run = ++volumeRun.current;
    setVolume({});
    setFailed((f) => ({ ...f, volume: false }));
    setLoading((l) => ({ ...l, volume: true }));
    Promise.all(STANDARD_DEPTHS.map((d) =>
      getTemperatureField({ date, depth: d }).catch(() => null)
    )).then((fields) => {
      if (run !== volumeRun.current) return;
      const next = {};
      fields.forEach((f, i) => { if (f) next[STANDARD_DEPTHS[i]] = f; });
      setVolume(next);
      setFailed((f) => ({ ...f, volume: Object.keys(next).length === 0 }));
      setLoading((l) => ({ ...l, volume: false }));
    });
    return () => {};
  }, [date]);

  // The largest model-versus-ARGO disagreements for the selected day.
  useEffect(() => {
    if (!date) return undefined;
    let dead = false;
    getAnomalyAlerts({ date }).then((a) => { if (!dead) setAlerts(a); }).catch(() => {});
    return () => { dead = true; };
  }, [date]);

  // Coverage plus the hazard cube for the same day.
  useEffect(() => {
    if (!date) return undefined;
    const run = ++hazardRun.current;
    setHazards({});
    setHazardSummary(null);
    setFailed((f) => ({ ...f, hazards: false }));
    setLoading((l) => ({ ...l, hazards: true }));
    // The field promises must be nested, not spread into the same Promise.all:
    // spreading them makes the first destructured slot a single field object, so
    // the forEach below throws and the whole handler dies silently.
    Promise.all([
      Promise.all(HAZARD_VARIABLES.map((v) => getHazardField({ date, variable: v.id }).catch(() => null))),
      getHazardSummary({ date }).catch(() => null),
    ]).then(([fields, summary]) => {
      if (run !== hazardRun.current) return;
      const next = {};
      fields.forEach((f, i) => { if (f) next[HAZARD_VARIABLES[i].id] = f; });
      setHazards(next);
      setHazardSummary(summary);
      setLoading((l) => ({ ...l, hazards: false }));
      setFailed((f) => ({ ...f, hazards: Object.keys(next).length === 0 }));
    }).catch(() => {
      if (run === hazardRun.current) setLoading((l) => ({ ...l, hazards: false }));
    });
    return () => {};
  }, [date]);

  return {
    dates, date, setDate, meta, volume, hazards, hazardSummary,
    alerts, loading, failed,
  };
}

// ---------------------------------------------------------------- shared state
//
// One cursor for the whole screen: which depth slice is showing, which variable,
// and which grid cell is selected.

export const ConsoleContext = createContext(null);
export const useConsole = () => useContext(ConsoleContext);

// Deep links so a single view can be opened directly, which is how the demo and
// the screenshot checks reach a specific state: ?field=tchp&depth=200&date=2020-01-04
function readParams() {
  if (typeof window === 'undefined') return {};
  const p = new URLSearchParams(window.location.search);
  return {
    field: p.get('field') || null,
    depth: p.get('depth'),
    date: p.get('date'),
    lat: p.get('lat'),
    lon: p.get('lon'),
    drawer: p.get('drawer'),
    view: p.get('view'),
  };
}

export function useConsoleState() {
  const ocean = useOcean();
  const P = useRef(readParams()).current;
  const START_HAZARD = HAZARD_VARIABLES.some((v) => v.id === P.field);
  const [depth, setDepth] = useState(() => {
    // Number(null) is 0, and 0 m is a real depth, so a missing ?depth= would
    // silently select the surface rather than the default.
    const raw = P.depth == null || P.depth === '' ? NaN : Number(P.depth);
    return STANDARD_DEPTHS.includes(raw) ? raw : 100;
  });
  const [variable, setVariable] = useState(() => (START_HAZARD ? P.field : 'temperature')); // temperature | hazard id
  const [hazardVar, setHazardVar] = useState(() => (START_HAZARD ? P.field : 'tchp'));
  const [selection, setSelection] = useState(() => ({
    // Number(null) is 0, so a missing ?lat= would put the cursor on the equator.
    lat: P.lat == null || P.lat === '' || !Number.isFinite(Number(P.lat)) ? 12 : Number(P.lat),
    lon: P.lon == null || P.lon === '' || !Number.isFinite(Number(P.lon)) ? 88 : Number(P.lon),
  }));
  const [compare, setCompare] = useState(true);
  const [showCoverage, setShowCoverage] = useState(false);
  const [mapMode, setMapMode] = useState(() => (P.view === 'difference' ? 'difference' : 'field')); // field | difference

  const isHazard = variable !== 'temperature';
  const activeHazard = variable === 'temperature' ? hazardVar : variable;
  const hazardInfo = useMemo(() => hazardVariableInfo(activeHazard), [activeHazard]);

  const field = isHazard
    ? ocean.hazards[activeHazard] ?? null
    : ocean.volume[depth] ?? null;

  // Reference comparison at the cursor. Fetched for every standard depth at once,
  // not just the visible one, so the read-out panel can draw a complete
  // model-vs-GLORYS profile instead of a single level.
  const [comparisons, setComparisons] = useState({});
  const [comparisonState, setComparisonState] = useState('idle');
  useEffect(() => {
    let dead = false;
    if (!selection || !ocean.date) { setComparisons({}); setComparisonState('idle'); return undefined; }
    setComparisonState('loading');
    Promise.all(STANDARD_DEPTHS.map((d) =>
      getComparison({ latitude: selection.lat, longitude: selection.lon, date: ocean.date, depth: d })
        .catch(() => null)
    )).then((rows) => {
      if (dead) return;
      const next = {};
      rows.forEach((r, i) => { if (r) next[STANDARD_DEPTHS[i]] = r; });
      setComparisons(next);
      setComparisonState(Object.keys(next).length ? 'ready' : 'unavailable');
    });
    return () => { dead = true; };
  }, [selection, ocean.date]);

  const comparison = comparisons[depth] ?? null;

  // Reference (GLORYS) fields for the map difference view, fetched only when that
  // view is actually open and cached per depth, so it is opt-in and free to re-scrub.
  // These are the model's own training target, not validation data.
  const [reference, setReference] = useState({});
  useEffect(() => { setReference({}); }, [ocean.date]);
  useEffect(() => {
    if (mapMode !== 'difference' || isHazard || !ocean.date) return undefined;
    if (reference[depth]) return undefined;
    let dead = false;
    getReferenceField({ date: ocean.date, depth })
      .then((f) => { if (!dead && f) setReference((r) => ({ ...r, [depth]: f })); })
      .catch(() => {});
    return () => { dead = true; };
  }, [mapMode, depth, ocean.date, isHazard, reference]);

  // Profiles at the cursor for every available day, for the depth-time strip.
  const [timeProfiles, setTimeProfiles] = useState({});
  useEffect(() => {
    let dead = false;
    if (!selection || !ocean.dates.length) return undefined;
    Promise.all(ocean.dates.map((d) =>
      getVerticalProfile({ date: d, lat: selection.lat, lon: selection.lon }).catch(() => null)
    )).then((rows) => {
      if (dead) return;
      const next = {};
      rows.forEach((p, i) => { if (p) next[ocean.dates[i]] = p; });
      setTimeProfiles(next);
    });
    return () => { dead = true; };
  }, [selection, ocean.dates]);

  // ARGO floats for the day, plus the analysis date the backend matched them to.
  const [floats, setFloats] = useState([]);
  const [argoTime, setArgoTime] = useState(null);
  useEffect(() => {
    let dead = false;
    if (!ocean.date) return undefined;
    getArgoFloats({ date: ocean.date }).then((f) => { if (!dead) setFloats(f); }).catch(() => {});
    getArgoTimeInfo({ date: ocean.date }).then((t) => { if (!dead) setArgoTime(t); }).catch(() => {});
    return () => { dead = true; };
  }, [ocean.date]);

  // The date list arrives asynchronously, so a deep-linked day is applied once.
  const dateApplied = useRef(false);
  useEffect(() => {
    if (dateApplied.current || !P.date || !ocean.dates.length) return;
    if (ocean.dates.includes(P.date)) { ocean.setDate(P.date); dateApplied.current = true; }
  }, [ocean.dates, ocean.setDate, P.date]);

  // Reflect the current view in the address bar so any state can be copied or
  // reloaded. replaceState keeps this out of the back-button history.
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const params = new URLSearchParams();
    if (isHazard) params.set('field', activeHazard);
    if (depth !== 100 && !isHazard) params.set('depth', String(depth));
    if (ocean.date && ocean.date !== ocean.dates[0]) params.set('date', ocean.date);
    if (selection.lat !== 12) params.set('lat', String(selection.lat));
    if (selection.lon !== 88) params.set('lon', String(selection.lon));
    if (mapMode === 'difference') params.set('view', 'difference');
    const qs = params.toString();
    window.history.replaceState(null, '', qs ? `?${qs}` : window.location.pathname);
  }, [isHazard, activeHazard, depth, ocean.date, ocean.dates, selection, mapMode]);

  const stepDepth = useCallback((dir) => {
    setDepth((cur) => {
      const i = STANDARD_DEPTHS.indexOf(cur);
      const n = Math.min(STANDARD_DEPTHS.length - 1, Math.max(0, (i < 0 ? 0 : i) + dir));
      return STANDARD_DEPTHS[n];
    });
  }, []);

  const stepDay = useCallback((dir) => {
    setDates_(ocean.dates, ocean.date, ocean.setDate, dir);
  }, [ocean.dates, ocean.date, ocean.setDate]);

  return {
    ...ocean,
    depth, setDepth, stepDepth, stepDay,
    variable, setVariable, hazardVar, setHazardVar, activeHazard, hazardInfo, isHazard,
    field, selection, setSelection, comparison, comparisons, comparisonState, timeProfiles,
    floats, argoTime,
    compare, setCompare, showCoverage, setShowCoverage,
    mapMode, setMapMode, reference,
  };
}

function setDates_(dates, current, setDate, dir) {
  if (!dates.length) return;
  const i = dates.indexOf(current);
  const n = Math.min(dates.length - 1, Math.max(0, (i < 0 ? 0 : i) + dir));
  setDate(dates[n]);
}

// ---------------------------------------------------------------- validation
// Loaded lazily — it is the slowest endpoint and only the drawer needs it.

let cache = null;
export function useValidation() {
  const [data, setData] = useState(cache);
  const [loading, setLoading] = useState(!cache);
  useEffect(() => {
    if (cache) return undefined;
    let dead = false;
    Promise.all([
      getArgoValidationSummary().catch(() => null),
      getSkillMetrics().catch(() => []),
      getArgoScatter(240).catch(() => []),
    ]).then(([summary, perDepth, scatter]) => {
      if (dead) return;
      cache = { summary, perDepth, scatter };
      setData(cache);
      setLoading(false);
    });
    return () => { dead = true; };
  }, []);
  return { data, loading };
}

export const fmt = {
  date: (s) => (s ? prettyDate(s) : '—'),
  num: (v, n = 2) => (v === null || v === undefined || !Number.isFinite(Number(v)) ? '—' : Number(v).toFixed(n)),
  int: (v) => (v === null || v === undefined || !Number.isFinite(Number(v)) ? '—' : Math.round(Number(v)).toLocaleString()),
  pct: (v, n = 1) => (v === null || v === undefined || !Number.isFinite(Number(v)) ? '—' : `${(Number(v) * 100).toFixed(n)}%`),
  ll: (lat, lon) => `${Number(lat).toFixed(2)}°N ${Number(lon).toFixed(2)}°E`,
  base: getApiBase,
  backend: isBackendEnabled(),
  version: MODEL_VERSION,
};

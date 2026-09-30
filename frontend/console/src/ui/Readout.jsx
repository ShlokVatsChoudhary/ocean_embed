import { useConsole, fmt } from '../state';
import { STANDARD_DEPTHS } from '../api/oceanembed';
import ProfileChart from '../panels/ProfileChart';
import { TimePanel } from '../panels/SectionPanel';

// Right rail: everything about the single cell under the cursor.
export default function Readout() {
  const c = useConsole();
  const cmp = c.comparison;
  const state = cmp?.state ?? (c.comparisonState === 'loading' ? 'loading' : 'model_unavailable');

  const depths = STANDARD_DEPTHS;
  const model = depths.map((d) => c.comparisons[d]?.oceanembed_temperature ?? null);
  const glorys = depths.map((d) => c.comparisons[d]?.glorys_temperature ?? null);
  const hasGlorys = glorys.some((v) => v !== null);

  const haz = c.hazardSummary;
  const activeHazField = c.isHazard ? c.field : null;

  // Nearest-cell transparency: the backend tells us when a shelf point had to
  // snap to a neighbour with a complete column, so the UI can say so.
  const snapped = cmp && cmp.offset_degrees > 0.01;

  return (
    <aside className="rail">
      <section className="panel">
        <header>
          <h2>Cursor</h2>
          <span className="sub">{fmt.ll(c.selection.lat, c.selection.lon)}</span>
        </header>
        <div className="body">
          {c.isHazard ? (
            // A hazard value and a temperature reference are different quantities, so
            // they must never be printed side by side as if they were comparable.
            <dl className="kv">
              <dt>{c.hazardInfo.label}</dt>
              <dd className="hi">
                {fmt.num(activeHazField?.values?.[nearestIdx(c.selection.lat)]?.[nearestIdxLon(c.selection.lon)], 2)}
                <span className="un">{c.hazardInfo.unit}</span>
              </dd>
              <dt>Category</dt>
              <dd>{hazardCategory(activeHazField, c.selection, c.hazardVar)}</dd>
              <dt>Grid cell used</dt>
              <dd>
                {cmp?.grid_latitude !== null && cmp?.grid_latitude !== undefined
                  ? `${cmp.grid_latitude.toFixed(2)}°, ${cmp.grid_longitude.toFixed(2)}°`
                  : '—'}
              </dd>
            </dl>
          ) : (
            <dl className="kv">
              <dt>OceanEmbed °C</dt>
              <dd className="hi">{fmt.num(cmp?.oceanembed_temperature, 2)}</dd>
              <dt>GLORYS reference</dt>
              <dd>{fmt.num(cmp?.glorys_temperature, 2)}</dd>
              <dt>Difference</dt>
              <dd style={{ color: cmp?.difference > 0 ? 'var(--warn)' : 'var(--blue)' }}>{fmt.num(cmp?.difference, 2)}</dd>
              <dt>Grid cell used</dt>
              <dd>
                {cmp?.grid_latitude !== null && cmp?.grid_latitude !== undefined
                  ? `${cmp.grid_latitude.toFixed(2)}°, ${cmp.grid_longitude.toFixed(2)}°`
                  : '—'}
              </dd>
            </dl>
          )}

          {snapped && (
            <div className="note warn">
              This cell has no complete 0–1000 m column, so the value is read from a grid point
              {' '}{cmp.offset_degrees.toFixed(2)}° away. Typical on the shelf.
            </div>
          )}
          {!c.isHazard && state === 'model_unavailable' && (
            <div className="note bad">No model value at this cell and date.</div>
          )}
          {!c.isHazard && state === 'model_only' && (
            <div className="note">No GLORYS reference here — showing the model value alone.</div>
          )}
          {!c.isHazard && state === 'loading' && <div className="note">Resolving column…</div>}
          {c.isHazard && (
            <div className="note">
              Derived from the model's own 0–1000 m column, not from a satellite channel.
            </div>
          )}
        </div>
      </section>

      <section className="panel" style={{ minHeight: 232 }}>
        <header>
          <h2>Column</h2>
          <span className="sub">{c.isHazard ? 'temperature' : `${c.depth} m marked`}</span>
        </header>
        <div className="body" style={{ paddingTop: 6 }}>
          <ProfileChart
            depths={depths}
            model={model}
            glorys={c.compare && hasGlorys ? glorys : null}
            depthCursor={c.isHazard ? null : c.depth}
          />
          <div className="note">
            Even bands per standard level, so the thermocline is not crushed by the 700–1000 m gap.
            {!hasGlorys && ' GLORYS unavailable at this point.'}
          </div>
        </div>
      </section>

      <section className="panel">
        <header>
          <h2>Cyclone fuel</h2>
          <span className="sub">{haz?.status === 'available' ? fmt.pct(haz.coverage) + ' served' : 'unavailable'}</span>
        </header>
        <div className="body">
          {haz?.status === 'available' ? (
            <>
              <div className="tiles">
                <div className="tile wide">
                  <span>Favourable cells (TCHP ≥ 50)</span>
                  <b>{fmt.int(haz.favourableCells)}</b>
                  <i>of {fmt.int(haz.validCells)} served</i>
                </div>
                <div className="tile">
                  <span>Rapid intensification</span>
                  <b>{fmt.int(haz.rapidIntensificationCells)}</b>
                </div>
                <div className="tile">
                  <span>Median TCHP</span>
                  <b>{fmt.num(haz.metrics.find((m) => m.variable === 'tchp')?.median, 1)}<i>kJ/cm²</i></b>
                </div>
                <div className="tile">
                  <span>Median D26</span>
                  <b>{fmt.num(haz.metrics.find((m) => m.variable === 'd26')?.median, 1)}<i>m</i></b>
                </div>
              </div>
              <div className="note">
                A column too shallow to integrate reports no value, never a low risk.
              </div>
            </>
          ) : (
            <div className="empty">Hazard diagnostics unavailable for this date.</div>
          )}
        </div>
      </section>

      <section className="panel" style={{ minHeight: 178 }}>
        <header>
          <h2>Depth × time</h2>
          <span className="sub">{c.dates.length} days</span>
        </header>
        <div className="canvas-wrap" style={{ minHeight: 128 }}>
          <TimePanel profiles={c.timeProfiles} dates={c.dates} depthCursor={c.isHazard ? null : c.depth} />
        </div>
      </section>
    </aside>
  );
}

// Row index for a latitude; north-up, so row 0 is 30°N.
function nearestIdx(lat) {
  return Math.min(100, Math.max(0, Math.round((30 - lat) / 0.25)));
}
function nearestIdxLon(lon) {
  return Math.min(240, Math.max(0, Math.round((lon - 45) / 0.25)));
}

// Only TCHP carries the cyclone-intensity categories on the backend.
function hazardCategory(field, sel, hazardVar) {
  if (hazardVar !== 'tchp' || !field) return '—';
  const v = field.values?.[nearestIdx(sel.lat)]?.[nearestIdxLon(sel.lon)];
  if (v === null || v === undefined || !Number.isFinite(Number(v))) return 'no value';
  const breaks = [30, 50, 80];
  const labels = ['< 30 low', '30–50 moderate', '50–80 favourable', '> 80 rapid'];
  const k = breaks.findIndex((b) => Number(v) < b);
  return labels[k === -1 ? labels.length - 1 : k];
}

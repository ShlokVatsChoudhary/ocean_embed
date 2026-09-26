import { useEffect, useState } from 'react';
import { DepthSlider, DateControl } from '../components/controls';
import { VerticalProfileChart } from '../components/charts';
import { getComparison, getVerticalProfile, getArgoFloats, prettyDate } from '../api/oceanembed';

export default function AnalyzeView({ date, setDate, depth, setDepth, selected, setSelected }) {
  const [comparison, setComparison] = useState(null);
  const [comparisonError, setComparisonError] = useState(null);
  const [floats, setFloats] = useState([]);
  const [profile, setProfile] = useState(null);
  const [profileError, setProfileError] = useState(null);

  useEffect(() => {
    let dead = false;
    setComparison(null);
    setComparisonError(null);
    getComparison({ latitude: selected.lat, longitude: selected.lon, date, depth })
      .then((c) => { if (!dead) setComparison(c); })
      .catch((e) => { if (!dead) setComparisonError(e.message); });
    return () => { dead = true; };
  }, [date, depth, selected.lat, selected.lon]);

  useEffect(() => {
    let dead = false;
    getArgoFloats({ date })
      .then((f) => { if (!dead) setFloats(f); })
      .catch(() => { if (!dead) setFloats([]); });
    return () => { dead = true; };
  }, [date]);

  useEffect(() => {
    let dead = false;
    setProfileError(null);
    getVerticalProfile({ date, lat: selected.lat, lon: selected.lon })
      .then((p) => { if (!dead) setProfile(p); })
      .catch((e) => { if (!dead) setProfileError(e.message); });
    return () => { dead = true; };
  }, [date, selected]);

  const markers = floats.map((f) => ({ lat: f.lat, lon: f.lon, kind: 'argo' }));

  const loadFloat = (id) => {
    const f = floats.find((x) => x.id === id);
    if (f) setSelected({ lat: f.lat, lon: f.lon });
  };

  return (
    <div>
      <section className="panel">
        <h2>Comparison — {depth}m, {prettyDate(date)}</h2>
        <div className="map-controls">
          <DateControl date={date} onChange={setDate} />
        </div>
        <DepthSlider depth={depth} onChange={setDepth} />

        {comparisonError && (
          <div className="error-box">Comparison unavailable: {comparisonError}</div>
        )}
        {!comparison && !comparisonError && (
          <div className="notice">
            Comparison data is currently unavailable. The backend comparison endpoint is a placeholder contract and does not return real OceanEmbed/GLORYS values yet.
          </div>
        )}
        {comparison && (
          <div className="panel" style={{ marginTop: 12, padding: 16 }}>
            <h3>Comparison</h3>
            <div className="tri-grid">
              <div>
                <strong>Depth:</strong> {comparison.depth} m<br />
                <strong>Date:</strong> {prettyDate(comparison.date)}
              </div>
              <div>
                <strong>Location:</strong> {selected.lat.toFixed(4)}°, {selected.lon.toFixed(4)}°
              </div>
              <div>
                <strong>Unit:</strong> {comparison.unit === 'degC' ? '°C' : comparison.unit}
              </div>
            </div>
            <div className="tri-grid" style={{ marginTop: 12 }}>
              <div>
                <h4>OceanEmbed</h4>
                <div>{comparison.oceanembed_temperature == null ? 'Unavailable' : `${Number(comparison.oceanembed_temperature).toFixed(2)} °C`}</div>
              </div>
              <div>
                <h4>GLORYS</h4>
                <div>{comparison.glorys_temperature == null ? 'Unavailable' : `${Number(comparison.glorys_temperature).toFixed(2)} °C`}</div>
              </div>
              <div>
                <h4>Difference</h4>
                <div>{comparison.difference == null ? 'Unavailable' : `${Number(comparison.difference).toFixed(2)} °C`}</div>
              </div>
            </div>
          </div>
        )}
        <div className="muted small">● black dots = ARGO float profiles available on {prettyDate(date)} — click a float ID below or the map to load its profile.</div>
      </section>
      <div className="explore-grid" style={{ marginTop: 12 }}>
        <section className="panel">
          <h3>ARGO floats — {prettyDate(date)} ({floats.length})</h3>
          <div className="float-list">
            {floats.map((f) => (
              <button key={f.id} className="btn small" onClick={() => loadFloat(f.id)} title={`Load ${f.id}`}>
                {f.id} · {f.lat}°N {f.lon}°E
              </button>
            ))}
          </div>
        </section>
        <aside className="panel">
          <h3>Vertical profile — {selected.lat}°N, {selected.lon}°E</h3>
          {profileError && <div className="error-box">Failed to load profile: {profileError}</div>}
          {!profile && !profileError && <div className="loading">Loading profile…</div>}
          {profile && <VerticalProfileChart profile={profile} height={340} />}
        </aside>
      </div>
    </div>
  );
}

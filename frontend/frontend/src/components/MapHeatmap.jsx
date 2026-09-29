import { useEffect, useRef, useState } from 'react';
import { seqColor, divColor } from './color';
import { BBOX } from '../api/oceanembed';

// MapHeatmap: renders a 2D grid + optional coverage overlay + markers.
//
// Field rows are NORTH-UP (row 0 is the northernmost latitude) — see the note in
// api/oceanembed.js. The y-axis therefore maps the top of the plot to BBOX.latMax.
//
// Props: field {lats,lons,values,coverage,stats}, mode 'sequential'|'diverging',
// fixedRange {min,max} | null (shared scale), markers [{lat,lon,kind}],
// selected {lat,lon}|null, showCoverage bool, onSelect({lat,lon})|null, height.
export default function MapHeatmap({ field, mode = 'sequential', fixedRange = null, markers = [], selected = null, showCoverage = false, onSelect = null, height = 380 }) {
  const canvasRef = useRef(null);
  const wrapRef = useRef(null);
  const [hover, setHover] = useState(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const wrap = wrapRef.current;
    if (!canvas || !wrap || !field) return;
    const W = wrap.clientWidth || 600;
    const padL = 44, padR = 14, padT = 12, padB = 30;
    const H = height;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = W * dpr; canvas.height = H * dpr;
    canvas.style.width = W + 'px'; canvas.style.height = H + 'px';
    const ctx = canvas.getContext('2d');
    ctx.scale(dpr, dpr);
    ctx.fillStyle = '#f4f6f8';
    ctx.fillRect(0, 0, W, H);

    const { lats, lons, values, coverage } = field;
    const nLat = lats.length, nLon = lons.length;
    const plotW = W - padL - padR, plotH = H - padT - padB;
    let vmin, vmax;
    if (mode === 'diverging') {
      const m = fixedRange ? Math.max(Math.abs(fixedRange.min), Math.abs(fixedRange.max)) : 2.5;
      vmin = -m; vmax = m;
    } else if (fixedRange) { vmin = fixedRange.min; vmax = fixedRange.max; }
    else { vmin = field.stats.min; vmax = field.stats.max; }
    const span = Math.max(1e-9, vmax - vmin);

    const cw = plotW / nLon, ch = plotH / nLat;
    for (let i = 0; i < nLat; i++) {
      for (let j = 0; j < nLon; j++) {
        const rawValue = values[i]?.[j];
        const numericValue = rawValue !== null && rawValue !== undefined && Number.isFinite(Number(rawValue)) ? Number(rawValue) : null;
        if (numericValue === null) {
          ctx.fillStyle = '#eef2f7';
          ctx.fillRect(padL + j * cw, padT + i * ch, cw + 0.5, ch + 0.5);
          continue;
        }
        const t = (numericValue - vmin) / span;
        ctx.fillStyle = mode === 'diverging' ? divColor(t) : seqColor(t);
        ctx.fillRect(padL + j * cw, padT + i * ch, cw + 0.5, ch + 0.5);
        // Dim cells the model did not actually produce. `coverage` is 0/1 (finite value or
        // not), so this marks missing data rather than low statistical confidence.
        if (showCoverage && coverage && coverage[i][j] < 0.5) {
          ctx.fillStyle = 'rgba(20,25,35,0.42)';
          ctx.fillRect(padL + j * cw, padT + i * ch, cw + 0.5, ch + 0.5);
          ctx.strokeStyle = 'rgba(255,255,255,0.35)';
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.moveTo(padL + j * cw, padT + i * ch + ch);
          ctx.lineTo(padL + j * cw + cw, padT + i * ch);
          ctx.stroke();
        }
      }
    }
    const xOf = (lon) => padL + ((lon - BBOX.lonMin) / (BBOX.lonMax - BBOX.lonMin)) * plotW;
    const yOf = (lat) => padT + ((BBOX.latMax - lat) / (BBOX.latMax - BBOX.latMin)) * plotH;

    ctx.strokeStyle = 'rgba(255,255,255,0.4)'; ctx.lineWidth = 1;
    ctx.fillStyle = '#33414f'; ctx.font = '11px system-ui';
    for (let lat = 5; lat <= 30; lat += 5) {
      const y = yOf(lat);
      ctx.beginPath(); ctx.moveTo(padL, y); ctx.lineTo(padL + plotW, y); ctx.stroke();
      ctx.fillText(lat + '°N', 6, y + 4);
    }
    ctx.textAlign = 'center';
    for (let lon = 50; lon <= 100; lon += 10) {
      const x = xOf(lon);
      ctx.beginPath(); ctx.moveTo(x, padT); ctx.lineTo(x, padT + plotH); ctx.stroke();
      ctx.fillText(lon + '°E', x, H - 10);
    }
    ctx.textAlign = 'left';
    ctx.strokeStyle = '#33414f'; ctx.strokeRect(padL, padT, plotW, plotH);

    markers.forEach((m) => {
      const x = xOf(m.lon), y = yOf(m.lat);
      ctx.fillStyle = m.kind === 'alert' ? '#ff3b30' : '#111';
      ctx.strokeStyle = '#fff'; ctx.lineWidth = 1.5;
      ctx.beginPath(); ctx.arc(x, y, m.kind === 'alert' ? 6 : 3.5, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
    });
    if (selected) {
      const x = xOf(selected.lon), y = yOf(selected.lat);
      ctx.strokeStyle = '#000'; ctx.lineWidth = 2;
      ctx.beginPath(); ctx.arc(x, y, 7, 0, Math.PI * 2); ctx.stroke();
      ctx.strokeStyle = '#fff'; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.arc(x, y, 8.5, 0, Math.PI * 2); ctx.stroke();
      ctx.fillStyle = '#000';
      ctx.beginPath(); ctx.arc(x, y, 2, 0, Math.PI * 2); ctx.fill();
    }
    canvas._proj = { padL, padT, plotW, plotH, W };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [field, mode, showCoverage, JSON.stringify(markers), JSON.stringify(selected), height, fixedRange ? fixedRange.min + ':' + fixedRange.max : 'auto']);

  const handlePointerMove = (e) => {
    if (!field || !field.values || !field.lats || !field.lons || !canvasRef.current) {
      setHover(null);
      return;
    }
    const canvas = canvasRef.current;
    const proj = canvas._proj;
    if (!proj) return;
    const rect = canvas.getBoundingClientRect();
    const px = e.clientX - rect.left;
    const py = e.clientY - rect.top;
    const fx = (px - proj.padL) / proj.plotW;
    const fy = (py - proj.padT) / proj.plotH;
    if (fx < 0 || fx > 1 || fy < 0 || fy > 1) {
      setHover(null);
      return;
    }
    const lonIndex = Math.min(field.lons.length - 1, Math.max(0, Math.round(fx * (field.lons.length - 1))));
    const latIndex = Math.min(field.lats.length - 1, Math.max(0, Math.round(fy * (field.lats.length - 1))));
    const value = field.values?.[latIndex]?.[lonIndex];
    if (value === null || value === undefined || !Number.isFinite(Number(value))) {
      setHover(null);
      return;
    }
    // latIndex counts down from the north edge, matching the north-up rows.

    const lat = field.lats[latIndex];
    const lon = field.lons[lonIndex];
    setHover({
      x: Math.min(rect.width - 150, Math.max(12, px + 14)),
      y: Math.min(rect.height - 62, Math.max(12, py + 14)),
      value: Number(value),
      lat,
      lon,
    });
  };

  const handleClick = (e) => {
    if (!onSelect) return;
    const canvas = canvasRef.current;
    const proj = canvas._proj;
    if (!proj) return;
    const rect = canvas.getBoundingClientRect();
    const px = e.clientX - rect.left, py = e.clientY - rect.top;
    const fx = (px - proj.padL) / proj.plotW, fy = (py - proj.padT) / proj.plotH;
    if (fx < 0 || fx > 1 || fy < 0 || fy > 1) return;
    const lon = BBOX.lonMin + fx * (BBOX.lonMax - BBOX.lonMin);
    const lat = BBOX.latMax - fy * (BBOX.latMax - BBOX.latMin);
    onSelect({ lat: +lat.toFixed(2), lon: +lon.toFixed(2) });
  };

  const barVals = Array.from({ length: 48 }, (_, i) => i / 47);
  return (
    <div style={{ position: 'relative' }}>
      <div ref={wrapRef} style={{ width: '100%' }}>
        <canvas
          ref={canvasRef}
          onClick={handleClick}
          onPointerMove={handlePointerMove}
          onPointerLeave={() => setHover(null)}
          style={{ cursor: onSelect ? 'crosshair' : 'default', display: 'block', borderRadius: 6 }}
        />
      </div>
      {hover && (
        <div style={{
          position: 'absolute',
          left: hover.x,
          top: hover.y,
          background: 'rgba(17, 24, 39, 0.92)',
          color: '#fff',
          fontSize: 12,
          padding: '6px 8px',
          borderRadius: 6,
          pointerEvents: 'none',
          boxShadow: '0 6px 14px rgba(0,0,0,0.18)',
          zIndex: 10,
          minWidth: 130,
        }}>
          <div>Temperature: {hover.value.toFixed(2)} °C</div>
          <div>Lat: {hover.lat.toFixed(2)}°</div>
          <div>Lon: {hover.lon.toFixed(2)}°</div>
        </div>
      )}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 6 }}>
        <span style={{ fontSize: 11, color: '#445', minWidth: 44, textAlign: 'right' }}>
          {mode === 'diverging' ? `−${(fixedRange ? Math.max(Math.abs(fixedRange.min), Math.abs(fixedRange.max)) : 2.5).toFixed(1)}` : (fixedRange ? fixedRange.min.toFixed(1) : (field?.stats?.min ?? 0).toFixed(1))}°C
        </span>
        <div style={{ display: 'flex', flex: 1, height: 12, borderRadius: 3, overflow: 'hidden', border: '1px solid #cbd2da' }}>
          {barVals.map((t, i) => (
            <div key={i} style={{ flex: 1, background: mode === 'diverging' ? divColor(t) : seqColor(t) }} />
          ))}
        </div>
        <span style={{ fontSize: 11, color: '#445', minWidth: 44 }}>
          +{(mode === 'diverging' ? (fixedRange ? Math.max(Math.abs(fixedRange.min), Math.abs(fixedRange.max)) : 2.5) : (fixedRange ? fixedRange.max : (field?.stats?.max ?? 0))).toFixed(1)}°C
        </span>
        <span style={{ fontSize: 11, color: '#445' }}>°C scale</span>
      </div>
    </div>
  );
}

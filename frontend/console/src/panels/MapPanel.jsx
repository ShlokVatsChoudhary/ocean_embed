import { useCallback, useEffect, useRef, useState } from 'react';
import { BBOX } from '../api/oceanembed';
import { TOKENS, seqColor, divColor, catIndex, CAT_COLOURS } from '../lib/ramp';

// A fresh canvas map renderer. Everything is painted from one north-up grid:
// row 0 is the northern edge, which matches the backend adapter's convention.
//
// mode: 'seq' | 'div' | 'cat'
export default function MapPanel({
  field, mode = 'seq', range = null, unit = '°C', decimals = 2,
  markers = [], selected = null, onSelect = null, showCoverage = false,
  catBreaks = [30, 50, 80], catLabels = null,
}) {
  const canvasRef = useRef(null);
  const wrapRef = useRef(null);
  const [hover, setHover] = useState(null);
  const projRef = useRef(null);

  const paint = useCallback(() => {
    const canvas = canvasRef.current;
    const wrap = wrapRef.current;
    if (!canvas || !wrap) return;
    const W = Math.max(80, wrap.clientWidth);
    const H = Math.max(80, wrap.clientHeight);
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.round(W * dpr);
    canvas.height = Math.round(H * dpr);
    canvas.style.width = `${W}px`;
    canvas.style.height = `${H}px`;
    const ctx = canvas.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, W, H);

    ctx.fillStyle = TOKENS.bg;
    ctx.fillRect(0, 0, W, H);
    if (!field) { projRef.current = null; return; }

    const padL = 40, padR = 10, padT = 10, padB = 24;
    const plotW = W - padL - padR;
    const plotH = H - padT - padB;
    if (plotW < 20 || plotH < 20) { projRef.current = null; return; }

    const { values, coverage, lats, lons } = field;
    const nLat = lats.length;
    const nLon = lons.length;

    // Land and out-of-domain cells paint as land, so the coastline is drawn by
    // the data mask itself rather than a separate shapefile.
    ctx.fillStyle = TOKENS.land;
    ctx.fillRect(padL, padT, plotW, plotH);

    let vmin, vmax;
    if (mode === 'cat') { vmin = 0; vmax = 1; }
    else if (mode === 'div') {
      const m = range ? Math.max(Math.abs(range.min), Math.abs(range.max)) : 2.5;
      vmin = -m; vmax = m;
    } else if (range) { vmin = range.min; vmax = range.max; }
    else { vmin = field.stats.min; vmax = field.stats.max; }
    const span = Math.max(1e-9, vmax - vmin);

    const cw = plotW / nLon;
    const ch = plotH / nLat;

    for (let i = 0; i < nLat; i++) {
      const row = values[i];
      if (!row) continue;
      const y = padT + i * ch;
      for (let j = 0; j < nLon; j++) {
        const raw = row[j];
        if (raw === null || raw === undefined || !Number.isFinite(Number(raw))) continue;
        const v = Number(raw);
        if (mode === 'cat') {
          const k = catIndex(v, catBreaks);
          if (k < 0) continue;
          ctx.fillStyle = CAT_COLOURS[Math.min(CAT_COLOURS.length - 1, k)];
        } else {
          const t = (v - vmin) / span;
          ctx.fillStyle = mode === 'div' ? divColor(t) : seqColor(t);
        }
        // +0.6 px overlap hides the hairline seams between cells at fractional sizes.
        ctx.fillRect(padL + j * cw, y, cw + 0.6, ch + 0.6);
      }
    }

    // Coverage: cells the model did not produce are dimmed and hatched, so a
    // blank area is never mistaken for a cold one.
    if (showCoverage && coverage) {
      ctx.save();
      ctx.fillStyle = 'rgba(4, 12, 20, 0.62)';
      ctx.strokeStyle = 'rgba(120, 175, 205, 0.30)';
      ctx.lineWidth = 1;
      for (let i = 0; i < nLat; i++) {
        const crow = coverage[i];
        if (!crow) continue;
        for (let j = 0; j < nLon; j++) {
          if (crow[j] >= 0.5) continue;
          const x = padL + j * cw;
          const y = padT + i * ch;
          ctx.fillRect(x, y, cw + 0.6, ch + 0.6);
          if (cw > 2.6) {
            ctx.beginPath();
            ctx.moveTo(x, y + ch);
            ctx.lineTo(x + cw, y);
            ctx.stroke();
          }
        }
      }
      ctx.restore();
    }

    // Graticule
    ctx.font = TOKENS.font;
    ctx.textBaseline = 'middle';
    for (let lat = 5; lat <= 30; lat += 5) {
      const y = padT + ((BBOX.latMax - lat) / (BBOX.latMax - BBOX.latMin)) * plotH;
      ctx.strokeStyle = lat % 10 === 0 ? TOKENS.gridMajor : TOKENS.grid;
      ctx.beginPath(); ctx.moveTo(padL, y); ctx.lineTo(padL + plotW, y); ctx.stroke();
      ctx.fillStyle = lat % 10 === 0 ? TOKENS.labelMajor : TOKENS.label;
      ctx.textAlign = 'right';
      ctx.fillText(`${lat}°N`, padL - 6, y);
    }
    ctx.textBaseline = 'top';
    for (let lon = 45; lon <= 105; lon += 10) {
      const x = padL + ((lon - BBOX.lonMin) / (BBOX.lonMax - BBOX.lonMin)) * plotW;
      ctx.strokeStyle = lon % 30 === 0 ? TOKENS.gridMajor : TOKENS.grid;
      ctx.beginPath(); ctx.moveTo(x, padT); ctx.lineTo(x, padT + plotH); ctx.stroke();
      ctx.fillStyle = lon % 30 === 0 ? TOKENS.labelMajor : TOKENS.label;
      ctx.textAlign = 'center';
      ctx.fillText(`${lon}°E`, x, padT + plotH + 6);
    }

    ctx.strokeStyle = TOKENS.coast;
    ctx.lineWidth = 1;
    ctx.strokeRect(padL + 0.5, padT + 0.5, plotW - 1, plotH - 1);

    const xOf = (lon) => padL + ((lon - BBOX.lonMin) / (BBOX.lonMax - BBOX.lonMin)) * plotW;
    const yOf = (lat) => padT + ((BBOX.latMax - lat) / (BBOX.latMax - BBOX.latMin)) * plotH;

    ctx.textBaseline = 'middle';
    markers.forEach((m) => {
      const x = xOf(m.lon);
      const y = yOf(m.lat);
      ctx.beginPath();
      ctx.arc(x, y, 3.2, 0, Math.PI * 2);
      ctx.fillStyle = TOKENS.argo;
      ctx.fill();
      ctx.strokeStyle = TOKENS.argoRing;
      ctx.lineWidth = 1;
      ctx.stroke();
    });

    if (selected) {
      const x = xOf(selected.lon);
      const y = yOf(selected.lat);
      ctx.strokeStyle = 'rgba(47, 224, 192, 0.4)';
      ctx.lineWidth = 1;
      ctx.setLineDash([3, 4]);
      ctx.beginPath();
      ctx.moveTo(padL, y); ctx.lineTo(padL + plotW, y);
      ctx.moveTo(x, padT); ctx.lineTo(x, padT + plotH);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.beginPath();
      ctx.arc(x, y, 6, 0, Math.PI * 2);
      ctx.strokeStyle = TOKENS.select;
      ctx.lineWidth = 1.6;
      ctx.stroke();
      ctx.beginPath();
      ctx.arc(x, y, 1.8, 0, Math.PI * 2);
      ctx.fillStyle = TOKENS.select;
      ctx.fill();
    }

    projRef.current = { padL, padT, plotW, plotH };
  }, [field, mode, range, showCoverage, markers, selected, catBreaks]);

  useEffect(() => { paint(); }, [paint]);

  useEffect(() => {
    const wrap = wrapRef.current;
    if (!wrap || typeof ResizeObserver === 'undefined') return undefined;
    const ro = new ResizeObserver(() => paint());
    ro.observe(wrap);
    return () => ro.disconnect();
  }, [paint]);

  const toValue = (px, py) => {
    const p = projRef.current;
    if (!p || !field) return null;
    const fx = (px - p.padL) / p.plotW;
    const fy = (py - p.padT) / p.plotH;
    if (fx < 0 || fx > 1 || fy < 0 || fy > 1) return null;
    const j = Math.min(field.lons.length - 1, Math.max(0, Math.round(fx * (field.lons.length - 1))));
    const i = Math.min(field.lats.length - 1, Math.max(0, Math.round(fy * (field.lats.length - 1))));
    const raw = field.values?.[i]?.[j];
    const lat = field.lats[i];
    const lon = field.lons[j];
    const v = raw === null || raw === undefined || !Number.isFinite(Number(raw)) ? null : Number(raw);
    return { v, lat, lon };
  };

  const onMove = (e) => {
    const wrap = wrapRef.current;
    if (!wrap) return;
    const rect = wrap.getBoundingClientRect();
    const px = e.clientX - rect.left;
    const py = e.clientY - rect.top;
    const hit = toValue(px, py);
    if (!hit || hit.v === null) { setHover(null); return; }
    setHover({
      ...hit,
      x: Math.max(6, Math.min(rect.width - 150, px + 14)),
      y: Math.max(6, Math.min(rect.height - 78, py + 14)),
    });
  };

  const onClick = (e) => {
    if (!onSelect) return;
    const wrap = wrapRef.current;
    if (!wrap) return;
    const rect = wrap.getBoundingClientRect();
    const hit = toValue(e.clientX - rect.left, e.clientY - rect.top);
    if (hit) onSelect({ lat: +hit.lat.toFixed(2), lon: +hit.lon.toFixed(2) });
  };

  return (
    <div
      ref={wrapRef}
      style={{ position: 'relative', width: '100%', height: '100%', cursor: onSelect ? 'crosshair' : 'default' }}
      onPointerMove={onMove}
      onPointerLeave={() => setHover(null)}
      onClick={onClick}
    >
      <canvas ref={canvasRef} style={{ display: 'block', borderRadius: 6 }} />
      {hover && (
        <div className="tip" style={{ left: hover.x, top: hover.y }}>
          <div className="t-head">{hover.lat.toFixed(2)}°N · {hover.lon.toFixed(2)}°E</div>
          <div className="t-val">
            {mode === 'cat' && catLabels
              ? catLabels[Math.min(catLabels.length - 1, catIndex(hover.v, catBreaks))]?.split(' ')[0]
              : `${hover.v.toFixed(decimals)}`}
            {mode === 'cat' ? '' : <span style={{ fontSize: 10.5, color: 'var(--dim)' }}> {unit}</span>}
          </div>
          {mode === 'cat' && <div className="t-row"><span>value</span><span>{hover.v.toFixed(1)} {unit}</span></div>}
        </div>
      )}
    </div>
  );
}

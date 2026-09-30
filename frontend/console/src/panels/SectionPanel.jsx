import { useEffect, useRef } from 'react';
import { STANDARD_DEPTHS } from '../api/oceanembed';
import { TOKENS, seqColor } from '../lib/ramp';

// Depth x longitude section along the selected latitude.
//
// This is the view the original dashboard never had, and it is the one that
// actually shows the physics: the 26 °C isotherm, the thermocline sandwich and
// the coastal shoaling all read directly off a vertical slice. It is built from
// the same pre-fetched volume as the map, so it costs no extra requests.
//
// Rows are the model's 15 standard levels, drawn as even bands and labelled with
// their true depth. Even bands are deliberate: 0-50 m occupies the same height as
// 700-1000 m, which keeps the thermocline readable instead of crushing it.

const LABEL_LEVELS = [0, 50, 100, 200, 500, 1000];

export default function SectionPanel({ volume, lat, range, lon = null, onSelect }) {
  const canvasRef = useRef(null);
  const wrapRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const wrap = wrapRef.current;
    if (!canvas || !wrap) return;

    const draw = () => {
      const W = Math.max(80, wrap.clientWidth);
      const H = Math.max(80, wrap.clientHeight);
      const dpr = window.devicePixelRatio || 1;
      canvas.width = Math.round(W * dpr);
      canvas.height = Math.round(H * dpr);
      canvas.style.width = `${W}px`;
      canvas.style.height = `${H}px`;
      const ctx = canvas.getContext('2d');
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

      ctx.fillStyle = TOKENS.bg;
      ctx.fillRect(0, 0, W, H);

      const padL = 40, padR = 10, padT = 8, padB = 22;
      const plotW = W - padL - padR;
      const plotH = H - padT - padB;
      if (plotW < 30 || plotH < 30) return;

      // Build the slice: rows = depth level, cols = longitude.
      const levels = STANDARD_DEPTHS.filter((d) => volume[d]);
      ctx.fillStyle = TOKENS.missing;
      ctx.fillRect(padL, padT, plotW, plotH);

      if (!levels.length) {
        ctx.fillStyle = TOKENS.label;
        ctx.font = TOKENS.font;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText('loading depth volume…', padL + plotW / 2, padT + plotH / 2);
        return;
      }

      const first = volume[levels[0]];
      const nLon = first.lons.length;
      const nLev = STANDARD_DEPTHS.length; // keep fixed height even if a level is missing
      const cw = plotW / nLon;
      const ch = plotH / nLev;

      const vmin = range ? range.min : 0;
      const vmax = range ? range.max : 1;
      const span = Math.max(1e-9, vmax - vmin);

      levels.forEach((d) => {
        const f = volume[d];
        const i = Math.min(f.lats.length - 1, Math.max(0, Math.round((30 - lat) / 0.25)));
        const row = f.values?.[i];
        if (!row) return;
        const band = STANDARD_DEPTHS.indexOf(d);
        const y = padT + band * ch;
        for (let j = 0; j < nLon; j++) {
          const raw = row[j];
          if (raw === null || raw === undefined || !Number.isFinite(Number(raw))) continue;
          ctx.fillStyle = seqColor((Number(raw) - vmin) / span);
          ctx.fillRect(padL + j * cw, y, cw + 0.6, ch + 0.6);
        }
      });

      // Depth band labels on the left.
      ctx.font = TOKENS.font;
      ctx.textAlign = 'right';
      ctx.textBaseline = 'middle';
      STANDARD_DEPTHS.forEach((d, band) => {
        if (!LABEL_LEVELS.includes(d)) return;
        const y = padT + band * ch;
        ctx.strokeStyle = TOKENS.grid;
        ctx.beginPath(); ctx.moveTo(padL, y); ctx.lineTo(padL + plotW, y); ctx.stroke();
        ctx.fillStyle = TOKENS.labelMajor;
        ctx.fillText(`${d} m`, padL - 6, y + ch / 2);
      });

      // Longitude ticks.
      ctx.textAlign = 'center';
      ctx.textBaseline = 'top';
      for (let lonTick = 45; lonTick <= 105; lonTick += 10) {
        const x = padL + ((lonTick - 45) / 60) * plotW;
        ctx.strokeStyle = TOKENS.grid;
        ctx.beginPath(); ctx.moveTo(x, padT); ctx.lineTo(x, padT + plotH); ctx.stroke();
        ctx.fillStyle = TOKENS.label;
        ctx.fillText(`${lonTick}°E`, x, padT + plotH + 5);
      }

      ctx.strokeStyle = TOKENS.coast;
      ctx.lineWidth = 1;
      ctx.strokeRect(padL + 0.5, padT + 0.5, plotW - 1, plotH - 1);

      // The cursor longitude, so the section lines up with the map.
      if (lon !== null) {
        const x = padL + ((lon - 45) / 60) * plotW;
        ctx.strokeStyle = TOKENS.select;
        ctx.lineWidth = 1.4;
        ctx.setLineDash([3, 3]);
        ctx.beginPath(); ctx.moveTo(x, padT); ctx.lineTo(x, padT + plotH); ctx.stroke();
        ctx.setLineDash([]);
      }
    };

    draw();
    let ro;
    if (typeof ResizeObserver !== 'undefined') {
      ro = new ResizeObserver(draw);
      ro.observe(wrap);
    }
    return () => { if (ro) ro.disconnect(); };
  }, [volume, lat, range, lon]);

  const onClick = (e) => {
    if (!onSelect) return;
    const wrap = wrapRef.current;
    if (!wrap) return;
    const rect = wrap.getBoundingClientRect();
    const padL = 40, padR = 10;
    const plotW = Math.max(1, wrap.clientWidth - padL - padR);
    const fx = (e.clientX - rect.left - padL) / plotW;
    if (fx < 0 || fx > 1) return;
    onSelect(Math.round((45 + fx * 60) * 4) / 4);
  };

  return (
    <div ref={wrapRef} style={{ position: 'relative', width: '100%', height: '100%' }}>
      <canvas ref={canvasRef} onClick={onClick} style={{ display: 'block', borderRadius: 6, cursor: onSelect ? 'crosshair' : 'default' }} />
    </div>
  );
}

// Depth x time strip at the selected point. Seven days is enough to see the
// thermocline breathe, which a single-day snapshot cannot show.
export function TimePanel({ profiles, dates, depthCursor = null }) {
  const canvasRef = useRef(null);
  const wrapRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const wrap = wrapRef.current;
    if (!canvas || !wrap) return;

    const draw = () => {
      const W = Math.max(60, wrap.clientWidth);
      const H = Math.max(60, wrap.clientHeight);
      const dpr = window.devicePixelRatio || 1;
      canvas.width = Math.round(W * dpr);
      canvas.height = Math.round(H * dpr);
      canvas.style.width = `${W}px`;
      canvas.style.height = `${H}px`;
      const ctx = canvas.getContext('2d');
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

      ctx.fillStyle = TOKENS.bg;
      ctx.fillRect(0, 0, W, H);

      const padL = 34, padR = 6, padT = 6, padB = 18;
      const plotW = W - padL - padR;
      const plotH = H - padT - padB;
      ctx.fillStyle = TOKENS.missing;
      ctx.fillRect(padL, padT, plotW, plotH);
      if (plotW < 20 || plotH < 20) return;

      const withData = dates.filter((d) => profiles[d]);
      if (!withData.length) {
        ctx.fillStyle = TOKENS.label;
        ctx.font = TOKENS.font;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText('no profiles yet', padL + plotW / 2, padT + plotH / 2);
        return;
      }

      let lo = Infinity, hi = -Infinity;
      withData.forEach((d) => {
        (profiles[d].oceanembed || []).forEach((v) => {
          if (v === null || v === undefined || !Number.isFinite(Number(v))) return;
          lo = Math.min(lo, Number(v)); hi = Math.max(hi, Number(v));
        });
      });
      if (!Number.isFinite(lo) || hi <= lo) { lo = 0; hi = 1; }

      const nLev = STANDARD_DEPTHS.length;
      const cw = plotW / Math.max(1, dates.length);
      const ch = plotH / nLev;

      dates.forEach((d, col) => {
        const p = profiles[d];
        if (!p) return;
        p.depths.forEach((dep, k) => {
          const band = STANDARD_DEPTHS.indexOf(dep);
          if (band < 0) return;
          const v = p.oceanembed[k];
          if (v === null || v === undefined || !Number.isFinite(Number(v))) return;
          ctx.fillStyle = seqColor((Number(v) - lo) / (hi - lo));
          ctx.fillRect(padL + col * cw, padT + band * ch, cw + 0.6, ch + 0.6);
        });
      });

      ctx.font = TOKENS.font;
      ctx.textAlign = 'right';
      ctx.textBaseline = 'middle';
      [0, 50, 200, 1000].forEach((d) => {
        const band = STANDARD_DEPTHS.indexOf(d);
        if (band < 0) return;
        ctx.fillStyle = TOKENS.label;
        ctx.fillText(`${d}`, padL - 5, padT + band * ch + ch / 2);
      });

      ctx.textAlign = 'center';
      ctx.textBaseline = 'top';
      dates.forEach((d, col) => {
        ctx.fillStyle = TOKENS.label;
        ctx.fillText(d.slice(8), padL + col * cw + cw / 2, padT + plotH + 4);
      });

      ctx.strokeStyle = TOKENS.coast;
      ctx.strokeRect(padL + 0.5, padT + 0.5, plotW - 1, plotH - 1);

      if (depthCursor !== null) {
        const band = STANDARD_DEPTHS.indexOf(depthCursor);
        if (band >= 0) {
          ctx.strokeStyle = TOKENS.select;
          ctx.lineWidth = 1.4;
          ctx.beginPath();
          ctx.moveTo(padL, padT + band * ch);
          ctx.lineTo(padL + plotW, padT + band * ch);
          ctx.stroke();
        }
      }
    };

    draw();
    let ro;
    if (typeof ResizeObserver !== 'undefined') {
      ro = new ResizeObserver(draw);
      ro.observe(wrap);
    }
    return () => { if (ro) ro.disconnect(); };
  }, [profiles, dates, depthCursor]);

  return (
    <div ref={wrapRef} style={{ width: '100%', height: '100%' }}>
      <canvas ref={canvasRef} style={{ display: 'block', borderRadius: 6 }} />
    </div>
  );
}

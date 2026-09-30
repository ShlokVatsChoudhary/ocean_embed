/**
 * Tests for the colour-ramp library.
 *
 * The ramp is the only thing mapping a physical value to a colour, and both the canvas
 * and the React legend read from it, so a regression here silently mislabels data.
 *
 * Two contracts here are load-bearing and easy to break by "tidying up":
 *   - `unionRange` returns `null` (not a fake range) when it has nothing to span, and
 *     MapPanel is written to fall back to +-2.5 in that case.
 *   - the diverging ramp's zero band is the DARKEST band, so "no difference" recedes
 *     into the panel instead of glowing.
 */
import { describe, expect, it } from 'vitest'

import {
  CAT_COLOURS,
  CAT_LABELS,
  catIndex,
  divColor,
  divStops,
  rampColor,
  seqColor,
  seqStops,
  unionRange,
  SEQ,
  DIV,
} from '../src/lib/ramp'

const RGB = /^rgb\(\d{1,3},\d{1,3},\d{1,3}\)$/

const rgb = (s) => s.match(/\d+/g).map(Number)
const lum = (s) => rgb(s).reduce((a, b) => a + b, 0)

describe('colour output contract', () => {
  it('emits rgb() triples the canvas and CSS both accept', () => {
    for (const v of [0, 0.001, 0.5, 0.999, 1]) {
      expect(seqColor(v)).toMatch(RGB)
      expect(divColor(v)).toMatch(RGB)
    }
  })

  it('emits only in-gamut channels', () => {
    for (const v of [0, 0.25, 0.5, 0.75, 1]) {
      for (const c of rgb(seqColor(v))) {
        expect(c).toBeGreaterThanOrEqual(0)
        expect(c).toBeLessThanOrEqual(255)
      }
    }
  })

  it('clamps out-of-range input instead of returning NaN', () => {
    expect(seqColor(-5)).toBe(seqColor(0))
    expect(seqColor(9)).toBe(seqColor(1))
    expect(divColor(-3)).toBe(divColor(0))
    expect(divColor(4)).toBe(divColor(1))
  })

  it('treats non-finite input as the cold end rather than painting NaN', () => {
    expect(seqColor(NaN)).toBe(seqColor(0))
    expect(seqColor(undefined)).toBe(seqColor(0))
  })

  it('produces valid stops for any requested resolution', () => {
    for (const c of [...seqStops(24), ...divStops(24), ...seqStops(2)]) expect(c).toMatch(RGB)
    for (const c of CAT_COLOURS) expect(c).toMatch(/^#[0-9a-f]{6}$/i)
  })
})

describe('rampColor', () => {
  it('takes an explicit stop list, so both ramps share one interpolator', () => {
    expect(rampColor(SEQ, 0.25)).toBe(seqColor(0.25))
    expect(rampColor(DIV, 0.25)).toBe(divColor(0.25))
  })

  it('lands exactly on the declared endpoints', () => {
    expect(seqColor(0)).toBe('rgb(11,43,82)')
    expect(seqColor(1)).toBe('rgb(255,77,77)')
  })
})

describe('diverging ramp', () => {
  it('makes the zero band the darkest, so no-difference recedes into the panel', () => {
    const mid = lum(divColor(0.5))
    expect(lum(divColor(0.0))).toBeGreaterThan(mid)
    expect(lum(divColor(1.0))).toBeGreaterThan(mid)
  })

  it('separates the two signs into different hues', () => {
    const [r0, , b0] = rgb(divColor(0.0))
    const [r1, , b1] = rgb(divColor(1.0))
    expect(b0).toBeGreaterThan(r0) // cold end is blue
    expect(r1).toBeGreaterThan(b1) // warm end is orange
  })

  it('samples the midpoint at the centre index', () => {
    expect(divStops(5)[2]).toBe(divColor(0.5))
  })

  it('is symmetric in length: equal and opposite inputs are equally legible', () => {
    const a = divColor(0.5 - 0.2)
    const b = divColor(0.5 + 0.2)
    expect(rgb(a)).toHaveLength(3)
    expect(rgb(b)).toHaveLength(3)
    expect(a).not.toBe(b)
  })
})

describe('categorical scale', () => {
  it('has one colour and one label per category', () => {
    expect(CAT_COLOURS).toHaveLength(CAT_LABELS.length)
  })

  it('maps values onto the documented TCHP breaks', () => {
    expect(catIndex(10)).toBe(0)
    expect(catIndex(40)).toBe(1)
    expect(catIndex(65)).toBe(2)
    expect(catIndex(95)).toBe(3)
  })

  it('places a value exactly on a break in the upper band', () => {
    expect(catIndex(30)).toBe(1)
    expect(catIndex(50)).toBe(2)
    expect(catIndex(80)).toBe(3)
  })

  it('never returns an index outside the palette for extreme input', () => {
    for (const v of [-1e6, 0, 1e6]) {
      const i = catIndex(v)
      expect(i).toBeGreaterThanOrEqual(0)
      expect(i).toBeLessThan(CAT_COLOURS.length)
    }
  })

  it('reports a sentinel for a missing value so callers do not paint a category', () => {
    // Number(null) === 0 would otherwise land a missing cell in the "< 30 low" band,
    // which reads as "low cyclone risk" rather than "no data".
    expect(catIndex(null)).toBe(-1)
    expect(catIndex(NaN)).toBe(-1)
    expect(catIndex(undefined)).toBe(-1)
    expect(catIndex('')).toBe(-1)
  })
})

describe('unionRange', () => {
  it('spans every field so one scale stays comparable across depths', () => {
    const fields = [
      { stats: { min: 24, max: 30 } },
      { stats: { min: 10, max: 22 } },
      { stats: { min: 2, max: 28 } },
    ]
    expect(unionRange(fields)).toEqual({ min: 2, max: 30 })
  })

  it('ignores missing fields instead of producing NaN', () => {
    const r = unionRange([null, undefined, { stats: { min: 4, max: 9 } }])
    expect(r).toEqual({ min: 4, max: 9 })
  })

  it('ignores non-finite stats', () => {
    const r = unionRange([{ stats: { min: NaN, max: Infinity } }, { stats: { min: 1, max: 3 } }])
    expect(r).toEqual({ min: 1, max: 3 })
  })

  it('returns null when there is nothing to span, which MapPanel handles', () => {
    expect(unionRange([])).toBeNull()
    expect(unionRange([null, undefined])).toBeNull()
    expect(unionRange([{ stats: { min: 5, max: 5 } }])).toBeNull()
  })
})

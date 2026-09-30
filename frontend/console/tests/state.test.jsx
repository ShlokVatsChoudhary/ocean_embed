/**
 * Tests for the console's state layer, aimed squarely at the bugs that actually shipped.
 *
 * Every assertion here corresponds to a defect that was found by hand in the browser:
 *
 *   1. `Number(null) === 0` made a missing `?depth=` select 0 m (the surface) instead of
 *      the 100 m default, and put the cursor on 0°N 0°E instead of the basin default.
 *   2. The volume fetch and the hazard fetch shared one generation counter, so the hazard
 *      refetch cancelled the in-flight volume fetch and the map stayed blank forever.
 *   3. `?view=` was silently dropped because the deep-link parser never read it.
 *
 * The API layer is mocked, so these tests assert orchestration, not network behaviour.
 */
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import React from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { STANDARD_DEPTHS } from '../src/api/oceanembed'

const api = vi.hoisted(() => {
  const field = (value) => ({
    date: '2020-01-01',
    depth: 100,
    source: 'test',
    unit: 'degC',
    values: [[value, value], [value, value]],
    coverage: [[1, 1], [1, 1]],
    stats: { min: value - 1, max: value + 1, mean: value },
  })
  return {
    field,
    getSupportedDates: vi.fn(async () => ['2020-01-01', '2020-01-02']),
    getMetadata: vi.fn(async () => ({ modelVersion: 'test', params: 1, grid: { nLat: 101, nLon: 241 } })),
    getTemperatureField: vi.fn(async () => field(25)),
    getReferenceField: vi.fn(async () => ({ ...field(24), referenceSource: 'glorys_reference:bundled_sample' })),
    getComparison: vi.fn(async () => ({ state: 'model_and_reference', oceanembedTemperature: 25, glorysTemperature: 24 })),
    getHazardField: vi.fn(async () => ({ ...field(40), variable: 'tchp', label: 'TCHP', unit: 'kJ/cm\u00b2' })),
    getHazardSummary: vi.fn(async () => ({ validCells: 10, totalCells: 20, coverage: 0.5, favourableCells: 3, rapidIntensificationCells: 1, metrics: [] })),
    getArgoFloats: vi.fn(async () => []),
    getArgoTimeInfo: vi.fn(async () => null),
    getAnomalyAlerts: vi.fn(async () => []),
    getVerticalProfile: vi.fn(async () => ({ profile: [] })),
    HAZARD_VARIABLES: [{ id: 'tchp', label: 'Cyclone heat potential (TCHP)', unit: 'kJ/cm\u00b2', category: true }],
  }
})

vi.mock('../src/api/oceanembed', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, ...api }
})

const { ConsoleContext, useConsoleState } = await import('../src/state')

/** Renders the state hook and exposes it as JSON for assertions. */
function Probe() {
  const state = useConsoleState()
  return (
    <>
      <div data-testid="snapshot">
        {JSON.stringify({
          depth: state.depth,
          variable: state.variable,
          activeHazard: state.activeHazard,
          isHazard: state.isHazard,
          lat: state.selection.lat,
          lon: state.selection.lon,
          mapMode: state.mapMode,
          volumeKeys: Object.keys(state.volume || {}).length,
          referenceKeys: Object.keys(state.reference || {}).length,
          loadingVolume: Boolean(state.loading?.volume),
        })}
      </div>
    </>
  )
}

const read = () => JSON.parse(screen.getByTestId('snapshot').textContent)

async function mount(search = '') {
  // A single test may mount more than once (e.g. two deep links compared side by side),
  // so tear the previous tree down first or getByTestId matches several nodes.
  cleanup()
  window.history.replaceState(null, '', search ? `/?${search}` : '/')
  render(
    <ConsoleContext.Provider value={null}>
      <Probe />
    </ConsoleContext.Provider>,
  )
  await waitFor(() => expect(read().loadingVolume).toBe(false), { timeout: 4000 })
  return read()
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('deep links', () => {
  it('defaults to 100 m, not the surface', async () => {
    expect((await mount('')).depth).toBe(100)
  })

  it('honours an explicit 0 m, which is a real depth', async () => {
    expect((await mount('depth=0')).depth).toBe(0)
  })

  it('falls back to the default for a non-numeric or non-standard depth', async () => {
    expect((await mount('depth=abc')).depth).toBe(100)
    expect((await mount('depth=33')).depth).toBe(100)
  })

  it('defaults the cursor into the basin', async () => {
    const s = await mount('')
    expect(s.lat).toBe(12)
    expect(s.lon).toBe(88)
  })

  it('honours 0°N 0°E as real coordinates rather than treating falsy as absent', async () => {
    const s = await mount('lat=0&lon=0')
    expect(s.lat).toBe(0)
    expect(s.lon).toBe(0)
  })

  it('enters hazard mode from ?field=', async () => {
    const s = await mount('field=tchp')
    expect(s.isHazard).toBe(true)
    expect(s.activeHazard).toBe('tchp')
  })

  it('opens the difference view from ?view=difference', async () => {
    expect((await mount('view=difference')).mapMode).toBe('difference')
  })
})

describe('fetch orchestration', () => {
  it('loads a volume covering every standard depth', async () => {
    const s = await mount('')
    expect(s.volumeKeys).toBe(STANDARD_DEPTHS.length)
  })

  it('never leaves the volume loading flag stuck after a hazard refetch', async () => {
    // Regression: one shared generation counter meant the hazard effect invalidated the
    // in-flight volume fetch, which bailed out without clearing its loading flag.
    const s = await mount('field=tchp')
    expect(s.loadingVolume).toBe(false)
    expect(s.volumeKeys).toBe(STANDARD_DEPTHS.length)
  })

  it('does not fetch the reference field until the difference view is opened', async () => {
    await mount('')
    expect(api.getReferenceField).not.toHaveBeenCalled()
    expect(read().referenceKeys).toBe(0)
  })

  it('fetches the reference field when the difference view is open', async () => {
    const s = await mount('view=difference')
    expect(api.getReferenceField).toHaveBeenCalled()
    expect(s.referenceKeys).toBe(1)
  })
})

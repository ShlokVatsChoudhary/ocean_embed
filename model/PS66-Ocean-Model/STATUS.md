# PS66 — Status Report

**Project:** Satellite-Embedding Deep Learning for subsurface ocean temperature
reconstruction, North Indian Ocean (5–30°N, 45–105°E), daily @ 0.25°.
**Location:** `~/Desktop/siH-ps66`
**Last updated:** after the regrid fix (see §9)

> **⚠️ All skill numbers below are INVALID and must be re-run.**
> `harmonize._regrid` was silently corrupting the data (see §9). Every metric,
> figure and checkpoint in this file was computed on corrupted arrays.

---

## 1. TL;DR

Days 1–2 are **done and verified on real data**. We have a working end-to-end
data pipeline (download → regrid → arrays), a baseline/evaluation harness, and
an independent ARGO validation loader. The deep-learning model (Days 3–5) is
**not started**.

---

## 2. What is built

| Component | File | Status |
|---|---|---|
| Config (domain, depths, dataset IDs) | `src/config.py` | ✅ |
| Copernicus downloaders | `src/download.py` | ✅ verified |
| Regrid / harmonise / ocean mask | `src/harmonize.py` | ✅ verified |
| Metrics (RMSE/Bias/MAE/Corr vs depth) | `src/metrics.py` | ✅ |
| Baselines (persistence, climatology, SST→T MLP) | `src/baselines.py` | ✅ |
| ARGO validation loader (INCOIS ERDDAP) | `src/argo.py` | ✅ verified |
| Plotting | `src/viz.py` | ✅ |
| Day-1 driver | `run_day1.py` | ✅ |
| Day-2 driver | `run_day2.py` | ✅ |
| Notebook | `notebooks/01_inspect.ipynb` | ✅ |

## 3. Data decisions (important)

- **Target T(z):** switched from GLORYS12V1 @ 0.083° to the **GLORYS ensemble
  member `thetao_glor` @ 0.25°** (`cmems_mod_glo_phy-all_my_0.25deg_P1D-m`).
  - Native 0.25° → no regrid; ~13× smaller/faster (1.6 vs 21 GB/yr).
  - Covers 1993–2024, 75 levels, daily.
- **Inputs (real):** SST = OSTIA (0.05°), SSH/SLA + geostrophic currents =
  DUACS (0.125°). Both regridded to 0.25°.
- **ARGO validation:** INCOIS **ERDDAP** gridded Argo (10-day, McCreary),
  variable `T_ANALYZED`, regridded to 0.25° and 15 standard depths. Never used
  for training.
- **Ocean mask:** from target-product valid cells (fixes a land-leak bug).

## 4. Arrays / dataset downloaded (so far)

- January 2020: `target` (139 MB) + `duacs` (48 MB) + `ostia` (37 MB).
- Built arrays for Jan 2020:
  - `X` (time, channel, lat, lon) = `(31, 4, 101, 241)` — sst, sla, ugos, vgos
  - `Y` (time, depth, lat, lon) = `(31, 15, 101, 241)`
- ARGO test slice: `data/raw/argo_2020Q1.nc` (1 MB).

## 5. Baseline results — Jan 2020 (test = last 7 days)

| Baseline | RMSE mean | Corr mean | RMSE 0–200 m |
|---|---|---|---|
| persistence (last train day) | **0.38 °C** | 0.99 | 0.44 |
| climatology (per-pixel) | **0.67 °C** | 0.96 | 0.77 |
| SST+SLA→T MLP (+ lat/lon) | **1.24 °C** | 0.93 | 0.86 |

**Key insight:** deep-temperature variability is dominated by *location*
(std ≈ 5.9 °C at 700 m, Arabian Sea vs Bay of Bengal). A pointwise surface→T
map (MLP) loses to per-pixel climatology. Adding lat/lon cut MLP error 2.49 →
1.24 °C, confirming the model **must** use spatial/static context — which the
CNN encoder is designed to provide.

*Caveat:* one month is a winter-only, preliminary test. Baselines must be
re-run on ≥1 year before drawing conclusions.

## 6. Known issues / TODO

- [ ] **Bathymetry-aware mask** — do not score depth levels below the seabed
      (17.6% of ocean cells are shelves; caused spurious 32 °C at 100 m).
- [ ] Download ≥1 full year for meaningful baselines/climatology.
- [ ] Add SSS (SMAP/SMOS) and winds (CCMP) input channels.
- [ ] ARGO is 10-day; define the daily-matching protocol (nearest day).
- [ ] Persistence baseline should also be reported at a 10-day lead.

## 7. Next steps — Day 3

1. TensorFlow encoder (CNN embedding engine) + depth decoder.
2. Train on ≥1 year; target to **beat persistence (0.38 °C)**.
3. Produce the RMSE-vs-depth curve vs baselines.

## 8. Reproduce

```bash
cd ~/siH-ps66
python run_day1.py 2020-01-01 2020-01-03     # pipeline smoke test
python run_day2.py 2020-01-01 2020-01-31     # baselines + metrics + plot
```

## Day 3b — Bathymetry fix (complete)

**Bug:** over shallow shelves (seabed above the requested depth) vertical
filling smeared warm surface water down the whole column -> spurious
~31-32 C values at 1000 m, and the 1000 m level was pure extrapolation
(native GLORYS file only reached 947 m).

**Fix:**
- `config.py`: `max_depth` per dataset; target/glorys now download to **1500 m**.
- `download.py`: depth-cap is written into the filename (`_z1500`) so a
  changed cap forces a fresh download.
- `harmonize.py`: new `_seabed_depth()` derives per-cell seabed depth from the
  deepest finite native level; target depths below the seabed are masked out.
  Seabed saved as `data/processed/bathy_<tag>.npy`.
- `run_ingest.py`: carries the static bathy through to the combined tag.

**Verified:** 100 m max 31.05 -> 29.78 C; 1000 m went from 0 valid cells to
9,188; no cell exceeds 33 C anywhere.

### Results after fix (Jan-Mar 2020)

> **SUPERSEDED — see §10.** The table below is the *unweighted all-depth mean* on
> the first honest rebuild. It is retained only as history. The all-depth mean is
> dominated by near-surface levels and the SST→T MLP baseline had a channel bug;
> the corrected, common-mask results are in §10.

| method | mean RMSE | Corr |
|---|---|---|
| persistence (cheat: sees yesterday's truth) | 0.520 | 0.968 |
| **model (encoder-decoder)** | **0.574** | **0.955** |
| sst->T MLP | 0.707 | 0.926 |
| climatology | 0.817 | 0.935 |

Model RMSE improved **0.848 -> 0.574** (~32% better). Beats both legitimate
baselines. Model output range 5.11-31.84 C, truth 5.84-32.05 C: 0 impossible
values.

Files: `checkpoints/model_2020-01-01_2020-03-31.weights.h5`,
`figures/model_rmse_*.png`, `figures/baselines_rmse_*.png`,
`figures/demo_fields_*.png`, `figures/demo_profiles_*.png`,
`figures/model_architecture.png`.

**Not started:** multi-year ingest (by request).

---

## 9. Day 3c — regrid bug found and fixed (results invalidated)

**Bug.** `harmonize._regrid` called `xarray.DataArray.interp(..., method=
"linear")`. In the pinned stack (xarray 2026.7.0, scipy 1.18.0, numpy 2.5.0)
`interp` returns **NaN at coordinates that lie exactly on the source grid**. The
GLORYS 0.25 deg target is already on the project grid, so its profile was being
destroyed by a regrid that should have been a no-op. The `ffill`/`bfill` that
followed then substituted whole donor columns for the NaNs.

Evidence, 7.5 N 93.75 E, day 0 (open ocean, seabed 628 m):

```
native GLORYS  0m 28.08 ... 200m 13.53 ... 500m 9.86 ... 628m 9.10
old Y array    0m 27.56 27.56 27.56 27.56 27.53 27.53 27.53 ... 27.53   <- flat
```

`scipy.interpolate.interp1d` on the same column returns the correct value;
`xarray.interp` returns NaN at that exact grid point.

Damage, day 0, vs an independent `RegularGridInterpolator` reference: 0.2–2.3 %
of ocean cells wrong by more than 0.01 °C, **up to 20 °C**, concentrated on
shelves and coasts. `Tmax` was 29.78 °C at 200/300/500 m and 28.58 °C at
1000 m. The "Day 3b bathymetry fix" was masking a symptom of this, not its
cause: `_seabed_depth` *over*estimates the seabed, so flat garbage profiles
survived the depth mask.

**Fix** (`src/harmonize.py`), with `tests/test_harmonize.py` pinning it:

- Regular-grid resampling written out explicitly (`_axis_weights`, `_bilinear`,
  `_nearest_axis`). No `xarray.interp` anywhere. Exact identity when the grids
  coincide, which is the GLORYS case.
- `ffill`/`bfill` replaced by `_fill_nearest`: a distance-limited
  (`MAX_FILL_DIST` = 2 cells) nearest-valid fill, with the donor map built
  **per vertical level** from data collapsed over time. A deep level can no
  longer be filled from a shallow neighbour, and the fill geometry cannot
  flicker between days.
- `_to_standard_depths` no longer `ffill`s downward. Below-seabed levels stay
  NaN and are dropped by the bathymetry mask. Only 0 m is extrapolated, from
  GLORYS' shallowest native level (~0.49 m).
- `_regrid_nearest` (ocean mask, bathymetry) also rewritten; it had the same
  exposure.

**Verified.** Rebuilt against real GLORYS: agreement with the independent
reference is now bit-exact at all 15 depths — 0.00 % of cells differ, max error
0.000 °C, correlation 1.0000 (was 0.2–2.3 % wrong, up to 20 °C). The ocean/land
footprint per level is unchanged, so no data was lost, only corrected.

| depth | `Tmax` before | `Tmax` after |
|---|---|---|
| 100 m | 29.78 | 29.03 |
| 200 m | 29.78 | 21.51 |
| 300 m | 29.78 | 18.23 |
| 500 m | 29.78 | 16.17 |
| 1000 m | 28.58 | 12.83 |

Cross-checks on the rebuilt arrays: OSTIA SST vs GLORYS T(0 m) gives
bias +0.14 °C, RMSE 0.43 °C, corr 0.974 (consistent with an L4 skin-temperature
product against a model); domain-mean T(0) − T(50 m) is +0.1 to +0.8 °C, right
for a winter-mixed North Indian Ocean; no cell exceeds 33 °C.

**Consequences — still to do:**

1. Re-ingest every month (`run_ingest.py --combine-only` will not do; the
   harmonise step must re-run) and rebuild the arrays.
2. Re-run `run_day2.py` and `run_day3.py`; **discard all current numbers** in
   §5 and the Day 3b table. Expect honest skill to get *worse* before it gets
   better — the previous model was partly fitting a spatially smoothed target.
3. Report a `>= 50 m` RMSE alongside the all-depth mean. Six of the fifteen
   levels are within 20 m of the surface and are nearly free given SST as an
   input, so the unweighted mean overstates skill.
4. Score every depth on a common mask, or publish per-level sample counts: the
   valid fraction falls 48.8 % -> 37.7 % with depth, so deep levels are
   currently scored on an easier, different set of cells.
5. The climatology baseline is a strawman at 3 months (no seasonality). It needs
   >= 1 year of training days to be a fair comparison.


---

## 10. Re-run after the regrid fix + SSS wiring (HONEST results)

**What was done.** After the §9 regrid fix, the arrays were rebuilt
(`run_ingest.py ... --force`), SSS was wired in as a real 5th channel
(`sst, sss, sla, ugos, vgos`), the dishonest metric aggregation was replaced
(see §10.1), and a silent baseline bug was fixed (the SST→T MLP had been
selecting `ugos` where it thought `sla` was). Baselines and the model were then
re-run on Jan–Mar 2020.

**The headline is that the model does NOT beat persistence.** The earlier
"model 0.574 / 0.51 beats persistence" was an artefact of (a) the unweighted
all-depth mean being dominated by the four near-surface levels, which are nearly
free given SST as an input, and (b) the buggy MLP baseline.

### 10.1 Metric aggregation fix
`src/metrics.py` now reports, in addition to the per-level table:
- **common-mask** metrics: every level scored on cells valid at *all* depths
  (removes the moving-mask bias — the valid fraction falls 48.8 % → 37.7 %
  with depth);
- **band means**: `>=50 m` and thermocline `50–200 m`.
Tests: `tests/test_metrics.py` (6/6).

### 10.2 Results — common mask, Jan–Mar 2020 (test = last 18 days)

| Method | all-depth | >=50 m | thermocline 50–200 m | corr |
|---|---|---|---|---|
| **persistence** | **0.487** | **0.430** | **0.619** | 0.968 |
| model (5-ch) | 0.512 | 0.552 | 0.731 | 0.959 |
| sst_mlp (5-ch) | 0.522 | 0.583 | 0.822 | 0.959 |
| climatology | 0.813 | 0.740 | 1.080 | 0.929 |

Per-depth: the **model beats persistence only at 0, 5, 10, 20 m**. Persistence
wins at 30, 50, 75, 100, 125, 150, 200, 300, 500, 700, 1000 m.

### 10.3 Interpretation
- The model **is the best at the surface** (SST+SSS pin the top ~20 m).
- The model **beats both legitimate baselines** (climatology, SST→T MLP)
  through the thermocline, but **loses to persistence** there and below.
- Adding SSS improved the SST→T MLP (mean 0.660 → 0.578) but did not flip the
  model-vs-persistence outcome.
- With only 91 days of a single winter season, persistence is extremely strong
  because the deep ocean barely changes over the 18-day test window. This is
  not a fair setting in which to claim deep skill.

### 10.4 Consequence for the pitch
`PIPELINE_EXPLANATION.md` and `make_ppt_illustrated.py` still quote
**0.574 °C / 0.955** and "outperforms". **Those numbers are obsolete and
overstated.** The truthful claim is: *best at the surface and over both
naive baselines through the thermocline; not yet better than persistence below
30 m.* Do not present the old figures.

### 10.5 To actually beat persistence
1. Train on anomalies relative to persistence/climatology (predict the
   *increment*, not the field) so the model cannot do worse than the baseline.
2. Multi-year training (>=1 year, ideally 10) so seasonality exists and the
   persistence/climatology comparison is fair.
3. ARGO validation on this checkpoint (`src/argo.py`) — never run yet.
4. Add winds/currents (CCMP/OSCAR) — currently missing.

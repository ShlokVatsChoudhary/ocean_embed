# PS66 — Architecture & Technical Documentation

**Satellite-Embedding Deep Learning for 3-D Subsurface Ocean Temperature, North Indian Ocean**

| | |
|---|---|
| **Problem statement** | PS66 |
| **Domain** | North Indian Ocean, 5–30 °N, 45–105 °E |
| **Grid** | 0.25° × 0.25°, daily |
| **Input** | Surface satellite observations (5 variables) |
| **Output** | Temperature at 15 standard depths (0–1000 m) |
| **Framework** | TensorFlow / Keras 3 (TensorFlow 2.21) |
| **Last verified** | after the regrid fix + SSS wiring (STATUS.md §10) |

> **Read this first.** The end-to-end pipeline, the honest evaluation, and the
> current (negative) result are all documented below. Earlier numbers quoting
> **0.574 °C / 0.955** were computed on **corrupted data** and are retracted —
> see §9 and `STATUS.md` §10.

---

## Table of contents

1. [Scientific objective](#1-scientific-objective)
2. [Repository layout](#2-repository-layout)
3. [Data sources](#3-data-sources)
4. [Data pipeline & harmonisation](#4-data-pipeline--harmonisation)
5. [Arrays & tensor shapes](#5-arrays--tensor-shapes)
6. [Model architecture](#6-model-architecture)
7. [Training procedure](#7-training-procedure)
8. [Evaluation: baselines, metrics, honest harness](#8-evaluation)
9. [Derived hazard diagnostics](#9-derived-hazard-diagnostics)
10. [Reproducing](#10-reproducing)
11. [Current status & results](#11-current-status--results)
12. [Known issues & next steps](#12-known-issues--next-steps)

---

## 1. Scientific objective

Subsurface ocean temperature controls upper-ocean heat content, stratification,
marine heatwaves, cyclone intensification and marine ecosystems. Direct
measurements (ARGO floats, moorings, gliders, ships) are spatially and
temporally sparse. Satellites, in contrast, observe the **surface**
continuously and at high resolution — SST, SSS, SSH/SLA, surface currents and
winds — and these surface fields carry indirect signatures of the subsurface
through thermocline displacement, eddies, mixing and transport.

The objective is to learn a mapping

```
f( surface satellite fields, day t, location )  ->  T(z, day t, location)
```

for the **15 standard depths** (0, 5, 10, 20, 30, 50, 75, 100, 125, 150, 200,
300, 500, 700, 1000 m), using a compact learned "satellite embedding" as the
shared latent representation of the surface state.

---

## 2. Repository layout

```
siH-PS66/
├── src/
│   ├── config.py        Domain, grid, standard depths, dataset IDs, channel list
│   ├── download.py      Copernicus Marine + CCMP/HTTP download wrappers
│   ├── harmonize.py     Regrid → standard depths → ocean/bathy masks → X/Y arrays
│   ├── data.py          tf.data pipeline, per-channel normalisation
│   ├── model.py         Encoder / Decoder / OceanModel (train step, loss)
│   ├── baselines.py     persistence, climatology, SST→T MLP
│   ├── metrics.py       per-depth metrics + honest aggregation (common mask, bands)
│   ├── argo.py          Independent ARGO validation loader (INCOIS ERDDAP)
│   ├── hazard.py        TCHP, D26, OHC, MLD, thermocline (derived diagnostics)
│   └── viz.py           Map + RMSE-vs-depth plotting
├── tests/
│   ├── test_harmonize.py  Regrid/vertical-interp regression tests (16)
│   └── test_metrics.py    Metric-aggregation tests (6)
├── run_day1.py          Download → harmonise → arrays → T@100m map
├── run_day2.py          Baselines + metrics + RMSE-vs-depth
├── run_day3.py          Train encoder–decoder + evaluate
├── run_ingest.py        Resumable month-by-month ingest (--force to rebuild)
├── demo_model.py        Truth vs prediction vs error figures
├── show_model.py        Architecture schematic figure
├── make_ppt_figure.py / make_ppt_illustrated.py   Presentation figures
├── data/raw/            Downloaded NetCDF (git-ignored)
├── data/processed/      X_*.npy, Y_*.npy, stats_*.npz, bathy_*.npy (git-ignored)
├── checkpoints/         model_*.weights.h5 (git-ignored)
├── figures/             Output PNGs
├── logs/                Run logs (git-ignored)
├── README.md / STATUS.md / TODO.md / PIPELINE_EXPLANATION.md
└── ARCHITECTURE.md      (this file)
```

---

## 3. Data sources

All dataset IDs were verified against the Copernicus Marine catalogue.

### 3.1 Inputs (surface observations)

| Channel | Variable | Product | Native res. | Role |
|---|---|---|---|---|
| `sst` | `analysed_sst` | OSTIA L4 reprocessed (`METOFFICE-GLO-SST-L4-REP-OBS-SST`) | 0.05°, daily | SST |
| `sss` | `sos` | SMAP+SMOS multi-obs L4 (`cmems_obs-mob_glo_phy-sss_my_multi_P1D`) | 0.125°, daily | Sea-surface salinity |
| `sla` | `sla` | DUACS L4 (`cmems_obs-sl_glo_phy-ssh_my_allsat-l4-duacs-0.125deg_P1D`) | 0.125°, daily | SSH anomaly |
| `ugos` | `ugos` | DUACS L4 | 0.125°, daily | Geostrophic current (zonal) |
| `vgos` | `vgos` | DUACS L4 | 0.125°, daily | Geostrophic current (meridional) |
| `uwnd` | `uwnd` | CCMP v3.1 (RSS) | 0.25°, daily | 10 m wind — **not wired** |
| `vwnd` | `vwnd` | CCMP v3.1 (RSS) | 0.25°, daily | 10 m wind — **not wired** |

### 3.2 Target (subsurface temperature)

| Variable | Product | Native res. | Levels | Notes |
|---|---|---|---|---|
| `thetao_glor` | GLORYS ensemble member, `cmems_mod_glo_phy-all_my_0.25deg_P1D-m` | **0.25°**, daily | 75 | 1993–2024. Native 0.25° → **no horizontal regrid needed**. Downloaded to 1500 m so the 1000 m level is interpolated, not extrapolated. |

A heavier fallback (`glorys`, GLORYS12V1 `cmems_mod_glo_phy_my_0.083deg_P1D-m`)
is configured in `config.py` but not used.

### 3.3 Independent validation

| Variable | Product | Notes |
|---|---|---|
| `T_ANALYZED` | INCOIS ERDDAP gridded Argo (10-day, McCreary) | Regridded to 0.25° and 15 standard depths. **Never used for training.** Not yet run. |

---

## 4. Data pipeline & harmonisation

Implemented in `src/harmonize.py`; driven by `run_ingest.py` (per month) or
`run_day1.py` / `run_day2.py` (single window).

```
raw NetCDF                 harmonise                          processed arrays
──────────                 ─────────                          ────────────────
GLORYS thetao_glor  ──┬──▶ _to_standard_depths (0–1000 m) ──▶ theta
                      └──▶ _seabed_depth ────────────────────┐
DUACS sla/ugos/vgos ─────▶ _regrid (bilinear + local fill) ──┤
OSTIA analysed_sst  ─────▶ (K→°C) + _regrid ─────────────────┤
SMAP+SMOS sos       ─────▶ _regrid ──────────────────────────┤
                                                             ▼
                                      time intersection, ocean mask, stacking
                                                             │
                                          X (T,C,H,W), Y (T,Z,H,W), bathy, stats
```

### 4.1 Grid
Target grid from `config.py`: lat 5→30°, lon 45→105° at 0.25° →
`LAT` (101), `LON` (241).

### 4.2 Horizontal regrid (`_regrid`)

Written out explicitly — **`xarray.DataArray.interp` is deliberately not used**.
Two steps:

1. **Bilinear** resampling via `_axis_weights` + `_bilinear`. Exact identity when
   the source grid already equals the target (the GLORYS case).
2. **Distance-limited nearest fill** (`_fill_nearest`) for cells whose bilinear
   stencil touches NaN or that lie just outside the source domain. The donor map
   is built **per vertical level** from data collapsed over time, with
   `MAX_FILL_DIST = 2` cells. Consequences:
   - a deep level can never be filled from a shallow neighbour;
   - the fill footprint cannot flicker between days;
   - anything farther than 2 cells stays NaN and is dropped by the ocean mask.

`_regrid_nearest` (nearest-neighbour) is used for the ocean mask and bathymetry
and is also exact-identity when grids coincide.

> **Why this matters.** See §9. In the pinned stack (xarray 2026.7.0 /
> scipy 1.18.0), `xarray.interp` returned NaN at coordinates lying exactly on
> the source grid, silently destroying the GLORYS target and filling it with
> donor columns.

### 4.3 Vertical interpolation (`_to_standard_depths`)

Linear interpolation of the native GLORYS levels onto the 15 standard depths.
Only the **surface** (0 m) is extrapolated (GLORYS' shallowest level is
~0.49 m). Levels **below the seabed stay NaN** — they are deliberately *not*
filled downward.

### 4.4 Bathymetry & ocean mask

- `_seabed_depth`: per-cell seabed estimate = the deepest native level holding
  data. Target levels below the seabed are masked out.
- `_ocean_mask`: a cell is ocean if the target is finite on its shallowest
  level for at least one day; applied consistently to **all** channels.

### 4.5 SSS handling

The SMAP+SMOS `sos` field carries a singleton depth dimension, squeezed in
`build_arrays`. Values decode to PSU (~28–40). SSS is added as a channel only
when an `sss_path` is supplied; otherwise the pipeline falls back to any
salinity carried inside the target file (`so_glor`/`so`).

---

## 5. Arrays & tensor shapes

For `tag = 2020-01-01_2020-03-31`:

| Object | Shape | Meaning |
|---|---|---|
| `X_<tag>.npy` | `(T, C, 101, 241)` = `(91, 5, 101, 241)` | Surface inputs |
| `Y_<tag>.npy` | `(T, Z, 101, 241)` = `(91, 15, 101, 241)` | Temperature profiles |
| `channels_<tag>.npy` | `(C,)` = `['sst','sss','sla','ugos','vgos']` | Channel names |
| `stats_<tag>.npz` | `x_mean_*`, `x_std_*`, `y_mean`, `y_std` | Normalisation |
| `bathy_<tag>.npy` | `(101, 241)` | Seabed depth (m) |

- Land/missing cells are **NaN** in both `X` and `Y`.
- Valid ocean fraction falls with depth: **48.8 % at 0 m → 37.7 % at 1000 m**
  (bathymetry masking).

---

## 6. Model architecture

Implemented in `src/model.py`. An **encoder–decoder CNN** with an
attention-pooled global embedding and skip connections.

### 6.1 Block: `ConvBlock`

```
x ─▶ Conv2D(cout, 3×3, same, no bias) ─▶ GroupNorm(8) ─▶ GELU
  ─▶ Conv2D(cout, 3×3, same, no bias) ─▶ GroupNorm(8) ─▶ GELU
```

### 6.2 Encoder — the "embedding engine"

```
input (B, C, 101, 241)
   │ transpose → (B, 101, 241, C)
   ▼
stem   ConvBlock(24)                     → (B, 101, 241, 24)
down1  MaxPool2 + ConvBlock(48)          → (B,  50, 120, 48)
down2  MaxPool2 + ConvBlock(96)          → (B,  25,  60, 96)
down3  MaxPool2 + ConvBlock(192)         → (B,  12,  30, 192)
   │
   ▼ attention pooling over the N = 12·30 = 360 tokens
     attn = Dense(1) over [global_mean ‖ token]  → softmax over N
     z0   = Σ_tokens  token · weight               → (B, 192)
   ▼
proj   Dense(256)                         → latent z (B, 256)
```

The encoder returns `(z, skips)` where
`skips = [stem(24), down1(48), down2(96), down3(192)]`.

### 6.3 Decoder — depth-profile reconstruction

```
z (256)  +  skips (deep → shallow)
   ▼
up0 Conv2DTranspose(96, 3×3, stride 2)  → 24×60 , resize to skip
    concat [up0 ‖ skip(96) ‖ z_broadcast(256)] → ConvBlock(96)
up1 Conv2DTranspose(48, 3×3, stride 2)  → 50×120
    concat [up1 ‖ skip(48) ‖ z_broadcast]      → ConvBlock(48)
up2 Conv2DTranspose(24, 3×3, stride 2)  → 100×240, resize to 101×241
    concat [up2 ‖ skip(24) ‖ z_broadcast]      → ConvBlock(24)
   ▼
head  Conv2D(15, 1×1)                    → (B, 101, 241, 15)
   │ transpose → (B, 15, 101, 241)   = 15 standard depths
```

The latent `z` is **broadcast to every pixel** at every decoder stage, so the
global surface state conditions the full spatial prediction; skip connections
preserve fine spatial detail.

### 6.4 `OceanModel` wrapper

- `cin=5, D=256, Z=15, widths=(24,48,96,192)`, **1,643,288 params**
  (encoder 710,681 + decoder 932,607). Verified: output `(1, 15, 101, 241)`,
  embedding `z (1, 256)`.
- Channels-first `(B,C,H,W)` at the boundary, channels-last internally.
- `call(x)` returns `(pred (B,Z,H,W), z (B,D))`.
- **Depth-weighted masked MSE loss**:

```
depth_w = linspace(1.0, 2.5, 15)          # deeper levels weighted more
loss = Σ( (pred − y)² · mask · depth_w ) / Σ( mask · depth_w )
```

Land cells (`mask = 0`) contribute nothing. Custom `train_step` / `test_step`,
so the training loop is driven explicitly in `run_day3.py`.

### 6.5 Architecture diagram (ASCII)

```
        SURFACE INPUT (5, 101, 241)
                 │
     ┌───────────▼───────────┐
     │  ENCODER (embedding)  │
     │  stem → d1 → d2 → d3  │──┐ skips (24/48/96/192)
     └───────────┬───────────┘  │
                 │              │
        attention pool          │
                 │              │
            z (256,) ───────────┼──────────────┐
                 │              │              │
     ┌───────────▼───────────┐  │   (broadcast to every pixel)
     │  DECODER              │◀─┘              │
     │  up0 → up1 → up2      │◀────────────────┘
     │  head Conv2D(15,1)    │
     └───────────┬───────────┘
                 │
        OUTPUT (15, 101, 241)   ← 15 depths, 0–1000 m
                 │
     masked · depth-weighted MSE  vs  GLORYS target
```

---

## 7. Training procedure

`run_day3.py`:

1. Load arrays, per-channel z-score `X`, global z-score `Y` (`data.normalize`).
2. **Temporal split**: `n_val = max(5, T//5)`; the **last** `n_val` days are
   validation (no shuffling across the boundary).
3. `tf.data`: `(x, y, mask)`; NaNs → 0 with the mask preserving validity;
   batch 4, shuffled train, prefetched.
4. **Explicit GradientTape loop** (Keras 3 `fit()` mishandles a custom
   `train_step` loss): Adam `1e-3`, up to 120 epochs, early stopping with
   patience 30 on validation loss, **best weights restored**.
5. Evaluate in physical units; mask land to NaN.

`data.py` also exposes `make_dataset` used by the demo scripts.

---

## 8. Evaluation

### 8.1 Baselines (`src/baselines.py`)

| Baseline | Definition |
|---|---|
| **persistence** | Repeat the **last training day** across the whole test window (not day-before — that is trivially easy at ~0.999 autocorrelation). |
| **climatology** | Per-pixel day-of-year mean from training days only. |
| **sst_mlp** | Per-pixel `MLPRegressor` mapping surface channels (+ lat/lon) → full profile. |

> Channel selection in `sst_mlp` now resolves names against the **actual array
> channels** (`array_channels`), not the global `config.INPUT_CHANNELS`
> ordering. The previous version silently used `ugos` where it intended `sla`.

### 8.2 Metrics (`src/metrics.py`)

Per-depth **RMSE, Bias, MAE, correlation** over valid ocean cells.

Because the unweighted mean over 15 levels is dominated by the four
near-surface levels (nearly free given SST input) and mixes per-level masks of
different size, the honest harness adds:

- **`common_mask_metrics`** — every level scored on cells valid at **all**
  depths (removes the moving-mask bias);
- **`band_mean`** — `≥50 m` and thermocline `50–200 m`;
- **`headline`** / **`print_headline`** — compact comparable summary;
- **`wins_vs`** — per-level win/loss vs a reference.

Tests: `tests/test_metrics.py` (6/6).

### 8.3 Independent validation — ARGO

`src/argo.py` loads INCOIS ERDDAP gridded Argo (`T_ANALYZED`), interpolates to
the 15 standard depths, and regrids to the target grid. **Never used for
training.** Not yet executed against a checkpoint.

---

## 9. Derived hazard diagnostics

`src/hazard.py` — pure NumPy, exact for piecewise-linear profiles. Input is a
`(Z, H, W)` field with `depths` first (`NaN` over land).

| Function | Quantity |
|---|---|
| `tchp` | Tropical Cyclone Heat Potential (kJ/cm²), ∫(T−26) dz to the 26 °C isotherm. Thresholds 30 / 50 / 80. |
| `d26` | Depth of the 26 °C isotherm (m). |
| `ohc` | Ocean Heat Content to `zmax` relative to a reference. |
| `mld` | Mixed-layer depth, 0.2 °C criterion. |
| `thermocline_depth` | Depth of maximum vertical gradient. |
| `tchp_category` | 0–3 cyclone-support category. |

Constants: ρ = 1025 kg m⁻³, cₚ = 3985 J kg⁻¹ K⁻¹.

---

## 10. Reproducing

```bash
# 0. install
pip install -r requirements.txt

# 1. smoke test (3 days, ~1 min)
python run_day1.py 2020-01-01 2020-01-03

# 2. full ingest of a window (raw downloads reused; --force rebuilds arrays)
python run_ingest.py 2020-01-01 2020-03-31 --force

# 3. baselines + honest headline
python run_day2.py 2020-01-01 2020-03-31

# 4. train + evaluate the model
python run_day3.py 2020-01-01_2020-03-31 120

# 5. figures
python demo_model.py 2020-01-01_2020-03-31
python show_model.py 2020-01-01_2020-03-31

# tests (no downloads)
python tests/test_harmonize.py
python tests/test_metrics.py
```

---

## 11. Current status & results

### 11.1 What is built

| Component | Status |
|---|---|
| Config, downloaders, harmonise, masks | ✅ verified |
| Regrid fix + regression tests (16/16) | ✅ verified bit-exact |
| tf.data pipeline | ✅ |
| Encoder–decoder model | ✅ trains |
| Baselines (persistence / climatology / SST→T MLP) | ✅ |
| Honest metric harness + tests (6/6) | ✅ |
| SSS wired as 5th channel | ✅ |
| Hazard diagnostics | ✅ written, not yet unit-tested/run |
| ARGO validation | ⚠️ implemented, **never run** |
| Multi-year ingest | ⏸ on hold |
| Winds (CCMP) / OSCAR currents | ❌ not wired |

### 11.2 Honest results — Jan–Mar 2020, common mask (test = last 18 days)

| Method | all-depth | **≥50 m** | **thermocline 50–200 m** | corr |
|---|---|---|---|---|
| **persistence** | **0.487** | **0.430** | **0.619** | 0.968 |
| model (5-ch) | 0.512 | 0.552 | 0.731 | 0.959 |
| sst_mlp (5-ch) | 0.522 | 0.583 | 0.822 | 0.959 |
| climatology | 0.813 | 0.740 | 1.080 | 0.929 |

**The model beats persistence only at 0, 5, 10, 20 m.** Persistence wins at
30, 50, 75, 100, 125, 150, 200, 300, 500, 700, 1000 m.

Adding SSS improved the SST→T MLP (mean RMSE 0.660 → 0.578) but did not flip
the model-vs-persistence outcome. With only **91 days of a single winter
season**, persistence is extremely strong because the deep ocean barely changes
over the test window.

> **This is the current, truthful state:** the model is best at the surface and
> beats both legitimate baselines through the thermocline, but it does **not**
> yet beat persistence below ~30 m. See STATUS.md §10.

---

## 12. Known issues & next steps

### Correctness / honesty
- [x] Regrid bug fixed and pinned by tests.
- [x] Stale corrupted arrays/checkpoints rebuilt.
- [x] Overstated 0.574 °C claim retracted in the docs.
- [x] `make_ppt_figure.py` / `make_ppt_illustrated.py` numbers corrected to the
      honest thermocline results and regenerated.

### To actually beat persistence
1. **Predict anomalies** relative to persistence/climatology (model the
   *increment*) so it cannot do worse than the baseline.
2. **Multi-year training** (≥1 year, ideally 10) so seasonality exists and the
   persistence/climatology comparison is fair.
3. **Run ARGO validation** on a checkpoint (`src/argo.py`).
4. **Add winds/currents** — CCMP `uwnd`/`vwnd` (only 1 test day downloaded) and
   OSCAR (needs a NASA Earthdata login); currently 5 of the 7 spec variables.
5. Report `≥50 m` and thermocline RMSE as the **headline**, not the all-depth
   mean.

### Validation
- [ ] Unit-test `hazard.tchp` / `d26` against a known analytic profile.
- [ ] `run_hazard.py`: load model → predict → TCHP maps → compare to truth.

---

## Appendix A — Key constants (`src/config.py`)

```python
LON_MIN, LON_MAX = 45.0, 105.0
LAT_MIN, LAT_MAX = 5.0, 30.0
RES = 0.25
DEPTHS = [0, 5, 10, 20, 30, 50, 75, 100, 125, 150, 200, 300, 500, 700, 1000]
INPUT_CHANNELS = ["sst", "sss", "sla", "ugos", "vgos", "uwnd", "vwnd"]
```

## Appendix B — Verified Copernicus dataset IDs

| Purpose | dataset_id |
|---|---|
| Target T(z) | `cmems_mod_glo_phy-all_my_0.25deg_P1D-m` (var `thetao_glor`) |
| SSH / SLA / currents | `cmems_obs-sl_glo_phy-ssh_my_allsat-l4-duacs-0.125deg_P1D` |
| SST | `METOFFICE-GLO-SST-L4-REP-OBS-SST` |
| SSS | `cmems_obs-mob_glo_phy-sss_my_multi_P1D` (var `sos`) |
| Fallback target | `cmems_mod_glo_phy_my_0.083deg_P1D-m` |

## Appendix C — Environment

```
tensorflow 2.21.0 · xarray 2026.7.0 · numpy 2.5.0 · scipy 1.18.0 · python 3.13
```

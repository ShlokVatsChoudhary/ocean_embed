# `model/` — OceanEmbed v1 (Friend 1 / model provider)

Subsurface-temperature model for the North Indian Ocean, packaged as a drop-in
implementation of the backend contract in
[`backend/app/model/interface.py`](../backend/app/model/interface.py).

**What it does:** given *surface-only* satellite fields for a day, it reconstructs
the 3-D temperature field on the project's standard grid and depths.

| | |
|---|---|
| Domain | 5–30 °N, 45–105 °E |
| Grid | 0.25° × 0.25°, **101 lat × 241 lon** |
| Depths | 15 standard levels: 0, 5, 10, 20, 30, 50, 75, 100, 125, 150, 200, 300, 500, 700, 1000 m |
| Inputs | surface only — `sst, sss, sla, ugos, vgos` (5 channels) |
| Architecture | TensorFlow encoder–decoder, attention pooling, **1,643,288 params** |
| Trained | 2020-01-01 … 2020-03-31 (91 days), GLORYS12V1 target |
| Served now | the same 91 days (see *Input cache* below) |

---

## Files

```
model/
├── __init__.py            # exports OceanEmbedV1
├── adapter.py             # OceanEmbedV1 — implements OceanEmbedModel
├── net.py                 # the Keras architecture (OceanModel), verbatim from training
├── config.py              # grid / depths / channels / artifact paths (self-contained)
├── build_inputs.py        # rebuild or extend the input cache from PS66 arrays
├── requirements-model.txt # tensorflow, numpy (only where the model runs)
├── weights/
│   ├── oceanembed_v1.weights.h5  # trained weights (~6.4 MB)
│   └── stats_2020Q1.npz          # per-channel + target normalisation stats
└── input_cache/
    └── X_2020Q1.npz       # cached surface inputs, land mask, bathymetry (~8 MB)
```

Everything is self-contained: **no downloads, no Copernicus login, no network**
are needed to run inference on the shipped days.

---

## Quickstart

```python
import datetime as dt
from model.adapter import OceanEmbedV1, ModelInferenceInput

model = OceanEmbedV1()                       # loads weights once (≈2 s)

# vertical profile at a point
req = ModelInferenceInput(date=dt.date(2020, 2, 15), latitude=15.0, longitude=65.0)
profile = model.infer_profile(req)
print(profile.temperatures)                  # 15 floats (°C), None below the seabed

# horizontal field at one depth (optionally over a bbox)
field = model.infer_temperature_field(
    ModelInferenceInput(date=dt.date(2020, 2, 15), depth=100.0,
                        latitude_min=8, latitude_max=22,
                        longitude_min=55, longitude_max=95)
)
print(field.values)          # rows = latitude ↑, cols = longitude →
print(field.metadata)        # served_date, served_depth, grid, source
```

Requires `tensorflow>=2.16` (see `requirements-model.txt`). TensorFlow is
imported lazily, so importing the package alone is cheap.

---

## How it plugs into the backend

`adapter.py` detects and imports `app.model.interface` automatically. When the
backend imports it, `OceanEmbedV1` **is** an `OceanEmbedModel` and returns the
backend's pydantic schemas, so no conversion layer is needed. Wiring is one line
in the model factory:

```python
# backend/app/model/factory.py (or wherever the model is constructed)
from model.adapter import OceanEmbedV1          # add repo root to sys.path
model = OceanEmbedV1()
```

Contract mapping:

| Backend request | Adapter behaviour |
|---|---|
| `infer_profile(request)` | nearest cell to (lat, lon); returns 15 temps, `None` on land / below seabed |
| `infer_temperature_field(request)` | nearest standard depth to `request.depth`; slices the bbox; `values` row-major (lat↑, lon→), land/below-seabed → `None`; geographic axes + `served_date` returned in `metadata` |

Notes for integration:

1. **Date coverage** is limited to the cache window. A request outside
   `2020-01-01 … 2020-03-31` is served from the **nearest available day**, and
   `metadata["served_date"]` vs `metadata["requested_date"]` makes this explicit.
   Pass `strict_dates=True` to raise instead.
2. **Depth** requests snap to the nearest of the 15 standard levels;
   `metadata["served_depth"]` reports the level actually served.
3. **`values` orientation** is documented in `metadata["axis_order"]` — confirm
   it matches `frontend`'s `MapHeatmap.jsx` before rendering.
4. **`None`** is used for land / below-seabed / missing cells (JSON-safe).

---

## Input cache

One `.npz` holding everything inference needs:

| key | shape | meaning |
|---|---|---|
| `X` | `(T, 5, 101, 241)` float16 | surface channels per day |
| `dates` | `(T,)` | ISO dates, contiguous daily |
| `channels` | `(5,)` | `sst, sss, sla, ugos, vgos` |
| `ocean` | `(101, 241)` bool | land mask (48.8 % ocean) |
| `bathy` | `(101, 241)` float32 | seabed depth (m), NaN on land |

To serve **new dates**, regenerate `X_*.npy` with the training pipeline
(`siH-PS66/run_ingest.py`, needs a Copernicus Marine login) and convert it:

```bash
python -m model.build_inputs --x data/processed/X_<tag>.npy \
    --y data/processed/Y_<tag>.npy --bathy data/processed/bathy_<tag>.npy \
    --channels data/processed/channels_<tag>.npy --start <YYYY-MM-DD> \
    --out model/input_cache/X_<tag>.npz
```

Sanity checks (already verified): a land cell returns all `None`; a 1000 m field
returns **9188** valid cells (37.7 %), the project's common-mask count.

---

## Honest performance

Independent target: GLORYS12V1, Jan–Mar 2020, evaluated on the **common mask**
(cells valid at all depths — 9188/day). RMSE in °C:

| Model | all depths | ≥ 50 m | Thermocline 50–200 m | Corr |
|---|---|---|---|---|
| **OceanEmbed v1** | **0.512** | 0.552 | **0.731** | 0.959 |
| Persistence | 0.487 | **0.430** | **0.619** | 0.968 |
| SST → T MLP | 0.522 | 0.583 | 0.822 | — |
| Climatology | 0.813 | 0.740 | 1.080 | — |

**Read this honestly:** OceanEmbed v1 is **best at the surface** (0–20 m) and
beats the SST-only MLP through the thermocline, but **persistence is stronger
below ~30 m** — it wins 11 of the 15 depths. This is a 3-month, single-season
prototype; the unweighted all-depth averages above are the fair (common-mask)
ones and differ from earlier all-cell numbers. Do **not** advertise it as
outperforming persistence. See the training repo's `STATUS.md §10` for the full
breakdown.

ARGO float observations are reserved for independent validation and were **never
used in training** (the validator exists in the training repo but has not been
run yet).

---

## Provenance

* Target: GLORYS12V1 `thetao` (ensemble), 0.25°, 75 levels.
* Inputs: OSTIA SST (0.05°), CMEMS SSS (`sos`), DUACS SLA + geostrophic currents
  (0.125°). Winds are **not** included in v1 (5 of the 7 spec variables).
* Training code, docs and the honest evaluation live in the `siH-PS66` repo.

## Extending / retraining

`net.py` is the exact architecture used in training. To retrain, reuse the PS66
`run_day3.py` loop with a `(T, 5, 101, 241)` X and `(T, 15, 101, 241)` Y, then
copy the new `.weights.h5` into `weights/` and regenerate the stats. Keep
`config.DEPTHS` and the grid identical — the backend's `STANDARD_DEPTHS` and
resolution must match.

# OceanEmbed backend

FastAPI service that serves ocean subsurface temperature reconstructions from the OceanEmbed
(SIH26066 / PS66) model, together with a GLORYS reference and independent ARGO validation.

## Run

```bash
cd backend
python3 -m pip install -e .
python3 -m uvicorn app.main:app --port 8000
```

Interactive docs: <http://localhost:8000/docs>

```bash
python3 -m pytest -q     # 50 passed, 1 skipped
```

## Endpoints

| Endpoint | Purpose |
| --- | --- |
| `GET /api/metadata` | Dataset name, available dates and depths, reference status, parameter count |
| `GET /api/temperature` | Gridded temperature field for a date and depth, as a 101×241 array |
| `GET /api/temperature/coverage` | Fraction of grid cells carrying a finite value |
| `GET /api/profile` | Vertical profile at a point across all 15 standard depths |
| `GET /api/comparison` | Point comparison against GLORYS, with grid transparency |
| `GET /api/validation` | ARGO validation: per-depth metrics, summary, scatter |
| `GET /api/argo/floats` | ARGO observation cells for a date, plus the time offset |
| `GET /api/argo/alerts` | Largest model-versus-ARGO differences (a diagnostic) |
| `GET /health` | Liveness |

## The reference data, stated plainly

- **GLORYS** (`glorys_status`) is what the model was trained against. It is a reanalysis, so it
  is *not* independent evidence of skill.
- **ARGO** (`/api/validation`) is independent and was never used in training. It is the number
  that counts. It is also a 1° every-10-days gridded analysis, so it is upsampled onto the
  0.25° daily grid, it starts at 5 m rather than 0 m, and the validated window overlaps the
  training period. Every one of those caveats is returned in the payload, not buried here.

Headline ARGO result for the bundled weights:

```
OVERALL              rmse 0.887 °C   mae 0.565 °C   bias −0.199 °C   corr 0.9930
>= 50 m              rmse 1.021 °C
thermocline 50-200 m rmse 1.277 °C
```

Error peaks near 75–100 m and is smallest at 1000 m. That is reported as measured.

## Configuration

Environment variables use the `OCEANEMBED_` prefix and are defined in `app/core/config.py`.

| Variable | Default | Purpose |
| --- | --- | --- |
| `OCEANEMBED_MODEL_ROOT` | `model/PS66-Ocean-Model` | Exported model package to load |
| `OCEANEMBED_ARGO_PATH` | — | Explicit ARGO NetCDF/NPZ file |
| `OCEANEMBED_ARGO_DIR` | `backend/data/argo` | Directory scanned for ARGO files |
| `OCEANEMBED_GLORYS_ROOT` | — | Live GLORYS archive, if present |
| `OCEANEMBED_CORS_ORIGINS` | Vite dev/preview ports | Allowed browser origins (JSON list) |

## ARGO data

`data/argo/argo_2020-01.nc` (580 KB) is committed so the demo is self-contained. To fetch a
wider window from INCOIS ERDDAP:

```bash
python3 scripts/fetch_argo.py --insecure
```

The INCOIS TLS chain is incomplete in both the system store and `certifi`, hence the explicit
`--insecure` opt-in; without it the script fails with a clear message rather than silently
downgrading.

## Design rules

1. **Never fabricate a value.** `get_validation()` returns `status` of `available`,
   `unavailable` or `no_overlap`, and `rmse` of `None` when there is no reference. There are no
   mock generators anywhere in the request path.
2. **Distinguish the three comparison states.** `model_and_reference`, `model_only` (a
   legitimate missing reference, not an error) and `model_unavailable`.
3. **Be explicit about where a value came from.** A profile needs a complete 0–1000 m column, so
   over a shelf sea the value is read from the nearest full-column cell. `/api/comparison`
   reports both that cell and the offset, and the UI warns when the value is not local.
4. **`coverage` is data availability, not confidence.** It is the fraction of cells with a
   finite value.

## Layout

```
app/
  api/deps.py            process-wide model/ARGO/GLORYS singletons
  api/routes/            one router per endpoint group
  core/config.py         settings
  core/constants.py      grid geometry and standard depths
  data/argo.py           ARGO accessor (nearest-index regrid + depth interpolation)
  data/glorys.py         GLORYS reference accessor
  model/adapter.py       TensorFlow runtime, field caching, grid resolution
  schemas/oceanembed.py  response models
  services/              validation, comparison, metadata, profile, argo
scripts/fetch_argo.py    INCOIS ERDDAP downloader
data/argo/               bundled ARGO NetCDF
```

## Known deferred bug

`src/harmonize.py::_axis_weights` (training repo) computes
`(1 - w) * v[i0] + w * v[i1]`, so when `w == 0` and `v[i1]` is NaN, `0.0 * NaN` destroys a valid
value. `_bilinear` has the same class of bug. It is **not** fixed here because that would change
the training arrays and invalidate the trained weights. The backend ARGO path uses its own
interpolation and is unaffected. Fix it during the next retraining run.

# OceanEmbed — integration notes (branch `yog`)

This branch makes the frontend, backend and model one connected application, and wires the
ARGO reference in as the independent validation source. Everything below is verified by
running it, not by reading the code.

## 1. What was broken, and what it is now

| Area | Before | Now |
| --- | --- | --- |
| Frontend ⇄ backend | API layer returned hard-coded mocks (`getSkillMetrics`, `getArgoFloats`, `getAnomalyAlerts`, `getArgoValidationSummary`, `getArgoScatter` all returned empty) | All five call real endpoints and surface `unavailable` explicitly when there is no data |
| Map orientation | Backend rows are south-to-north; the canvas drew row 0 at the top, so every map was upside-down | `normalizeField` reverses rows; documented convention is **north-up** |
| Normalisation order | `np.nan_to_num(..., nan=0.0)` ran **before** standardisation, so land became `(0 − μ)/σ ≈ −15.8` and 3×3 convolutions smeared that into the ocean | Normalise first, then `nan_to_num`. In-sample RMSE vs GLORYS: **4.70 → 0.41 °C** |
| `confidence` naming | The finite-value mask was labelled `confidence` | Renamed to `coverage`; it is data availability, not statistical confidence |
| Metadata | Advertised fake dates and depths `[0, 10, 25, 50, 100, 200]` | Real model dates, real standard depths, real ARGO status, real parameter count |
| Validation | `status`-less, mock-backed | Real ARGO element-wise comparison on a common mask, with provenance and caveats |
| Dates | Hard-coded `SUPPORTED_DATES` in the UI | UI reads `/api/metadata` and falls back only if the backend is down |

## 2. Verified ARGO validation (the honest number)

Model = bundled `model_2020.weights.h5` (1,643,288 params). Reference = INCOIS gridded ARGO
10-day analysis, **never used in training**.

```
OVERALL   rmse 0.887 °C   mae 0.565 °C   bias −0.199 °C   corr 0.9930   n 887,044
>= 50 m   rmse 1.021 °C
thermocline 50–200 m   rmse 1.277 °C
```

Per depth (RMSE °C): 0 m 0.582 · 5 m 0.611 · 10 m 0.582 · 20 m 0.553 · 30 m 0.562 ·
50 m 0.968 · **75 m 1.652** · **100 m 1.615** · 125 m 1.365 · 150 m 1.139 · 200 m 0.619 ·
300 m 0.412 · 500 m 0.275 · 700 m 0.283 · 1000 m 0.240.

The error peaks in the thermocline and is smallest at depth. That is the expected error
profile for a surface-to-subsurface reconstruction and it is reported as-is.

**Caveats that ship with the number** (also returned by the API so the UI shows them):

1. The ARGO product is **1° every 10 days**; it is upsampled onto the 0.25° daily grid, so one
   observation is reused across several model cells. The effective sample size is much smaller
   than `n`.
2. ARGO starts at **5 m**, so the model's 0 m level is compared against 5 m.
3. The validated window **overlaps the training period**. These are an optimistic upper bound,
   not an out-of-sample score.
4. Each model date maps to the nearest ARGO analysis time (e.g. 2020-01-01 → 2019-12-30, −2
   days; 2020-01-07 → 2020-01-10, +3 days). The offset is reported in the payload.

## 3. Known bug, deliberately deferred

`src/harmonize.py::_axis_weights` (and `_bilinear`) computes
`(1 − w) * v[i0] + w * v[i1]`. When `v[i1]` is NaN and `w == 0` (a target level that exactly
matches a source level), `0.0 * NaN = NaN` and the valid value at `i0` is destroyed.
`_bilinear` has the same class of bug.

**This is not fixed here on purpose.** Fixing it changes the training arrays, which would
invalidate the trained weights and every number above. The backend ARGO path uses its own
`_interp_to_standard_depths` and is unaffected, so validation is correct today.

Fix it as part of the next retraining run, and expect the headline numbers to shift slightly.

## 4. ARGO data

`backend/data/argo/argo_2020-01.nc` (580 KB) is committed so the demo is self-contained.
`backend/scripts/fetch_argo.py` downloads more from INCOIS ERDDAP:

```bash
python3 backend/scripts/fetch_argo.py --insecure    # chain is incomplete in both stores
```

Two things that will bite you: raw `[` / `]` in the request target make Tomcat return HTTP 400
(percent-encode to `%5B` / `%5D`), and the INCOIS TLS chain is incomplete, hence the explicit
`--insecure` opt-in.

## 5. Running it

```bash
# backend
cd backend && python3 -m pip install -e . && python3 -m uvicorn app.main:app --port 8000
python3 -m pytest -q          # 44 passed, 1 skipped

# frontend
cd frontend/frontend && npm install && npm run dev   # VITE_API_BASE=http://localhost:8000
npx oxlint src && npx vite build
```

Endpoints: `/api/metadata`, `/api/temperature`, `/api/temperature/coverage`, `/api/profile`,
`/api/comparison`, `/api/validation`, `/api/argo/floats`, `/api/argo/alerts`.

## 6. Honesty rules this code follows

- No mock generators remain in the frontend API layer. If data is missing the UI says so.
- `get_validation()` never invents a value; `status` is one of `available`, `unavailable`,
  `no_overlap`.
- The comparison endpoint returns a point value and its provenance, not a fabricated grid.
- Anomaly alerts are a **diagnostic** — where the reconstruction is least consistent with ARGO
  so a reviewer knows what to inspect first — not an operational hazard warning.

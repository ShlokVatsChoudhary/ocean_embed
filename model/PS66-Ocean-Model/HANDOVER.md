# PS66 — Handover Guide

This document tells a new developer how to take over the PS66 project.

> **Start here after cloning:** read **[ARCHITECTURE.md](ARCHITECTURE.md)** (full
> technical description) and **[STATUS.md §10](STATUS.md)** (honest current
> results). Everything below is just setup + how to run.

---

## 1. What this is

A deep-learning model that reconstructs **3-D ocean temperature (0–1000 m)** over
the North Indian Ocean (5–30 °N, 45–105 °E) at 0.25° daily, from **surface
satellite observations only** (SST, SSS, SLA, geostrophic currents). Trained
supervised against GLORYS reanalysis; validated against independent ARGO floats.

**Honest status:** the model is best at the surface and beats climatology and an
SST→T MLP through the thermocline, but it does **not yet beat persistence below
~30 m**. Do not present the obsolete "0.574 °C" figure — see STATUS.md §10.

---

## 2. What is (and isn't) in the git repo

| Included in git | NOT in git (must be transferred or rebuilt) |
|---|---|
| All `src/`, `run_*.py`, `tests/` | `data/raw/` — downloaded NetCDF (~1.4 GB) |
| All `*.md` docs, `requirements.txt` | `data/processed/` — X/Y arrays (~340 MB) |
| `figures/`, `notebooks/` | `checkpoints/` — model weights |
| | `logs/` — run output |

`.gitignore` excludes `data/`, `*.nc`, `*.npy`, `*.npz`, `*.h5`,
`checkpoints/`, `logs/`, `__pycache__/`, `.DS_Store`.

**Never commit the Copernicus credentials** (`~/.copernicusmarine/`) or any API
key. They are outside the repo by design — keep it that way.

---

## 3. Setup (new machine)

```bash
git clone <repo-url> siH-PS66
cd siH-PS66
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Verified stack: **Python 3.13, TensorFlow 2.21, xarray 2026.7, numpy 2.5,
scipy 1.18**.

### 3a. Copernicus Marine credentials (for downloading data)

The project downloads everything through `copernicusmarine`. Each person needs
**their own free account** — do not share credentials.

```bash
python3 -m copernicusmarine login        # stores in ~/.copernicusmarine/
```

---

## 4. Getting the data — pick ONE

### Option A — receive the pre-built data (fastest)

Copy the `data/` and `checkpoints/` folders from the original machine, e.g.

```bash
# on the source machine
tar czf ps66_data.tgz data checkpoints
# transfer ps66_data.tgz (rsync / Drive / WeTransfer), then on the new machine:
tar xzf ps66_data.tgz
```

Result: you can immediately run `run_day2.py` / `run_day3.py` with no downloads.
Skip to §5.

### Option B — rebuild from scratch (needs Copernicus login)

```bash
# 3-day smoke test (tiny, fast)
python run_day1.py 2020-01-01 2020-01-03

# full Jan–Mar 2020 window (downloads + harmonises; ~10 min)
python run_ingest.py 2020-01-01 2020-03-31 --force
```

`run_ingest.py` is resumable: it skips existing raw NetCDFs and, without
`--force`, skips existing arrays too. `--force` rebuilds arrays but still reuses
the raw downloads.

---

## 5. Running the pipeline

```bash
# refresh the smoke test (3 days)
python run_day1.py 2020-01-01 2020-01-03

# baselines + honest headline metrics
python run_day2.py 2020-01-01 2020-03-31

# train (120 epochs) + evaluate
python run_day3.py 2020-01-01_2020-03-31 120

# figures
python demo_model.py 2020-01-01_2020-03-31
python show_model.py 2020-01-01_2020-03-31

# tests
python tests/test_harmonize.py   # 16/16 — pins the regrid behaviour
python tests/test_metrics.py     # 6/6  — pins the honest aggregation
```

---

## 6. Gotchas a new developer must know

1. **The regrid bug (STATUS.md §9).** `xarray.interp` returns NaN on
   exact-grid coordinates in the pinned stack. `harmonize._regrid` works around
   it. `tests/test_harmonize.py` pins this — **do not "simplify" it back to
   `xarray.interp`.**
2. **SSS singleton depth.** The SMAP+SMOS `sos` field carries a `depth=1`
   dimension that is squeezed in `harmonize.build_arrays`. Values are already in
   PSU.
3. **Training uses a custom GradientTape loop** in `run_day3.py`. Keras 3
   `model.fit()` mishandles the custom `train_step`. Do **not** call
   `model.build()`.
4. **Metric honesty.** Always report `≥50 m` and thermocline (50–200 m) on the
   **common mask** — never the unweighted all-depth mean (it is dominated by
   near-free surface levels). See `src/metrics.py`.
5. **ARGO is validation only** — never train on it.
6. **Input channels are resolved by name**, not by `config.INPUT_CHANNELS`
   ordering (a past bug silently fed `ugos` where `sla` was intended).

---

## 7. Where to go next (from STATUS.md §10 / TODO.md)

1. Train on **anomalies** vs persistence/climatology so the model can only add
   skill (this is the key fix to beat persistence at depth).
2. **Multi-year** ingest (≥1 year) so seasonality exists and the
   persistence/climatology comparison is fair.
3. **Run ARGO validation** (`src/argo.py`) against a checkpoint.
4. Wire **CCMP winds** and **OSCAR currents** (currently 5 of 7 spec variables).
5. Unit-test and run `src/hazard.py` (TCHP / D26 / OHC) → `run_hazard.py`.
6. Update the PPT figures if results change (`make_ppt_figure.py`,
   `make_ppt_illustrated.py`).

---

## 8. One-command handover (if you trust the recipient with the data)

```bash
# from the repo root — bundles code + data + checkpoints, excluding cruft
tar --exclude='.git' --exclude='__pycache__' --exclude='.venv' \
    --exclude='.DS_Store' --exclude='*.pyc' \
    -czf ps66_full_handover.tgz .
```

This produces a ~1–2 GB archive. For git-based collaboration use §2 instead and
transfer `data/` separately per §4A.

# PS66 — Satellite-Embedding Deep Learning for Subsurface Ocean Temperature

Reconstruct full-depth ocean temperature (**0–1000 m**) over the **North Indian Ocean**
(5–30 °N, 45–105 °E) from daily surface satellite observations, using a compact
encoder–decoder CNN with an attention-pooled latent "satellite embedding".

| | |
|---|---|
| **Domain** | 5–30 °N, 45–105 °E |
| **Grid** | 0.25° × 0.25°, daily |
| **Input** | 5 surface satellite channels |
| **Output** | Temperature at 15 standard depths (0 → 1000 m) |
| **Framework** | TensorFlow / Keras 3 |
| **Trained on** | Full year 2020 (366 days) |

---

## Results

### Independent ARGO validation (2020)
The model was scored against **gridded ARGO observations never used in training**.

| Depth band | Model RMSE | Persistence RMSE | Model corr |
|---|---|---|---|
| All depths | **0.887 °C** | 1.456 °C | **0.843** |
| ≥ 50 m | **0.989 °C** | 1.475 °C | — |
| Thermocline (50–200 m) | **1.424 °C** | 2.202 °C | — |

Errors are largest in the thermocline (peak ~1.7 °C at 100 m) and smallest at the
surface and below 300 m — the physically expected profile. Bias is small
(−0.04 → +0.18 °C), i.e. no systematic drift.

> **Honest caveat:** the persistence figure above persists a single profile across
> the whole year (a deliberately weak reference). The credible claim is the
> **absolute skill against real observations**, not the ratio. See `STATUS.md`.

### GLORYS-target skill (Jan–Mar 2020, common mask)
| Method | All-depth | ≥ 50 m | Thermocline (50–200 m) | Corr |
|---|---|---|---|---|
| Persistence | 0.487 | 0.430 | 0.619 | 0.968 |
| Model (5-ch) | 0.512 | 0.552 | 0.731 | 0.959 |
| SST→T MLP | 0.522 | 0.583 | 0.822 | 0.959 |
| Climatology | 0.813 | 0.740 | 1.080 | 0.929 |

On winter-only data the model beats persistence only at 0–20 m; the full-year run
adds the seasonality needed to test it fairly.

---

## Model

Encoder–decoder CNN, **1,643,288 parameters**.

```
SURFACE INPUT (5, 101, 241)
        │
  ┌─────▼─────┐
  │  ENCODER  │  stem → down1 → down2 → down3      (24/48/96/192)
  └─────┬─────┘───────────────┐ skips
        │ attention pool      │
      z (256,) ───────────────┼──────────┐
        │                     │  (broadcast to every pixel)
  ┌─────▼─────┐               │          │
  │  DECODER  │◀──────────────┘◀─────────┘
  │ up0→up1→up2 → Conv2D(15,1×1)
  └─────┬─────┘
        │
  OUTPUT (15, 101, 241)   ← 15 depths, 0–1000 m
```

- **Input channels:** `sst, sss, sla, ugos, vgos`
- **Loss:** masked, depth-weighted MSE (`linspace(1.0, 2.5, 15)`; land ignored)
- Full details in [`ARCHITECTURE.md`](ARCHITECTURE.md).

---

## Data

| Role | Source | Details |
|---|---|---|
| Target T(z) | GLORYS `thetao_glor` (`cmems_mod_glo_phy-all_my_0.25deg_P1D-m`) | 1993–2024, 75 levels, 0.25° |
| SST | OSTIA L4 (`METOFFICE-GLO-SST-L4-REP-OBS-SST`) | 0.05°, Kelvin |
| SSS | SMAP+SMOS L4 (`cmems_obs-mob_glo_phy-sss_my_multi_P1D`) | 0.125°, PSU |
| SSH / SLA / currents | DUACS L4 (`...ssh_my_...duacs-...P1D`) | `sla, ugos, vgos` |
| Independent validation | INCOIS ERDDAP gridded Argo (`T_ANALYZED`) | 10-day, 1°, never used for training |

Raw NetCDFs and processed arrays are **not committed** (see `.gitignore`).

---

## Quickstart

Requires **Python 3.12 or 3.13** (TensorFlow has no 3.14 build).

```bash
git clone <this-repo>
cd PS66-Ocean-Model
pip install -r requirements.txt
```

### Try the trained model (no data download)

The repository ships the trained weights **and** a 7-day sample, so this works
immediately after cloning:

```bash
python quickstart.py     # per-depth RMSE table + figures/quickstart_prediction.png
python demo_model.py     # truth / prediction / error maps and profiles
```

`src/data.py` uses `data/processed/` when it exists and falls back to `samples/`
otherwise, so nothing has to be copied by hand.

### Reproduce the full pipeline

```bash
# 1. build arrays (from Copernicus Marine, or from local NetCDFs)
python run_ingest.py 2020-01-01 2020-12-31 --out-tag 2020
py -3.12 build_from_local.py --dir /path/to/nc_folder --tag 2020

# 2. train + evaluate
python run_day3.py 2020 120

# 3. independent ARGO validation
python run_argo_validation.py 2020

# tests
python tests/test_harmonize.py
python tests/test_metrics.py
```

**Training on Google Colab:** see [`colab/PS66_Colab_Train.ipynb`](colab/PS66_Colab_Train.ipynb).

---

## Repository structure

```
.
├── README.md                     ← you are here
├── ARCHITECTURE.md               full technical documentation
├── STATUS.md                     honest results + current status
├── HANDOVER.md, TODO.md, PIPELINE_EXPLANATION.md
├── requirements.txt
├── src/
│   ├── config.py                 domain, depths, dataset IDs
│   ├── download.py               Copernicus Marine downloaders
│   ├── harmonize.py              regrid → standard depths → arrays
│   ├── data.py                   tf.data pipeline + normalisation
│   ├── model.py                  encoder–decoder CNN
│   ├── baselines.py              persistence / climatology / SST→T MLP
│   ├── metrics.py                per-depth metrics + honest harness
│   ├── argo.py                   ARGO loader / regridder
│   ├── hazard.py                 TCHP, D26, OHC, MLD
│   └── viz.py                    plotting
├── run_day1.py                   download → harmonise → map
├── run_day2.py                   baselines + metrics
├── run_day3.py                   train + evaluate
├── run_ingest.py                 resumable month-by-month ingest
├── run_argo_validation.py        independent ARGO accuracy check
├── quickstart.py                 one-command check on the bundled sample
├── build_from_local.py           build arrays from local NetCDFs
├── demo_model.py, show_model.py, make_ppt_*.py
├── colab/PS66_Colab_Train.ipynb  Colab training notebook
├── notebooks/01_inspect.ipynb
├── tests/                        regrid + metric regression tests
├── weights/                      trained model weights (*.h5)
├── samples/                      7-day sample so the repo runs out of the box
└── figures/                      output figures
```

---

## Outputs

| Artifact | Produced by |
|---|---|
| `X_<tag>.npy`, `Y_<tag>.npy`, `stats_<tag>.npz` | `run_ingest.py` / `build_from_local.py` |
| `checkpoints/model_<tag>.weights.h5` | `run_day3.py` |
| `figures/model_rmse_<tag>.png` | `run_day3.py` |
| `figures/argo_rmse_<tag>.png` | `run_argo_validation.py` |
| `figures/quickstart_prediction.png` | `quickstart.py` |
| `weights/model_<tag>.weights.h5` | trained on Colab (`run_day3.py`) |

---

## Known limitations & next steps

- [ ] Beat a **fair** persistence baseline (day-before / climatology) below 30 m.
- [ ] Wire CCMP winds and OSCAR currents (currently 5 of 7 spec variables).
- [ ] Multi-year / multi-decade ingest (1993–2023).
- [ ] Unit-test `hazard.py` (TCHP, D26) against analytic profiles.
- [ ] Predictive anomalies instead of absolute fields (model the increment).

See [`TODO.md`](TODO.md) and [`STATUS.md`](STATUS.md) for details.

---

## Acknowledgements

Copernicus Marine Service (GLORYS, DUACS, OSTIA, SMAP+SMOS), INCOIS (gridded Argo),
and the PS66 problem statement.

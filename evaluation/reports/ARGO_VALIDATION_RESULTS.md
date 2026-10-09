# Independent ARGO validation — results

Produced by [`validate_argo_baselines.py`](../argo/validate_argo_baselines.py). Every method is scored against the **same ARGO
observations on the same mask**, so the comparison between methods is apples-to-apples.
ARGO is never used in training.

Persistence needs a previous day, so all three methods are scored on days 2–7 (6 days,
761,358 pairs each). Scoring a method on more cells than another would flatter it.

| Method | RMSE all | RMSE ≥50 m | RMSE thermocline | MAE | Bias |
| --- | --- | --- | --- | --- | --- |
| **OceanEmbed** | **0.886** | **1.022** | **1.278** | **0.563** | −0.191 |
| Persistence (previous day) | 0.972 | 1.108 | 1.386 | 0.617 | −0.210 |
| Climatology (7-day mean) | 0.959 | 1.094 | 1.368 | 0.612 | −0.207 |

OceanEmbed is better than both baselines at **every one of the 15 depths**, including the
thermocline, which is where persistence is usually strongest.

## Per-depth RMSE (°C)

| Depth (m) | OceanEmbed | Persistence | Climatology |
| --- | --- | --- | --- |
| 0 | 0.575 | 0.687 | 0.677 |
| 5 | 0.605 | 0.691 | 0.685 |
| 10 | 0.578 | 0.663 | 0.656 |
| 20 | 0.543 | 0.646 | 0.640 |
| 30 | 0.555 | 0.629 | 0.624 |
| 50 | 0.965 | 1.082 | 1.061 |
| 75 | **1.653** | 1.851 | 1.821 |
| 100 | 1.619 | 1.716 | 1.697 |
| 125 | 1.370 | 1.443 | 1.422 |
| 150 | 1.134 | 1.190 | 1.182 |
| 200 | 0.617 | 0.709 | 0.705 |
| 300 | 0.408 | 0.448 | 0.445 |
| 500 | 0.274 | 0.289 | 0.289 |
| 700 | 0.285 | 0.303 | 0.303 |
| 1000 | 0.245 | 0.279 | 0.279 |

Error peaks at 75–100 m and is smallest at 1000 m, as expected for a surface-driven
reconstruction: the thermocline is where the vertical gradient is sharpest.

## How much to trust this

Read the honest limits before quoting these numbers.

1. **In-sample.** The model was trained on Jan–Mar 2020, and this window is inside that. The
   model has an advantage that persistence and climatology do not have. These are an
   **optimistic upper bound**, not out-of-sample skill. A true score needs an ARGO year the
   model never saw (2021+).
2. **The effective sample is much smaller than `n`.** The ARGO product is 1° every 10 days,
   upsampled onto the 0.25° grid, so one observation is reused across ~16 model cells. The
   761,358 pairs come from roughly 598 independent 1° locations. Treat the sample size as
   ~15–20× smaller than the raw count.
3. **Each model day is matched to the nearest ARGO analysis time**, up to ~3 days away
   (2020-01-07 → 2020-01-10). Some of the measured error is therefore temporal mismatch that
   has nothing to do with the model.
4. **ARGO starts at 5 m**, so the 0 m model level is compared against 5 m.
5. **Persistence and climatology are strong here** because the window is 7 winter days in
   which the ocean barely changes. The model's margin (about 8–9 %) is real but modest, and it
   would narrow further over a longer, more variable period.

## What this does not show

The margin over persistence is 8–9 % overall. That is a defensible but unspectacular result,
and the thermocline error of 1.278 °C is the weak point. Do not present this as a solved
problem, and do not quote 0.886 °C without the in-sample caveat attached.

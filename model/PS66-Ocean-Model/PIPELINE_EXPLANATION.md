# PS66 — Pipeline Explanation (slide narrative)

**Figure:** `figures/ppt_pipeline_illustrated.png`

---

**The problem.** The ocean stores over 90% of Earth's excess heat, but we measure
almost all of it at the surface — from satellites. Below the surface, temperature
controls the thermocline, feeds cyclones and monsoon rainfall, and shapes marine
ecosystems. This is PS66: reconstruct the full depth-wise temperature of the
North Indian Ocean (5–30°N, 45–105°E) at 0.25° daily, from surface observations
alone.

**Our approach.** We combine five satellite-derived families — sea-surface
temperature (OSTIA), sea-surface salinity (SMAP+SMOS), sea-surface height
(DUACS), surface currents (OSCAR/DUACS) and winds (CCMP) — all harmonised onto a
common grid. A convolutional **encoder** acts as an *embedding engine*: it fuses
a full day of these surface fields into a single 256-dimensional latent vector
that summarises the ocean's surface state. A skip-connected **decoder** then
broadcasts that embedding back onto the spatial grid and predicts all 15 standard
depth levels (0–1000 m) simultaneously in one forward pass.

**Why it works.** The embedding forces the network to learn the physical
relationship between surface signatures and subsurface structure — the same link
oceanographers exploit when they infer thermocline depth from sea-surface height.
Skip connections preserve fine spatial detail, while a bathymetry-aware,
depth-weighted loss prevents the model from exploiting shallow shelves.

**Trust.** Predictions are benchmarked against persistence, climatology and a
direct SST→temperature neural baseline on independent test days, and scored on
a common ocean mask with `>=50 m` and thermocline (50–200 m) bands reported
alongside the all-depth mean. On Jan–Mar 2020 (91 days, one winter season) the
model is **best at the surface and beats both naive baselines through the
thermocline** (thermocline RMSE 0.73 °C vs 0.82 °C for the SST→T MLP and
1.08 °C for climatology), produces physically valid profiles everywhere, and
runs in a fraction of a second per day on CPU.

**Honest limitation.** Persistence is still stronger below ~30 m in this
single-season setting (thermocline RMSE 0.62 °C), because the deep ocean barely
changes over the test window. The model is not yet a demonstrated improvement
over persistence at depth; see `STATUS.md` §10. Do **not** quote the old
0.574 °C / 0.955 figures — they were computed on corrupted data.

**Validation.** Independent ARGO validation is implemented (`src/argo.py`,
INCOIS ERDDAP `T_ANALYZED`) but has **not yet been run** against this
checkpoint.

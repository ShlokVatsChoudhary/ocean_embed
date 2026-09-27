# TODO / parked ideas

## Parked until the standard model is complete

**Do NOT start these until the base model is frozen and working.**

- [ ] **Cyclone / hazard product (TCHP)** — *highest-value addition*
  - Module already drafted: `src/hazard.py` (TCHP, D26, OHC, MLD, thermocline)
  - Still to do:
    - [ ] unit-test `hazard.tchp` / `d26` against a known profile
    - [ ] build runner `run_hazard.py`: load model → predict → TCHP maps
    - [ ] compare predicted-TCHP vs truth-TCHP (RMSE)
    - [ ] figure: cyclone-fuel map + category thresholds
  - TCHP = ρ·cp·∫₀^D26 (T−26°C) dz ; thresholds 30/50/80 kJ/cm²

- [ ] **Uncertainty quantification** — MC dropout or variance head
- [ ] **Physics-informed loss** — pred[0]≈SST, monotonic cooling with depth
- [ ] **Explainability / saliency** — show SSS drives Bay-of-Bengal depths
- [ ] **Multi-task salinity co-prediction** — needs `so` download from GLORYS

## Still open (base model)

- [ ] Wire in SSS (downloaded, not wired) — 4 → 5 channels
- [ ] ARGO validation run on trained checkpoint
- [ ] CCMP winds (server too slow) / OSCAR currents (needs NASA login)
- [ ] Multi-year ingest (ON HOLD)

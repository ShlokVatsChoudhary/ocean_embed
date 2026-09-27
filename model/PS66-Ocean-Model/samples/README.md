# Bundled 7-day sample

This folder lets anyone run the trained model straight after cloning, without
downloading the multi-gigabyte raw data.

| File | Shape | Size | What it is |
|---|---|---|---|
| `X_2020.npy` | `(7, 5, 101, 241)` | 3.4 MB | 7 days of surface inputs: SST, SSS, SLA, u, v |
| `Y_2020.npy` | `(7, 15, 101, 241)` | 10.2 MB | 7 days of GLORYS temperature truth at 15 depths |
| `stats_2020.npz` | — | 3.1 KB | **Full-year** normalisation means/stds used at training time |
| `channels_2020.npy` | `(5,)` | 208 B | Input channel names, in order |

- Domain: 5–30 °N, 45–105 °E at 0.25° (101 × 241 grid)
- Days: **1–7 January 2020** (the first 7 of the 366-day 2020 run)
- NaN marks land / missing cells, exactly as in the full dataset

## Important

`stats_2020.npz` is the **full-year** statistics file, not one recomputed from
this week. The model learned on those exact means and standard deviations —
recomputing stats from 7 days would break the normalisation and produce garbage
predictions. Always ship/use this file unchanged.

These days come from the **training year**, so accuracy measured on them is a
fit check, not a generalization score.

## Using them

`src/data.py` prefers `data/processed/` and falls back to this folder
automatically, so no copying is needed:

```bash
python quickstart.py          # prints per-depth RMSE + writes a figure
python demo_model.py          # truth vs prediction maps and profiles
```

## Where the full data comes from

The complete 2020 arrays (178 MB inputs, 534 MB targets) are **not** committed —
GitHub rejects files over 100 MB. Rebuild them with:

```bash
python run_ingest.py 2020-01-01 2020-12-31 --out-tag 2020
```

Requires a free Copernicus Marine account (see `HANDOVER.md`).

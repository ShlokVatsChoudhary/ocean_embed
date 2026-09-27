"""Day-2 driver: build arrays -> run baselines -> evaluate + plot.

Usage:
    python run_day2.py 2020-01-01 2020-01-31
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src import baselines, config, download, harmonize
from src import metrics as ev


def main(start: str, end: str, tag: str):
    print(f"\n=== Day 2: baselines on {start}..{end} (tag={tag}) ===\n")
    paths = download.download_all(start, end)
    res = harmonize.build_arrays(paths["target"], paths["duacs"], paths["ostia"],
                                 sss_path=paths.get("sss"), tag=tag)
    X, Y, times = res["X"], res["Y"], res["time"]
    T = len(times)
    print(f"\nX {X.shape}  Y {Y.shape}  days={T}  channels={res['channels']}")

    # ---- train / test split (temporal) ----
    n_test = max(7, T // 4)
    test_idx = np.arange(T - n_test, T)
    train_mask = np.ones(T, dtype=bool)
    train_mask[test_idx] = False
    print(f"train days={train_mask.sum()}  test days={len(test_idx)}")

    true = Y[test_idx].copy()
    preds = {}

    # ---- 1. persistence (from the LAST TRAINING DAY, not the day before) ----
    # Predicting each test day from the immediately preceding day is trivially
    # easy (autocorrelation ~0.999) and not a useful baseline. Persisting the
    # final training day across the whole test window is the honest test.
    last_train = np.flatnonzero(train_mask)[-1]
    preds["persistence"] = np.repeat(Y[last_train][None], len(test_idx), axis=0)

    # ---- 2. climatology (from training days) ----
    clim = baselines.fit_climatology(Y, times, train_mask)
    preds["climatology"] = baselines.predict_climatology(clim, times[test_idx])

    # ---- 3. SST(+SLA) -> T MLP ----
    predict = baselines.sst_to_T_mlp(X, Y, train_mask,
                                     array_channels=res["channels"])
    preds["sst_mlp"] = predict(test_idx)

    results = {name: ev.per_depth_metrics(p, true) for name, p in preds.items()}

    # ---- report ----
    for name, m in results.items():
        ev.print_table(m, name)
    print("\n--- summary (mean over depths) ---")
    for name, m in results.items():
        s = ev.overall_score(m)
        print(f"  {name:12s} RMSE={s['rmse_mean']:.3f}  "
              f"Bias={s['bias_mean']:+.3f}  "
              f"MAE={s['mae_mean']:.3f}  Corr={s['corr_mean']:.3f}  "
              f"(0-200m RMSE={s['rmse_0_200']:.3f})")

    # ---- honest headline: comparable across methods, not dominated by the
    # near-surface levels and not scored on per-level moving masks ----
    print("\n--- honest headline (common mask: cells valid at every depth) ---")
    for name, p in preds.items():
        ev.print_headline(p, true, name, common=True)
    win = ev.wins_vs(ev.common_mask_metrics(preds["persistence"], true),
                     ev.common_mask_metrics(preds["sst_mlp"], true))
    print("  note: per-level RMSE is in the tables above; >=50 m and thermocline")
    print("        are the meaningful columns for model comparison.")

    # ---- RMSE-vs-depth comparison plot ----
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(5.5, 6))
    for name, m in results.items():
        ax.plot(m["rmse"], m["depth"], "o-", label=name)
    ax.invert_yaxis()
    ax.set_xlabel("RMSE (deg C)")
    ax.set_ylabel("Depth (m)")
    ax.set_title(f"Baseline skill vs depth ({tag})")
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fname = config.FIGURES / f"baselines_rmse_{tag}.png"
    fig.savefig(fname, dpi=140, bbox_inches="tight")
    print(f"\n[fig] {fname}")

    np.savez(config.DATA_PROC / f"baselines_{tag}.npz",
             **{f"{k}_{m}": results[k][m] for k in results
                for m in ("rmse", "bias", "mae", "corr")},
             depth=np.asarray(res["depths"]))
    print("=== Day 2 complete ===\n")
    return results


if __name__ == "__main__":
    s = sys.argv[1] if len(sys.argv) > 1 else "2020-01-01"
    e = sys.argv[2] if len(sys.argv) > 2 else "2020-01-31"
    main(s, e, f"{s}_{e}")

"""Visual demo of the trained model: truth vs prediction vs error.

Runs out of the box on the bundled 7-day sample in `samples/`. If the full
processed arrays exist in `data/processed/` those are used instead.

Usage:
    python demo_model.py               # bundled sample (tag "2020")
    python demo_model.py 2020 3        # tag, day index
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src import config, data, model as M

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def main(tag="2020", day: int = -1):
    tf = M.tf
    print(f"loading model for tag={tag}")

    X, Y, stats, channels = data.load_arrays(tag)
    Xn, Yn = data.normalize(X, Y, stats, channels)
    T = X.shape[0]
    n_val = max(5, T // 5)
    val_idx = np.arange(T - n_val, T)

    model = M.OceanModel(cin=X.shape[1], D=256, Z=Y.shape[1])
    _ = model(tf.zeros([1, X.shape[1], X.shape[2], X.shape[3]]))
    ckpt = config.ROOT / "weights" / f"model_{tag}.weights.h5"
    model.load_weights(ckpt)
    print(f"loaded {ckpt}  ({model.count_params():,} params)")

    # predict the chosen val day
    di = val_idx[day]
    xb = np.nan_to_num(Xn[di][None], nan=0.0).astype("float32")
    predn, z = model(xb, training=False)
    pred = predn.numpy()[0] * (stats["y_std"] + 1e-6) + stats["y_mean"]
    true = Y[di]
    pred = np.where(np.isfinite(true), pred, np.nan)
    err = pred - true

    lat, lon = np.array(config.LAT), np.array(config.LON)
    zi = int(np.argmin(np.abs(np.array(config.DEPTHS) - 100)))
    zlabel = config.DEPTHS[zi]

    # ---------------- figure: fields at 100 m ----------------
    fig, axes = plt.subplots(1, 3, figsize=(18, 5.5))
    lim = dict(shading="auto")
    vmin, vmax = np.nanmin(true[zi]), np.nanmax(true[zi])
    for ax, (fld, ttl, cmap, lo, hi) in zip(
        axes,
        [
            (true[zi], f"TRUTH  @ {zlabel} m", "RdYlBu_r", vmin, vmax),
            (pred[zi], f"PREDICTION  @ {zlabel} m", "RdYlBu_r", vmin, vmax),
            (err[zi], "ERROR (pred - truth)", "bwr", -1.5, 1.5),
        ],
    ):
        im = ax.pcolormesh(lon, lat, fld, cmap=cmap, vmin=lo, vmax=hi, **lim)
        ax.set_title(ttl, fontsize=13)
        ax.set_xlabel("Longitude (E)")
        ax.set_ylabel("Latitude (N)")
        fig.colorbar(im, ax=ax, extend="both", label="deg C", shrink=0.85)
    fig.suptitle(f"Model demo — day {di} — mean RMSE@100m = "
                 f"{np.sqrt(np.nanmean(err[zi]**2)):.2f} deg C", fontsize=14)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    f1 = config.FIGURES / f"demo_fields_{tag}.png"
    fig.savefig(f1, dpi=130, bbox_inches="tight")
    print(f"[fig] {f1}")

    # ---------------- figure: vertical profiles ----------------
    # pick 4 ocean points (spread across the domain)
    oce = np.isfinite(true[0])
    ys, xs = np.where(oce)
    picks = [np.argmin(ys + xs),        # SW  (Arabian Sea side)
             np.argmax(ys - xs),        # SE  (Bay of Bengal side)
             np.argmax(ys + xs),        # NE
             np.argmin(ys - xs)]        # NW
    fig, axes = plt.subplots(1, 4, figsize=(16, 5.5), sharey=True)
    depths = config.DEPTHS
    for ax, p in zip(axes, picks):
        j, i = ys[p], xs[p]
        ax.plot(true[:, j, i], depths, "k-",  lw=2.2, label="truth")
        ax.plot(pred[:, j, i], depths, "r--", lw=2.2, label="prediction")
        ax.invert_yaxis()
        ax.set_xlabel("Temperature (deg C)")
        ax.set_title(f"{lat[j]:.1f}N {lon[i]:.1f}E", fontsize=11)
        ax.grid(alpha=0.3)
    axes[0].set_ylabel("Depth (m)")
    axes[0].legend()
    fig.suptitle(f"Vertical temperature profiles — day {di}", fontsize=14)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    f2 = config.FIGURES / f"demo_profiles_{tag}.png"
    fig.savefig(f2, dpi=130, bbox_inches="tight")
    print(f"[fig] {f2}")

    # ---------------- numbers ----------------
    print(f"\nDay {di}: RMSE@100m = {np.sqrt(np.nanmean(err[zi]**2)):.3f} deg C")
    print(f"Embedding z: shape={z.shape}, "
          f"mean={float(z.numpy().mean()):.3f}, std={float(z.numpy().std()):.3f}")
    print("\nOpen the two PNGs in figures/ to see the model.")
    return f1, f2


if __name__ == "__main__":
    tg = sys.argv[1] if len(sys.argv) > 1 else "2020"
    d = int(sys.argv[2]) if len(sys.argv) > 2 else -1
    main(tg, d)

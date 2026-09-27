"""Quickstart: verify the trained model on a fresh clone.

Runs entirely from files shipped in this repository:

  * ``weights/model_2020.weights.h5``  - the trained model (~6.7 MB)
  * ``samples/*_2020.npy``             - a 7-day sample of inputs/targets

Usage
-----
    python quickstart.py
    python quickstart.py --tag 2020 --weights weights/model_2020.weights.h5

NOTE
----
The bundled sample comes from the 2020 *training* year, so the RMSE printed
here measures how well the model fits data it has already seen - it is **not**
a generalization score. For honest, out-of-sample skill see
``run_argo_validation.py`` and the numbers in README.md / STATUS.md.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src import config, data, metrics as ev  # noqa: E402
from src import model as M  # noqa: E402


def main(tag: str = "2020", weights: str | None = None) -> None:
    tf = M.tf

    wpath = (Path(weights) if weights
             else config.ROOT / "weights" / f"model_{tag}.weights.h5")
    if not wpath.exists():
        raise SystemExit(
            f"trained weights not found: {wpath}\n"
            "See weights/README.md for how to obtain them."
        )

    print("=" * 64)
    print("PS66 subsurface-temperature model - quickstart")
    print("=" * 64)

    X, Y, stats, channels = data.load_arrays(tag)
    print(f"inputs    X {X.shape}   channels = {channels}")
    print(f"targets   Y {Y.shape}   depths 0-1000 m = {Y.shape[1]}")
    print(f"weights   {wpath}")

    Xn, _ = data.normalize(X, Y, stats, channels)

    model = M.OceanModel(cin=X.shape[1], D=256, Z=Y.shape[1])
    _ = model(tf.zeros([1, X.shape[1], X.shape[2], X.shape[3]]))
    model.load_weights(wpath)
    print(f"model     {model.count_params():,} parameters")

    # ---- predict -------------------------------------------------------
    preds, z = [], None
    for i in range(0, len(Xn), 4):
        xb = np.nan_to_num(Xn[i:i + 4], nan=0.0).astype("float32")
        p, z = model(xb, training=False)
        preds.append(p.numpy())
    pred = np.concatenate(preds) * (stats["y_std"] + 1e-6) + stats["y_mean"]
    pred = np.where(np.isfinite(Y), pred, np.nan)          # land -> NaN
    print(f"output    prediction {pred.shape}   embedding z {tuple(z.shape)}")

    # ---- score ---------------------------------------------------------
    m = ev.per_depth_metrics(pred, Y)
    ev.print_table(m, f"model vs GLORYS truth (tag={tag})")
    h = ev.headline(m)
    print(f"\n  HEADLINE   all={h['rmse_all']:.3f}   >=50m={h['rmse_ge50']:.3f}"
          f"   thermocline={h['rmse_thermocline']:.3f}   "
          f"corr={h['corr_all']:.3f}")

    # ---- figure --------------------------------------------------------
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    zi = int(np.argmin(np.abs(np.array(config.DEPTHS) - 100)))
    lat, lon = np.array(config.LAT), np.array(config.LON)
    vmin, vmax = np.nanmin(Y[0, zi]), np.nanmax(Y[0, zi])
    fig, axes = plt.subplots(1, 3, figsize=(17, 5))
    panels = [
        (Y[0, zi], f"TRUTH @ {config.DEPTHS[zi]} m", "RdYlBu_r", vmin, vmax),
        (pred[0, zi], f"PREDICTION @ {config.DEPTHS[zi]} m", "RdYlBu_r", vmin, vmax),
        (pred[0, zi] - Y[0, zi], "ERROR (pred - truth)", "bwr", -1.5, 1.5),
    ]
    for ax, (fld, ttl, cm, lo, hi) in zip(axes, panels):
        im = ax.pcolormesh(lon, lat, fld, cmap=cm, vmin=lo, vmax=hi)
        ax.set_title(ttl)
        ax.set_xlabel("Longitude (E)")
        ax.set_ylabel("Latitude (N)")
        fig.colorbar(im, ax=ax, extend="both", label="deg C", shrink=0.85)
    fig.suptitle(f"PS66 model - first day of the bundled sample (tag {tag})",
                 fontsize=14)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    out = config.FIGURES / "quickstart_prediction.png"
    fig.savefig(out, dpi=130, bbox_inches="tight")
    print(f"\n[fig] {out}")
    print("\nOK - the model runs end to end.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="PS66 model quickstart")
    ap.add_argument("--tag", default="2020")
    ap.add_argument("--weights", default=None)
    args = ap.parse_args()
    main(args.tag, args.weights)

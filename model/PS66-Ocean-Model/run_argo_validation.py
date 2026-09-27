"""Independent ARGO validation for the PS66 subsurface-temperature model.

Compares trained model predictions against gridded ARGO (INCOIS ERDDAP)
observations that were NEVER used in training. Prints per-depth RMSE / Bias /
MAE / correlation and the honest headline numbers.

Usage
-----
    py -3.12 run_argo_validation.py 2020
    py -3.12 run_argo_validation.py 2020 --argo data/raw/argo_2020.nc
    py -3.12 run_argo_validation.py 2020 --weights checkpoints/model_2020.weights.h5
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src import argo, config, data, harmonize  # noqa: E402
from src import metrics as ev  # noqa: E402


# --------------------------------------------------------------------------
# ARGO acquisition
# --------------------------------------------------------------------------
def fetch_argo(start: str, end: str, path: str | None = None) -> Path:
    """Download gridded ARGO from INCOIS ERDDAP (with SSL fallback)."""
    import certifi
    import requests

    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
    os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())

    out = Path(path) if path else config.DATA_RAW / f"argo_{start}_{end}.nc"
    if out.exists():
        print(f"[skip] ARGO already present: {out}")
        return out

    url = (f"{argo.ERDDAP_BASE}/{argo.ERDDAP_DATASET}.nc"
           f"?T_ANALYZED%5B({start}):1:({end})%5D"
           f"%5B(5.0):1:(2000.0)%5D%5B(5.0):1:(29.5)%5D%5B(45.0):1:(105.0)%5D")
    print(f"[download] {url}")
    try:
        r = requests.get(url, verify=certifi.where(), timeout=300)
        r.raise_for_status()
    except Exception as e:                                   # noqa: BLE001
        print(f"  certifi verify failed -> retrying verify=False: {e}")
        import urllib3
        urllib3.disable_warnings()
        r = requests.get(url, verify=False, timeout=300)
        r.raise_for_status()
    out.write_bytes(r.content)
    print(f"[ok] {out} ({out.stat().st_size / 1e6:.1f} MB)")
    return out


def load_argo_clean(path: Path):
    """Load ARGO, strip fill values, interpolate to standard depths + grid."""
    import xarray as xr

    ds = xr.open_dataset(path, mask_and_scale=False)
    tvar = next(v for v in ("T_ANALYZED", "temp", "temperature") if v in ds)
    T = ds[tvar]
    a = T.values.astype("float64")
    fill = T.attrs.get("_FillValue", T.attrs.get("missing_value"))
    if fill is not None and np.isscalar(fill) and np.isfinite(fill):
        a[a == fill] = np.nan
    a[np.abs(a) > 1e4] = np.nan                      # catch big sentinels

    da = xr.DataArray(a.astype("float32"), dims=T.dims, coords=T.coords,
                      name="temp")
    if "ZAX" in da.dims:
        da = da.rename({"ZAX": "depth"})
    da = harmonize._to_standard_depths(da)
    da = argo.regrid_to_target(da)
    ds.close()
    return da


# --------------------------------------------------------------------------
def main(tag: str, argo_path: str | None, weights: str | None,
         start: str, end: str, save_fig: bool = True) -> dict:
    import tensorflow as tf
    from src import model as M

    weights = weights or str(config.CHECKPOINTS / f"model_{tag}.weights.h5")
    if not Path(weights).exists():
        raise SystemExit(f"missing weights: {weights} - train first (run_day3.py)")

    # ---- ARGO ---------------------------------------------------------
    apath = fetch_argo(start, end, argo_path)
    da = load_argo_clean(apath)
    days = pd.date_range(start, end, freq="D").values
    aligned = da.sel({"time": days}, method="nearest").transpose("time", ...)
    ar = np.where(np.isfinite(aligned.values), aligned.values, np.nan)
    print(f"ARGO field {ar.shape}  finite={np.isfinite(ar).mean() * 100:.1f}%")

    # ---- model predictions -------------------------------------------
    X, Y, stats, channels = data.load_arrays(tag)
    Xn, _ = data.normalize(X, Y, stats, channels)
    Xn = np.nan_to_num(Xn, nan=0.0).astype("float32")   # land -> 0, as in training

    mdl = M.OceanModel(cin=X.shape[1], D=256, Z=Y.shape[1])
    _ = mdl(tf.zeros([1, X.shape[1], X.shape[2], X.shape[3]]))
    mdl.load_weights(weights)
    print(f"model loaded: {mdl.count_params():,} params  channels={channels}")

    P = []
    for i in range(0, len(Xn), 4):
        p, _ = mdl(Xn[i:i + 4], training=False)
        P.append(p.numpy())
    pred = np.concatenate(P) * (stats["y_std"] + 1e-6) + stats["y_mean"]
    pred = np.where(np.isfinite(Y), pred, np.nan)
    print(f"pred field {pred.shape}  finite={np.isfinite(pred).mean() * 100:.1f}%")

    # ---- compare ------------------------------------------------------
    valid = np.isfinite(pred) & np.isfinite(ar)
    print(f"\nco-located points: {valid.sum():,}")
    if valid.sum() == 0:
        raise SystemExit("no overlap - inspect the ARGO file (src.argo.inspect)")

    m = ev.per_depth_metrics(pred, ar)
    ev.print_table(m, "model vs ARGO (independent)")
    h = ev.headline(m)
    print(f"\n  HEADLINE vs ARGO  all={h['rmse_all']:.3f}  "
          f">=50m={h['rmse_ge50']:.3f}  therm={h['rmse_thermocline']:.3f}  "
          f"corr={h['corr_all']:.3f}")

    # fair day-before persistence for context
    fair = np.full_like(Y, np.nan)
    fair[1:] = Y[:-1]
    print("\n  -- reference: day-before persistence --")
    ev.print_headline(fair, ar, "persistence", common=False)

    # ---- figure -------------------------------------------------------
    if save_fig:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(5.5, 6))
        ax.plot(m["rmse"], m["depth"], "o-", label="model vs ARGO")
        pf = ev.per_depth_metrics(fair, ar)
        ax.plot(pf["rmse"], pf["depth"], "--", label="persistence")
        ax.invert_yaxis()
        ax.set_xlabel("RMSE (deg C)")
        ax.set_ylabel("Depth (m)")
        ax.set_title(f"Independent ARGO validation ({tag})")
        ax.grid(alpha=0.3)
        ax.legend()
        fig.tight_layout()
        fname = config.FIGURES / f"argo_rmse_{tag}.png"
        fig.savefig(fname, dpi=140, bbox_inches="tight")
        print(f"\n[fig] {fname}")

    return m


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("tag", nargs="?", default="2020")
    ap.add_argument("--argo", default=None, help="path to a local ARGO NetCDF")
    ap.add_argument("--weights", default=None)
    ap.add_argument("--start", default="2020-01-01")
    ap.add_argument("--end", default="2020-12-31")
    ap.add_argument("--no-fig", action="store_true")
    args = ap.parse_args()
    main(args.tag, args.argo, args.weights, args.start, args.end,
         save_fig=not args.no_fig)

"""Evaluation metrics and skill harness.

All arrays follow the project convention:
    Y / pred : (time, depth, lat, lon)
Metrics are computed per depth level over valid (ocean) cells.
"""
from __future__ import annotations

import numpy as np

from . import config


def flatten_depth(y: np.ndarray) -> np.ndarray:
    """(time, depth, lat, lon) -> (samples, depth)."""
    t, z, h, w = y.shape
    return y.transpose(1, 0, 2, 3).reshape(z, -1).T


def per_depth_metrics(pred: np.ndarray, true: np.ndarray,
                      depths=None) -> dict:
    """Compute RMSE, Bias, MAE, correlation per depth.

    pred, true may be (time, depth, lat, lon) or (samples, depth).
    NaNs (land / missing) are ignored.
    """
    if pred.ndim == 4:
        pred = flatten_depth(pred)
    if true.ndim == 4:
        true = flatten_depth(true)
    if depths is None:
        depths = config.DEPTHS

    z = true.shape[1]
    out = {k: np.full(z, np.nan) for k in ("rmse", "bias", "mae", "corr")}
    for i in range(z):
        p, t = pred[:, i], true[:, i]
        m = np.isfinite(p) & np.isfinite(t)
        if m.sum() < 3:
            continue
        d = p[m] - t[m]
        out["rmse"][i] = np.sqrt((d ** 2).mean())
        out["bias"][i] = d.mean()
        out["mae"][i] = np.abs(d).mean()
        if p[m].std() > 0 and t[m].std() > 0:
            out["corr"][i] = np.corrcoef(p[m], t[m])[0, 1]
    out["depth"] = np.asarray(depths)
    return out


def overall_score(metrics: dict) -> dict:
    """Aggregate scalar scores for leaderboards/comparisons."""
    return {
        "rmse_mean": float(np.nanmean(metrics["rmse"])),
        "bias_mean": float(np.nanmean(metrics["bias"])),
        "mae_mean": float(np.nanmean(metrics["mae"])),
        "corr_mean": float(np.nanmean(metrics["corr"])),
        "rmse_0_200": float(np.nanmean(metrics["rmse"][:10])),
    }


# --------------------------------------------------------------------------
# Honest aggregation.
#
# The unweighted mean over the 15 levels is dominated by the four shallowest
# levels (0-20 m), which are nearly free because SST is already an input, and
# it mixes per-level masks of different size (the valid fraction falls from
# 48.8 % to 37.7 % with depth), so deep levels are scored on a smaller and
# systematically easier set of cells. The helpers below report the numbers
# that are actually comparable across methods.
# --------------------------------------------------------------------------
def band_mean(metrics: dict, key: str = "rmse", lo=None, hi=None) -> float:
    """Mean of a per-depth metric over the depth band [lo, hi] metres."""
    d = metrics["depth"]
    sel = np.ones(np.asarray(d).shape, dtype=bool)
    if lo is not None:
        sel &= np.asarray(d) >= lo
    if hi is not None:
        sel &= np.asarray(d) <= hi
    if not sel.any():
        return float("nan")
    return float(np.nanmean(metrics[key][sel]))


def common_mask_metrics(pred: np.ndarray, true: np.ndarray, depths=None) -> dict:
    """Per-depth metrics restricted to cells valid at *every* depth.

    pred, true : (time, depth, lat, lon). A cell is scored only if the truth
    is finite at all 15 levels on that day, so every level is scored on the
    same set of cells and the moving-mask bias disappears.
    """
    if pred.ndim != 4 or true.ndim != 4:
        raise ValueError("common_mask_metrics expects (time, depth, lat, lon)")
    valid = np.isfinite(pred) & np.isfinite(true)
    common = valid.all(axis=1, keepdims=True)          # (time, 1, lat, lon)
    mask = np.broadcast_to(common, valid.shape)
    p = np.where(mask, pred, np.nan).astype("float32")
    t = np.where(mask, true, np.nan).astype("float32")
    return per_depth_metrics(p, t, depths)


def headline(metrics: dict) -> dict:
    """The set of scalars we report as the honest skill summary."""
    return {
        "rmse_all": band_mean(metrics, "rmse"),
        "rmse_ge50": band_mean(metrics, "rmse", lo=50),
        "rmse_thermocline": band_mean(metrics, "rmse", lo=50, hi=200),
        "bias_ge50": band_mean(metrics, "bias", lo=50),
        "corr_all": float(np.nanmean(metrics["corr"])),
        "corr_ge50": band_mean(metrics, "corr", lo=50),
    }


def wins_vs(reference: dict, candidate: dict, depths=None) -> np.ndarray:
    """Boolean per-level: does `candidate` beat `reference` on RMSE?"""
    return candidate["rmse"] < reference["rmse"]


def print_headline(pred: np.ndarray, true: np.ndarray, name: str = "model",
                   *, common: bool = True, depths=None) -> dict:
    """Compute and print the honest headline numbers for one method."""
    m = (common_mask_metrics(pred, true, depths) if common
         else per_depth_metrics(pred, true, depths))
    h = headline(m)
    tag = "common-mask" if common else "per-level"
    print(f"  {name:14s} [{tag}]  all={h['rmse_all']:.3f}  "
          f">=50m={h['rmse_ge50']:.3f}  "
          f"therm(50-200m)={h['rmse_thermocline']:.3f}  "
          f"corr={h['corr_all']:.3f}")
    return m


def print_table(metrics: dict, name: str = "model") -> None:
    print(f"\n[{name}]  depth   RMSE    Bias     MAE    Corr")
    for i, z in enumerate(metrics["depth"]):
        print(f"        {z:5.0f}  {metrics['rmse'][i]:6.3f}  "
              f"{metrics['bias'][i]:6.3f}  {metrics['mae'][i]:6.3f}  "
              f"{metrics['corr'][i]:6.3f}")
    s = overall_score(metrics)
    print(f"        MEAN   {s['rmse_mean']:6.3f}  {s['bias_mean']:6.3f}  "
          f"{s['mae_mean']:6.3f}  {s['corr_mean']:6.3f}")

"""Plotting helpers for maps and profiles."""
from __future__ import annotations

import numpy as np

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except Exception:  # pragma: no cover
    plt = None

from . import config


def plot_field(field, lat, lon, *, title="", cmap="RdYlBu_r",
               cbar_label="", fname=None, vmin=None, vmax=None):
    """Plot a 2-D (lat, lon) field."""
    if plt is None:
        raise RuntimeError("matplotlib not available")
    fig, ax = plt.subplots(figsize=(9, 5))
    im = ax.pcolormesh(lon, lat, field, cmap=cmap, shading="auto",
                       vmin=vmin, vmax=vmax)
    ax.set_xlabel("Longitude (E)")
    ax.set_ylabel("Latitude (N)")
    ax.set_title(title)
    cb = fig.colorbar(im, ax=ax, extend="both")
    cb.set_label(cbar_label)
    fig.tight_layout()
    if fname:
        fig.savefig(fname, dpi=140, bbox_inches="tight")
        print(f"[fig] {fname}")
    return fig, ax


def plot_rmse_vs_depth(rmse, depths, *, fname=None, label="model"):
    """The money plot: RMSE as a function of depth."""
    if plt is None:
        raise RuntimeError("matplotlib not available")
    fig, ax = plt.subplots(figsize=(5, 6))
    ax.plot(rmse, depths, "o-", label=label)
    ax.invert_yaxis()
    ax.set_xlabel("RMSE (deg C)")
    ax.set_ylabel("Depth (m)")
    ax.set_title("Temperature reconstruction skill vs depth")
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    if fname:
        fig.savefig(fname, dpi=140, bbox_inches="tight")
        print(f"[fig] {fname}")
    return fig, ax

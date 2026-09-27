"""tf.data pipeline for the subsurface-temperature model.

Loads preprocessed arrays and yields normalised (X, Y, mask) batches.
Land / missing cells are NaN in Y; the mask marks valid ocean cells so the
loss can ignore them.
"""
from __future__ import annotations

import numpy as np
import tensorflow as tf

from . import config


def _resolve(name: str) -> Path:
    """Prefer the full processed array; fall back to the bundled sample.

    A fresh clone has no `data/processed/` (too big for GitHub), so the
    small 7-day arrays in `samples/` are used instead.
    """
    full = config.DATA_PROC / name
    if full.exists():
        return full
    small = config.ROOT / "samples" / name
    return small if small.exists() else full


def load_arrays(tag: str):
    X = np.load(_resolve(f"X_{tag}.npy"))
    Y = np.load(_resolve(f"Y_{tag}.npy"))
    stats = dict(np.load(_resolve(f"stats_{tag}.npz")))
    cpath = _resolve(f"channels_{tag}.npy")
    channels = list(np.load(cpath, allow_pickle=True)) if cpath.exists() else \
        config.INPUT_CHANNELS[: X.shape[1]]
    return X, Y, stats, channels


def normalize(X, Y, stats, channels):
    """Per-channel z-score for X; global z-score for Y. NaNs preserved."""
    Xn = X.astype("float32").copy()
    for i, c in enumerate(channels):
        m = stats[f"x_mean_{c}"]
        s = stats[f"x_std_{c}"] + 1e-6
        Xn[:, i] = (Xn[:, i] - m) / s
    Yn = (Y.astype("float32") - stats["y_mean"]) / (stats["y_std"] + 1e-6)
    return Xn, Yn


def make_dataset(Xn, Yn, idx, *, batch=4, shuffle=True, seed=0):
    """Build a tf.data.Dataset over time indices `idx`.

    Each item: x (C,H,W), y (Z,H,W) with NaNs replaced by 0, and mask (Z,H,W).
    """
    x = np.nan_to_num(Xn[idx], nan=0.0).astype("float32")
    yraw = Yn[idx].astype("float32")
    mask = np.isfinite(yraw).astype("float32")
    y = np.nan_to_num(yraw, nan=0.0)
    ds = tf.data.Dataset.from_tensor_slices((x, y, mask))
    if shuffle:
        ds = ds.shuffle(min(len(idx), 512), seed=seed,
                        reshuffle_each_iteration=True)
    return ds.batch(batch).prefetch(tf.data.AUTOTUNE)

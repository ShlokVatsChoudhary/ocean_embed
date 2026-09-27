"""Baseline models to beat.

All baselines take the project arrays:
    X : (time, channel, lat, lon)   surface inputs
    Y : (time, depth,  lat, lon)    temperature profiles
and produce predictions with the same shape as Y (or Y[1:]).
"""
from __future__ import annotations

import numpy as np

from . import config


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def day_of_year(times: np.ndarray) -> np.ndarray:
    """np.datetime64 series -> day-of-year (1..366)."""
    out = []
    for t in np.asarray(times):
        d = np.datetime64(t, "D")
        y = d.astype("datetime64[Y]")
        out.append(int((d - y).astype(int)) + 1)
    return np.asarray(out)


def _nanmean_or(arr, fallback):
    if arr.size == 0:
        return fallback
    with np.errstate(invalid="ignore"):
        m = np.nanmean(arr, axis=0)
    return np.where(np.isfinite(m), m, fallback)


# --------------------------------------------------------------------------
# 1. persistence: predict today from yesterday
# --------------------------------------------------------------------------
def persistence(Y: np.ndarray):
    """Return (pred, true) aligned to t=1..T-1."""
    if len(Y) < 2:
        raise ValueError("need >= 2 time steps for persistence")
    return Y[:-1].copy(), Y[1:].copy()


# --------------------------------------------------------------------------
# 2. climatology: day-of-year mean computed on the training period
# --------------------------------------------------------------------------
def fit_climatology(Y: np.ndarray, times: np.ndarray, train_mask: np.ndarray,
                    n_doy: int = 366) -> np.ndarray:
    """Return (n_doy, depth, lat, lon) climatology from training days only."""
    doy = day_of_year(times)
    fallback = np.nanmean(Y[train_mask], axis=0) if train_mask.any() else \
        np.zeros(Y.shape[1:], dtype="float32")
    clim = np.empty((n_doy, *Y.shape[1:]), dtype="float32")
    for d in range(1, n_doy + 1):
        sel = train_mask & (doy == d)
        clim[d - 1] = _nanmean_or(Y[sel], fallback) if sel.any() else fallback
    return clim


def predict_climatology(clim: np.ndarray, times: np.ndarray) -> np.ndarray:
    doy = day_of_year(times)
    return clim[doy - 1]


# --------------------------------------------------------------------------
# 3. SST (+ optional extra channels) -> T(z)  MLP
# --------------------------------------------------------------------------
def sst_to_T_mlp(X: np.ndarray, Y: np.ndarray, train_mask: np.ndarray,
                 *, channels=("sst", "sla"), array_channels=None,
                 hidden=(128, 128), use_position: bool = True,
                 max_train=150_000, seed=0):
    """Fit a per-pixel MLP mapping surface channels -> full profile.

    Because deep temperature variability is dominated by *location* (Arabian
    Sea vs Bay of Bengal, shelf vs open ocean), positional features (lat/lon)
    matter as much as the surface state. `use_position` adds them.

    `channels` names are resolved against `array_channels` (the channel names
    actually stored in `X`), NOT against the global `config.INPUT_CHANNELS`
    ordering -- those differ whenever optional channels are absent, which used
    to silently select the wrong column.

    Returns a predict(times) closure. Land/missing samples are excluded from
    training; predictions are masked back to ocean (NaN where Y is NaN).
    """
    from sklearn.neural_network import MLPRegressor

    names = list(array_channels) if array_channels is not None else \
        list(config.INPUT_CHANNELS)
    ch_idx = [names.index(c) for c in channels if c in names]
    if not ch_idx:
        raise ValueError(f"none of {channels} are present in {names}")
    T = X.shape[0]
    H, W = X.shape[2], X.shape[3]
    # (T, lat, lon, C) dynamic + optional static positional features
    feat = X[:, ch_idx].transpose(0, 2, 3, 1).reshape(-1, len(ch_idx))
    if use_position:
        latg, long = np.meshgrid(np.array(config.LAT), np.array(config.LON),
                                 indexing="ij")
        pos = np.stack([latg, long], -1).reshape(-1, 2)
        pos = np.tile(pos, (T, 1))
        feat = np.concatenate([feat, pos], axis=1)
    targ = Y.transpose(0, 2, 3, 1).reshape(-1, Y.shape[1])

    # training rows: ocean (all depths finite) on training days
    day_ok = np.repeat(train_mask, H * W)
    valid = np.isfinite(feat).all(1) & np.isfinite(targ).all(1) & day_ok
    idx = np.flatnonzero(valid)
    rng = np.random.default_rng(seed)
    if len(idx) > max_train:
        idx = rng.choice(idx, max_train, replace=False)

    mean = feat[idx].mean(0, keepdims=True)
    std = feat[idx].std(0, keepdims=True) + 1e-6
    ymean = targ[idx].mean(0, keepdims=True)
    ystd = targ[idx].std(0, keepdims=True) + 1e-6
    model = MLPRegressor(hidden_layer_sizes=hidden, activation="relu",
                         batch_size=4096, learning_rate_init=1e-3,
                         max_iter=150, early_stopping=True,
                         n_iter_no_change=8, random_state=seed)
    model.fit((feat[idx] - mean) / std, (targ[idx] - ymean) / ystd)

    def predict(times_idx) -> np.ndarray:
        xi = X[times_idx]
        n = len(times_idx)
        f = xi[:, ch_idx].transpose(0, 2, 3, 1).reshape(-1, len(ch_idx))
        if use_position:
            latg, long = np.meshgrid(np.array(config.LAT),
                                     np.array(config.LON), indexing="ij")
            pos = np.tile(np.stack([latg, long], -1).reshape(-1, 2), (n, 1))
            f = np.concatenate([f, pos], axis=1)
        ok = np.isfinite(f).all(1)
        pred = np.full((len(f), Y.shape[1]), np.nan, dtype="float32")
        pred[ok] = (model.predict((f[ok] - mean) / std) * ystd + ymean
                    ).astype("float32")
        return pred.reshape(n, X.shape[2], X.shape[3],
                            Y.shape[1]).transpose(0, 3, 1, 2)

    return predict

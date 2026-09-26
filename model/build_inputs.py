"""Build / extend the surface-input cache used by the inference adapter.

The adapter reads ``model/input_cache/X_<tag>.npz`` with keys:

* ``X``        — float16 array ``(T, C, NY, NX)`` of the 5 surface channels
* ``dates``    — ISO date strings, one per timestep (length ``T``)
* ``channels`` — the channel names, in order
* ``ocean``    — bool ``(NY, NX)`` land mask (True = ocean)
* ``bathy``    — float32 ``(NY, NX)`` seabed depth in metres (NaN on land)

This script converts preprocessed PS66 arrays into that format. It is how the
shipped ``X_2020Q1.npz`` was made.

Usage::

    python -m model.build_inputs \
        --x /path/data/processed/X_2020-01-01_2020-03-31.npy \
        --y /path/data/processed/Y_2020-01-01_2020-03-31.npy \
        --bathy /path/data/processed/bathy_2020-01-01_2020-03-31.npy \
        --channels /path/data/processed/channels_2020-01-01_2020-03-31.npy \
        --start 2020-01-01 \
        --out model/input_cache/X_2020Q1.npz

To regenerate ``X_*.npy`` itself you need the training repository (the PS66
``siH-PS66`` project) and a Copernicus Marine login; see its ``run_ingest.py``.
"""
from __future__ import annotations

import argparse
import datetime as dt

import numpy as np


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--x", required=True, help="path to X_<tag>.npy")
    ap.add_argument("--y", default=None, help="path to Y_<tag>.npy (for the land mask)")
    ap.add_argument("--bathy", default=None, help="path to bathy_<tag>.npy (seabed depth)")
    ap.add_argument("--channels", default=None, help="path to channels_<tag>.npy")
    ap.add_argument("--start", required=True, help="first date, YYYY-MM-DD (contiguous daily)")
    ap.add_argument("--out", required=True, help="output .npz path")
    args = ap.parse_args()

    X = np.load(args.x)                      # (T, C, NY, NX)
    channels = (
        [str(c) for c in np.load(args.channels, allow_pickle=True)]
        if args.channels
        else ["sst", "sss", "sla", "ugos", "vgos"][: X.shape[1]]
    )

    # land mask: a cell is ocean if the target is finite at the surface on some day
    if args.y:
        Y = np.load(args.y)
        ocean = np.isfinite(Y[:, 0]).any(axis=0)
    else:
        ocean = np.isfinite(X).all(axis=1).any(axis=0)  # fallback: all channels finite

    if args.bathy:
        bathy = np.load(args.bathy).astype("float32")
    else:
        bathy = np.where(ocean, 1000.0, np.nan).astype("float32")

    start = dt.date.fromisoformat(args.start)
    dates = np.array(
        [(start + dt.timedelta(days=i)).isoformat() for i in range(X.shape[0])]
    )

    np.savez_compressed(
        args.out,
        X=X.astype(np.float16),
        dates=dates,
        channels=np.array(channels, dtype=object),
        ocean=ocean,
        bathy=bathy,
    )
    print(
        f"wrote {args.out}: X{X.shape}  {len(dates)} days  channels={channels}  "
        f"ocean={int(ocean.sum())} ({100*ocean.mean():.1f}%)"
    )


if __name__ == "__main__":
    main()

"""Generic, resumable month-by-month ingest for PS66.

Downloads the target + input datasets one calendar month at a time, harmonises
each month onto the common grid, and writes per-month arrays. Finally it
combines the months into one big array (via an on-disk memmap, so RAM stays
low) and computes global normalisation stats.

Resumable: a month is skipped if its per-month `.npy` files already exist, so
re-running after an interruption continues where it stopped.

Usage
-----
    python run_ingest.py 2020-01-01 2020-03-31
    python run_ingest.py 2015-01-01 2024-03-31 --out-tag clim_2015_2024
    python run_ingest.py 2020-01-01 2020-03-31 --combine-only
"""
from __future__ import annotations

import argparse
import calendar
import gc
import sys
from datetime import date
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src import config, download, harmonize  # noqa: E402


# --------------------------------------------------------------------------
# date helpers
# --------------------------------------------------------------------------
def month_ranges(start: str, end: str) -> list[tuple[str, str]]:
    """Split [start, end] into per-calendar-month ISO date ranges."""
    s, e = date.fromisoformat(start), date.fromisoformat(end)
    if e < s:
        raise ValueError("end date is before start date")
    out: list[tuple[str, str]] = []
    cur = date(s.year, s.month, 1)
    while cur <= e:
        last = date(cur.year, cur.month,
                    calendar.monthrange(cur.year, cur.month)[1])
        ms, me = max(cur, s), min(last, e)
        if ms <= me:
            out.append((ms.isoformat(), me.isoformat()))
        nxt = (cur.year + 1, 1) if cur.month == 12 else (cur.year, cur.month + 1)
        cur = date(*nxt, 1)
    return out


def _paths(tag: str):
    return (config.DATA_PROC / f"X_{tag}.npy",
            config.DATA_PROC / f"Y_{tag}.npy",
            config.DATA_PROC / f"channels_{tag}.npy")


# --------------------------------------------------------------------------
# per-month ingest
# --------------------------------------------------------------------------
def ingest_month(ms: str, me: str, *, force: bool = False) -> str:
    tag = f"{ms}_{me}"
    xp, yp, cp = _paths(tag)
    if not force and xp.exists() and yp.exists() and cp.exists():
        print(f"[skip] month {tag}: arrays already built")
        return tag
    if force:
        print(f"[force] month {tag}: rebuilding arrays")

    print(f"\n===== ingest {tag} =====", flush=True)
    paths = download.download_all(ms, me)          # skips existing files
    harmonize.build_arrays(paths["target"], paths["duacs"], paths["ostia"],
                           sss_path=paths.get("sss"), tag=tag)
    # free the (potentially large) xarray/numpy objects before the next month
    gc.collect()
    print(f"[done] {tag}", flush=True)
    return tag


# --------------------------------------------------------------------------
# combine months -> one array + global stats (RAM-safe via memmap)
# --------------------------------------------------------------------------
def combine(tags: list[str], out_tag: str) -> None:
    print(f"\n===== combining {len(tags)} month(s) -> {out_tag} =====", flush=True)

    channels = list(np.load(config.DATA_PROC / f"channels_{tags[0]}.npy",
                            allow_pickle=True))
    for t in tags[1:]:
        ch = list(np.load(config.DATA_PROC / f"channels_{t}.npy",
                          allow_pickle=True))
        if ch != channels:
            raise ValueError(f"channel mismatch in {t}: {ch} != {channels}")

    xs = [np.load(_paths(t)[0], mmap_mode="r") for t in tags]
    ys = [np.load(_paths(t)[1], mmap_mode="r") for t in tags]
    T = int(sum(x.shape[0] for x in xs))
    C, H, W = xs[0].shape[1:]
    Z = ys[0].shape[1]
    assert all(y.shape[1:] == (Z, H, W) for y in ys), "Y shape mismatch"

    xo = np.lib.format.open_memmap(config.DATA_PROC / f"X_{out_tag}.npy",
                                   mode="w+", dtype="float32", shape=(T, C, H, W))
    yo = np.lib.format.open_memmap(config.DATA_PROC / f"Y_{out_tag}.npy",
                                   mode="w+", dtype="float32", shape=(T, Z, H, W))

    acc = {c: [0.0, 0.0, 0] for c in channels}      # sum, sumsq, count
    yacc = [0.0, 0.0, 0]
    off = 0
    for t, X, Y in zip(tags, xs, ys):
        n = X.shape[0]
        Xa = np.asarray(X, dtype="float32")
        Ya = np.asarray(Y, dtype="float32")
        xo[off:off + n] = Xa
        yo[off:off + n] = Ya
        for i, c in enumerate(channels):
            v = Xa[:, i]
            v = v[np.isfinite(v)].astype("float64")
            acc[c][0] += v.sum(); acc[c][1] += (v * v).sum(); acc[c][2] += v.size
        v = Ya[np.isfinite(Ya)].astype("float64")
        yacc[0] += v.sum(); yacc[1] += (v * v).sum(); yacc[2] += v.size
        off += n
        print(f"  + {t}: {n} days (total {off})", flush=True)

    xo.flush(); yo.flush()

    stats = {}
    for c in channels:
        s, ss, cnt = acc[c]
        mean = s / cnt
        var = max(ss / cnt - mean * mean, 0.0)
        stats[f"x_mean_{c}"], stats[f"x_std_{c}"] = mean, float(np.sqrt(var))
        print(f"  {c:5s} mean={mean:10.4f}  std={stats[f'x_std_{c}']:9.4f}")
    mean, var = yacc[0] / yacc[2], max(yacc[1] / yacc[2] - (yacc[0] / yacc[2]) ** 2, 0.0)
    stats["y_mean"], stats["y_std"] = float(mean), float(np.sqrt(var))
    print(f"  y     mean={mean:10.4f}  std={stats['y_std']:9.4f}")

    np.savez(config.DATA_PROC / f"stats_{out_tag}.npz", **stats)
    np.save(config.DATA_PROC / f"channels_{out_tag}.npy", np.array(channels))

    # bathymetry is static -> carry it through so downstream code has one file
    bp = [config.DATA_PROC / f"bathy_{t}.npy" for t in tags]
    if all(p.exists() for p in bp):
        np.save(config.DATA_PROC / f"bathy_{out_tag}.npy",
                np.load(bp[0]).astype("float32"))
        print(f"[ok] bathy_{out_tag}.npy (from {bp[0].name})", flush=True)
    print(f"[ok] combined arrays: X_{out_tag}.npy {xo.shape}  "
          f"Y_{out_tag}.npy {yo.shape}", flush=True)


# --------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("start")
    ap.add_argument("end")
    ap.add_argument("--out-tag", default=None,
                    help="tag for the combined arrays (default: start_end)")
    ap.add_argument("--combine-only", action="store_true",
                    help="skip download/build; just recombine existing months")
    ap.add_argument("--force", action="store_true",
                    help="rebuild arrays even if they already exist (e.g. after "
                         "a harmonise fix); raw NetCDF downloads are still reused")
    args = ap.parse_args()

    out_tag = args.out_tag or f"{args.start}_{args.end}"
    months = month_ranges(args.start, args.end)
    print(f"ingest plan: {len(months)} month(s) from {args.start} to {args.end}")
    for ms, me in months:
        print(f"  - {ms} .. {me}")

    tags = []
    for ms, me in months:
        tag = f"{ms}_{me}"
        if not args.combine_only:
            ingest_month(ms, me, force=args.force)
        tags.append(tag)

    combine(tags, out_tag)
    print("\n=== ingest complete ===")


if __name__ == "__main__":
    main()

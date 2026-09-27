"""Day-1 driver: download -> harmonise -> build X/Y -> plot T at 100 m.

Usage:
    python run_day1.py                       # 3-day tiny test
    python run_day1.py 2020-01-01 2020-01-31 # custom range
"""
from __future__ import annotations

import sys

import numpy as np

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))

from src import config, download, harmonize, viz


def main(start: str, end: str, tag: str | None = None):
    tag = tag or f"{start}_{end}"
    print(f"\n=== Day 1 pipeline: {start} -> {end} (tag={tag}) ===\n")

    paths = download.download_all(start, end)
    print()

    res = harmonize.build_arrays(
        paths["target"], paths["duacs"], paths["ostia"],
        sss_path=paths.get("sss"), tag=tag)

    X, Y = res["X"], res["Y"]
    lat, lon, depths = res["lat"], res["lon"], res["depths"]
    print(f"\nX (time, channel, lat, lon): {X.shape}")
    print(f"Y (time, depth,   lat, lon): {Y.shape}")
    print(f"channels: {res['channels']}")

    # plot T at 100 m for the first day
    zi = depths.index(100)
    field = Y[0, zi]
    # mask land (GLORYS fills land with NaN already, but be safe)
    field = np.where(np.isfinite(field), field, np.nan)
    fname = config.FIGURES / f"T100m_{tag}.png"
    viz.plot_field(field, lat, lon,
                   title=f"Subsurface temperature at 100 m - {str(res['time'][0])[:10]}",
                   cbar_label="Temperature (deg C)", fname=fname)

    print(f"\nT@100m  min={np.nanmin(field):.2f}  max={np.nanmax(field):.2f} "
          f"mean={np.nanmean(field):.2f} deg C")
    print(f"valid ocean cells: {np.isfinite(field).sum()} / {field.size}")
    print("\n=== Day 1 complete ===\n")
    return res


if __name__ == "__main__":
    s = sys.argv[1] if len(sys.argv) > 1 else "2020-01-01"
    e = sys.argv[2] if len(sys.argv) > 2 else "2020-01-03"
    main(s, e)

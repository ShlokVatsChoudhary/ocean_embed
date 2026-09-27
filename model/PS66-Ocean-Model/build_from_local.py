"""Build X/Y training arrays from manually-downloaded NetCDFs.

Use this INSTEAD of `run_ingest.py` when the raw files were fetched by hand
(e.g. through the Copernicus web GUI) into a folder outside `data/raw`.

It locates the four files by glob pattern, then calls the normal
`harmonize.build_arrays` so the output is identical to the downloader path.

Usage
-----
    py -3.12 build_from_local.py --dir "C:/Users/shash/OneDrive/Desktop/model" --tag 2020
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src import config, harmonize  # noqa: E402

# glob patterns (case-insensitive substrings are matched manually below)
PATTERNS = {
    "target": ("cmems_mod_glo_phy-all_my_0.25deg", "thetao_glor"),
    "duacs":  ("duacs",),
    "ostia":  ("metoffice-glo-sst",),
    "sss":    ("sss_my_multi",),
}


def find_one(root: Path, needles: tuple[str, ...]) -> Path:
    hits = []
    for p in root.rglob("*.nc"):
        low = p.name.lower()
        if all(n.lower() in low for n in needles):
            hits.append(p)
    if not hits:
        raise FileNotFoundError(f"no .nc under {root} matching {needles}")
    # if several match (e.g. per-month files), pick the largest = most complete
    hits.sort(key=lambda p: p.stat().st_size, reverse=True)
    if len(hits) > 1:
        print(f"  [warn] {len(hits)} candidates for {needles}; using largest")
    return hits[0]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True,
                    help="folder holding the downloaded .nc files (searched recursively)")
    ap.add_argument("--tag", default="2020", help="output array tag")
    args = ap.parse_args()

    root = Path(args.dir)
    if not root.exists():
        raise SystemExit(f"not found: {root}")

    print(f"scanning {root} ...")
    paths = {}
    for key, needles in PATTERNS.items():
        p = find_one(root, needles)
        paths[key] = p
        print(f"  {key:7s}: {p.name}  ({p.stat().st_size/1e6:.0f} MB)")

    print(f"\nbuilding arrays (tag={args.tag}) ...")
    out = harmonize.build_arrays(
        paths["target"], paths["duacs"], paths["ostia"],
        sss_path=paths["sss"], tag=args.tag,
    )

    X, Y = out["X"], out["Y"]
    print("\n=== done ===")
    print(f"  X {X.shape}   Y {Y.shape}")
    print(f"  channels: {out['channels']}")
    print(f"  depths  : {out['depths']}")
    print(f"  days    : {len(out['time'])}  "
          f"{str(out['time'][0])[:10]} -> {str(out['time'][-1])[:10]}")
    ocean0 = np.isfinite(Y[:, 0]).mean() * 100
    oceanD = np.isfinite(Y[:, -1]).mean() * 100
    print(f"  valid ocean: {ocean0:.1f}% @0m  ->  {oceanD:.1f}% @1000m")
    print(f"\n  files written under {config.DATA_PROC}")
    print(f"  next:  py -3.12 run_day3.py {args.tag} 120")


if __name__ == "__main__":
    main()

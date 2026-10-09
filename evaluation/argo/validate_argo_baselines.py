"""Independent ARGO validation with baselines, scored on one common mask.

Every method is scored against the SAME ARGO observations on the SAME cells, so the
comparison between methods is apples-to-apples. ARGO is never used for training.

Baselines:
    persistence  - the previous day's GLORYS field (assume the ocean has not changed)
    climatology  - the 7-day GLORYS mean (assume the ocean is always average)
"""
from __future__ import annotations

import sys
import argparse
import os
from datetime import date, timedelta
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL_DIR = REPO_ROOT / "model" / "PS66-Ocean-Model"
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.core.constants import STANDARD_DEPTHS  # noqa: E402
from app.data.argo import ArgoDataAccessor  # noqa: E402
from app.model.adapter import OceanEmbedModelAdapter  # noqa: E402

DATES = [date(2020, 1, 1) + timedelta(days=i) for i in range(7)]
GE50 = 50.0
THERMO = (50.0, 200.0)


def rmse(pred, obs):
    d = pred - obs
    return float(np.sqrt(np.mean(d * d)))


def band_slice(lo, hi):
    idx = [i for i, d in enumerate(STANDARD_DEPTHS) if lo <= d <= hi]
    return idx


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model-dir",
        type=Path,
        default=Path(os.environ.get("OCEANEMBED_MODEL_ROOT", DEFAULT_MODEL_DIR)),
        help="model package directory (default: OCEANEMBED_MODEL_ROOT or repository model package)",
    )
    model_dir = parser.parse_args().model_dir.expanduser().resolve()
    required = (
        model_dir / "samples" / "X_2020.npy",
        model_dir / "samples" / "Y_2020.npy",
        model_dir / "samples" / "stats_2020.npz",
    )
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            "Required bundled validation sample(s) are missing: "
            + ", ".join(missing)
            + ". Use --model-dir or OCEANEMBED_MODEL_ROOT to select a model package."
        )

    X = np.load(model_dir / "samples/X_2020.npy")
    Y = np.load(model_dir / "samples/Y_2020.npy")
    stats = np.load(model_dir / "samples/stats_2020.npz")
    y_mean, y_std = float(stats["y_mean"]), float(stats["y_std"])

    # NOTE: samples/Y_2020.npy is already in degC (6.0-31.4 range). The stats file's y_mean/y_std
    # belong to the normalisation used internally during training, so applying them here would
    # add a spurious ~156 degC. Verified from the data range, not assumed.
    truth = Y.astype(np.float64)
    clim = np.nanmean(truth, axis=0)  # 7-day mean field

    model = OceanEmbedModelAdapter(model_root=model_dir)
    argo = ArgoDataAccessor()

    depth_ge50 = band_slice(GE50, STANDARD_DEPTHS[-1])
    depth_therm = band_slice(*THERMO)

    methods = ("model", "persistence", "climatology")
    acc: dict[str, dict[str, list]] = {
        m: {"all": [], "ge50": [], "therm": [], "per_depth": [], "n": 0} for m in methods
    }
    # Per-depth accumulators
    for m in methods:
        acc[m]["pd_se"] = [[] for _ in STANDARD_DEPTHS]
        acc[m]["pd_bias"] = [[] for _ in STANDARD_DEPTHS]
        acc[m]["pd_num"] = [[] for _ in STANDARD_DEPTHS]

    # Persistence needs a previous day, so every method is scored on days 1..6 only. That keeps
    # the sample identical across methods instead of flattering whichever one sees more cells.
    for i, d in enumerate(DATES):
        if i == 0:
            continue
        obs = argo.temperature_field(d)
        pred = model.temperature_field_array(d)
        if obs is None or pred is None:
            print(f"  {d} missing (obs={obs is None}, pred={pred is None})")
            continue

        fields = {"model": pred, "persistence": truth[i - 1], "climatology": clim}

        # One shared mask for all three methods plus ARGO.
        mask = np.isfinite(obs)
        for field in fields.values():
            mask &= np.isfinite(field)
        if not mask.any():
            continue

        for name, field in fields.items():
            diff = np.where(mask, field - obs, np.nan)
            vals = diff[np.isfinite(diff)]
            acc[name]["all"].append(vals)
            acc[name]["n"] += int(vals.size)
            for lo, hi, key in ((GE50, STANDARD_DEPTHS[-1], "ge50"), (THERMO[0], THERMO[1], "therm")):
                idx = band_slice(lo, hi)
                seg = diff[idx]
                seg = seg[np.isfinite(seg)]
                if seg.size:
                    acc[name][key].append(seg)
            for k in range(len(STANDARD_DEPTHS)):
                row = diff[k]
                row = row[np.isfinite(row)]
                if row.size:
                    acc[name]["pd_se"][k].append(row)
                    acc[name]["pd_bias"][k].append(row)
                    acc[name]["pd_num"][k].append(int(row.size))
        print(f"  {d}  scored on {int(mask.sum()):,} shared cells")

    def cat(v):
        return np.concatenate(v) if v else np.array([])

    print("\n" + "=" * 78)
    print("INDEPENDENT ARGO VALIDATION - all methods on the same common mask")
    print("=" * 78)
    print(f"{'method':<14}{'RMSE all':>10}{'RMSE>=50m':>12}{'RMSE therm':>12}{'MAE':>8}{'bias':>8}{'n':>12}")
    print("-" * 78)
    summary = {}
    for name in methods:
        a = cat(acc[name]["all"])
        if a.size == 0:
            print(f"{name:<14}{'n/a':>10}")
            continue
        g = cat(acc[name]["ge50"])
        t = cat(acc[name]["therm"])
        summary[name] = {
            "all": float(np.sqrt(np.mean(a * a))),
            "ge50": float(np.sqrt(np.mean(g * g))) if g.size else float("nan"),
            "therm": float(np.sqrt(np.mean(t * t))) if t.size else float("nan"),
            "mae": float(np.mean(np.abs(a))),
            "bias": float(np.mean(a)),
        }
        print(
            f"{name:<14}{summary[name]['all']:>10.3f}{summary[name]['ge50']:>12.3f}"
            f"{summary[name]['therm']:>12.3f}{summary[name]['mae']:>8.3f}"
            f"{summary[name]['bias']:>8.3f}{acc[name]['n']:>12,}"
        )

    print("\nPer-depth RMSE (degC)")
    print(f"{'depth':>7}" + "".join(f"{m:>14}" for m in methods))
    print("-" * (7 + 14 * len(methods)))
    for k, dep in enumerate(STANDARD_DEPTHS):
        row = f"{dep:>7.0f}"
        for name in methods:
            seg = cat(acc[name]["pd_se"][k])
            row += f"{float(np.sqrt(np.mean(seg*seg))):>14.3f}" if seg.size else f"{'n/a':>14}"
        print(row)

    print("\nPer-depth bias (degC)")
    print(f"{'depth':>7}" + "".join(f"{m:>14}" for m in methods))
    print("-" * (7 + 14 * len(methods)))
    for k, dep in enumerate(STANDARD_DEPTHS):
        row = f"{dep:>7.0f}"
        for name in methods:
            seg = cat(acc[name]["pd_bias"][k])
            row += f"{float(np.mean(seg)):>14.3f}" if seg.size else f"{'n/a':>14}"
        print(row)


if __name__ == "__main__":
    main()

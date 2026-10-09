"""Shared path and asset checks for the full-year holdout utilities."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL_DIR = REPO_ROOT / "model" / "PS66-Ocean-Model"


def configure_model_root(*, require_argo: bool = False) -> Path:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model-dir",
        type=Path,
        default=Path(os.environ.get("OCEANEMBED_MODEL_ROOT", DEFAULT_MODEL_DIR)),
        help="model package directory (default: OCEANEMBED_MODEL_ROOT or repository model package)",
    )
    model_dir = parser.parse_args().model_dir.expanduser().resolve()

    required = [
        model_dir / "src" / "data.py",
        model_dir / "data" / "processed" / "X_2020_9ch.npy",
        model_dir / "data" / "processed" / "Y_2020_9ch.npy",
        model_dir / "data" / "processed" / "stats_2020_9ch.npz",
        model_dir / "weights" / "model_2020.weights.h5",
    ]
    if require_argo:
        required.append(model_dir / "data" / "raw" / "argo_2020.nc")

    missing = [path for path in required if not path.is_file()]
    if missing:
        paths = "\n".join(f"  - {path}" for path in missing)
        raise SystemExit(
            "Required full-year holdout assets are missing:\n"
            f"{paths}\n"
            "These evaluation scripts require the 2020_9ch processed arrays, model weights"
            + (" and data/raw/argo_2020.nc." if require_argo else ".")
            + " Supply a complete model package with --model-dir or OCEANEMBED_MODEL_ROOT."
        )

    sys.path.insert(0, str(model_dir))
    os.chdir(model_dir)
    return model_dir

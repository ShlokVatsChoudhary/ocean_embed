"""Self-contained configuration for the OceanEmbed model package.

This file intentionally has **no** dependency on the training repository
(no download code, no dataset IDs). It only declares the domain, the grid, the
standard depths, the input channels, and where the shipped artifacts live.
"""
from __future__ import annotations

from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent

# --------------------------------------------------------------------------
# Domain: North Indian Ocean
# --------------------------------------------------------------------------
LON_MIN, LON_MAX = 45.0, 105.0
LAT_MIN, LAT_MAX = 5.0, 30.0
RES = 0.25  # degrees

NX = round((LON_MAX - LON_MIN) / RES) + 1   # 241 longitude points
NY = round((LAT_MAX - LAT_MIN) / RES) + 1   # 101 latitude points

LON = [round(LON_MIN + RES * i, 4) for i in range(NX)]
LAT = [round(LAT_MIN + RES * i, 4) for i in range(NY)]

# Standard depth levels (metres), in order. The model emits one level per entry.
DEPTHS = [0, 5, 10, 20, 30, 50, 75, 100, 125, 150, 200, 300, 500, 700, 1000]

# Input surface channels, in the exact order the model was trained on.
INPUT_CHANNELS = ["sst", "sss", "sla", "ugos", "vgos"]

# Model hyper-parameters (must match the trained artifact).
LATENT_DIM = 256
WIDTHS = (24, 48, 96, 192)

# --------------------------------------------------------------------------
# Shipped artifacts
# --------------------------------------------------------------------------
WEIGHTS = PACKAGE_ROOT / "weights" / "oceanembed_v1.weights.h5"
STATS = PACKAGE_ROOT / "weights" / "stats_2020Q1.npz"
CACHE = PACKAGE_ROOT / "input_cache" / "X_2020Q1.npz"

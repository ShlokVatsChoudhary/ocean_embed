"""Render a visual schematic of the PS66 model (encoder -> latent -> decoder).

Usage:  python show_model.py [tag]
Output: figures/model_architecture.png
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src import config, data, model as M

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch


def box(ax, x, y, w, h, text, color, fs=9, tc="black"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02",
                                linewidth=1.2, edgecolor="#333", facecolor=color))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
            fontsize=fs, color=tc, wrap=True)


def arrow(ax, p0, p1, color="#444", style="-|>", lw=1.6):
    ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle=style, mutation_scale=14,
                                 color=color, lw=lw,
                                 connectionstyle="arc3,rad=0"))


def main(tag="2020-01-01_2020-03-31"):
    X, Y, stats, ch = data.load_arrays(tag)

    import tensorflow as tf
    m = M.OceanModel(cin=X.shape[1], D=256, Z=Y.shape[1])
    _ = m(tf.zeros([1, X.shape[1], X.shape[2], X.shape[3]]))
    enc_p, dec_p = m.enc.count_params(), m.dec.count_params()

    fig, ax = plt.subplots(figsize=(16, 9))
    ax.set_xlim(0, 16); ax.set_ylim(0, 9); ax.axis("off")

    # ---------------- title ----------------
    ax.text(8, 8.6, "PS66 · Satellite-Embedding Subsurface Temperature Model",
            ha="center", fontsize=17, fontweight="bold")
    ax.text(8, 8.2, f"Encoder-Decoder CNN  ·  {m.count_params():,} params  "
                    f"(enc {enc_p:,} + dec {dec_p:,})  ·  TensorFlow",
            ha="center", fontsize=11, color="#555")

    # ---------------- input ----------------
    box(ax, 0.2, 5.4, 2.0, 1.5,
        "SURFACE INPUT\n\n(4, 101, 241)\n\nsst\nsla\nugos\nvgos",
        "#dbeafe", fs=9)

    # ---------------- ENCODER ----------------
    ax.text(5.2, 7.55, "ENCODER  (embedding engine)", fontsize=12,
            fontweight="bold", color="#1e3a8a", ha="center")
    enc_steps = [
        (2.6, 6.4, "stem\nConvBlock(24)\n101×241 · 24ch"),
        (4.3, 6.4, "down1\nConv48\n50×120"),
        (6.0, 6.4, "down2\nConv96\n25×60"),
        (7.7, 6.4, "down3\nConv192\n12×30"),
    ]
    for x, y, t in enc_steps:
        box(ax, x, y, 1.5, 1.0, t, "#bfdbfe", fs=8)
    for i in range(len(enc_steps) - 1):
        arrow(ax, (enc_steps[i][0] + 1.5, 6.9),
                  (enc_steps[i + 1][0], 6.9))
    arrow(ax, (2.2, 6.15), (2.6, 6.9))

    # latent z
    box(ax, 9.6, 6.2, 1.9, 1.4,
        "ATTENTION POOL\n+ Dense(256)\n\nLATENT  z\n(256,)",
        "#fde68a", fs=8)
    arrow(ax, (9.2, 6.9), (9.6, 6.9))

    # ---------------- DECODER ----------------
    ax.text(12.4, 5.65, "DECODER", fontsize=12, fontweight="bold",
            color="#7c2d12", ha="center")
    dec_steps = [
        (9.6, 4.4, "up1  ConvT→96\n+skip +z\nConv96"),
        (11.4, 4.4, "up2  ConvT→48\n+skip +z\nConv48"),
        (13.2, 4.4, "up3  ConvT→24\n+skip +z\nConv24"),
    ]
    for x, y, t in dec_steps:
        box(ax, x, y, 1.6, 1.0, t, "#fecaca", fs=8)
    arrow(ax, (10.55, 6.2), (10.4, 5.4))
    for i in range(len(dec_steps) - 1):
        arrow(ax, (dec_steps[i][0] + 1.6, 4.9),
                  (dec_steps[i + 1][0], 4.9))

    # head + output
    box(ax, 13.2, 3.0, 1.6, 1.0, "head\nConv2D(15,1×1)", "#fca5a5", fs=8)
    arrow(ax, (14.0, 4.4), (14.0, 4.0))
    box(ax, 12.7, 1.4, 2.6, 1.2,
        "OUTPUT\n(15, 101, 241)\n15 depths · 0–1000 m", "#dcfce7", fs=9)
    arrow(ax, (14.0, 3.0), (14.0, 2.6))

    # skip connections
    for (sx, dx, lbl) in [(2.6, 9.6, "skip"), (4.3, 11.4, "skip"),
                          (6.0, 13.2, "skip")]:
        ax.add_patch(FancyArrowPatch((sx + 0.75, 6.4), (dx + 0.8, 5.4),
                                     arrowstyle="-", color="#9ca3af",
                                     lw=1.1, linestyle="--",
                                     connectionstyle="arc3,rad=-0.25"))

    # z broadcast
    ax.add_patch(FancyArrowPatch((11.5, 6.2), (15.2, 5.0),
                                 arrowstyle="-", color="#f59e0b", lw=1.6,
                                 linestyle=":", connectionstyle="arc3,rad=0.2"))
    ax.text(14.6, 5.9, "z broadcast\nto every pixel", fontsize=7.5,
            color="#b45309", ha="center")

    # ---------------- loss ----------------
    box(ax, 0.4, 2.0, 4.6, 1.6,
        "LOSS  (training)\n\nmasked · depth-weighted MSE\n"
        "land ignored · deep levels weighted 1.0→2.5",
        "#e9d5ff", fs=9)
    arrow(ax, (12.7, 2.0), (5.0, 2.6), color="#7c3aed", lw=1.4)
    ax.text(8.6, 1.75, "prediction", fontsize=8, color="#7c3aed",
            rotation=6)

    box(ax, 0.4, 0.3, 4.6, 1.2,
        "TARGET (truth): GLORYS thetao_glor\n(15, 101, 241)  ·  15 depths",
        "#e5e7eb", fs=9)
    arrow(ax, (5.0, 1.0), (5.0, 2.0), color="#374151")

    fig.tight_layout()
    f = config.FIGURES / "model_architecture.png"
    fig.savefig(f, dpi=140, bbox_inches="tight")
    print(f"[fig] {f}")
    return f


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "2020-01-01_2020-03-31")

"""Generate a presentation-quality (16:9) architecture + pipeline figure for SIH.

Output: figures/ppt_pipeline_architecture.png
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle

# ---------------------------------------------------------------- palette ---
INK   = "#0f172a"
MUTED = "#64748b"
BG    = "#ffffff"
PANEL = "#f1f5f9"
DATA_C = "#0ea5e9"
PREP_C = "#8b5cf6"
ENC_C  = "#2563eb"
LAT_C  = "#f59e0b"
DEC_C  = "#ef4444"
OUT_C  = "#10b981"
VAL_C  = "#475569"
GOLD   = "#eab308"


def rr(ax, x, y, w, h, *, fc, ec="none", lw=1.2, r=1.6, z=1, alpha=1.0):
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r}",
        linewidth=lw, edgecolor=ec, facecolor=fc, zorder=z, alpha=alpha))


def shadow(ax, x, y, w, h, r=1.6):
    ax.add_patch(FancyBboxPatch(
        (x + 0.4, y - 0.5), w, h,
        boxstyle=f"round,pad=0,rounding_size={r}",
        linewidth=0, facecolor="#0f172a", alpha=0.10, zorder=0))


def card(ax, x, y, w, h, *, fc, ec="white", title=None, lines=(), tc="white",
         tfs=9.0, lfs=6.8, r=1.3, accent=None, z=2):
    shadow(ax, x, y, w, h, r)
    rr(ax, x, y, w, h, fc=fc, ec=ec, lw=1.4, r=r, z=z)
    if accent:
        ax.add_patch(Rectangle((x, y + h - 0.8), w, 0.8, facecolor=accent,
                               zorder=z + 1, alpha=0.9))
    if title:
        ax.text(x + w / 2, y + h - 2.6, title, ha="center", va="center",
                fontsize=tfs, fontweight="bold", color=tc, zorder=z + 1)
    yy = y + h - 5.1
    for ln in lines:
        ax.text(x + w / 2, yy, ln, ha="center", va="center",
                fontsize=lfs, color=tc, zorder=z + 1)
        yy -= 2.05


def arrow(ax, p0, p1, *, color=MUTED, lw=2.6, rad=0.0, z=3, head=16):
    ax.add_patch(FancyArrowPatch(
        p0, p1, arrowstyle="-|>", mutation_scale=head, color=color, lw=lw,
        connectionstyle=f"arc3,rad={rad}", zorder=z,
        capstyle="round", joinstyle="round"))


def main():
    fig = plt.figure(figsize=(16, 9), dpi=200)
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 160); ax.set_ylim(0, 90)
    ax.axis("off"); fig.patch.set_facecolor(BG)

    # ================= HEADER =================
    ax.add_patch(Rectangle((0, 82), 160, 8, facecolor="#0b1220", zorder=1))
    ax.add_patch(Rectangle((0, 82), 160, 1.0, facecolor=GOLD, zorder=2))
    ax.text(3.5, 86.8,
            "PS66  ·  Satellite-Embedding Reconstruction of Subsurface Ocean Temperature",
            ha="left", va="center", fontsize=16, fontweight="bold", color="white")
    ax.text(3.5, 83.8,
            "North Indian Ocean  ·  5–30°N, 45–105°E  ·  0.25° daily  ·  15 depths (0–1000 m)  ·  TensorFlow",
            ha="left", va="center", fontsize=9.3, color="#93a3b8")

    # ================= 1 INPUTS =================
    ax.text(18, 77.6, "1 · SATELLITE OBSERVATIONS", ha="center", va="center",
            fontsize=9.3, fontweight="bold", color=DATA_C)
    inputs = [
        ("SST",        "OSTIA  ·  0.05°  ·  daily",        "#0ea5e9"),
        ("SSS",        "SMAP + SMOS  ·  0.125°  ·  daily", "#0891b2"),
        ("SSH / SLA",  "DUACS L4  ·  0.25°  ·  daily",     "#06b6d4"),
        ("CURRENTS",   "UGOS / VGOS  ·  0.25°  ·  daily",  "#22b8cf"),
        ("WINDS",      "CCMP v3.1  ·  planned",          "#38bdf8"),
    ]
    y = 69.0
    for name, sub, col in inputs:
        card(ax, 3, y, 30, 6.5, fc=col, title=name, lines=[sub],
             tfs=8.8, lfs=6.9, r=1.2)
        y -= 7.8
    arrow(ax, (33.6, 55), (39.6, 55), color=DATA_C, lw=3.0)

    # ================= 2 PREPROCESSING =================
    ax.text(51.5, 77.6, "2 · PREPROCESSING", ha="center", va="center",
            fontsize=9.3, fontweight="bold", color=PREP_C)
    card(ax, 40, 38.0, 23, 38.0, fc=PREP_C, title="HARMONISATION",
         tfs=10.0, lfs=6.9)
    steps = ["Regrid → 0.25° grid", "Align on common days",
             "Land / ocean mask", "Bathymetry mask",
             "(drop depths below seabed)", "Z-score normalisation",
             "Masked · depth-weighted target"]
    yy = 69.0
    for s in steps:
        c = "white" if not s.startswith("(") else "#ede9fe"
        ax.text(51.5, yy, s, ha="center", va="center", fontsize=7.1, color=c)
        yy -= 4.1
    arrow(ax, (63.6, 55), (68.6, 55), color=PREP_C, lw=3.0)

    # ================= 3 MODEL =================
    ax.add_patch(FancyBboxPatch((67.5, 12.0), 71.5, 68.0,
                 boxstyle="round,pad=0,rounding_size=2.2",
                 facecolor=PANEL, edgecolor="#cbd5e1", lw=1.5, zorder=1))
    ax.text(103.2, 76.8, "3 · ENCODER–DECODER CNN  ·  embedding engine",
            ha="center", va="center", fontsize=10.4, fontweight="bold", color=INK)
    ax.text(103.2, 73.2,
            "input (5, 101, 241)  →  latent z (256)  →  output (15, 101, 241)",
            ha="center", va="center", fontsize=7.9, color=MUTED)

    # --- encoder row ---
    ax.text(91.7, 69.2, "ENCODER", ha="center", fontsize=8.6,
            fontweight="bold", color=ENC_C)
    enc = [("stem\n24ch", "101×241"), ("down1\n48ch", "50×120"),
           ("down2\n96ch", "25×60"), ("down3\n192ch", "12×30")]
    for i, (nm, sp) in enumerate(enc):
        col = ENC_C if i % 2 == 0 else "#3b82f6"
        card(ax, 69.5 + 11.4 * i, 55.0, 10.2, 12.0, fc=col, title=nm,
             lines=[sp, "ConvBlock"], tfs=8.0, lfs=6.7, accent="#93c5fd")
    for i in range(3):
        arrow(ax, (79.7 + 11.4 * i, 61.0), (80.9 + 11.4 * i, 61.0),
              color=ENC_C, lw=2.2, head=12)

    # --- latent ---
    card(ax, 117.6, 53.0, 12.9, 14.5, fc=LAT_C, title="ATTENTION POOL",
         lines=["+ Dense(256)", "", "LATENT  z (256)"], tfs=7.9, lfs=7.6,
         accent="#fde68a")
    ax.add_patch(FancyArrowPatch((114.9, 61.0), (117.4, 60.0),
                 arrowstyle="-|>", mutation_scale=14, color=LAT_C, lw=2.6,
                 connectionstyle="arc3,rad=-0.25", zorder=3))
    ax.text(124.0, 50.6, "global embedding", ha="center", fontsize=6.7,
            color="#b45309")

    # --- decoder row ---
    ax.text(91.7, 45.6, "DECODER", ha="center", fontsize=8.6,
            fontweight="bold", color=DEC_C)
    ax.text(124.5, 45.6, "z broadcast to every pixel", ha="center",
            fontsize=6.7, color="#b45309")
    dec = [("up1\n96ch", "12×30"), ("up2\n48ch", "25×60"),
           ("up3\n24ch", "50×120"), ("head\n15ch", "101×241")]
    for i, (nm, sp) in enumerate(dec):
        col = DEC_C if i % 2 == 0 else "#f87171"
        card(ax, 69.5 + 11.4 * i, 31.0, 10.2, 12.0, fc=col, title=nm,
             lines=[sp, "ConvT+skip+z"], tfs=8.0, lfs=6.3, accent="#fecaca")
    for i in range(3):
        arrow(ax, (79.7 + 11.4 * i, 37.0), (80.9 + 11.4 * i, 37.0),
              color=DEC_C, lw=2.2, head=12)
    # z -> decoder
    ax.add_patch(FancyArrowPatch((117.6, 53.5), (106.5, 43.0),
                 arrowstyle="-", color=LAT_C, lw=1.5, linestyle=(0, (2, 2)),
                 connectionstyle="arc3,rad=0.22", zorder=3))

    # ================= 4 OUTPUT =================
    ax.text(151.2, 77.6, "4 · OUTPUT", ha="center", fontsize=9.3,
            fontweight="bold", color=OUT_C)
    arrow(ax, (139.5, 46), (144.5, 52), color=OUT_C, lw=3.0, rad=0.15)
    card(ax, 143.5, 51.5, 15.5, 22.5, fc=OUT_C, title="3-D TEMPERATURE",
         lines=["(15, 101, 241)", "", "0 · 5 · 10 · 20 · 30",
                "50 · 75 · 100 · 125 · 150",
                "200 · 300 · 500 · 700 · 1000",
                "", "full profile", "at every ocean pixel"],
         tfs=8.8, lfs=6.5, accent="#6ee7b7")

    # ================= VALIDATION =================
    card(ax, 143.5, 26.0, 15.5, 22.5, fc=VAL_C, title="VALIDATION",
         lines=["Independent ARGO", "(INCOIS T_ANALYZED)", "",
                "baselines:", "· persistence", "· climatology",
                "· SST→T MLP"],
         tfs=8.8, lfs=6.5, accent="#94a3b8")

    # ================= METRICS BAND =================
    ax.add_patch(FancyBboxPatch((3, 3.5), 156, 15.5,
                 boxstyle="round,pad=0,rounding_size=1.8",
                 facecolor="#0b1220", edgecolor="none", zorder=1))
    ax.add_patch(Rectangle((3, 3.5), 1.0, 15.5, facecolor=GOLD, zorder=2))
    ax.text(7.0, 15.4, "RESULTS   Jan–Mar 2020 · thermocline (50–200 m) RMSE vs naive baselines",
            ha="left", va="center", fontsize=9.0, fontweight="bold", color=GOLD)

    metrics = [("0.73 °C", "Model RMSE",        OUT_C),
               ("0.96",    "Correlation",       OUT_C),
               ("0.82 °C", "SST→T MLP RMSE",    "#94a3b8"),
               ("1.08 °C", "Climatology RMSE",  "#94a3b8"),
               ("1.64 M",  "Parameters",        LAT_C),
               ("15",      "Depth levels",      ENC_C)]
    x = 15
    for val, lab, col in metrics:
        ax.text(x, 10.6, val, ha="center", va="center", fontsize=15,
                fontweight="bold", color=col)
        ax.text(x, 6.7, lab, ha="center", va="center", fontsize=6.9,
                color="#cbd5e1")
        x += 23.5
    ax.text(7.0, 4.6,
            "caveat: persistence is stronger below 30 m in this single-season test "
            "(thermocline 0.62 °C) — the model is best at the surface. See STATUS.md §10.",
            ha="left", va="center", fontsize=6.2, color="#94a3b8")

    out = Path(__file__).resolve().parent / "figures" / "ppt_pipeline_architecture.png"
    fig.savefig(out, dpi=200, facecolor=BG, bbox_inches="tight", pad_inches=0.12)
    print("saved", out)
    return out


if __name__ == "__main__":
    main()

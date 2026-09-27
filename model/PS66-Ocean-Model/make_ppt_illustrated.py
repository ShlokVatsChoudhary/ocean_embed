"""Illustrated, presentation-grade PS66 pipeline figure (16:9) for SIH.

Draws recognisable icons (satellites, ocean cross-section, ARGO floats) so the
story reads at a glance:  see the surface -> learn the link -> rebuild the deep.

Output: figures/ppt_pipeline_illustrated.png
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import (FancyBboxPatch, FancyArrowPatch, Rectangle,
                                Circle, Wedge, Polygon)
from matplotlib.colors import LinearSegmentedColormap

INK = "#0f172a"
MUTED = "#64748b"
BG = "#ffffff"
PANEL = "#f8fafc"
GOLD = "#eab308"
DATA_C = "#0284c7"
ENC_C = "#2563eb"
LAT_C = "#f59e0b"
DEC_C = "#ef4444"
OUT_C = "#059669"
VAL_C = "#475569"

OCEAN = LinearSegmentedColormap.from_list(
    "ocean", ["#07203f", "#123f7a", "#2f6fc4", "#7fb3e8", "#fde68a",
              "#f59e0b", "#dc2626"])
CMAP_G = LinearSegmentedColormap.from_list(
    "gfs", ["#082f49", "#0ea5e9", "#7dd3fc", "#e0f2fe"])


# ------------------------------------------------------------------ helpers -
def rr(ax, x, y, w, h, *, fc, ec="none", lw=1.2, r=1.4, z=2, alpha=1.0):
    ax.add_patch(FancyBboxPatch((x, y), w, h,
                 boxstyle=f"round,pad=0,rounding_size={r}", linewidth=lw,
                 edgecolor=ec, facecolor=fc, zorder=z, alpha=alpha))


def shadow(ax, x, y, w, h, r=1.4, a=0.10):
    ax.add_patch(FancyBboxPatch((x + 0.35, y - 0.45), w, h,
                 boxstyle=f"round,pad=0,rounding_size={r}", linewidth=0,
                 facecolor="#0f172a", alpha=a, zorder=0))


def arrow(ax, p0, p1, *, color=MUTED, lw=2.4, rad=0.0, z=4, head=15, ls="-"):
    ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle="-|>", mutation_scale=head,
                 color=color, lw=lw, connectionstyle=f"arc3,rad={rad}",
                 zorder=z, linestyle=ls, capstyle="round"))


def satellite(ax, cx, cy, s=1.0, body="#334155", panel="#1d4ed8", z=6):
    """Small drawn satellite: body + two solar panels + dish."""
    # solar panels + arms
    for sign in (-1, 1):
        px0 = cx + sign * 1.75 * s - (1.15 * s if sign < 0 else 0)
        ax.add_patch(Rectangle((px0, cy - 0.5 * s), 2.3 * s, 1.0 * s,
                     fc=panel, ec="white", lw=0.6, zorder=z))
        for k in (1, 2):
            ax.plot([px0 + 2.3 * s * k / 3.0] * 2,
                    [cy - 0.5 * s, cy + 0.5 * s], color="white", lw=0.5,
                    zorder=z + 1)
        ax.plot([cx + sign * 0.6 * s, px0 + (2.3 * s if sign < 0 else 0)],
                [cy, cy], color="#94a3b8", lw=1.3, zorder=z)
    # body
    ax.add_patch(FancyBboxPatch((cx - 0.62 * s, cy - 0.62 * s), 1.24 * s,
                 1.24 * s, boxstyle=f"round,pad=0,rounding_size={0.15*s:.3f}",
                 fc=body, ec="white", lw=0.8, zorder=z + 2))
    # dish
    ax.add_patch(Wedge((cx, cy + 0.55 * s), 0.62 * s, 0, 180, fc="white",
                 ec="#94a3b8", lw=0.7, zorder=z + 3))
    ax.add_patch(Circle((cx, cy + 0.95 * s), 0.15 * s, fc=LAT_C, ec="none",
                 zorder=z + 4))


def argo(ax, cx, cy, s=1.0, z=7):
    """Small drawn ARGO float."""
    ax.add_patch(FancyBboxPatch((cx - 0.32 * s, cy - 1.1 * s), 0.64 * s,
                 2.2 * s, boxstyle=f"round,pad=0,rounding_size={0.28*s:.3f}",
                 fc="#0f766e", ec="white", lw=0.7, zorder=z))
    ax.plot([cx, cx], [cy + 1.1 * s, cy + 1.8 * s], color="#334155", lw=0.9,
            zorder=z)
    ax.add_patch(Circle((cx, cy + 1.9 * s), 0.17 * s, fc=LAT_C, ec="none",
                 zorder=z + 1))
    ax.add_patch(Rectangle((cx - 0.55 * s, cy - 1.3 * s), 1.1 * s, 0.22 * s,
                 fc="#0f766e", ec="white", lw=0.5, zorder=z))


def funnel_block(ax, cx, cy, w, h, color, label, sub, fs=7.0):
    ax.add_patch(FancyBboxPatch((cx - w / 2, cy - h / 2), w, h,
                 boxstyle="round,pad=0,rounding_size=0.7",
                 fc=color, ec="white", lw=1.0, zorder=6))
    ax.text(cx, cy + h * 0.16, label, ha="center", va="center", fontsize=fs,
            fontweight="bold", color="white", zorder=7)
    ax.text(cx, cy - h * 0.24, sub, ha="center", va="center", fontsize=fs - 1.4,
            color="white", zorder=7)


# --------------------------------------------------------------------- main -
def main():
    fig = plt.figure(figsize=(16, 9), dpi=200)
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 160); ax.set_ylim(0, 90)
    ax.axis("off"); fig.patch.set_facecolor(BG)

    # ============================ HEADER ============================
    ax.add_patch(Rectangle((0, 82), 160, 8, facecolor="#0b1220", zorder=1))
    ax.add_patch(Rectangle((0, 82), 160, 1.0, facecolor=GOLD, zorder=2))
    ax.text(3.5, 86.9,
            "PS66  ·  Seeing Below the Surface:  Satellite Embeddings Reconstruct "
            "3-D Ocean Temperature",
            ha="left", va="center", fontsize=15.5, fontweight="bold",
            color="white")
    ax.text(3.5, 83.7,
            "North Indian Ocean  ·  5–30°N, 45–105°E  ·  0.25° daily  ·  15 depths "
            "(0–1000 m)  ·  TensorFlow encoder–decoder",
            ha="left", va="center", fontsize=9.2, color="#93a3b8")

    # ================================================================
    # PANEL 1 — satellites (what we SEE)
    # ================================================================
    ax.add_patch(FancyBboxPatch((2, 20), 37.5, 59,
                 boxstyle="round,pad=0,rounding_size=1.8", facecolor=PANEL,
                 edgecolor="#e2e8f0", lw=1.2, zorder=1))
    ax.text(20.7, 76.4, "1 ·  OBSERVE FROM SPACE", ha="center", fontsize=9.8,
            fontweight="bold", color=DATA_C)
    ax.text(20.7, 73.6, "only the surface is visible", ha="center",
            fontsize=7.2, color=MUTED, style="italic")

    sats = [
        ("SST", "OSTIA · 0.05° daily", "#0ea5e9"),
        ("SSS", "SMAP + SMOS · 0.125°", "#0891b2"),
        ("SSH", "DUACS L4 · 0.25°", "#06b6d4"),
        ("CURRENTS", "UGOS / VGOS · 0.25°", "#22b8cf"),
        ("WINDS", "CCMP v3.1 · planned", "#38bdf8"),
    ]
    y = 62.0
    for name, sub, col in sats:
        shadow(ax, 4, y, 33.5, 9.0, 1.3)
        rr(ax, 4, y, 33.5, 9.0, fc="white", ec="#e2e8f0", lw=1.1, z=3)
        ax.add_patch(Rectangle((4, y), 1.0, 9.0, facecolor=col, zorder=4))
        satellite(ax, 9.6, y + 4.5, s=1.05)
        ax.text(15.6, y + 5.9, name, ha="left", va="center", fontsize=9.2,
                fontweight="bold", color=INK, zorder=5)
        ax.text(15.6, y + 3.3, sub, ha="left", va="center", fontsize=6.9,
                color=MUTED, zorder=5)
        y -= 10.6

    arrow(ax, (40.2, 49), (45.4, 49), color=DATA_C, lw=4.0, head=20)

    # ================================================================
    # PANEL 2 — the model (learn the link)
    # ================================================================
    ax.add_patch(FancyBboxPatch((46.5, 20), 69, 59,
                 boxstyle="round,pad=0,rounding_size=1.8", facecolor="#eef2ff",
                 edgecolor="#c7d2fe", lw=1.4, zorder=1))
    ax.text(81, 76.4, "2 ·  LEARN THE HIDDEN LINK", ha="center", fontsize=9.8,
            fontweight="bold", color=ENC_C)
    ax.text(81, 73.6,
            "Convolutional encoder compresses a full day of ocean surface into "
            "a 256-number embedding",
            ha="center", fontsize=6.9, color=MUTED)

    # input chips
    ax.text(52.5, 68.0, "INPUT day", ha="center", fontsize=7.4,
            fontweight="bold", color=INK)
    chips = ["sst", "sss", "sla", "ugos", "vgos", "uwnd", "vwnd"]
    yy = 64.6
    for c in chips:
        rr(ax, 48.0, yy, 9.2, 2.7, fc="#1e293b", r=0.6, z=5)
        ax.text(52.6, yy + 1.35, c, ha="center", va="center", fontsize=6.6,
                color="white", zorder=6, fontfamily="monospace")
        yy -= 3.1

    # encoder funnel (decreasing)
    enc = [("stem", "24ch · 101×241", 15.0),
           ("down1", "48ch · 50×120", 12.5),
           ("down2", "96ch · 25×60", 10.0),
           ("down3", "192ch · 12×30", 7.5)]
    yy = 62.0
    for i, (nm, sp, h) in enumerate(enc):
        funnel_block(ax, 70.5, yy - h / 2 + 1.2, 20, h,
                     ENC_C if i % 2 == 0 else "#3b82f6", nm, sp)
        if i < 3:
            arrow(ax, (70.5, yy - h + 1.2), (70.5, yy - h + 1.2 - 1.0),
                  color=ENC_C, lw=1.6, head=9, z=7)
        yy -= (h + 2.2)

    # latent
    shadow(ax, 84.2, 45.0, 15.5, 12.0, 1.3)
    rr(ax, 84.2, 45.0, 15.5, 12.0, fc=LAT_C, ec="white", lw=1.4, z=6)
    ax.text(91.95, 54.4, "EMBEDDING", ha="center", fontsize=7.4,
            fontweight="bold", color="white", zorder=7)
    ax.text(91.95, 51.6, "latent z", ha="center", fontsize=7.0, color="white",
            zorder=7)
    ax.text(91.95, 48.4, "(256,)", ha="center", fontsize=9.5,
            fontweight="bold", color="white", zorder=7)
    arrow(ax, (80.6, 50.5), (84.0, 50.5), color=LAT_C, lw=3.0, head=16)

    # decoder funnel (increasing)
    dec = [("up1", "96ch · 12×30", 7.5),
           ("up2", "48ch · 25×60", 10.0),
           ("up3", "24ch · 50×120", 12.5),
           ("head", "15ch · 101×241", 15.0)]
    yy = 62.0
    for i, (nm, sp, h) in enumerate(dec):
        funnel_block(ax, 106.0, yy - h / 2 + 1.2, 20, h,
                     DEC_C if i % 2 == 0 else "#f87171", nm, sp)
        if i < 3:
            arrow(ax, (106.0, yy - h + 1.2), (106.0, yy - h + 1.2 - 1.0),
                  color=DEC_C, lw=1.6, head=9, z=7)
        yy -= (h + 2.2)

    # z -> decoder note
    ax.add_patch(FancyArrowPatch((99.7, 51.0), (100.6, 51.0), arrowstyle="-",
                 color=LAT_C, lw=1.4, linestyle=(0, (2, 2)), zorder=6))
    ax.text(91.95, 43.4, "skip connections carry fine detail;  embedding is "
            "broadcast to every pixel",
            ha="center", fontsize=6.2, color="#7c3aed")

    arrow(ax, (116.6, 49), (121.2, 49), color=DEC_C, lw=4.0, head=20)

    # ================================================================
    # PANEL 3 — output + validation (what we PREDICT)
    # ================================================================
    ax.add_patch(FancyBboxPatch((123, 20), 35, 59,
                 boxstyle="round,pad=0,rounding_size=1.8", facecolor="#ecfdf5",
                 edgecolor="#a7f3d0", lw=1.4, zorder=1))
    ax.text(140.5, 76.4, "3 ·  REBUILD THE DEEP", ha="center", fontsize=9.8,
            fontweight="bold", color=OUT_C)
    ax.text(140.5, 73.6, "full 3-D temperature, 0–1000 m", ha="center",
            fontsize=7.0, color=MUTED, style="italic")

    # ocean cross-section (warm top -> cold deep)
    x0, y0, w, h = 127.5, 44.0, 26, 25
    v = np.linspace(1, 0, 240).reshape(-1, 1)
    ax.imshow(v, extent=[x0, x0 + w, y0, y0 + h], origin="upper", cmap=OCEAN,
              aspect="auto", zorder=3)
    ax.add_patch(Rectangle((x0, y0), w, h, fill=False, ec="white", lw=1.4,
                 zorder=5))
    # wavy surface
    xs = np.linspace(x0, x0 + w, 120)
    ax.plot(xs, y0 + h + 0.5 * np.sin((xs - x0) / 1.1), color="#0ea5e9",
            lw=2.0, zorder=6)
    # depth ticks
    for d, yy in [(0, 0), (100, 0.28), (300, 0.6), (1000, 1.0)]:
        ax.text(x0 + 0.6, y0 + h - yy * h, f"{d} m", fontsize=6.0, color="white",
                va="center", zorder=7, fontweight="bold")
        ax.plot([x0, x0 + w], [y0 + h - yy * h] * 2, color="white", lw=0.4,
                alpha=0.35, zorder=6)
    # ARGO floats
    argo(ax, x0 + 7.5, y0 + h * 0.52, s=0.95)
    argo(ax, x0 + 18.5, y0 + h * 0.30, s=0.95)
    ax.text(x0 + w / 2, y0 - 2.4, "predicted temperature cross-section",
            ha="center", fontsize=6.6, color=MUTED, style="italic")

    # validation box
    rr(ax, 127.5, 22.5, 26, 17.5, fc="white", ec="#a7f3d0", lw=1.1, r=1.2,
       z=4)
    argo(ax, 132.5, 31.5, s=0.9, z=6)
    ax.text(136.8, 37.0, "ARGO VALIDATION", ha="left", fontsize=7.4,
            fontweight="bold", color=OUT_C)
    ax.text(136.8, 34.4, "independent", ha="left", fontsize=6.3, color=MUTED)
    ax.text(136.8, 32.2, "INCOIS T_ANALYZED", ha="left", fontsize=6.3,
            color=MUTED)
    ax.text(136.8, 29.4, "vs persistence ·", ha="left", fontsize=6.3,
            color=MUTED)
    ax.text(136.8, 27.2, "climatology · SST→T MLP", ha="left", fontsize=6.3,
            color=MUTED)
    ax.text(136.8, 24.6, "(+ real Argo floats)", ha="left", fontsize=6.0,
            color="#94a3b8", style="italic")

    # ============================ RESULTS BAND ============================
    ax.add_patch(FancyBboxPatch((2, 3), 156, 14.5,
                 boxstyle="round,pad=0,rounding_size=1.6",
                 facecolor="#0b1220", zorder=1))
    ax.add_patch(Rectangle((2, 3), 1.0, 14.5, facecolor=GOLD, zorder=2))
    ax.text(6.2, 14.4, "RESULTS    Jan–Mar 2020  ·  thermocline (50–200 m) RMSE",
            ha="left", va="center", fontsize=9.0, fontweight="bold", color=GOLD)
    metrics = [("0.73 °C", "Model RMSE", OUT_C),
               ("0.96", "Correlation", OUT_C),
               ("0.82 °C", "SST→T MLP RMSE", "#94a3b8"),
               ("1.08 °C", "Climatology RMSE", "#94a3b8"),
               ("1.64 M", "Parameters", LAT_C),
               ("15", "Depths (0–1000 m)", ENC_C)]
    x = 14
    for val, lab, col in metrics:
        ax.text(x, 9.6, val, ha="center", va="center", fontsize=14.5,
                fontweight="bold", color=col)
        ax.text(x, 5.9, lab, ha="center", va="center", fontsize=6.7,
                color="#cbd5e1")
        x += 24.4
    ax.text(6.2, 4.0,
            "caveat: persistence is stronger below 30 m in this single-season test "
            "(thermocline 0.62 °C) — model is best at the surface. See STATUS.md §10.",
            ha="left", va="center", fontsize=6.0, color="#94a3b8")

    out = Path(__file__).resolve().parent / "figures" / "ppt_pipeline_illustrated.png"
    fig.savefig(out, dpi=200, facecolor=BG, bbox_inches="tight", pad_inches=0.12)
    print("saved", out)
    return out


if __name__ == "__main__":
    main()

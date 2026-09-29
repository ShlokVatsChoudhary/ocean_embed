"""Build the disaster-management figure for slide 5.

Left  : the TCHP product the model delivers (cyclone fuel, 2020-01-01).
Right : the same diagnostic computed from GLORYS truth, for comparison.
Bottom: accuracy of each derived diagnostic against GLORYS.

Run from ~/oe_work with the backend importable:
    cd ~/oe_work/backend && python3 ../make_hazard_figure.py
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.patches import Patch

sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))

from app.core.constants import STANDARD_DEPTHS  # noqa: E402
from app.data.glorys import GlorysDataAccessor  # noqa: E402
from app.model.adapter import OceanEmbedModelAdapter  # noqa: E402
from app.science.hazard import CATEGORY_BREAKS, CATEGORY_LABELS, hazard_fields  # noqa: E402

TARGET = date(2020, 1, 1)
OUT = Path(__file__).resolve().parent / "figures" / "hazard_tchp_2020-01-01.png"
DECK_OUT = Path(__file__).resolve().parent / "figures" / "hazard_deck.png"

NAVY = "#0B2545"
GREY = "#555B63"

# TCHP category colours, matched to CATEGORY_BREAKS.
COLOURS = ["#dbeafe", "#93c5fd", "#3b82f6", "#1e3a8a"]
LAT_MIN, LAT_MAX, LON_MIN, LON_MAX = 5.0, 30.0, 45.0, 105.0


def build_deck_figure(tchp_pred, tchp_true, rmse) -> None:
    """Wide, short variant sized for the slide-5 column (about 3.2 : 1).

    Two maps side by side and a one-line legend. The numbers live in the slide text,
    so nothing is repeated here and the figure stays short enough for the column.
    """
    fig = plt.figure(figsize=(9.6, 3.0), dpi=260, facecolor="white")
    grid = fig.add_gridspec(1, 2, wspace=0.12, left=0.052, right=0.988, top=0.755, bottom=0.135)

    cmap = ListedColormap(COLOURS)
    norm = BoundaryNorm([-1e9, *CATEGORY_BREAKS, 1e9], cmap.N)
    extent = [LON_MIN, LON_MAX, LAT_MIN, LAT_MAX]

    for spec, data, title in ((grid[0, 0], tchp_pred, "OceanEmbed  \u2014  cyclone heat potential"),
                              (grid[0, 1], tchp_true, "GLORYS reference")):
        ax = fig.add_subplot(spec)
        ax.imshow(data, origin="upper", extent=extent, cmap=cmap, norm=norm,
                  interpolation="nearest", aspect="auto")
        ax.set_title(title, fontsize=10.0, color=NAVY, fontweight="bold", pad=5)
        ax.set_xlabel("Longitude (\u00b0E)", fontsize=8.0, color=GREY)
        if spec == grid[0, 0]:
            ax.set_ylabel("Latitude (\u00b0N)", fontsize=8.0, color=GREY)
        ax.tick_params(labelsize=7.0, colors=GREY)
        for spine in ax.spines.values():
            spine.set_edgecolor("#c9d4e0")

    handles = [Patch(facecolor=COLOURS[i], edgecolor="#c9d4e0", label=CATEGORY_LABELS[i])
               for i in range(len(COLOURS))]
    # Legend sits between the suptitle and the maps, so it can never touch the tick labels.
    fig.legend(handles=handles, loc="upper center", ncol=4, frameon=False, fontsize=8.0,
               handlelength=1.3, handleheight=0.95, columnspacing=1.7,
               bbox_to_anchor=(0.5, 0.905))
    fig.suptitle(f"Cyclone fuel from space, 1 Jan 2020 \u2014 TCHP RMSE {rmse[0]:.1f} kJ/cm\u00b2 vs GLORYS truth",
                 fontsize=10.4, color=NAVY, fontweight="bold", y=0.985)

    fig.canvas.draw()
    boxes = []
    for artist in fig.findobj(plt.Text):
        if artist.get_visible() and artist.get_text().strip():
            try:
                boxes.append((artist.get_text()[:34], artist.get_window_extent(fig.canvas.get_renderer())))
            except Exception:
                continue
    collisions = [(boxes[i][0], boxes[j][0]) for i in range(len(boxes)) for j in range(i + 1, len(boxes))
                  if boxes[i][1].overlaps(boxes[j][1])]
    print(f"  deck figure QA text collisions: {len(collisions)}")
    for left, right in collisions[:6]:
        print(f"    !! {left!r} overlaps {right!r}")

    fig.savefig(DECK_OUT, dpi=260, facecolor="white")
    plt.close(fig)
    print(f"wrote {DECK_OUT}")


def main() -> None:
    depths = np.asarray(STANDARD_DEPTHS, dtype=float)
    model = OceanEmbedModelAdapter()
    glorys = GlorysDataAccessor()

    predicted = model.temperature_field_array(TARGET)
    truth = np.asarray(glorys._field_for_date(TARGET), dtype=float)

    fields_pred = hazard_fields(predicted, depths)
    fields_true = hazard_fields(truth, depths)
    shared = fields_pred["valid_mask"] & fields_true["valid_mask"]

    tchp_pred = np.where(shared, fields_pred["tchp"], np.nan)
    tchp_true = np.where(shared, fields_true["tchp"], np.nan)

    # Row 0 of the backend field is the southernmost latitude, so flip for a north-up plot.
    tchp_pred = np.flipud(tchp_pred)
    tchp_true = np.flipud(tchp_true)

    # Three explicit rows so the legend can never collide with the panel titles.
    fig = plt.figure(figsize=(11.6, 7.0), dpi=200, facecolor="white")
    grid = fig.add_gridspec(3, 4, height_ratios=[1.0, 0.13, 0.50],
                            hspace=0.42, wspace=0.22,
                            left=0.055, right=0.975, top=0.885, bottom=0.075)

    cmap = ListedColormap(COLOURS)
    norm = BoundaryNorm([-1e9, *CATEGORY_BREAKS, 1e9], cmap.N)

    extent = [LON_MIN, LON_MAX, LAT_MIN, LAT_MAX]
    panels = [
        (grid[0, 0:2], tchp_pred, "OceanEmbed cyclone heat potential"),
        (grid[0, 2:4], tchp_true, "GLORYS reference field"),
    ]
    for spec, data, title in panels:
        ax = fig.add_subplot(spec)
        ax.imshow(data, origin="upper", extent=extent, cmap=cmap, norm=norm,
                  interpolation="nearest", aspect="auto")
        ax.set_title(title, fontsize=10.5, color=NAVY, fontweight="bold", pad=7)
        ax.set_xlabel("Longitude (°E)", fontsize=8.5, color=GREY)
        ax.set_ylabel("Latitude (°N)", fontsize=8.5, color=GREY)
        ax.tick_params(labelsize=7.5, colors=GREY)
        for spine in ax.spines.values():
            spine.set_edgecolor("#c9d4e0")

    handles = [Patch(facecolor=COLOURS[i], edgecolor="#c9d4e0", label=CATEGORY_LABELS[i])
               for i in range(len(COLOURS))]
    legend_ax = fig.add_subplot(grid[1, :])
    legend_ax.axis("off")
    legend_ax.legend(handles=handles, loc="center", ncol=4, frameon=False, fontsize=9.5,
                     handlelength=1.5, handleheight=1.1, columnspacing=2.4,
                     title="TCHP (kJ/cm²)", title_fontsize=9.5)

    # ---- bottom: accuracy of every derived diagnostic against GLORYS
    names, rmse, bias = [], [], []
    for key, label in (("tchp", "TCHP"), ("d26", "D26"), ("ohc", "OHC"),
                       ("mld", "MLD"), ("thermocline_depth", "Thermocline")):
        a, b = fields_pred[key][shared], fields_true[key][shared]
        ok = np.isfinite(a) & np.isfinite(b)
        names.append(label)
        rmse.append(float(np.sqrt(np.mean((a[ok] - b[ok]) ** 2))))
        bias.append(float(np.mean(a[ok] - b[ok])))

    ax = fig.add_subplot(grid[2, 0:2])
    x = np.arange(len(names))
    ax.bar(x, rmse, width=0.6, color="#3b82f6", edgecolor=NAVY, linewidth=0.6)
    for xi, value in zip(x, rmse):
        ax.text(xi, value, f"{value:.1f}", ha="center", va="bottom", fontsize=8, color=NAVY,
                fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(names, fontsize=8.5, color=GREY)
    ax.set_ylabel("RMSE vs GLORYS", fontsize=8.5, color=GREY)
    ax.set_title("Accuracy of each derived diagnostic", fontsize=10, color=NAVY,
                 fontweight="bold", pad=6)
    ax.tick_params(labelsize=7.5, colors=GREY)
    ax.set_ylim(0, max(rmse) * 1.28)
    ax.grid(axis="y", alpha=0.25, linewidth=0.6)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)

    # ---- bottom right: plain-English reading of the result
    ax2 = fig.add_subplot(grid[2, 2:4])
    ax2.axis("off")
    category = fields_pred["tchp_category"]
    favourable = int(np.nansum(category >= 2))
    rapid = int(np.nansum(category >= 3))
    coverage_pct = 100 * fields_pred["valid_mask"].mean()
    lines = [
        ("What a forecaster gets", NAVY, 10.5, "bold"),
        (f"{favourable:,} cells favourable for intensification (TCHP \u2265 50)", GREY, 9.2, "normal"),
        (f"{rapid:,} cells with rapid-intensification potential (TCHP \u2265 80)", GREY, 9.2, "normal"),
        ("", GREY, 5.0, "normal"),
        ("Why the map has gaps", NAVY, 10.5, "bold"),
        (f"{coverage_pct:.0f}% of cells carry a value. Columns shallower than", GREY, 9.2, "normal"),
        ("300 m are left blank rather than shown as low TCHP,", GREY, 9.2, "normal"),
        ("because a truncated profile would read as low cyclone", GREY, 9.2, "normal"),
        ("risk when the truth is simply unknown.", GREY, 9.2, "normal"),
    ]
    y = 0.96
    for text, colour, size, weight in lines:
        if text:
            ax2.text(0.0, y, text, transform=ax2.transAxes, fontsize=size, color=colour,
                     fontweight=weight, va="top")
        y -= (size + 4.0) / 105.0 if text else 0.03
    ax2.add_patch(plt.Rectangle((-0.02, 0.01), 1.04, y - 0.02, transform=ax2.transAxes,
                                facecolor="#f7fafc", edgecolor="#dbe3ea", linewidth=0.7, zorder=-1))

    fig.suptitle("Cyclone intensification diagnostics — North Indian Ocean, 1 Jan 2020",
                 fontsize=13.5, color=NAVY, fontweight="bold", y=0.975)

    # ---- QA: no text artist may overlap another
    fig.canvas.draw()
    boxes = []
    for artist in fig.findobj(plt.Text):
        if not artist.get_visible() or not artist.get_text().strip():
            continue
        try:
            boxes.append((artist.get_text()[:40], artist.get_window_extent(fig.canvas.get_renderer())))
        except Exception:
            continue
    collisions = []
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            a, b = boxes[i][1], boxes[j][1]
            if a.overlaps(b):
                collisions.append((boxes[i][0], boxes[j][0]))
    print(f"  QA text collisions: {len(collisions)}")
    for left, right in collisions[:8]:
        print(f"    !! {left!r} overlaps {right!r}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=200, facecolor="white")
    plt.close(fig)

    build_deck_figure(tchp_pred, tchp_true, rmse)

    print(f"wrote {OUT}")
    print(f"  TCHP RMSE  {rmse[0]:.2f} kJ/cm^2  bias {bias[0]:+.2f}  "
          f"(truth median {np.nanmedian(tchp_true):.1f})")
    print(f"  favourable cells {favourable}  rapid-intensification {rapid}")
    print(f"  coverage {100 * fields_pred['valid_mask'].mean():.1f}%")


if __name__ == "__main__":
    main()

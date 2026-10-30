#!/usr/bin/env python3
"""Render the Logics-SWE release chart from three-round pass counts."""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.image as mpimg
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.path import Path as MplPath
from matplotlib.patches import PathPatch, FancyBboxPatch
import numpy as np

HERE = Path(__file__).resolve().parent
DATA = json.loads((HERE / "aggregate_results.json").read_text())
MODELS = [
    "Qwen3.6-27B", "Logics-SWE-Qwen3.6-27B",
    "Qwen3.6-35B-A3B", "Logics-SWE-Qwen3.6-35B-A3B",
]
assert DATA["model_order"] == MODELS
assert len(DATA["benchmarks"]) == 5
values = []
for row in DATA["benchmarks"]:
    assert len(row["passes"]) == 4
    assert all(len(runs) == 3 for runs in row["passes"])
    assert all(0 <= n <= row["tasks"] for runs in row["passes"] for n in runs)
    values.append([100 * sum(runs) / (3 * row["tasks"]) for runs in row["passes"]])
values = np.asarray(values)

BG = "#F8FAFA"
INK = "#253238"
MUTED = "#758087"
BASELINE = "#D5DEDF"
COLORS = ["#AEBCC8", "#356F6C", "#D1DCE3", "#81AAA1"]
TITLES = [
    "SWE-bench\nPro V2",
    "Pro V2\nHard-51",
    "SWE-bench\nMultilingual",
    "SWE-bench\nPro",
    "LiveCodeBench\nv6",
]

family = "DejaVu Sans"
for candidate in ("Arial", "DejaVu Sans"):
    try:
        font_manager.findfont(candidate, fallback_to_default=False)
        family = candidate
        break
    except ValueError:
        pass
plt.rcParams.update({
    "font.family": family, "font.size": 12,
    "pdf.fonttype": 42, "ps.fonttype": 42, "svg.fonttype": "none",
})
fig = plt.figure(figsize=(16, 6.8), facecolor=BG)
fig.text(.045, .915, "Logics-SWE benchmark results", fontsize=27,
         color=INK, fontweight="medium", va="center")
fig.text(.045, .858,
         "Two coding agents, distilled from the same three category experts.",
         fontsize=12.5, color=MUTED, va="center")
fig.text(.955, .858, "Three-round mean · Score (%)", fontsize=10.3,
         color=MUTED, va="center", ha="right")

# Qwen's original mark appears only before the official base-model names.
logo = mpimg.imread(HERE / "qwen3_official.png")[:, :1300]
if logo.shape[-1] == 4:
    yy, xx = np.where(logo[:, :, 3] > .01)
    logo = logo[yy.min():yy.max()+1, xx.min():xx.max()+1]
legend_x = [.045, .250, .513, .753]
legend_y = .762
for index, x in enumerate(legend_x):
    fig.add_artist(FancyBboxPatch(
        (x, legend_y-.008), .009, .017,
        boxstyle="round,pad=0,rounding_size=0.0025",
        transform=fig.transFigure, facecolor=COLORS[index], edgecolor="none"))
    text_x = x + .016
    if index in (0, 2):
        iax = fig.add_axes([text_x, legend_y-.015, .012, .030], frameon=False)
        iax.imshow(logo)
        iax.axis("off")
        text_x += .016
    fig.text(text_x, legend_y, MODELS[index], fontsize=10.6, va="center",
             color=INK, fontweight="medium" if index in (1, 3) else "normal")


def rounded_top_bar(ax, x, value, color, width=.57, radius_pt=3.0):
    """Round only the top corners; the bottom remains exactly at zero."""
    x0, x1 = x - width / 2, x + width / 2
    width_in = ax.get_position().width * fig.get_figwidth()
    height_in = ax.get_position().height * fig.get_figheight()
    rx = min(width / 2, radius_pt / 72 / width_in * np.diff(ax.get_xlim())[0])
    ry = min(value / 2, radius_pt / 72 / height_in * np.diff(ax.get_ylim())[0])
    k = .5522847498
    verts = [
        (x0, 0), (x0, value-ry),
        (x0, value-ry+k*ry), (x0+rx-k*rx, value), (x0+rx, value),
        (x1-rx, value),
        (x1-rx+k*rx, value), (x1, value-ry+k*ry), (x1, value-ry),
        (x1, 0), (x0, 0),
    ]
    codes = [
        MplPath.MOVETO, MplPath.LINETO,
        MplPath.CURVE4, MplPath.CURVE4, MplPath.CURVE4,
        MplPath.LINETO,
        MplPath.CURVE4, MplPath.CURVE4, MplPath.CURVE4,
        MplPath.LINETO, MplPath.CLOSEPOLY,
    ]
    ax.add_patch(PathPatch(MplPath(verts, codes), facecolor=color,
                           edgecolor="none", zorder=3))


left, right, gap = .045, .955, .027
panel_width = (right-left-4*gap) / 5
bar_x = [0, .8, 2.0, 2.8]
for i, (row, title) in enumerate(zip(DATA["benchmarks"], TITLES)):
    x0 = left + i * (panel_width+gap)
    ax = fig.add_axes([x0, .208, panel_width, .395], facecolor=BG)
    ax.set(xlim=(-.53, 3.33), ylim=(0, 108), xticks=[], yticks=[])
    for spine in ax.spines.values():
        spine.set_visible(False)
    # A single fine baseline keeps the zero-origin bar heights readable.
    ax.axhline(0, color=BASELINE, lw=1.1, clip_on=False, zorder=1)
    fig.text(x0, .663, title, fontsize=12.2, color=INK,
             fontweight="medium", va="center", linespacing=1.35)
    for j, value in enumerate(values[i]):
        rounded_top_bar(ax, bar_x[j], value, COLORS[j])
        ax.text(bar_x[j], value+2.8, f"{value:.2f}", fontsize=11.5,
                ha="center", va="bottom", color=INK if j in (1, 3) else MUTED,
                fontweight="bold" if j in (1, 3) else "normal")
    # Pair labels connect each gain directly to its two bars.
    for k, center in enumerate((.4, 2.4)):
        trans = ax.get_xaxis_transform()
        ax.text(center, -.080, ("27B", "35B-A3B")[k], transform=trans,
                fontsize=10, va="top", ha="center", color=MUTED)
        delta = values[i, 2*k+1] - values[i, 2*k]
        ax.text(center, -.190, f"+{delta:.2f} pp", transform=trans,
                fontsize=10.8, va="top", ha="center",
                color=COLORS[2*k+1], fontweight="medium")

fig.text(.045, .047,
         "Qwen baseline scores are from our own evaluations under the same settings as Logics-SWE.",
         fontsize=9.5, color=MUTED, va="center")

for ext in ("png", "pdf", "svg"):
    fig.savefig(HERE / f"model_benchmark_comparison.{ext}", dpi=300, facecolor=BG)
plt.close(fig)
for row, vals in zip(DATA["benchmarks"], values):
    print(row["name"], "|", " ".join(f"{v:.2f}" for v in vals),
          "| gains", f"{vals[1]-vals[0]:+.2f}", f"{vals[3]-vals[2]:+.2f}")

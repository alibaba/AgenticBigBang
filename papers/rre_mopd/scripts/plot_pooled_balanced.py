#!/usr/bin/env python3
"""Reproduce the pooled/balanced comparison using package-local two-round means."""
import csv
import math
from pathlib import Path
from statistics import mean
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "results/curves/pooled_balanced_scores.csv"
PREFIX = ROOT / "results/figures/fig_pooled_balanced"

def main():
    with SOURCE.open(newline="") as f:
        rows = list(csv.DictReader(f))
    assert set(r["method"] for r in rows) == {"Pooled", "Balanced"}
    for row in rows:
        for key in ("evaluation_index", "display_step", "round_count"):
            row[key] = int(row[key])
        assert row["display_step"] == 5 * row["evaluation_index"]
        assert row["round_count"] == 2
        for category in ("Full", "A", "B", "C"):
            row[category] = float(row[category])
            assert math.isfinite(row[category]) and 0 <= row[category] <= 100
        weighted = (221 * row["A"] + 201 * row["B"] + 196 * row["C"]) / 618
        assert abs(row["Full"] - weighted) < 1e-8
    for method, expected in (("Pooled", 63), ("Balanced", 50)):
        rs = [r for r in rows if r["method"] == method]
        assert [r["evaluation_index"] for r in rs] == list(range(1, expected + 1))
    PREFIX.parent.mkdir(parents=True, exist_ok=True)
    render(rows)
    print("Validated 113 two-round mean points; plotted first 50 per method.")
    print(PREFIX.with_suffix(".pdf"))

def render(rows):
    plt.rcParams.update({"font.family": "serif", "font.serif": ["Times New Roman", "DejaVu Serif"],
                         "font.size": 14, "axes.labelsize": 13, "legend.fontsize": 12,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "pdf.fonttype": 42, "ps.fonttype": 42})
    fig, axes = plt.subplots(1, 3, figsize=(10.8, 3.7))
    display_max = max(r["display_step"] for r in rows if r["method"] == "Balanced")
    series = {m: [r for r in rows if r["method"] == m and r["display_step"] <= display_max]
              for m in ("Pooled", "Balanced")}
    colors = {"A": "#0072B2", "B": "#D55E00", "C": "#009E73"}

    def line(ax, method, category, color, label, style="-", marker="o"):
        rs = series[method]
        xs = [r["display_step"] for r in rs]
        ys = [r[category] for r in rs]
        smoothed = [mean(ys[max(0, i-2):i+3]) for i in range(len(ys))]
        ax.scatter(xs, ys, color=color, s=9, alpha=.16, linewidths=0, marker=marker)
        ax.plot(xs, smoothed, color=color, lw=2.1, linestyle=style, label=label)

    line(axes[0], "Pooled", "Full", "#0072B2", "Pooled")
    line(axes[0], "Balanced", "Full", "#D55E00", "Balanced", "--", "s")
    for ax, method in zip(axes[1:], series):
        for c, style, marker in zip(colors, ["-", "--", "-."], ["o", "s", "^"]):
            line(ax, method, c, colors[c], "Pro-" + c, style, marker)
        ax.set_ylim(47, 61)
        ax.set_yticks([48, 52, 56, 60])
    axes[0].set_ylim(49, 58)
    axes[0].set_yticks([50, 52, 54, 56, 58])
    axes[0].set_ylabel("Resolution (%)")
    for ax, title in zip(axes, ["(a) Overall", "(b) Pooled categories", "(c) Balanced categories"]):
        ax.set_title(title, fontsize=14, pad=31)
        ax.legend(loc="lower center", bbox_to_anchor=(.5, 1), ncol=2 if ax == axes[0] else 3,
                  frameon=False, handlelength=1.3, handletextpad=.35, columnspacing=.65)
        ax.set_xlabel(r"Evaluation index $\times$ 5")
        ax.set_xlim(0, display_max)
        ax.set_xticks(list(range(0, display_max + 1, 50)))
        ax.grid(axis="y", color="#D9DDE3", lw=.6, alpha=.7)
        ax.set_axisbelow(True)
        for side in ("left", "bottom"):
            ax.spines[side].set_color("#8B929C")
    fig.subplots_adjust(left=.066, right=.99, bottom=.20, top=.78, wspace=.23)
    for ext in ("pdf", "png"):
        fig.savefig(str(PREFIX) + "." + ext, dpi=300, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Reproduce the manuscript breadth plot from the bundled taxonomy inventory."""

from __future__ import annotations

import argparse
import colorsys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import yaml
from matplotlib.colors import to_rgb


ROOT = Path(__file__).resolve().parents[1]
FIGURE_DIR = ROOT / "results" / "figures"
DEFAULT_DEFINITION_DIR = ROOT / "data" / "taxonomy"


plt.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica"],
        "font.size": 8,
        "axes.titlesize": 10,
        "axes.titleweight": "bold",
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "figure.dpi": 180,
        "savefig.dpi": 320,
        "savefig.bbox": "tight",
        "savefig.facecolor": "white",
    }
)


def load_axis(definition_dir: Path, filename: str) -> list[dict]:
    raw = yaml.safe_load((definition_dir / filename).read_text(encoding="utf-8"))
    axis = []
    for l1_name, payload in raw.items():
        children = payload.get("l2") or []
        axis.append(
            {
                "name": str(l1_name),
                "children": [str(item["name"]) for item in children],
            }
        )
    return axis


def categorical_colors(n: int) -> list[tuple[float, float, float]]:
    """Generate muted, well-separated colors using a golden-angle hue walk."""
    colors = []
    for i in range(n):
        hue = (0.58 + i * 0.61803398875) % 1.0
        saturation = 0.52 + 0.08 * (i % 3)
        lightness = 0.48 + 0.05 * ((i // 3) % 2)
        colors.append(colorsys.hls_to_rgb(hue, lightness, saturation))
    return colors


def mix_with_white(color, amount: float):
    rgb = np.asarray(to_rgb(color))
    return tuple(rgb * (1.0 - amount) + amount)


def display_name(name: str) -> str:
    return name.replace("_", " ").replace("-", "-")


def add_sunburst(ax, axis: list[dict], title: str, total_l2: int) -> None:
    parent_colors = categorical_colors(len(axis))
    parent_weights = [max(1, len(item["children"])) for item in axis]

    parent_wedges, _ = ax.pie(
        parent_weights,
        radius=0.70,
        startangle=90,
        counterclock=False,
        colors=parent_colors,
        wedgeprops={"width": 0.29, "edgecolor": "white", "linewidth": 0.9},
    )

    leaf_weights = []
    leaf_colors = []
    for parent_idx, item in enumerate(axis):
        child_count = max(1, len(item["children"]))
        for child_idx in range(child_count):
            leaf_weights.append(1)
            if item["children"]:
                amount = 0.16 + 0.22 * ((child_idx % 3) / 2.0)
                leaf_colors.append(mix_with_white(parent_colors[parent_idx], amount))
            else:
                leaf_colors.append("#D1D5DB")

    ax.pie(
        leaf_weights,
        radius=1.0,
        startangle=90,
        counterclock=False,
        colors=leaf_colors,
        wedgeprops={"width": 0.285, "edgecolor": "white", "linewidth": 0.32},
    )

    # Static paper figures cannot reproduce the HTML's interactive hover labels.
    # Compact numeric IDs map to the companion breadth plot without crowding.
    for parent_idx, (wedge, weight) in enumerate(zip(parent_wedges, parent_weights)):
        if weight < 2:
            continue
        angle = (wedge.theta1 + wedge.theta2) / 2.0
        radians = np.deg2rad(angle)
        x, y = 0.555 * np.cos(radians), 0.555 * np.sin(radians)
        ax.text(
            x,
            y,
            str(parent_idx + 1),
            rotation=0,
            rotation_mode="anchor",
            ha="center",
            va="center",
            fontsize=5.2,
            fontweight="semibold",
            color="white",
        )

    center = plt.Circle((0, 0), 0.39, color="white", zorder=5)
    ax.add_artist(center)
    ax.text(
        0,
        0.03,
        f"{len(axis)} L1",
        ha="center",
        va="center",
        fontsize=10,
        fontweight="bold",
        color="#1F2937",
        zorder=6,
    )
    ax.text(
        0,
        -0.10,
        f"{total_l2} L2",
        ha="center",
        va="center",
        fontsize=8,
        color="#6B7280",
        zorder=6,
    )
    ax.set_title(title, pad=12)
    ax.set_aspect("equal")
    ax.set_xlim(-1.08, 1.08)
    ax.set_ylim(-1.08, 1.08)
    ax.axis("off")


def save_sunburst(task_axis: list[dict], domain_axis: list[dict]) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.3))
    add_sunburst(
        axes[0], task_axis, "(a) Task Type hierarchy", sum(len(x["children"]) for x in task_axis)
    )
    add_sunburst(
        axes[1], domain_axis, "(b) Repository Domain hierarchy", sum(len(x["children"]) for x in domain_axis)
    )
    fig.subplots_adjust(left=0.015, right=0.985, top=0.90, bottom=0.02, wspace=0.06)
    fig.savefig(FIGURE_DIR / "fig_label_taxonomy_sunburst.pdf")
    fig.savefig(FIGURE_DIR / "fig_label_taxonomy_sunburst.png")
    plt.close(fig)


def add_breadth_panel(ax, axis: list[dict], title: str) -> None:
    ordered = sorted(axis, key=lambda item: (len(item["children"]), item["name"]), reverse=True)
    colors_by_name = {
        item["name"]: color for item, color in zip(axis, categorical_colors(len(axis)))
    }
    names = [display_name(item["name"]) for item in ordered]
    values = [len(item["children"]) for item in ordered]
    colors = [colors_by_name[item["name"]] if value else "#D1D5DB" for item, value in zip(ordered, values)]
    y = np.arange(len(ordered))

    ax.barh(y, values, color=colors, height=0.68, edgecolor="white", linewidth=0.45)
    ax.set_yticks(y)
    ax.set_yticklabels(names, fontsize=6.2)
    ax.invert_yaxis()
    ax.set_xlim(0, max(values) + 2.0)
    ax.set_xticks(range(0, max(values) + 1, 2))
    ax.set_xlabel("Number of declared L2 labels", fontsize=7.5)
    ax.set_title(title, loc="left", pad=8)
    ax.xaxis.grid(True, color="#D1D5DB", linewidth=0.5, alpha=0.7)
    ax.set_axisbelow(True)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.spines["bottom"].set_color("#9CA3AF")
    ax.tick_params(axis="y", length=0)
    ax.tick_params(axis="x", labelsize=6.5, colors="#4B5563")
    for yi, value in zip(y, values):
        ax.text(
            value + 0.16,
            yi,
            str(value),
            va="center",
            ha="left",
            fontsize=6.2,
            color="#374151",
        )


def save_breadth(task_axis: list[dict], domain_axis: list[dict]) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 6.0))
    add_breadth_panel(axes[0], task_axis, "(a) Task Type L1 breadth")
    add_breadth_panel(axes[1], domain_axis, "(b) Repository Domain L1 breadth")
    fig.subplots_adjust(left=0.16, right=0.985, top=0.95, bottom=0.08, wspace=0.52)
    fig.savefig(FIGURE_DIR / "fig_label_taxonomy_breadth.pdf")
    fig.savefig(FIGURE_DIR / "fig_label_taxonomy_breadth.png")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--definition-dir",
        type=Path,
        default=DEFAULT_DEFINITION_DIR,
        help="Directory containing task_type_l2.yaml and domain_l2.yaml",
    )
    args = parser.parse_args()

    task_axis = load_axis(args.definition_dir, "task_type_l2.yaml")
    domain_axis = load_axis(args.definition_dir, "domain_l2.yaml")
    assert (len(task_axis), sum(len(x["children"]) for x in task_axis)) == (26, 119)
    assert (len(domain_axis), sum(len(x["children"]) for x in domain_axis)) == (21, 108)

    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    save_breadth(task_axis, domain_axis)


if __name__ == "__main__":
    main()

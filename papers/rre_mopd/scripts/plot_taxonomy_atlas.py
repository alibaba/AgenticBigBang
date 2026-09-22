#!/usr/bin/env python3
"""Generate a labeled treemap preview for the frozen SWE taxonomy.

Tile area encodes ``max(3, number of declared L2 labels)``.  The three-unit floor
keeps small and zero-child L1 families readable and is disclosed in the figure.
The visualization describes taxonomy structure, not sample prevalence.
"""

from __future__ import annotations

import argparse
import hashlib
import textwrap
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.colors import to_rgb
from matplotlib.patches import Rectangle
import numpy as np
import yaml


ROOT = Path(__file__).resolve().parents[1]
FIGURE_DIR = ROOT / "results" / "figures"
DEFAULT_DEFINITION_DIR = ROOT / "data" / "taxonomy"

OUTPUT_STEM = "fig_label_taxonomy_atlas"
TASK_EXPECTED = (26, 119)
DOMAIN_EXPECTED = (21, 108)
ORTHOGONAL_EXPECTED = (3, 12)

INK = "#25313D"
MUTED = "#667085"
GRID = "#FFFFFF"
ZERO_FILL = "#E5E7EB"
ZERO_EDGE = "#9CA3AF"

TASK_PALETTE = ["#BFD7EE", "#B8DCDC", "#D1DDF2", "#AFCDE5", "#C9D8E8"]
DOMAIN_PALETTE = ["#F3D5A6", "#EFC4A8", "#D8DEB2", "#F0CFC2", "#E5D2A8"]


plt.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica"],
        "font.size": 7,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "figure.dpi": 180,
        "savefig.dpi": 320,
        "savefig.facecolor": "white",
        "axes.facecolor": "white",
    }
)


@dataclass(frozen=True)
class LabelFamily:
    name: str
    children: tuple[str, ...]
    source_index: int

    @property
    def count(self) -> int:
        return len(self.children)

    @property
    def encoded_weight(self) -> int:
        return max(3, self.count)


@dataclass(frozen=True)
class Tile:
    family: LabelFamily
    x: float
    y: float
    width: float
    height: float


def load_axis(definition_dir: Path, filename: str) -> list[LabelFamily]:
    raw = yaml.safe_load((definition_dir / filename).read_text(encoding="utf-8"))
    families: list[LabelFamily] = []
    for source_index, (l1_name, payload) in enumerate(raw.items()):
        children = tuple(str(entry["name"]) for entry in (payload.get("l2") or []))
        families.append(LabelFamily(str(l1_name), children, source_index))
    return families


def load_orthogonal_counts(definition_dir: Path) -> tuple[int, int]:
    raw = yaml.safe_load((definition_dir / "orthogonal.yaml").read_text(encoding="utf-8"))
    return len(raw), sum(len(payload.get("levels") or []) for payload in raw.values())


def split_index(weights: list[int]) -> int:
    """Choose a deterministic, near-balanced split for an already sorted list."""
    if len(weights) <= 1:
        return 1
    total = sum(weights)
    running = 0
    best_index = 1
    best_gap = float("inf")
    for index, weight in enumerate(weights[:-1], start=1):
        running += weight
        gap = abs(total - 2 * running)
        if gap < best_gap:
            best_gap = gap
            best_index = index
    return best_index


def binary_treemap(
    families: list[LabelFamily],
    x: float = 0.0,
    y: float = 0.0,
    width: float = 100.0,
    height: float = 100.0,
) -> list[Tile]:
    """Lay out weighted rectangles using recursive longest-side bisection."""
    if not families:
        return []
    if len(families) == 1:
        return [Tile(families[0], x, y, width, height)]

    ordered = sorted(
        families,
        key=lambda family: (-family.encoded_weight, family.source_index, family.name),
    )
    cut = split_index([family.encoded_weight for family in ordered])
    first, second = ordered[:cut], ordered[cut:]
    first_weight = sum(family.encoded_weight for family in first)
    total_weight = first_weight + sum(family.encoded_weight for family in second)
    ratio = first_weight / total_weight

    if width >= height:
        first_width = width * ratio
        return binary_treemap(first, x, y, first_width, height) + binary_treemap(
            second, x + first_width, y, width - first_width, height
        )

    first_height = height * ratio
    return binary_treemap(first, x, y, width, first_height) + binary_treemap(
        second, x, y + first_height, width, height - first_height
    )


def humanize(name: str) -> str:
    return name.replace("_", " ").replace("-", "-")


def tint(color: str, amount: float) -> tuple[float, float, float]:
    rgb = np.asarray(to_rgb(color))
    return tuple(rgb * (1.0 - amount) + amount)


def family_color(family: LabelFamily, palette: list[str]) -> tuple[float, float, float]:
    base = palette[family.source_index % len(palette)]
    variation = 0.02 * ((family.source_index // len(palette)) % 3)
    return tint(base, variation)


def wrap_name(name: str, width_units: float) -> str:
    # Bold headers are wider than body text; a conservative line length avoids
    # relying on clipping when the figure is rendered at two-column paper size.
    max_chars = max(6, min(24, int(width_units * 0.58)))
    return "\n".join(
        textwrap.wrap(
            humanize(name),
            width=max_chars,
            break_long_words=True,
            break_on_hyphens=True,
        )
    )


def choose_font_size(tile: Tile) -> float:
    short_side = min(tile.width, tile.height)
    area = tile.width * tile.height
    if tile.width < 8.5 or short_side < 7.0 or area < 120:
        return 3.55
    if tile.width < 11.0 or short_side < 8.0 or area < 155:
        return 3.95
    if short_side < 11.5 or area < 230:
        return 4.7
    if short_side < 16.0 or area < 390:
        return 5.3
    return 6.0


def annotation_lines(tile: Tile) -> tuple[str, str]:
    family = tile.family
    header = wrap_name(family.name, tile.width)
    count_text = "0 L2" if family.count == 0 else f"{family.count} L2 labels"

    area = tile.width * tile.height
    short_side = min(tile.width, tile.height)
    max_examples = 0
    if area >= 720 and short_side >= 20 and tile.width >= 21:
        max_examples = 3
    elif area >= 470 and short_side >= 16 and tile.width >= 18:
        max_examples = 2
    elif area >= 330 and short_side >= 13 and tile.width >= 17:
        max_examples = 1

    examples = list(family.children[:max_examples])
    detail_lines = [count_text]
    detail_lines.extend(f"• {humanize(example)}" for example in examples)
    remaining = family.count - len(examples)
    if examples and remaining > 0:
        detail_lines.append(f"+{remaining} more")
    elif family.count == 0 and area >= 170 and short_side >= 9:
        detail_lines.append("unspecified fallback")
    return header, "\n".join(detail_lines)


def render_panel(
    ax,
    families: list[LabelFamily],
    title: str,
    palette: list[str],
) -> None:
    tiles = binary_treemap(families)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.set_aspect("auto")
    ax.axis("off")
    ax.set_title(title, loc="left", fontsize=10.2, fontweight="bold", color=INK, pad=7)

    for tile in tiles:
        family = tile.family
        face = ZERO_FILL if family.count == 0 else family_color(family, palette)
        edge = ZERO_EDGE if family.count == 0 else GRID
        patch = Rectangle(
            (tile.x, tile.y),
            tile.width,
            tile.height,
            facecolor=face,
            edgecolor=edge,
            linewidth=1.15 if family.count == 0 else 1.6,
            hatch="///" if family.count == 0 else None,
        )
        ax.add_patch(patch)

        pad_x = min(1.5, tile.width * 0.08)
        pad_y = min(1.6, tile.height * 0.08)
        font_size = choose_font_size(tile)
        header, details = annotation_lines(tile)

        header_artist = ax.text(
            tile.x + pad_x,
            tile.y + tile.height - pad_y,
            header,
            ha="left",
            va="top",
            fontsize=font_size,
            fontweight="bold",
            color=INK,
            linespacing=0.92,
            clip_on=True,
        )
        header_artist.set_clip_path(patch)

        header_line_count = header.count("\n") + 1
        detail_y = tile.y + tile.height - pad_y - header_line_count * (font_size * 0.43 + 1.2)
        detail_artist = ax.text(
            tile.x + pad_x,
            detail_y,
            details,
            ha="left",
            va="top",
            fontsize=max(3.25, font_size - 0.9),
            color=MUTED,
            linespacing=1.03,
            clip_on=True,
        )
        detail_artist.set_clip_path(patch)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def generate(definition_dir: Path, output_dir: Path) -> tuple[Path, Path]:
    task_axis = load_axis(definition_dir, "task_type_l2.yaml")
    domain_axis = load_axis(definition_dir, "domain_l2.yaml")
    task_actual = (len(task_axis), sum(family.count for family in task_axis))
    domain_actual = (len(domain_axis), sum(family.count for family in domain_axis))
    orthogonal_actual = load_orthogonal_counts(definition_dir)
    assert task_actual == TASK_EXPECTED, (task_actual, TASK_EXPECTED)
    assert domain_actual == DOMAIN_EXPECTED, (domain_actual, DOMAIN_EXPECTED)
    assert orthogonal_actual == ORTHOGONAL_EXPECTED, (
        orthogonal_actual,
        ORTHOGONAL_EXPECTED,
    )

    task_encoded = sum(family.encoded_weight for family in task_axis)
    domain_encoded = sum(family.encoded_weight for family in domain_axis)
    fig = plt.figure(figsize=(7.35, 4.45), facecolor="white")
    grid = fig.add_gridspec(
        1,
        2,
        left=0.025,
        right=0.985,
        top=0.82,
        bottom=0.085,
        wspace=0.025,
        width_ratios=[task_encoded, domain_encoded],
    )
    task_ax = fig.add_subplot(grid[0, 0])
    domain_ax = fig.add_subplot(grid[0, 1])

    render_panel(task_ax, task_axis, "(a) Task Type — 26 L1 / 119 L2", TASK_PALETTE)
    render_panel(
        domain_ax,
        domain_axis,
        "(b) Repository Domain — 21 L1 / 108 L2",
        DOMAIN_PALETTE,
    )

    fig.text(
        0.025,
        0.965,
        "A rich, factorized taxonomy for software-engineering tasks",
        ha="left",
        va="top",
        fontsize=13.0,
        fontweight="bold",
        color=INK,
    )
    fig.text(
        0.025,
        0.905,
        "47 semantic families  •  227 fine-grained labels  •  "
        "3 orthogonal axes / 12 scale levels",
        ha="left",
        va="top",
        fontsize=8.6,
        color=MUTED,
    )
    fig.text(
        0.025,
        0.025,
        "Tile area uses a 3-unit visibility floor, then follows L2 count; hatched gray "
        "tiles have no "
        "concrete child. Structural inventory, not sample frequency.",
        ha="left",
        va="bottom",
        fontsize=6.2,
        color=MUTED,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    png_path = output_dir / f"{OUTPUT_STEM}.png"
    pdf_path = output_dir / f"{OUTPUT_STEM}.pdf"
    fig.savefig(
        png_path,
        dpi=320,
        facecolor="white",
        metadata={"Software": "matplotlib", "Title": "SWE Label Taxonomy Atlas"},
    )
    fig.savefig(
        pdf_path,
        facecolor="white",
        metadata={
            "Title": "SWE Label Taxonomy Atlas",
            "Author": "",
            "Subject": "Structural taxonomy preview",
            "Keywords": "",
            "Creator": "matplotlib",
            "Producer": "matplotlib",
            "CreationDate": None,
            "ModDate": None,
        },
    )
    plt.close(fig)
    return png_path, pdf_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--definition-dir", type=Path, default=DEFAULT_DEFINITION_DIR)
    parser.add_argument("--output-dir", type=Path, default=FIGURE_DIR)
    args = parser.parse_args()

    png_path, pdf_path = generate(args.definition_dir, args.output_dir)
    print(f"PNG {png_path} sha256={file_sha256(png_path)}")
    print(f"PDF {pdf_path} sha256={file_sha256(pdf_path)}")


if __name__ == "__main__":
    main()

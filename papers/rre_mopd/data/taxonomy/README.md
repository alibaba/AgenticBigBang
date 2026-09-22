# Frozen taxonomy definitions

These three YAML files are exact copies of the shared SWE Labeler definitions
at this package snapshot. They make the two taxonomy figures independently
reproducible without requiring the repository-level labeling implementation.

- `task_type_l2.yaml`: 26 L1 families and 119 concrete L2 labels.
- `domain_l2.yaml`: 21 L1 families and 108 concrete L2 labels.
- `orthogonal.yaml`: 3 axes and 12 levels.
- `routing.json`: the manuscript's 18-family A/B/C whitelist, plus the three
  unrouted Domain-L1 families. This is the declared mapping rule.

The existing 1,531 per-instance annotations for the cross-benchmark profile
and structural audit are provided separately in
[`../labeling/`](../labeling/README.md), with a reproduction script.

From the paper package root:

```bash
python3 scripts/plot_taxonomy_atlas.py
python3 scripts/plot_taxonomy_breadth.py
```

Both commands require `pyyaml`, `numpy`, and `matplotlib` and write under
`results/figures/`; they do not overwrite the frozen `results/figures/paper/` assets.

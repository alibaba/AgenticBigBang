# Expanded SWE evaluation figure

The chart is generated from `aggregate_results.json`, which records the number
of passes and tasks in each of three evaluation rounds. To regenerate the
PNG, vector PDF, and editable SVG, run:

```bash
python3 plot_model_benchmark_comparison.py
```

The Qwen3 logo is from the [official Qwen3 repository](https://github.com/QwenLM/Qwen3)
and is retained as `qwen3_official.png` for reproducibility.

The design uses five horizontal panels, with each student placed beside its
corresponding base model. Bar heights share one zero-based percentage scale;
gains are calculated from unrounded values.

The [Flint model card](https://huggingface.co/RecursiveSI/flint) informed the
restrained typography and subtly rounded bar tops. This figure uses its own
teal and blue-gray palette, paired-model layout, cool neutral background, and
gain labels.

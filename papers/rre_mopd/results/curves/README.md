# Figure data

This directory contains pooled category-dynamics and training-metric curves.

## Category dynamics under pooled joint RL

These files contain the data for the pooled category-dynamics figure.

| File | Rows | Contents |
| --- | ---: | --- |
| `category_seesaw_source.csv` | 126 | Two replicates for each of 63 plotted progress points. |
| `category_seesaw_motivation.csv` | 64 | One baseline anchor plus 63 computed gain points, before smoothing. |

In the source CSV, `plot_step` is the figure's x coordinate; `round` is a local
replicate label (1 or 2). `Full`, `A`, `B`, and `C` are resolution percentages.
These curve replicates are separate from the three-round final-model evaluations
listed in `data/manifests/evaluation_runs.csv`.

In the computed CSV, `step` is the same plotting coordinate. `Full`, `A`, `B`,
and `C` are gains over the bundled Pro-618 Base means, in percentage points.
`G_sim` is the minimum of the three category gains; `SSG = Full - G_sim`.
The step-zero anchor has zero gains. Plot coordinates do not specify weight-file
identities or wall-clock training durations.

The plotting script validates each computed point against the two replicate
scores and Base means in `results/aggregate/evaluation_model_scores.csv`.
It uses a centered three-point mean, shortened at the endpoints, with the
baseline anchor fixed at zero. Faint lines show unsmoothed values.

From the package root, with `numpy` and `matplotlib` installed:

```bash
python3 scripts/aggregate_evaluation_results.py
python3 scripts/plot_category_seesaw.py
```

Outputs: `results/figures/fig_category_seesaw_motivation.pdf` and `.png`.

## MOPD training dynamics

`mopd_training_points.csv` has columns `metric,step,value`, with 263 rows:
136 `score` points (steps 0–135) and 127 `kl_mean` points (steps 0–126).
`score` is on the 0–1 scale and is multiplied by 100 for plotting;
`kl_mean` is plotted without rescaling. These are training metrics, not
three-round benchmark outcomes.

The plot shows raw values and a 20-point trailing arithmetic mean, with shorter
windows at the start. Its summary annotations compare steps 0–19 and 107–126,
the latter ending at the common last step of both metrics. All 136 score points
remain visible even though its summary ends at step 126.

```bash
python3 scripts/plot_mopd_training.py
```

Outputs: `results/figures/fig_mopd_training.pdf` and `.png`.

## RRE training dynamics

`rre_training_points.csv` has columns `stage,expert,plot_step,score`.
Its 1,806 rows comprise two stages (`stage1_rl`, Initial RL; `stage3_rl`,
Expanded RL) and three experts (A/B/C), each with 301 points at plotting
coordinates 0–300. `score` is on the 0–1 scale and is multiplied by 100 for
plotting. `plot_step` is an aligned figure coordinate, not a weight-file identity.

The script draws raw values and a 20-point trailing mean. The displayed y-axis
is 30–70%; triangle markers indicate raw points outside that range. Their full
values remain in the CSV and participate in smoothing.

```bash
python3 scripts/plot_rre_training.py
```

Outputs: `results/figures/fig_rre_training.pdf` and `.png`.
Both training plots require `matplotlib` and use only files within this package.

## Final-policy category gains and expert-gain recovery

This figure uses the existing evaluation task, run, and outcome tables; it has
no additional curve input file. For each Pro-A/B/C category, the script computes
each model's three-round mean and subtracts the Base mean in percentage points.
The corresponding expert is that category's `second_repair_sft` model.

Recovery is `100 * (MOPD mean - Base mean) / (expert mean - Base mean)`.
Values above 100% are retained. This ratio measures recovery of the expert's
gain over Base, not the ratio of absolute resolution rates.

```bash
python3 scripts/plot_category_gains.py
```

Requires `numpy` and `matplotlib`. Outputs:

- `results/aggregate/category_gains.csv`: 12 category/policy rows with means,
  gains, and MOPD recovery percentages; generated from the evaluation tables.
- `results/figures/fig_mopd_category_gains.pdf` and `.png`.

Scores use fixed category denominators and include missing outcomes as zero.
There is no smoothing in this bar chart; rounding is applied only to plot labels.

## Pooled versus balanced RL comparison

`pooled_balanced_scores.csv` contains 113 evaluation points: 63 Pooled and
50 Balanced. Each row contains two-round mean resolution percentages, not
individual-round results or final-model three-round scores.

Fields: method, evaluation_index (one-based within method), display_step
(evaluation_index multiplied by five), round_count (2), and Full/A/B/C.
The display coordinate is not elapsed training steps or matched compute.
Original checkpoint identifiers and earlier display offsets are not included.

Run `python3 scripts/plot_pooled_balanced.py` from the package root.
The script validates indices, score bounds, and the category-weighted Full
score with denominators 221/201/196. It renders the first 50 points of each
method (display coordinates 5–250), preserving all 63 Pooled points in the CSV.
Scatter points show the supplied two-round means. Lines use a centered
five-point moving average over the displayed series; boundary windows shorten.
No interpolation or baseline point is added.

Outputs: `results/figures/fig_pooled_balanced.pdf` and `.png`.
The script requires matplotlib. It reproduces this comparison figure only;
it does not reconstruct separate round scores. To reproduce the process
summary over these same 50 displayed points, run
`python3 scripts/reproduce_statistics.py`; see `scripts/STATISTICS.md`.

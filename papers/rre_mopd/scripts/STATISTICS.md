# Statistical reproduction

Run from the paper package root:

```bash
python3 scripts/aggregate_evaluation_results.py
python3 scripts/reproduce_statistics.py
```

Both scripts use only the standard library and package-local data.
The second command writes five CSV files under results/aggregate.

## Training diagnostics

- training_record_summary.csv: three phase means and their differences.
- training_record_changes.csv: higher/equal/lower counts for RL versus Base,
  SFT versus Base, and SFT versus RL, plus positive/negative contributions.
- repair_record_cohorts.csv: recovery and gain-retention counts and percentages.

The Initial-RL record manifest supplies multiplicities: A=601, B=516,
C=1652, total=2769. Rates come from the 2768-task mastery table. A repeated
record shares its task's observed rate, rather than representing a new probe.
Comparisons use exact fractions before rounding. Missing or invalid counts
raise errors. The repair manifest supplies actual exposure, not a causal
control. Its trajectory counts are not multiplied by record multiplicity.

## Multilingual intervals

multilingual_paired_bootstrap.csv compares MOPD to Base, pooled, and balanced.
Each task's binary scores are averaged over three rounds before differences
are formed. All 300 tasks, including unrouted tasks, are retained. Task IDs
are sorted. For each comparison, Python Random(20260911) draws 10000 paired
resamples of 300 tasks with replacement. Bounds use sorted draw indices
249 and 9749 (zero-based), matching the manuscript calculation rather than
an interpolated percentile convention. Outputs are percentage points.
Stored zero scores remain zero; missing task rows trigger an error.

## Pooled/balanced process statistics

pooled_balanced_process_summary.csv uses the first 50 evaluation points per
method, matching the displayed plot. Each point is already a two-round mean.
Subtract the three-round Base category means, calculate Gsim as the minimum
of the A/B/C gains, then SSG as Full gain minus Gsim. Average these unsmoothed
point-level quantities. The final Full gain uses the separately recorded
three-round final-model scores, not the last curve point. Display indices
are not matched training steps or equal-compute observations.

No inference settings or historical evaluation scores are altered by these
scripts. Numeric outputs are full precision; paper tables round to two decimals.

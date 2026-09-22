# Manuscript figures and reproduced plots

`paper/` contains the **10 exact image assets referenced by the full manuscript**,
in main-text and appendix order. `figure_manifest.csv` records their paths and
SHA-256 hashes. These are frozen manuscript images, not additional observations.
The neighboring PDF/PNG pairs are package-local re-renderings of the result plots;
fonts, rendering versions, definition order, or metadata can differ without changing the data.

| Order | Manuscript asset in `paper/` | Supporting material |
| --- | --- | --- |
| 1 | fig_category_aware_agentic_rl_framework.png | Conceptual overview; no empirical input table. |
| 2 | fig_category_seesaw_motivation.pdf | `../curves/category_seesaw_source.csv`, computed gains, `../../scripts/plot_category_seesaw.py`. |
| 3 | fig_label_taxonomy_atlas.pdf | `../../data/taxonomy/`, `../../scripts/plot_taxonomy_atlas.py`. |
| 4 | full_new_rre_png.png | Conceptual RRE diagram; no empirical input table. |
| 5 | fig_pooled_balanced_contiguous_20260917.pdf | `../curves/pooled_balanced_scores.csv`, `../../scripts/plot_pooled_balanced.py`. |
| 6 | fig_rre_training.pdf | `../curves/rre_training_points.csv`, `../../scripts/plot_rre_training.py`. |
| 7 | fig_mopd_training.pdf | `../curves/mopd_training_points.csv`, `../../scripts/plot_mopd_training.py`. |
| 8 | fig_mopd_category_gains.pdf | Evaluation task/run/outcome tables, `../../scripts/plot_category_gains.py`. |
| 9 | fig_label_taxonomy_breadth.pdf | `../../data/taxonomy/`, `../../scripts/plot_taxonomy_breadth.py`. |
| 10 | label_to_category_figma.pdf | Conceptual routing diagram; no empirical input table. |

Taxonomy plots require `pyyaml`, `numpy`, and `matplotlib`. Their counts describe
the definition inventory (26/119 Task-Type and 21/108 Domain labels; 3/12 scale
axes/levels), not the empirical label distribution of any dataset. The atlas
uses a three-unit visibility floor; its tile areas are not strictly proportional
to L2 counts for families with fewer than three children.

The manuscript figure assets retain third-party generation/software credits.
No author identity, company deployment address, or private provenance was added.
Do not replace original benchmark text or delete third-party credits to suppress
generic company-name keyword matches.

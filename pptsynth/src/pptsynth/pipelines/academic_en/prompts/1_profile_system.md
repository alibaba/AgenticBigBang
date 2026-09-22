# Stage 1: Paper Profile

Your job in this session: read `material.pdf` carefully and produce a single
JSON object — a *Paper Card* — that captures every piece of information the
downstream stages need to write a high-quality, professional PPTSynth
academic task case. You will not write any other files in this stage. The
Paper Card you produce is the **only** thing the next stages will see.

## Inputs available in this session

- `material.pdf` in the working directory.
- A JSON Schema named `paper_card.schema.json` mounted into the working
  directory; your final JSON must validate against it.
- An optional file `_hint.txt` may exist with the paper's filename and
  the OpenReview-style ID extracted from the filename. Use it only as a
  weak prior for the title; the PDF is authoritative.

You have read access to nothing else. Do not search the web. Do not infer
metadata you cannot find in the PDF itself.

## Mandatory reading procedure

Do this even if you think you can skip it. Skipping is the single most
common cause of low-quality task synthesis.

1. **Pass A — Structural map.** Read pages 1-2 of `material.pdf` (title
   page + abstract + intro). Capture: exact title, full author list with
   `*` for equal contribution if marked, primary affiliations, and the
   abstract.
2. **Pass B — Body and figures.** Read the full body using a single
   wide-range Read call (e.g. `pages: "3-N"` where N is the last
   non-references page). Note every figure id, table id, the page it
   appears on, what it shows, and its caption sentence. Note the exact
   numerical results in the abstract, the results section, and any
   summary table.
3. **Pass C — Specifics worth a checklist.** Now scan again for: defined
   terms (acronyms, named modules, named losses), method-level
   distinctions the paper draws against prior work (e.g.
   "decision-level vs feature-level", "regression vs diffusion"),
   non-monotone trends or sweet spots, scope and dataset boundaries, and
   limitations or future-work caveats.
4. **Pass D — Trap hunt.** For each of these eight trap kinds, decide
   whether the paper presents a risk and capture it with both wrong and
   right phrasings:
   - `fabrication` — content the deck might invent that is not in the
     paper (e.g. additional experiments, deployment claims, comparisons
     not run).
   - `metric_misread` — an aggregate metric easily confused with a
     conditional one (e.g. "average accuracy" versus "worst-group
     accuracy").
   - `non_monotone_flattened` — a U-shape, inverted-U, or sweet spot
     described in the paper that a careless deck would flatten to "more
     is always better".
   - `method_level_confusion` — paper carefully distinguishes pipeline
     levels (e.g. "decision-level fusion" versus "feature-level fusion",
     "post-hoc" versus "training-time").
   - `scope_overclaim` — the paper proves a claim under a specific
     setting (sparse views, simulation only, in-the-wild N-shot) that a
     deck might overgeneralize.
   - `unit_or_definition_error` — quantities that are easy to render
     with the wrong unit, base rate, or definition.
   - `trend_direction_error` — a "decreased / increased / earlier /
     later" claim that a careless deck reverses.
   - `ablation_misattribution` — gains the paper attributes to a
     specific component that a deck might attribute to the whole system.

## Filling the Paper Card

The schema is the contract. Read it before writing anything. A few
high-leverage clarifications:

- `central_thesis`: one sentence capturing **problem + method + headline
  result/tradeoff**. Avoid "studies", "investigates", "explores".
- `page_count_range`: usually `[16, 20]`. Use `[14, 18]` for short
  papers (≤9 pdf pages of body) and `[18, 22]` for long, dense papers.
- `ordered_sections`: ≥11 entries, ≤14, in this canonical order
  (omit `visual_analysis` if there is no visual results worth a
  dedicated section; otherwise include exactly one):
  1. `title`
  2. `outline`
  3. `background`
  4. `limitations` (of existing methods)
  5. `method_overview`
  6. `methodology`
  7. `algorithm` (training procedure / loss / inference algorithm; may
     be combined into `methodology` if the paper is short — but if so
     mark its kind as `algorithm` and place it between methodology and
     datasets)
  8. `datasets`
  9. `setup` (experimental setup — baselines, metrics)
  10. `results`
  11. `visual_analysis` (optional — qualitative samples, ablation
      plots, uncertainty visualizations)
  12. `takeaways_limitations`
  13. `conclusion`
- For section `kind: title`, `bullets` must contain exactly four
  entries in this exact format:
  - `Paper Title: <full title>`
  - `Author Team: <authors>`
  - `Affiliation: <affiliations>`
  - `Conference: <full name + year>`
- For section `kind: outline`, `bullets` is `[]` (the deck will list
  itself).
- For every other section, give 2-5 bullets in `Label: qualitative
  claim` format, each bullet ≤ 25 words. Bullets describe **what
  topic/angle the slide must cover** and **what qualitative framing
  to highlight**. They are paper-specific at the topic / mechanism /
  dataset / baseline-name level (so they cannot be swapped into
  another paper unchanged), but they DO NOT pre-disclose specific
  numerical values, accuracy rankings, or `+/-Δ` gains — those are
  the answers the slide-generation model is supposed to retrieve from
  the PDF and earn credit for putting on slides.

  GOOD examples — bullets describe **scope** (what the slide must
  address: the question, the comparison structure, the topic).
  Note the recurring pattern *"describe the exact X used"* / *"state
  the X in big-O form"* / *"name the X without listing values"*:
  the bullet names the slot and hands the value-filling to the deck.
  - `Core Idea: Recast pose inference as patch-wise ray prediction, treating a camera as a bundle of rays represented in Plücker coordinates.`
  - `Step 1: Camera to Ray Bundle: Unprojecting pixel coordinates into 6-D Plücker rays using camera intrinsics and extrinsics.`
  - `State-of-the-Art Performance: Compare ray regression and diffusion models against existing learning-based and correspondence-based baselines on the headline pose-estimation benchmark.`
  - `Generalization: Address robustness on unseen object categories and in-the-wild self-captures.`
  - `Iteration Complexity: State the ergodic convergence rate under random block selection in big-O form, citing the relevant theorem.`
  - `Pretraining Scale: Describe the pretraining corpus by source family and order-of-magnitude, leaving the exact sample count to the deck.`
  - `Inference Cost: Outline the runtime budget per query relative to baselines, scoped to the evaluation hardware described in the paper.`
  - `Network Architecture: Describe the bipartite two-layer topology and the visible/hidden sizes used per dataset, leaving the exact dimensions to the deck.`
  - `Per-iteration Complexity: State how the subproblem cost scales with problem size and block size, naming the asymptotic regime in which OBCD wins.`
  - `MNIST Setup: Store digit images in a network with a small hidden-layer size (N_h ≪ image count); describe the exact N_v, N_h, and image count used.`
  - `CIFAR-10 Setup: Use a larger hidden layer than MNIST to handle the more complex correlated images; describe the exact dimensions used, highlighting the scaling argument.`
  - `Hyperparameters: Name the optimizer, learning-rate schedule, and seed-count protocol used for ablations, deferring the numeric values to the deck.`

  BAD examples — these bullets are in **answer-shape** (a reader of
  the bullet alone could write the slide without opening the PDF):
  - `BLINK-Depth: 90.3% accuracy versus SpatialRGPT 87.9% and human ceiling 98.3%.`              ← named values
  - `Headline: Sets new SOTA on Scan2Cap CIDEr 97.9, ScanQA EM 30.4, SQA3D EM 62.2.`             ← value list
  - `Tile Ablation: +17.1 AP-Small from tile-and-stitch on COCO.`                                ← Δ + attribution
  - `Convergence: Theorem 3.8 establishes E[‖∇f(x_k)‖²] ≤ O(1/ε) iterations under uniform sampling.`  ← theorem verbatim
  - `Pretraining Scale: 7 million paired image-text examples drawn from LAION-2B.`              ← exact dataset size
  - `Inference Cost: 30 seconds of CPU per query on a single A100.`                              ← setup constant
  - `MNIST: Stores digit images; network uses N_v = 784 visible neurons and N_h = 50 hidden neurons.`  ← architecture constants
  - `Per-iteration Cost: O(nr + rk² + k³) per iteration versus O(n²r) for full-gradient methods.`     ← O(...) bound stated as the bullet's payload
  - `Theory: OBCD provides O(1/ε) ergodic complexity to ε-BS_k stationarity.`                    ← O(1/ε) stated as the bullet's payload
  - `Training: 5 random seeds, batch size 256, learning rate 1e-4 for 100 epochs on 8×A100.`     ← training hyperparameters listed
  - `MNIST: 60,000 training images stored with N_h = 500 hidden neurons.`                       ← dataset count + architecture constant

  The contrast is structural, not stylistic. The GOOD bullets state
  *what to address* (rate, scale, runtime budget); the BAD bullets
  state *what to say* (the specific value, theorem, or constant).
  When in doubt: *could the deck still earn its grade by reading the
  PDF and putting the right number on the slide?* If yes, the bullet
  is in scope-shape; if the bullet already supplies the number, it
  is in answer-shape and must be rewritten. **Architecture sizes
  (N_v, N_h, layer widths, head counts), training hyperparameters
  (batch size, learning rate, epoch count, seed count), and
  asymptotic complexity expressions (O(...), Ω(...), Θ(...)) are
  all answer-shape even when they are not "results" — they are
  setup-side answers the deck should retrieve from the PDF.**
- Sections of kind `methodology`, `algorithm`, `results`,
  `visual_analysis`, and `limitations` SHOULD include a
  `design_constraint`. The `design_constraint` must reference an
  identifier you actually saw in the PDF and describe **what topic
  the figure/table covers**, never the specific value it contains.

  GOOD: `Display the conversion process diagram (refer to Fig 2) showing the flow between traditional camera parameters and Plücker rays.`
  GOOD: `Include the results table (refer to Tab 1 & 2) covering the comparison against PoseDiffusion and RelPose++.`
  GOOD: `Display the convergence plot (refer to Fig 4) showing how iterate-error scales with iteration count.`
  BAD: `Cite Table 13 to anchor the +17.1 AP-Small isolation result for the tile-and-stitch ablation on COCO classification.`
  BAD: `Display Table 4 showing 90.3% BLINK-Depth versus SpatialRGPT 87.9%.`
  BAD: `Include Theorem 3.8: E[‖∇f(x_k)‖²] ≤ O(1/ε).`
- `key_numbers` ≥ 6 entries. Each `claim` is a complete anchor in the
  form "value + unit + condition", not a bare number.
- `key_figures` ≥ 4 entries. Use the exact identifier the paper uses,
  e.g. `Fig 2`, not `Figure 2`. If the paper writes `Figure 2`, use
  `Figure 2`.
- `key_terms` ≥ 5. For each, give a one-sentence definition the deck
  must respect. If a careless deck would confuse it with another
  concept, fill `common_confusion`.
- `traps` ≥ 4. Use distinct `kind` values whenever possible to give
  Stage 3 enough material for a discriminating rubric.

## Anti-Pre-Disclosure (critical) — three principles

The slide-generation model will see only the rendered
`instructions.md`, never the Paper Card. Three principles keep
scope content and answer content cleanly separated.

### Principle 1 — Disjoint sets

The Paper Card's fields split into two roles by construction:

- **Scope fields** — `ordered_sections[*].bullets` and
  `ordered_sections[*].design_constraint`. These flow into
  `instructions.md`.
- **Answer fields** — `key_numbers[*].claim`,
  `key_terms[*].definition`, `traps[*].correct_form`, and the
  values cited in `key_figures`. These flow exclusively into the
  Stage 3 rubric and are **the score key**.

Anything you place in an answer field is by definition something
the deck must extract from the PDF to earn credit. Therefore: any
specific value, named comparison, theorem statement, complexity
bound, dataset size, setup constant, or correct phrasing that
appears in an answer field must NOT also appear inside a scope
field. Define answer content **once**, in the answer field.
Reference it from scope fields only by *what kind of fact it is*,
never by *the fact itself*.

### Principle 2 — Scope-shape, not answer-shape

Each bullet describes **what the slide must address** — the
question to answer, the comparison to make, the topic to cover —
not **what the slide will say**. The test is mechanical:

> Could a reader of the bullet alone, without opening the PDF,
> write down the slide's quantitative claim, theorem statement,
> complexity bound, dataset size, setup constant, or correct
> phrasing?

If yes, the bullet is in answer-shape and must be rewritten. The
shapes contrast like this:

- Numbers/scores — scope: *"Compare X and Y on the headline
  metric."*  answer: *"X 90.3 vs Y 87.9."*
- Theorems/complexity — scope: *"State the ergodic convergence
  rate, citing Theorem 3.8."*  answer: *"E[‖∇f‖²] ≤ O(1/ε)."*
- Dataset size — scope: *"Describe the pretraining corpus by
  source family and order-of-magnitude."*  answer: *"7M
  image-text pairs from LAION-2B."*
- Setup constants — scope: *"Outline the runtime budget per query
  on the paper's evaluation hardware."*  answer: *"30 s/query on
  A100."*
- Trap correction — scope: *"Distinguish decision-level fusion
  from feature-level fusion in the method narrative."*  answer:
  *"the model fuses at the decision level, not the feature
  level."*

The point is not to enumerate banned tokens. It is that bullets
answer the meta-question *"what does this slide need to talk
about?"* and never the object-level question itself.

### Principle 3 — Mirror check before writing

Before emitting `_paper_card.json`, walk every bullet and every
`design_constraint` and ask four questions. Questions 1-3 mirror
the bullet against the answer fields next door; **question 4
catches setup-side answers that are NOT in any answer field but
are still concrete tokens the deck must retrieve from the PDF.**

1. Does it contain a numeric token (digit + unit, %, ×, ratio,
   sample count, runtime, hardware spec) that also appears or can
   be paraphrased into a `key_numbers[*].claim`? If yes, move the
   token out — keep the topical framing, drop the value.
2. Does it state a theorem, a `≤`/`≥` inequality, an O(...)
   complexity bound, or a definition that overlaps with a
   `key_terms[*].definition` or a `traps[*].correct_form`? If
   yes, replace the statement with a reference to the *kind* of
   fact (`State the ergodic convergence rate`, `Define the named
   module`).
3. Does it name a dataset size, sample count, parameter count,
   training duration, or hardware spec that overlaps with any
   `key_numbers` entry? If yes, abstract to scope-shape framing
   (*order-of-magnitude*, *runtime budget*, *evaluation
   hardware*).
4. **(Independent of answer fields.)** Does it spell out an
   **architecture dimension** (`N_v = 784`, `N_h = 50`,
   `12 hidden layers`, `dim = 1024`), a **training
   hyperparameter** (`batch size 256`, `learning rate 1e-4`,
   `5 random seeds`, `95% CIs`), or an **asymptotic complexity
   expression** as the bullet's payload (`O(nr + rk² + k³)`,
   `O(1/ε)`, `Ω(n log n)`)? These are setup-side and theory-side
   answers — even when they do not duplicate a `key_numbers`
   entry, the deck is still expected to read them off the paper.
   Rewrite to scope-shape: *describe the bipartite topology and
   per-dataset visible/hidden sizes used*, *state the ergodic
   complexity in big-O form, citing the relevant theorem*. Do
   NOT fall back to "Theorem N.M holds" + a separate bullet
   carrying the bound — the bound itself is the answer regardless
   of which bullet hosts it. Equivalently for phrase forms: `784
   visible neurons` or `50 hidden neurons` is just as answer-shape
   as `N_v = 784`; the test is whether the deck can write the
   number without reading the PDF.

A bullet that survives the mirror check no longer doubles as the
rubric's score key.

## Self-refinement pass (before writing _paper_card.json)

After drafting bullets for every `ordered_section`, perform a
**self-refinement pass** before writing the JSON to disk:

1. **Count total bullets in Section 1** across all `ordered_sections`,
   excluding the four fixed Title-slide fields (Paper Title / Author
   Team / Affiliation / Conference) and the empty Outline section's
   `[]`.
2. **Target total: 35-40 bullets.** PPTSynth academic
   tasks cluster in this range. The per-section count need NOT be
   uniform — Methodology, Results, and Algorithm may legitimately
   carry 4-5 bullets, while Datasets, Conclusion, Background,
   Limitations, and Setup often need only 2-3. Let the paper drive
   the shape, not a uniform quota.
3. **If draft total > 40, trim** the lowest-yield bullets first.
   Drop a bullet that:
   - Restates a point already covered in another bullet of the same section.
   - Describes a sub-detail (one ablation cell, one hyperparameter)
     rather than a slide-level topic.
   - Reads as filler ("approach is effective", "method is novel",
     "improves performance").
   - Lives in an over-staffed section (5+ bullets in datasets,
     conclusion, background, limitations).
4. **Prefer dropping over merging.** Merge two bullets into one ONLY
   when they describe the same mechanism from different angles AND
   the combined sentence stays ≤ 25 words and keeps the
   `Label: claim` shape.
5. **If draft total < 35**, you've under-described the paper. Add
   bullets to the most central sections (Methodology, Results,
   Algorithm, Method Overview, Visual Analysis) until you reach 35.
   New bullets must obey the Anti-Pre-Disclosure rules above.

The refined Paper Card is what you write to `_paper_card.json`. Do
not write a draft to disk and then rewrite it; do the refinement
in-head before the single Write call.

## Anti-goals

- Do not paraphrase abstract back; the abstract is not a checklist.
- Do not number results with placeholder values like "≈X%" in
  `key_numbers`. Fill real numbers there. (Bullets stay value-free
  per Anti-Pre-Disclosure above; specific values live in
  `key_numbers`.)
- Do not list bullets that read like a textbook ("Define neural
  networks"). Bullets must be specific to *this* paper at the topic
  level.
- Do not use Chinese, even if the PDF is partly Chinese. The Paper
  Card and downstream task are English.

## Final response

After you have written the JSON to `_paper_card.json` using the Write tool,
emit **only** that JSON object as your final assistant message. No
markdown fences, no prose, no commentary.

**Do not run validation commands.** Do not call Bash or Python to check
the JSON, count items, or re-read what you wrote. The harness validates
the file rigorously against the schema after this stage; redundant checks
here only burn turns. One thorough read of the PDF, one Write of the
JSON, one final assistant message — that is the entire stage.

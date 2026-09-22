# Stage 1: Finance Document Profile

Your job in this session: read `material.pdf` carefully and produce a single
JSON object — a *Finance Doc Card* — that captures every piece of information the
downstream stages need to write a high-quality, professional PPTSynth
**economics/finance** task case. You will not write any other files in this
stage. The Doc Card you produce is the **only** thing the next stages will see.

Read the **Domain Context** appended to the end of this prompt first: it tells
you the document *family* (A = corporate disclosure, B = macro flagship), the
sub-genre, the reading approach, the suggested section template, the domain
terminology, the title-slide fields, and the finance trap catalogue to use.

## Inputs available in this session

- `material.pdf` in the working directory.
- `_case_meta.json` — ground-truth metadata for this document (family,
  sub_genre, issuer, reporting_period, pages). Trust it for `family`,
  `sub_genre`, `issuer`, and `reporting_period`; the PDF is authoritative for
  everything else (title, values, structure).
- `paper_card.schema.json` (the Doc Card JSON Schema) mounted into the working
  directory; your final JSON must validate against it.

Do not search the web. Do not infer metadata you cannot find in the PDF or
`_case_meta.json`.

## Mandatory reading procedure

Do this even if you think you can skip it. Skipping is the single most common
cause of low-quality task synthesis.

1. **Pass A — Structural map.** Read the cover / first pages: exact document
   title, issuer, reporting period, publication date, and the top-line summary
   or key-messages section.
2. **Pass B — The numbers.** Read the core quantitative content:
   - **Family A:** the income statement, the segment tables, and any
     capital/liquidity/cash-flow table. Capture each headline value WITH its
     unit (billion/million), its GAAP/non-GAAP (or constant-currency) label,
     and its period (which quarter/year; YoY or sequential).
   - **Family B:** the executive summary, the GDP and inflation **projection
     tables**, and the numbered exhibits. Capture each projection WITH its
     region/country, its horizon (which year), whether it is real or nominal,
     and whether it is a baseline or a scenario value. For long reports
     (100+ pages) do NOT read linearly — target the summary, the projection
     tables, the exhibits, then sample the regional/policy chapters using the
     `pages` parameter of Read.
3. **Pass C — Specifics worth a checklist.** Scan for: defined finance/econ
   terms (non-GAAP, constant currency, CET1, core inflation, output gap,
   baseline scenario…), management quotes and their attributed speaker
   (Family A), key policy recommendations (Family B), and any narrative that a
   careless deck would distort.
4. **Pass D — Trap hunt.** Use the **finance trap catalogue in the Domain
   Context** for your family. For each trap kind that the document actually
   presents a risk for, capture both the wrong phrasing (`claim_to_avoid`) and
   the faithful phrasing (`correct_form`). Aim for ≥4 distinct kinds. Common,
   high-value finance traps:
   - GAAP vs non-GAAP / adjusted figures (A).
   - Year-over-year vs sequential (QoQ) (A).
   - Net income vs net income attributable to shareholders (A).
   - Constant-currency vs reported growth (A).
   - Nominal vs real GDP growth (B).
   - Headline vs core inflation (B).
   - Basis points vs percentage points (B).
   - Forecast/projection vs realized historical value (B).
   - Baseline vs downside/alternative scenario (B).
   - Segment / region misattribution; unit-scale (million vs billion) errors.

## Filling the Doc Card

The schema is the contract. Read it before writing anything. High-leverage
clarifications:

- `family`, `sub_genre`, `issuer`, `reporting_period`: copy from
  `_case_meta.json`.
- `central_thesis`: one or two sentences. For A: the quarter's performance
  narrative and its main driver. For B: the growth/inflation assessment and its
  main policy implication. Avoid vague verbs ("discusses", "covers").
- `page_count_range`: default `[15, 20]` (matches PPTSynth economics gold).
  Use `[12, 16]` for a short update letter, `[16, 20]` for a dense report.
- `ordered_sections`: 8-16 entries following the **family section template in
  the Domain Context**, adapted to what the document actually contains. Start
  with a `title` section and end with a `closing`/`conclusion` section. Omit a
  templated section if the source does not support it; do not invent one.
- For section `kind: title`, `bullets` must contain exactly four entries in
  this exact format (these are the same for both families):
  - `Report Title: <full document title>`
  - `Issuer: <company (A) or institution (B)>`
  - `Reporting Period: <fiscal period (A) or edition/date (B)>`
  - `Publication Date: <announcement/release date, or "not stated">`
- For section `kind: outline`, `bullets` is `[]`.
- For every other section, give 2-5 bullets in `Label: qualitative claim`
  format, each ≤ 25 words. Bullets describe **what topic the slide must cover**
  and **what qualitative framing to highlight** — document-specific at the
  metric-name / segment / region / theme level (so they cannot be swapped into
  another document unchanged), but they DO NOT pre-disclose specific values.

  GOOD examples (scope-shape — the deck must still open the PDF to fill values):
  - `Top-Line Results: Present revenue, operating income, and net income for the quarter, with the GAAP vs non-GAAP distinction stated.`
  - `Segment Breakdown: Give revenue and profit for each reported business segment, highlighting the fastest-growing segment.`
  - `Growth Context: Show the quarter's revenue growth, distinguishing reported, constant-currency, and year-over-year framings.`
  - `Inflation Outlook: Present the projected inflation path, distinguishing headline and core, and the implied policy stance.`
  - `Regional Divergence: Compare the growth projections across advanced economies and EMDEs for the projection horizon.`

  BAD examples (answer-shape — a reader could write the slide without the PDF):
  - `Executive Summary: Revenue $62.0 billion, operating income $27.0 billion, net income $21.9 billion.`   ← named values
  - `Growth: Revenue up 18% YoY, Azure up 30% GAAP / 28% CC.`                                                ← growth values
  - `Segment: Intelligent Cloud revenue $25.9 billion, up 20%.`                                              ← value + attribution
  - `Inflation: Core inflation projected at 2.4% for 2024, down from 3.1%.`                                  ← projection values
  - `Reserve Build: $6.8 billion reserve build cut EPS by $1.66.`                                            ← value + effect

  The contrast is structural: GOOD bullets state *what to address* (which
  metric, which comparison, which distinction); BAD bullets state *what to say*
  (the specific dollar figure, percentage, or basis-point value). When in
  doubt: *could the deck still earn its grade by reading the PDF and putting the
  right number on the slide?* If yes, the bullet is scope-shape; if the bullet
  already supplies the number, rewrite it.

- Sections of kind `income_statement`, `segment_performance`,
  `growth_forecasts`, `inflation_forecasts`, `regional_breakdown`, and
  `exhibits` SHOULD include a `design_constraint`. It must name WHICH
  table/chart/exhibit the slide presents and WHAT TOPIC it shows, never a value.

  GOOD: `Present a table comparing all reported business segments on revenue and profit (refer to the segment table).`
  GOOD: `Include the GDP projection table showing growth by region across the projection horizon.`
  BAD: `Present the segment table showing Intelligent Cloud at $25.9B up 20%.`
  BAD: `Show the table with 1.7% GDP growth for 2024.`

- `key_numbers` ≥ 6. Each `claim` is a complete anchor: value + unit +
  GAAP/non-GAAP or real/nominal label (where relevant) + period/region. These
  are number-dense documents — capture the headline income-statement values,
  the per-segment values, the key growth/inflation projections, and any other
  figure a faithful deck must reproduce.
- `key_figures` ≥ 3. Use the label the document uses (e.g. `Exhibit 3`,
  `Segment Table`, `GDP Projections Table`, `page 4 chart`).
- `key_terms` ≥ 4. Finance/econ terms the deck must use correctly; fill
  `common_confusion` when a careless deck would misuse the term.
- `traps` ≥ 4, using distinct `kind` values from the family trap catalogue.

## Anti-Pre-Disclosure (critical) — three principles

The slide-generation model will see only the rendered `instructions.md`, never
the Doc Card. Keep scope content and answer content cleanly separated.

### Principle 1 — Disjoint sets
- **Scope fields** — `ordered_sections[*].bullets` and
  `ordered_sections[*].design_constraint`. These flow into `instructions.md`.
- **Answer fields** — `key_numbers[*].claim`, `key_terms[*].definition`,
  `traps[*].correct_form`, and the values behind `key_figures`. These flow
  exclusively into the Stage 3 rubric and are **the score key**.

Any specific dollar value, percentage, growth rate, basis-point figure,
EPS/ratio, projection, or correct phrasing that appears in an answer field must
NOT also appear inside a scope field. Define answer content **once**, in the
answer field. Reference it from scope fields only by *what kind of fact it is*.

### Principle 2 — Scope-shape, not answer-shape
Each bullet describes **what the slide must address**, not **what it will say**.
Mechanical test:

> Could a reader of the bullet alone, without opening the PDF, write down the
> slide's dollar figure, percentage, growth rate, basis-point value, or
> projection?

If yes, rewrite to scope-shape. Examples:
- Revenue — scope: *"Present the quarter's revenue with the GAAP/non-GAAP
  distinction."*  answer: *"$62.0 billion, up 18%."*
- Inflation — scope: *"Present the projected inflation path, headline vs
  core."*  answer: *"core 2.4% for 2024."*
- Trap correction — scope: *"Distinguish reported growth from constant-currency
  growth."*  answer: *"Azure grew 30% GAAP but 28% in constant currency."*

### Principle 3 — Mirror check before writing
Before emitting `_paper_card.json`, walk every bullet and every
`design_constraint` and ask: does it contain a monetary value, a percentage, a
growth rate, a basis-point figure, an EPS/ratio, or a projection that also lives
(or could be paraphrased) in an answer field? If yes, strip the value and keep
the topical framing. A bullet that survives no longer doubles as the score key.

## Self-refinement pass (before writing)

After drafting bullets for every `ordered_section`, count total Section-1
bullets (excluding the four title fields and the empty outline). **Target
30-40 bullets.** Let the document drive the shape — income statement, segment
performance, and forecast sections may carry 4-5 bullets; closing and risk
sections often need only 2. If over 40, trim the lowest-yield bullets (filler,
duplicates, single-cell sub-details). If under 30, you have under-described the
document; add bullets to the most central sections, obeying anti-pre-disclosure.
Do the refinement in-head; write the file once.

## Anti-goals
- Do not paraphrase the executive summary back as bullets; it is not a
  checklist.
- Do not put placeholder values ("≈X%") in `key_numbers`; fill real values
  there (bullets stay value-free).
- Do not expand or reinterpret forward-looking statements or risk factors.
- Output is English regardless of anything else.

## Final response

After writing the JSON to `_paper_card.json` using the Write tool, emit **only**
that JSON object as your final assistant message. No markdown fences, no prose.

**Do not run validation commands.** Do not call Bash/Python to check the JSON.
The harness validates the file against the schema after this stage. One thorough
read of the PDF, one Write of the JSON, one final assistant message.

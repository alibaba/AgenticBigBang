# Stage 3: Author the Judge Rubric

Your job: produce a single JSON file `generation_task/judge_prompt.json`
containing two arrays of binary rubric items styled exactly like required
PPTSynth **economics** checklists (Microsoft / JPMorgan earnings decks,
OECD / World Bank / IMF outlook decks). Nothing else goes into this file. The
material-dependent prefix and the per-slide fidelity checklist are appended
later by the harness.

Read the **Domain Context** at the end for the document family and its finance
trap catalogue.

## Inputs

- `_paper_card.json` — the validated Doc Card.
- `generation_task/instructions.md` — the rendered task. Each completeness item
  must map to something the deck is required to contain by `instructions.md`.
- `_field_manifest.txt` — auto-generated list of every key_number, trap, and
  confusable key_term. **You MUST cover every entry listed in this manifest.**

## Output shape

A JSON object with **only** these two keys:

```json
{
  "material_dependent_checklist_1": [ "<string>", "<string>", ... ],
  "material_dependent_checklist_2": [ "<string>", "<string>", ... ]
}
```

- `material_dependent_checklist_1` — **Content Completeness** (C1).
- `material_dependent_checklist_2` — **Content Correctness** (C2).

No other keys. No prefix. No comments.

## Item style (match required format exactly)

Every item is one Markdown-flavored string.

Completeness item shape:
```
\n**<binary question>?**\n\n  Note: You only need to check whether the slides contain the required contents; you do not need to verify their correctness.\n  If **no**, <what to describe>.\n
```

Correctness item shape:
```
\n**<binary question with concrete anchor>?**\n\n  If **no**, <what to describe>.\n
```

Structural details:
- Each string starts with `\n` and ends with `\n`.
- The question is wrapped in `**...**` and ends with `?`.
- Completeness items carry the verbatim "Note:" line above.
- Correctness items have no Note line — just the question and "If **no**, …".
- Every correctness item's "If **no**, …" must instruct the judge to answer no
  if (a) the value differs from the document, (b) a required label is wrong
  (GAAP/non-GAAP, real/nominal, headline/core, baseline/scenario, YoY/QoQ), or
  (c) quantitative content is shown without a data-source citation
  (e.g. page/table/exhibit). Fold this into the "If **no**" clause.

## Content rules

### Completeness checklist (C1)

#### Always-required items (exactly 3):
1. Title slide includes the report title, issuer, and reporting period.
2. An executive-summary / overview slide presenting the headline top-line
   figures (Family A) or the headline assessment (Family B).
3. A closing slide: forward-looking-statements disclaimer + investor contacts
   (Family A), or a conclusion + data-source note (Family B).

#### Document-specific items:
Generate one item per DISTINCT content block from `ordered_sections`. The count
is driven by the document — do NOT force a fixed number. Use the suggested count
from `_field_manifest.txt` as a guide. Typical range: **10-14 items total**
(3 always-required + 7-11 document-specific).

Rules:
- Use the document's own terms and named segments/regions/metrics.
- **Family A:** include a completeness item requiring a dedicated slide (or
  slides) covering ALL reported business segments by name.
- **Family B:** include a completeness item requiring the GDP-growth projection
  coverage and the inflation projection coverage across the reported
  regions/horizon.
- Describe table/chart CONTENT, not numbers ("a table comparing all segments on
  revenue and profit", not "Table 2").
- Each item tests ONE concept — split multi-part sections into separate items.

### Correctness checklist (C2)

#### Suggested functional types:
- **Definitional accuracy**: key_terms with common_confusion — "Is X correctly
  defined as ... rather than ...?" (e.g. non-GAAP vs GAAP, core vs headline).
- **Quantitative match**: embed values from key_numbers WITH unit + label +
  period/region (e.g. "GAAP revenue of $X billion for the quarter").
- **Label correctness**: reported vs constant-currency, real vs nominal,
  YoY vs QoQ, baseline vs scenario.
- **Segment / region accuracy** (Family A / Family B): per-segment revenue and
  net income; per-region/horizon growth and inflation projections.
- **Anti-fabrication**: traps of kind `fabrication` with "X rather than Y".
- **Data attribution**: the source of every cited number.

#### Mandatory coverage rules:
- You MUST reference ALL key_numbers entries across correctness items. Each
  key_number must appear as a concrete anchor in at least one item.
- You MUST create at least one item per traps entry, using the trap's
  `correct_form` as the correct answer and `claim_to_avoid` as the wrong
  alternative. Format: "correctly stated as X, not Y" or "X rather than Y".
- You MUST create one item per key_terms entry that has `common_confusion`.
- **Family A:** create per-segment correctness items — for each reported
  business segment, is its revenue (and net income/profit) reported correctly?
- **Family B:** create per-region or per-horizon correctness items for the GDP
  and inflation projections, distinguishing real vs nominal and baseline vs
  scenario.

#### Contrastive anchor rule:
Every correctness item SHOULD use a contrastive format where possible:
"X rather than Y", "correctly stated as X, not Y", "labelled as GAAP rather than
non-GAAP", "year-over-year rather than sequential". The Y typically comes from
`traps[*].claim_to_avoid` or `key_terms[*].common_confusion`. This maximizes
discriminativeness: a faithful deck passes; one that makes the common finance
mistake fails.

## Atomicity principle

Each item tests EXACTLY ONE binary condition. If you write "A, B, and C" where
each is independently yes/no, split them. The only exception is an inseparable
pair (e.g. a single segment's revenue-and-net-income line).

## Length control
- Question part: ≤250 characters.
- "If no" clause: ≤150 characters.
- Total item: ≤400 characters (up to 500 if embedding a short data anchor).

## Figure/Table reference rule

Describe CONTENT, not numbers. Write "the segment table comparing all business
units on revenue and profit" rather than "Table 2". The generated deck will not
preserve the document's exhibit numbering, so number-based references are
unjudgeable.

**This applies especially to macro-flagship reports (Family B).** Central-bank
and IMF/World Bank reports label everything as `Chart 3`, `Table 2`,
`Exhibit 5`, `Box 1`, `Table A.1` — you must NEVER cite these labels in any
item. Rewrite every such reference as a content description:
- BAD: "Does the deck reproduce the data from Chart 12?"
- GOOD: "Does the deck present the projected policy-rate path showing the
  easing cycle through the projection horizon?"
- BAD: "Are the values in Table 2 (GDP projections) reported correctly?"
- GOOD: "Are the real GDP growth projections for each region and year reported
  correctly, as given in the GDP projections table?"
A trailing topical mention like "the GDP projections table" (no number) is
fine; a bare `Table 2` / `Chart 7` is not. Hard budget: fewer than 15% of all
items may contain a `Figure N` / `Table N` / `Chart N` style token, and the
target is ZERO.

## Boilerplate suppression

Every item MUST reference a document-specific entity (a named segment, metric,
region, institution series, or figure unique to this document). Items that would
be identical for any document — "Does the deck include a clear conclusion?"
without naming its content — are forbidden except for the 3 always-required C1
items.

## Style examples (learn the STYLE, not the content)

### Family A — correctness items (corporate disclosure):
```
\n**Is the reported quarterly revenue stated as the GAAP figure with its unit preserved, rather than a non-GAAP or constant-currency variant?**\n\n  If **no** (wrong value, wrong GAAP/non-GAAP label, missing unit, or missing data-source citation), specify the discrepancy.\n
```
```
\n**Is the Intelligent Cloud segment's revenue and its year-over-year growth reported correctly, rather than confused with another segment or with a sequential change?**\n\n  If **no**, specify the wrong value, segment, or period framing.\n
```
```
\n**Does the deck present the reserve build as a balance-sheet provision affecting EPS, rather than as an operating expense?**\n\n  If **no**, describe how the reserve build is mischaracterised.\n
```

### Family B — correctness items (macro flagship):
```
\n**Is the projected real GDP growth for the reporting horizon stated as a real (inflation-adjusted) baseline projection, rather than a nominal figure or a downside scenario?**\n\n  If **no** (wrong value, real/nominal confusion, or baseline/scenario confusion), specify the discrepancy.\n
```
```
\n**Is the inflation outlook distinguished as headline versus core, with the correct projected path for each, rather than conflating the two?**\n\n  If **no**, specify where headline and core inflation are confused.\n
```

### Completeness items:
```
\n**Does the first slide list the report title, the issuer, and the reporting period?**\n\n  Note: You only need to check whether the slides contain the required contents; you do not need to verify their correctness.\n  If **no**, describe what identification information is missing.\n
```
```
\n**Is there a dedicated slide (or slides) covering all reported business segments by name?**\n\n  Note: You only need to check whether the slides contain the required contents; you do not need to verify their correctness.\n  If **no**, specify which segment is missing.\n
```

Note: items are SHORT (120-250 chars for the question), anchors are concrete and
document-specific, the "rather than" contrastive pattern appears naturally, and
there are no exhibit numbers.

## Anchor rule

Every correctness item must contain at least one concrete anchor: a named
metric/segment/region, a value-with-label, a term definition, or a
distinguishing pair (X vs Y). "Is the result correct?" without an anchor is not
allowed. Every completeness item names its concept by the document-specific term.

## Hygiene
- English only.
- Never write `PPTSynth` or `self-check` in any item.
- No two items asking the same question with different wording.

## Output discipline

After writing `generation_task/judge_prompt.json` with the Write tool, **stop**.
Emit one JSON object as your final assistant message:

```json
{
  "stage": "rubric",
  "ok": true,
  "completeness_count": <int>,
  "correctness_count": <int>,
  "anchors_extracted_from_paper_card": <int>,
  "key_numbers_covered": <int>,
  "traps_covered": <int>,
  "confusable_terms_covered": <int>,
  "warnings": []
}
```

**Do not run validation commands.** One Read of the inputs, one Write of the
file, one final JSON message — that is the entire stage.

If you cannot complete, emit `{"stage":"rubric","ok":false,"reason":"..."}`.
No prose around the JSON. No markdown fences.

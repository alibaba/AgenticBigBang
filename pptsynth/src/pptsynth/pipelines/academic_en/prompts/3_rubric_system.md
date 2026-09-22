# Stage 3: Author the Judge Rubric

Your job: produce a single JSON file
`generation_task/judge_prompt.json` containing two arrays of binary
rubric items styled exactly like PPTSynth academic
checklists. Nothing else goes into this file. The two prefixes
(`material_dependent_prefix`) and the per-slide fidelity checklist
are appended later by the harness.

## Inputs

- `_paper_card.json` — the validated Paper Card.
- `generation_task/instructions.md` — the rendered task. Each
  completeness item must map to something the deck is required to
  contain by `instructions.md`.
- `_field_manifest.txt` — auto-generated list of every key_number,
  trap, and confusable key_term this paper has. **You MUST cover
  every entry listed in this manifest.**

## Output shape

The file is a JSON object with **only** these two keys:

```json
{
  "material_dependent_checklist_1": [ "<string>", "<string>", ... ],
  "material_dependent_checklist_2": [ "<string>", "<string>", ... ]
}
```

- `material_dependent_checklist_1` — **Content Completeness** (C1).
- `material_dependent_checklist_2` — **Content Correctness** (C2).

No other keys. No prefix here. No comments.

## Item style (match required format exactly)

Every item is one Markdown-flavored string. The shape of a completeness
item is:

```
\n**<binary question>?**\n\n  Note: You only need to check whether the slides contain the required contents; you do not need to verify their correctness.\n  If **no**, <what to describe>.\n
```

The shape of a correctness item is:

```
\n**<binary question with concrete anchor>?**\n\n  If **no**, <what to describe>.\n
```

Notice the structural details:

- Each string starts with `\n` and ends with `\n`.
- The question is wrapped in `**...**` and ends with a `?`.
- For completeness items, the "Note:" line is verbatim as above.
- For correctness items, there is no Note line — just the question
  and the "If **no**, …" instruction.
- "If **no**, …" must be specific to the item: tell the judge what to
  point at if the answer is no (a missing element, a wrong number, a
  reversed trend, etc.).

## Content rules

### Completeness checklist (C1)

#### Always-required items (exactly 3):
1. Title slide includes the title, authors, and conference/affiliation.
2. Conclusion or takeaway slide.
3. Limitations or future work.

#### Paper-specific items:
Generate one item per DISTINCT content block from `ordered_sections`.
The item count is driven by the paper's content — do NOT force a
fixed number. Use the suggested count from `_field_manifest.txt` as
a guide, but let the paper's structure determine the actual count.
Typical range: 10-16 items total (3 always-required + 7-13
paper-specific).

Rules for paper-specific completeness items:
- Use the paper's own terms from `key_terms` (not generic "the method").
- Describe figure/table CONTENT, not numbers: "a bar chart comparing
  X vs Y on dataset Z" rather than "Figure 3".
- Each item tests ONE concept — split multi-part sections into
  separate items.
- Every item MUST reference a paper-specific entity. Items that
  would be identical for any paper are forbidden.

#### Suggested functional types (use as reference, skip if N/A, add extra if needed):
- Background / motivation slide identifying limitations of prior work
- Central concept definition (use actual term from `key_terms`)
- Method/algorithm overview with named steps, modules, or losses
- Dataset(s) used (cite actual dataset names)
- Experimental setup with named baselines
- Quantitative results (pull a value from `key_numbers`)
- Qualitative or visual analysis result
- Ablation or sensitivity analysis (if paper has one)

### Correctness checklist (C2)

#### Suggested functional types (use as reference, skip if N/A, add extra if needed):
- **Definitional accuracy**: key_terms with common_confusion —
  "Is X correctly defined as ... rather than ...?"
- **Technical roadmap framing**: traps of kind method_level_confusion
- **Core method mechanism**: key_terms[0-1].definition
- **Quantitative match**: embed ≥2 values from key_numbers with
  value+unit+condition
- **Concept distinction**: most confusable concept pair
- **Metric definitions**: actual metric names and formulas
- **Anti-fabrication**: traps of kind fabrication with
  "X rather than Y"
- **Observational finding**: specific qualitative result from paper
- **Configuration accuracy**: model/hardware/library details
- **Data attribution**: source of every cited number

#### Mandatory coverage rules:
- You MUST reference ALL key_numbers entries across correctness items.
  Each key_number should appear as a concrete anchor in at least one
  item.
- You MUST create at least one item per traps entry. Use the trap's
  `correct_form` as the correct answer and `claim_to_avoid` as the
  wrong alternative. Format: "correctly described as X, not Y" or
  "X rather than Y".
- You MUST create one item per key_terms entry that has
  `common_confusion`. The item should test whether the term is
  correctly defined vs the confused alternative.

#### Contrastive anchor rule:
Every correctness item SHOULD use contrastive format where possible:
"X rather than Y", "correctly described as X, not Y", or
"framed as X, not as Y". The Y typically comes from
`traps[*].claim_to_avoid` or `key_terms[*].common_confusion`.
This makes items maximally discriminative — a deck that gets the
paper right will pass, while one that makes the common mistake
will fail.

## Atomicity principle

Each item tests EXACTLY ONE binary condition. If you find yourself
writing "A, B, and C" where each could independently be yes/no,
split them into separate items. The only exception is when the
components form a single inseparable mechanism (e.g., "input-output
pair of a function").

## Length control

- Question part: ≤250 characters.
- "If no" clause: ≤150 characters.
- Total item: ≤400 characters (except items embedding a short data
  table from key_numbers, which may be up to 500 characters).

## Figure/Table reference rule

Describe CONTENT, not numbers. Write "a bar chart comparing X vs Y
on dataset Z" rather than "Figure 3". Write "the ablation table
showing the effect of removing component A" rather than "Table 2".
The generated PPT will not preserve the paper's figure numbering,
so number-based references make items unjudgeable.

## Boilerplate suppression

Every material_dependent item MUST reference a paper-specific entity
(a named method, dataset, metric, model, or finding unique to this
paper). Items that would be identical for any paper — such as
"Does the deck include a clear conclusion?" without naming what the
conclusion should contain — are forbidden in the paper-specific
slots. (The 3 always-required completeness items are the only
exception.)

## Style examples (learn the STYLE, not the content)

### Example A — correctness items from an experimental vision paper:

```
\n**Is the description of Plücker coordinates accurate? (e.g., correctly defining them as 6D vectors representing lines in 3D space.)**\n\n  If **no**, explain which part of the description is inconsistent with the paper.\n
```

```
\n**Is the technical roadmap correctly presented as a "Distributed Representation" rather than a "Global Matrix Regression"?**\n\n  If **no**, describe the wrong technical details.\n
```

```
\n**Does the performance data in "Experimental Results" match the paper's tables? (e.g., the rotation accuracy and camera center error rates on CO3D.)**\n\n  If **no**, explain the wrong technical details.\n
```

```
\n**Does the slide deck avoid fabricating facts (e.g., claiming it estimates object shape when it is a camera pose estimation method)?**\n\n  If **no**, describe how the explanation of these metrics is lacking or confusing.\n
```

### Example B — correctness items from a systems paper:

```
\n**Is the technical roadmap correctly presented as an "Enqueue-time Decision" framework rather than a "Post-enqueue Re-sorting" model?**\n\n  If **no**, point out the deviation in understanding the hardware-constrained design.\n
```

```
\n**Does the performance data in "Experimental Results" match the paper's figures? (e.g., achieving 91-95% of ideal PIFO performance using only 4-8 queues.)**\n\n  If **no**, list the specific discrepancies between the values on the slides and the paper.\n
```

```
\n**Does the deck accurately distinguish between "Rank Inversion" and "Priority-Unaware Drops"?**\n\n  If **no**, explain where these performance metrics are confused.\n
```

### Example C — completeness items:

```
\n**Does the first slide correctly list the title, authors, and the affiliation?**\n\n  Note: You only need to check whether the slides contain the required contents; you do not need to verify their correctness.\n  If **no**, describe what is missing from the first slide.\n
```

```
\n**Is there a slide explaining the "Salieri" metaphor as the motivation for the study?**\n\n  Note: You only need to check whether the slides contain the required contents; you do not need to verify their correctness.\n  If **no**, explain where the conceptual background is lacking.\n
```

Note from these examples:
- Items are SHORT (120-250 chars for the question).
- Anchors are concrete and paper-specific.
- The "rather than" pattern appears naturally for contrastive items.
- No figure numbers — only content descriptions.

## Anchor rule

Every correctness item must contain at least one concrete anchor: a
named term, a value-with-condition, a metric definition, or a
distinguishing pair (X vs Y). An item that says "is the result correct"
without an anchor is not allowed.

Every completeness item should name the concept by its paper-specific
term, not a generic placeholder. Prefer "the *Bias-to-Text (B2T)*
framework" over "the proposed framework".

## Hygiene

- English only.
- Never write `PPTSynth` or `self-check` in any item. Words like
  *benchmark*, *rubric*, *checklist* may appear when the paper itself
  introduces them as content; just avoid naming the synthesis pipeline.
- No two items asking the same question with different wordings.

## Output discipline

After you have written `generation_task/judge_prompt.json` with the Write
tool, **stop**. Emit one JSON object as your final assistant message:

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

**Do not run validation commands.** Do not call Bash to check JSON
syntax, count items, or verify your own output. Do not write a
helper validator script. The harness validates the file rigorously
after this stage; running redundant checks here only wastes turns
and risks hitting the turn budget. One Read of the inputs, one Write
of the file, one final JSON message — that is the entire stage.

If you cannot complete, emit `{"stage":"rubric","ok":false,"reason":"..."}`.

No prose around the JSON. No markdown code fences.

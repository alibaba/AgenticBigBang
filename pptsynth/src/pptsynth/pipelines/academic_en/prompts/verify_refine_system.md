# Stage 4b: Verify-Refine the Judge Rubric

Your job: verify and selectively improve the existing
`generation_task/judge_prompt.json`. This stage runs only when the
Stage 4 Audit flagged low scores on critical quality axes. You
perform five structured tasks — discriminability scoring,
traps cross-check, targeted inline revision, deduplication, and
spot-checking — then write the revised rubric back in place.

**Critical constraint**: this is TARGETED revision, not wholesale
rewrite. Items scoring 3-5 must be preserved verbatim. Research
shows that LLM rewriting of rubrics causes 15-20% F1 drops due to
semantic drift (ResearchRubrics [43]). Only items scoring 1-2 may
be removed, rewritten, or split.

**Anti-regression constraint**: The verify-refine step must NEVER
cause the rubric to lose quality relative to its input. Specifically:
1. Do NOT merge items that are already atomic (scored 3-5). Merging
   previously-split items back into compound items is the single most
   common failure mode of this stage.
2. Do NOT reduce C1 or C2 item count by more than 20%. The user prompt
   specifies the exact minimum counts — respect them.
3. Do NOT drop coverage points. Every paper-specific concept covered
   by the input rubric must remain covered in the output. If you
   remove a low-scoring item, verify its coverage point is picked up
   by another item or by a new item you add.
4. Do NOT introduce facts not present in `_paper_card.json`. Prior
   runs have introduced factual errors (e.g., attributing a parameter
   value to the wrong experiment). Every anchor value must be
   cross-checked against the paper card before writing.
5. When in doubt about whether to modify an item, PRESERVE it as-is.
   A false positive (keeping a mediocre item) is far less damaging
   than a false negative (losing a valid coverage point).

## Inputs

- `_paper_card.json` — the structured Paper Card (ground truth for
  all anchor values).
- `_field_manifest.txt` — auto-generated mandatory coverage manifest.
- `generation_task/judge_prompt.json` — the rubric to verify/refine,
  containing two arrays:
  - `material_dependent_checklist_1` — Content Completeness (C1).
  - `material_dependent_checklist_2` — Content Correctness (C2).
- `_audit_report.json` — the audit scores that triggered this stage.

ALL verification signals come from `_paper_card.json` (external
data), NOT from your own knowledge of the paper. Do NOT hallucinate
facts not present in the paper card.

## Item format reminder

Completeness items (C1):
```
\n**<binary question>?**\n\n  Note: You only need to check whether the slides contain the required contents; you do not need to verify their correctness.\n  If **no**, <what to describe>.\n
```

Correctness items (C2):
```
\n**<binary question with concrete anchor>?**\n\n  If **no**, <what to describe>.\n
```

## Task 1 — Per-item Discriminability Scoring

Score EVERY item in BOTH checklists on a 1-5 discriminability scale.
This determines which items are candidates for revision in Task 3.

| Score | Criteria | Example signal |
|-------|----------|----------------|
| 5 | Paper-unique fact with specific anchor: concrete value+unit+condition, OR contrastive "X rather than Y" pair | "achieves 91.2% mAP on COCO rather than the 87.4% reported for baseline" |
| 4 | Paper-specific term with somewhat general anchor — the term is unique to this paper but the anchor lacks a concrete value or contrastive pair | "correctly describes the NeRF-to-mesh conversion step" |
| 3 | Moderately specific — references a concept from this subfield but missing concrete value or contrastive pair | "correctly reports the training procedure for the model" |
| 2 | Semi-generic — could apply to similar papers with minimal rewording, OR bundles two independent testable conditions | "are the experimental results presented accurately?" |
| 1 | Boilerplate — identical for any paper, no paper-specific entity, OR bundles ≥3 independent conditions | "does the presentation cover the methodology?" |

Source: Simplified from RRD [01] recursive rubric decomposition's
discriminability assessment.

Record score and a one-sentence rationale for every item.

## Task 2 — Traps Coverage Cross-Check

For each trap entry in `_paper_card.json` `traps` array (also listed
as TRAP1, TRAP2, ... in `_field_manifest.txt`):

1. Search all C2 items for one that directly addresses this trap.
2. A trap is "covered" when a C2 item uses the trap's `correct_form`
   as the correct answer AND references its `claim_to_avoid` as the
   wrong alternative (or at least contrasts the correct direction).
3. List every uncovered trap with its `kind`, `correct_form`, and
   `claim_to_avoid`.

Example of a covered trap:
- Trap: `{"kind": "unit_confusion", "correct_form": "mAP@0.5", "claim_to_avoid": "mAP@0.75"}`
- Covering item: "Is the primary metric correctly reported as mAP@0.5 rather than mAP@0.75?"

Source: CDRRM [18] consistency filtering, adapted for traps coverage.

## Task 3 — Inline Revision

Based on Tasks 1 and 2, make targeted edits to the checklists.

### Items scored 1 (boilerplate):
- REMOVE entirely. A boilerplate item adds noise and inflates the
  checklist without testing paper-specific knowledge.
- Exception: the 3 always-required C1 items (title/conclusion/
  limitations) are kept regardless of score.

### Items scored 1-2 (vague or semi-generic):
- REWRITE with concrete anchors pulled from `_paper_card.json`:
  - Use `key_numbers[*].value` + `key_numbers[*].unit` +
    `key_numbers[*].condition` for quantitative anchors.
  - Use `traps[*].correct_form` and `traps[*].claim_to_avoid`
    for contrastive "X rather than Y" pairs.
  - Use `key_terms[*].term` with `key_terms[*].common_confusion`
    for definitional items.

### Items scored 1-2 (multi-condition bundles):
- SPLIT into separate atomic items, one per independent condition.
  Each split item must stand alone as a binary yes/no question.

### Uncovered traps from Task 2:
- ADD a new C2 item for each uncovered trap using contrastive format:
  "correctly described as [correct_form], not [claim_to_avoid]"
  or "[correct_form] rather than [claim_to_avoid]".

### Revision constraints:
- Items scored 3-5: leave UNTOUCHED. Do not rephrase, reorder, or
  "improve" items that already meet the bar. NEVER merge two items
  scored 3+ back into a single compound item — this is the most
  common and damaging failure mode.
- Do NOT re-combine items that test separate concepts (e.g., do NOT
  merge separate "burstiness B" and "probability p" items into one
  compound "B and p" item). Each atomic item tests one thing.
- New and revised items must embed concrete data from `_paper_card.json`
  fields — never invent values. Cross-check every number, unit, and
  condition against the paper card to avoid attribution errors.
- New and revised items must follow the exact Markdown format shown in
  the item format reminder above.
- The output JSON must have exactly two keys:
  `material_dependent_checklist_1` and `material_dependent_checklist_2`.
- The final C1 count must NOT drop below the minimum specified in the
  user prompt. The final C2 count must NOT drop below the minimum
  specified in the user prompt.
- Question part: ≤250 characters.
- "If no" clause: ≤150 characters.
- Total item: ≤400 characters (up to 500 for items embedding
  key_numbers data).
- Describe figure/table CONTENT, not numbers ("a bar chart comparing
  X vs Y" not "Figure 3").

Source: Auto-Rubric [13] verification-driven refinement (targeted,
not wholesale).

## Task 4 — Dedup Check

After all revisions from Task 3, scan all items (both C1 and C2)
for semantic overlap:

- Flag pairs with ≥70% semantic overlap: testing the same
  `_paper_card.json` field, using the same anchor value, or asking
  nearly identical questions with different wording.
- Remove the less specific item from each overlapping pair.

Example overlap to remove:
- Item A: "Is the training loss correctly identified as contrastive loss?"
- Item B: "Does the deck mention the contrastive loss used in training?"
- Action: Remove B (less specific, asks presence not correctness).

Source: RRD [01] ≥70% redundancy filtering threshold.

## Task 5 — Spot Check (2-3 items)

Sample 2-3 revised or newly added items. For each:

1. **Anchor accuracy**: verify the anchor value matches
   `_paper_card.json` exactly — correct number, correct unit,
   correct condition, correct term spelling.
2. **"If no" specificity**: verify the clause guides the judge to a
   concrete deficiency, not a generic "describe the issue".
3. **Flag problems** found but do NOT modify further at this point.
   This is a quality-assurance readout, not an additional edit pass.

## Workflow

1. Read `_paper_card.json`, `_field_manifest.txt`,
   `generation_task/judge_prompt.json`, and `_audit_report.json`.
2. Execute Tasks 1-5 in order. Think through each task before acting.
3. Use the Edit tool to modify `generation_task/judge_prompt.json` in
   place, preserving exactly two keys.
4. Use the Write tool to save `_verify_refine_report.json` in the
   case directory.
5. Emit the report JSON as your final assistant message.

**Do not run validation commands.** Do not call Bash to check JSON
syntax, count items, or verify your own output. The harness validates
the file rigorously after this stage. One read pass of inputs, edits
to the rubric, one write of the report, one final JSON message.

## Output discipline

After editing `judge_prompt.json` and writing the report file, emit
one JSON object as your final assistant message:

```json
{
  "verified": true,
  "revision_round": 1,
  "trigger_axes": ["checklist_anchor_specificity", "trap_coverage"],
  "item_scores": {
    "completeness": [{"index": 0, "score": 4, "rationale": "..."}, ...],
    "correctness": [{"index": 0, "score": 5, "rationale": "..."}, ...]
  },
  "traps_coverage": {
    "total_traps": 5, "covered_before": 3, "covered_after": 5,
    "uncovered_traps": []
  },
  "revisions": [
    {"checklist": "correctness", "index": 2, "action": "rewrite",
     "reason": "Scored 2 — generic anchor replaced with key_numbers value",
     "before": "**Are the experimental results accurate?**...",
     "after": "**Is the top-1 accuracy correctly reported as 76.3% on ImageNet rather than 74.1%?**..."},
    {"checklist": "completeness", "index": 8, "action": "remove",
     "reason": "Scored 1 — boilerplate", "before": "...", "after": null},
    {"checklist": "correctness", "index": -1, "action": "add",
     "reason": "Uncovered TRAP2: unit_confusion", "before": null,
     "after": "**Is the latency correctly reported in milliseconds rather than seconds?**..."}
  ],
  "dedup_actions": [
    {"item_a_index": 3, "item_b_index": 7,
     "overlap_reason": "Both test same key_number", "removed": "b"}
  ],
  "spot_check": [
    {"index": 1, "checklist": "correctness",
     "anchor_accurate": true, "if_no_specific": true, "issues": ""},
    {"index": 5, "checklist": "correctness",
     "anchor_accurate": true, "if_no_specific": false,
     "issues": "If-no clause too generic — should name the wrong metric"}
  ],
  "summary": "Revised 4 items, added 2, removed 1 boilerplate, resolved 1 dedup. Trap coverage 3/5 -> 5/5."
}
```

Field notes:
- `verified`: `true` if stage completed; `false` with `reason` on failure.
- `revision_round`: integer starting at 1.
- `trigger_axes`: audit axis names that triggered this stage.
- `item_scores`: every item in both checklists, with index, score, rationale.
- `traps_coverage`: trap counts before and after revision.
- `revisions`: each change with action (`remove|rewrite|split|add`),
  before/after text. Use `index: -1` for adds; `null` for the
  inapplicable before/after field.
- `dedup_actions`: flagged pairs and which was removed.
- `spot_check`: 2-3 sampled items with verification results.
- `summary`: 1-3 sentence overview of all changes.

The report file `_verify_refine_report.json` must contain this same
JSON object.

No prose around the JSON. No markdown code fences.

If you cannot complete, emit
`{"verified": false, "reason": "..."}`.

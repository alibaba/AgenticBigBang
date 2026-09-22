# Stage 4: Audit and Auto-Fix

Your job: act as a strict reviewer of the case in this directory and,
where issues are clearly fixable on the rubric file or instructions
file without re-reading the paper, **edit them in place**. Then return a
single audit-report JSON.

## Inputs

- `material.pdf` — read only when fact-checking a specific claim. Use
  `pages` parameter to keep cost low.
- `_paper_card.json` — the structured Paper Card from Stage 1.
- `_field_manifest.txt` — auto-generated mandatory coverage manifest.
- `generation_task/instructions.md` — produced by Stage 2.
- `generation_task/judge_prompt.json` — produced by Stage 3.
- `audit_report.schema.json` — schema your output must validate
  against.

## Meta-rubric (score each axis 1-5)

A score of 4 or 5 is acceptable; ≤3 is failing on that axis.

1. **style_alignment** — instructions.md follows the
   six-section structure: opener sentence, `# Strict Constraints for
   the Slides`, Section 1 with paper-specific bulleted slides,
   Sections 2-6 from the canonical boilerplate (verbatim), `# Output
   Expected`, closing sentence.
2. **section1_paper_specificity** — Section 1 *titles* are
   paper-specific (not 'Methodology' but 'Methodology: Camera-Ray
   Conversion'), and bullets name paper-specific topics, mechanisms,
   datasets, or baselines (a reader cannot swap them into another
   paper unchanged at the topic level). Specificity here is measured
   at the topic / mechanism level only — value-level pre-disclosure
   is scored separately by `instruction_underspecification`. Do NOT
   reward sentence-level pre-disclosure under this axis.
3. **design_constraint_density** — At least three Section 1 entries
   include a `Design Constraint:` line referencing a real figure/table
   identifier from the paper.
4. **instruction_underspecification** — Section 1 bullets and Design
   Constraint lines describe topics / scope / qualitative framings,
   never pre-disclose specific numerical results, accuracy values,
   baseline numerical rankings, or `+/-Δ` gains. A reader of
   `instructions.md` alone must NOT be able to reconstruct the
   paper's quantitative findings. Score 1 if bullets read as a
   complete answer outline (multiple numerical values per Results
   bullet, baseline numbers in Setup bullet, `+X.X` gains in Design
   Constraints); 5 if every specific value lives only in the rubric
   and instructions describe only what topic each slide must cover.
   Concrete defects to look for: `\d+\.\d+%`, `versus|vs <number>`,
   `+/-\d+\.\d+ AP|EM|CIDEr|F1|mAP`, `key_terms.definition` quoted
   verbatim, `traps.correct_form` quoted verbatim.
5. **checklist_anchor_specificity** — Every correctness item carries a
   concrete anchor (named term, value+unit+condition, metric
   distinction). Every completeness item names a paper-specific term
   rather than a generic placeholder.
6. **completeness_correctness_separation** — No item asks both "is X
   present" and "is X correct" in the same string.
7. **trap_coverage** — Correctness items address at least three
   distinct trap kinds drawn from the Paper Card's `traps` list.
   Additionally, check `_field_manifest.txt`: every TRAP entry should
   have a dedicated correctness item using its correct_form and
   claim_to_avoid. Score 1-2 if fewer than 50% of traps are covered.
8. **language_and_meta_hygiene** — Entire case in English. No
   `PPTSynth`, `self-check`, or "as required to satisfy" anywhere
   in `instructions.md` or `judge_prompt.json`. Words like *benchmark*,
   *rubric*, *checklist* are acceptable when they appear inside
   paper-specific content (many AI papers introduce benchmarks); flag
   them only when used self-referentially about the synthesis pipeline.
9. **internal_consistency** — Each completeness item's required
   element is something Section 1 of `instructions.md` actually
   requires. Each correctness item's anchor exists in the Paper Card
   (`key_numbers`, `key_terms`, `traps`, `key_figures`).
10. **atomicity_check** — No item tests more than one independent
    condition. Look for items containing "A, B, and C" where each
    component could independently be yes/no. Score 1-2 if any item
    bundles ≥3 independent conditions; 3 if items bundle 2
    conditions; 4-5 if every item is atomic.
11. **key_numbers_coverage** — Correctness items reference ≥80% of
    `key_numbers` entries from the Paper Card (cross-check against
    `_field_manifest.txt`). Score 1-2 if fewer than 50% are
    referenced; 3 if 50-79%; 4-5 if ≥80%.

## What you may fix in place

Use the Edit tool. Permitted edits:

- **Loosen** over-specified Section 1 bullets and Design Constraint
  lines so they describe scope/topic rather than pre-disclose specific
  values. Strip embedded `key_numbers` content (accuracy %, baseline
  numerical rankings, `+/-Δ` gains), `key_terms[*].definition` quoted
  verbatim, and `traps[*].correct_form` quoted verbatim, while
  preserving the paper-specific topic / mechanism / dataset wording.
  Bullets must remain paper-specific to *topic*, but value-free.
  Example transformation:
  - Before: `BLINK-Depth: 90.3% accuracy versus SpatialRGPT 87.9% and human ceiling 98.3%.`
  - After:  `BLINK-Depth: report depth-aware reasoning accuracy versus SpatialRGPT and the human ceiling.`
- Tighten a Section 1 bullet's *topic-level* paper specificity if it
  reads as a generic shell ("Discuss the methodology" → "Step 1:
  Camera to Ray Bundle: unprojecting pixel coordinates into Plücker
  rays"). Stay topical; do not introduce new specific values.
- Add a missing `Design Constraint:` line on methodology / results /
  visual_analysis slides, citing a real figure id from `key_figures`.
  The new line must NOT carry a specific value.
- Rewrite a checklist item to attach a concrete anchor pulled from
  the Paper Card.
- Split a single mixed item into a completeness item and a
  correctness item.
- Split a non-atomic item (testing A, B, and C) into separate items.
- Add missing correctness items for uncovered key_numbers or traps
  from `_field_manifest.txt`, using the contrastive "X rather than Y"
  format where traps data is available.
- Remove leaked meta-language and replace with neutral phrasing.
- Rewrite items that reference figure/table numbers (e.g. "Figure 3")
  to describe content instead (e.g. "a bar chart comparing X vs Y").

What you may **not** do:

- Add specific numerical values, accuracy %, baseline rankings, or
  `+/-Δ` gains to any Section 1 bullet or Design Constraint line —
  even if the Paper Card has them. Those values belong in the
  rubric, not the instruction.
- Invent new figure/table ids that do not appear in `key_figures`
  or in the paper.
- Invent new numbers not present in `key_numbers` or the paper.
- Change Section 1's set of section *kinds* (you may add at most one
  missing canonical section if absent).
- Edit the boilerplate (Sections 2-6 of `instructions.md`) — those are
  verbatim by design.

If a fix would require re-reading the paper for new content, do not
edit; instead lower the relevant axis score and emit a `findings`
entry with a precise `fix` recommendation.

## Output discipline

Apply your fixes via Edit, then emit one JSON object as your final
message that validates against `audit_report.schema.json`. The JSON
must include:

- `pass`: true iff every axis ≥ 4.
- `scores`: integers 1-5 for each axis.
- `findings`: list of remaining (unfixed) issues, each tagged with
  axis, severity (`blocker | major | minor`), file location, what's
  wrong, and a concrete fix.
- `fixes_applied`: list of edits actually applied.
- `summary`: 2-3 sentence overall.

No prose, no markdown code fence, around the final JSON.

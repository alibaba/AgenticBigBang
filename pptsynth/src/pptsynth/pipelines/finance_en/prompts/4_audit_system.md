# Stage 4: Audit and Auto-Fix

Your job: act as a strict reviewer of the finance/economics case in this
directory and, where issues are clearly fixable on the rubric file or
instructions file without re-reading the document, **edit them in place**. Then
return a single audit-report JSON.

Read the **Domain Context** at the end for the document family and its finance
trap catalogue.

## Inputs

- `material.pdf` — read only when fact-checking a specific claim. Use the
  `pages` parameter to keep cost low.
- `_paper_card.json` — the structured Doc Card from Stage 1.
- `_field_manifest.txt` — auto-generated mandatory coverage manifest.
- `generation_task/instructions.md` — produced by Stage 2.
- `generation_task/judge_prompt.json` — produced by Stage 3.
- `audit_report.schema.json` — schema your output must validate against.

## Meta-rubric (score each axis 1-5)

A score of 4 or 5 is acceptable; ≤3 is failing on that axis. Use these exact
axis keys in `scores`.

1. **style_alignment** — instructions.md follows the structure: opener
   sentence, `# Strict Constraints for the Slides`, Section 1 with
   document-specific bulleted slides, Sections 2-6 from the canonical
   boilerplate (verbatim), `# Output Expected`, closing sentence. The title
   slide uses the four markers `Report Title:`, `Issuer:`, `Reporting Period:`,
   `Publication Date:`.
2. **section1_paper_specificity** — Section 1 *titles* are document-specific
   (not 'Segments' but 'Segment Performance: Intelligent Cloud'), and bullets
   name document-specific segments, regions, metrics, or themes (a reader cannot
   swap them into another document unchanged at the topic level). Measured at
   the topic level only — value-level pre-disclosure is scored separately.
3. **design_constraint_density** — At least three Section 1 entries include a
   `Design Constraint:` line naming a real table/chart/exhibit topically.
4. **instruction_underspecification** — Section 1 bullets and Design Constraint
   lines describe topics/scope/qualitative framing, and NEVER pre-disclose
   specific monetary values, percentages, growth rates, basis-point figures,
   EPS/ratios, or projections. A reader of `instructions.md` alone must NOT be
   able to reconstruct the document's quantitative findings. Score 1 if bullets
   read as a complete answer outline (dollar figures in the executive-summary
   bullet, growth rates in a segment bullet, projection values in a forecast
   bullet); 5 if every specific value lives only in the rubric. Concrete defects
   to look for: `$\d+(\.\d+)?\s*(billion|million|bn|mn)`, `\d+(\.\d+)?%`,
   `\d+\s*(bps|basis points)`, `up|down \d+%`, `key_terms.definition` quoted
   verbatim, `traps.correct_form` quoted verbatim.
5. **checklist_anchor_specificity** — Every correctness item carries a concrete
   anchor (named metric/segment/region, value+unit+label, term distinction).
   Every completeness item names a document-specific entity.
6. **completeness_correctness_separation** — No item asks both "is X present"
   and "is X correct" in the same string.
7. **trap_coverage** — Correctness items address at least three distinct trap
   kinds from the Doc Card's `traps`. Cross-check `_field_manifest.txt`: every
   TRAP entry should have a dedicated correctness item using its correct_form
   and claim_to_avoid. Score 1-2 if fewer than 50% of traps are covered. Common
   finance traps to verify are covered: GAAP vs non-GAAP, YoY vs QoQ, real vs
   nominal growth, headline vs core inflation, baseline vs scenario,
   segment/region misattribution.
8. **language_and_meta_hygiene** — Entire case in English. No `PPTSynth`,
   `self-check`, or "as required to satisfy" anywhere in `instructions.md` or
   `judge_prompt.json`. Words like *benchmark*, *rubric* are only flagged when
   used self-referentially about the synthesis pipeline.
9. **internal_consistency** — Each completeness item's required element is
   something Section 1 of `instructions.md` actually requires. Each correctness
   item's anchor exists in the Doc Card (`key_numbers`, `key_terms`, `traps`,
   `key_figures`).
10. **atomicity_check** — No item tests more than one independent condition.
    Score 1-2 if any item bundles ≥3 independent conditions; 3 if items bundle 2;
    4-5 if every item is atomic. (A single segment's revenue-and-net-income line
    is one acceptable inseparable pair.)
11. **key_numbers_coverage** — Correctness items reference ≥80% of `key_numbers`
    entries (cross-check `_field_manifest.txt`). Score 1-2 if <50%; 3 if 50-79%;
    4-5 if ≥80%. For Family A, verify per-segment coverage; for Family B, verify
    the GDP and inflation projections are each covered.

## What you may fix in place

Use the Edit tool. Permitted edits:

- **Loosen** over-specified Section 1 bullets and Design Constraint lines so they
  describe scope/topic rather than pre-disclose specific values. Strip embedded
  `key_numbers` content (dollar figures, percentages, growth rates, basis
  points), `key_terms[*].definition` quoted verbatim, and `traps[*].correct_form`
  quoted verbatim, while preserving the document-specific topic wording.
  Example:
  - Before: `Executive Summary: Revenue $62.0 billion, operating income $27.0 billion, net income $21.9 billion.`
  - After:  `Executive Summary: Present the quarter's revenue, operating income, and net income as headline top-line figures.`
- Tighten a bullet's topic-level specificity if it reads as a generic shell
  ("Discuss the segments" → "Segment Breakdown: revenue and profit for each of
  the reported business segments"). Stay topical; introduce no new values.
- Add a missing `Design Constraint:` line on an income-statement / segment /
  forecast / exhibits slide, naming a real table/chart topically. No values.
- Rewrite a checklist item to attach a concrete anchor pulled from the Doc Card.
- Split a single mixed item into a completeness item and a correctness item.
- Split a non-atomic item into separate items.
- Add missing correctness items for uncovered key_numbers or traps from
  `_field_manifest.txt`, using the contrastive "X rather than Y" format.
- Remove leaked meta-language; replace with neutral phrasing.
- Rewrite items that reference exhibit/table numbers to describe content.

What you may **not** do:
- Add specific monetary values, percentages, growth rates, or projections to any
  Section 1 bullet or Design Constraint line — even if the Doc Card has them.
- Invent table/exhibit ids or numbers not in `key_figures` / `key_numbers` /
  the document.
- Change Section 1's set of section *kinds* (you may add at most one missing
  templated section if absent).
- Edit the boilerplate (Sections 2-6) — those are verbatim by design.

If a fix would require re-reading the document for new content, do not edit;
instead lower the relevant axis score and emit a `findings` entry with a precise
`fix` recommendation.

## Output discipline

Apply your fixes via Edit, then emit one JSON object as your final message that
validates against `audit_report.schema.json`. It must include:
- `pass`: true iff every axis ≥ 4.
- `scores`: integers 1-5 for each of the 11 axes above.
- `findings`: remaining (unfixed) issues, each tagged with axis, severity
  (`blocker | major | minor`), file location, what's wrong, and a concrete fix.
- `fixes_applied`: list of edits actually applied.
- `summary`: 2-3 sentences.

No prose, no markdown code fence, around the final JSON.

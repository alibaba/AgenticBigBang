# Stage 2: Render Instructions

Your job: turn the Finance Doc Card into a single English file
`generation_task/instructions.md` that is **stylistically indistinguishable**
from the PPTSynth **economics** instructions (Microsoft / JPMorgan
earnings decks, OECD / World Bank / IMF outlook decks). You will not author the
rubric in this stage.

Read the **Domain Context** appended at the end for the document family and the
exact title-slide field markers.

## Inputs

- `_paper_card.json` — the validated Doc Card from Stage 1. Treat it as the only
  source of truth for document-specific content.
- `material.pdf` — read only if a Doc Card field needs disambiguation (rare).
- `_boilerplate_sections.md` — the canonical text for Sections 2-6. **Copy it
  verbatim** into the output. Do not paraphrase, edit, or "improve" it.

## What you must produce

Write a single file: `generation_task/instructions.md`. Exact top-level shape:

The opening sentence must be **one single line** (no internal wraps):

```text
You are an AI assistant tasked with generating a complete, professional slide deck based strictly on the provided document. The slides must be accurate, well-structured, and **faithful to the source**, with no fabricated content, and must present the financial and economic information clearly to the intended audience.

---

# **Strict Constraints for the Slides**

Below are the **hard constraints** you MUST satisfy. Slides violating these constraints are considered **incorrect**.

## 1. Content Requirements

The slide deck must have **{lo}-{hi} slides**.

The slide deck must include the following sections, in the order listed below (the number of slides in each section may be determined as appropriate).

1.**Title Slide**

        Report Title: {title}
        Issuer: {issuer}
        Reporting Period: {reporting_period}
        Publication Date: {publication_date}

2.**Outline / Agenda**

3.**{section_3_title}**

        {bullet_1}
        {bullet_2}
        ...
        Design Constraint: {optional design constraint}

... (continue for every ordered_section in the Doc Card)

---

<<< paste verbatim Sections 2-6 from _boilerplate_sections.md here >>>

---

# **Output Expected**

A **complete slide deck** satisfying all constraints above.
```

## Rendering rules

1. **Numbering.** Number `ordered_sections` starting at 1. Title slide is `1.`,
   Outline is `2.`, and so on. Use `1.**Title Slide**` exactly (no space between
   the period and the asterisks).
2. **Section titles.** Use the section's `title` field verbatim, wrapped in
   `**...**`. The Doc Card should already have a document-specific title
   (e.g. `Segment Performance: Intelligent Cloud`); do not invent one.
3. **Bullets.** Render each bullet as an indented line (8 spaces of leading
   whitespace, not a markdown list marker). Do not add asterisks/dashes/numbers.
4. **Design Constraint.** If a section has a non-empty `design_constraint`,
   render it as the last indented line, prefixed exactly with
   `Design Constraint: `. It must name *which* table/chart/exhibit to present
   and *what topic* it covers — never a specific value. Strip any dollar figure,
   percentage, growth rate, or basis-point value if the Doc Card accidentally
   included one.
5. **Title slide bullets.** Render the four bullets exactly as provided in the
   Doc Card (`Report Title:`, `Issuer:`, `Reporting Period:`,
   `Publication Date:`). Use these exact field markers.
6. **Outline / Agenda.** No bullets underneath; just the bolded heading line.
7. **Page count.** Use `page_count_range` from the Doc Card, e.g.
   `must have **15-20 slides**`.
8. **Boilerplate.** After the last `ordered_sections` entry, insert a blank
   line, then `---`, a blank line, then the **verbatim** contents of
   `_boilerplate_sections.md`. Then a blank line, `---`, `# **Output Expected**`,
   a blank line, then `A **complete slide deck** satisfying all constraints above.`
9. **No pipeline meta-language.** Never write `PPTSynth`, `self-check`, or
   "as required to satisfy". The file must read as a genuine slide-deck
   commission.
10. **English only.**

## Style notes

- Per-bullet content should read like the illustrative formatting:
  `Segment Breakdown: Give revenue and profit for each reported business segment, highlighting the fastest-growing one.`
  Do not write essays in a single bullet.
- `Design Constraint:` sentences name the table/chart/exhibit topically
  (e.g. `Present the segment table comparing all business units on revenue and profit.`).

## Do not enrich bullets (critical anti-leakage rule)

Render `ordered_sections.bullets` and `design_constraint` exactly as the Doc
Card writes them. Do **not** inject specific monetary values, percentages,
growth rates, basis-point figures, EPS/ratio values, or projections sourced from
the Doc Card's **answer fields** (`key_numbers`, `key_terms`, `traps`, the
captions in `key_figures`) — even if those fields are richly populated.

The rule is structural: anything in an answer field is, by construction, the
Stage 3 rubric's score key. If it also lands in `instructions.md`, the
slide-generation model can copy the token instead of reading the document, and
the task degrades into fill-in-the-blank.

Concretely:
- A bullet describes *what the slide must address* (which metric, comparison, or
  distinction). Render it verbatim.
- A `Design Constraint:` line names *which* table/chart and *what topic*. Render
  it verbatim.
- If a Doc Card bullet or design_constraint accidentally contains a value that
  overlaps with `key_numbers[*].claim`, `key_terms[*].definition`, or
  `traps[*].correct_form`, **strip the value during rendering** — keep the
  topical framing, drop the specific number — and add a `warnings[]` entry.

Acceptance test: *a reader of `instructions.md` alone must NOT be able to
reconstruct the document's dollar figures, growth rates, or projections.* If
they can, the file is over-enriched.

## Output discipline

After writing `generation_task/instructions.md` with the Write tool, **stop**.
Emit a single JSON object as your final assistant message:

```json
{
  "stage": "task",
  "ok": true,
  "section_count": <int>,
  "design_constraint_count": <int>,
  "byte_size": <int>,
  "warnings": []
}
```

**Do not run validation commands.** One Read of `_paper_card.json`, one Read of
`_boilerplate_sections.md`, one Write of `instructions.md`, one final assistant
message — that is the entire stage.

If you cannot complete the task, return
`{"stage":"task","ok":false,"reason":"..."}`. No prose, no code fence.

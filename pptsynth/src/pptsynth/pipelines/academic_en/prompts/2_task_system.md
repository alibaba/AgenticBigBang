# Stage 2: Render Instructions

Your job: turn the Paper Card into a single English file
`generation_task/instructions.md` that is **stylistically indistinguishable**
from the PPTSynth academic instructions (CVPR / ICLR / ICML
oral cases). You will not author the rubric in this stage.

## Inputs

- `_paper_card.json` — the validated Paper Card from Stage 1. Treat it
  as the only source of truth for paper-specific content.
- `material.pdf` — read only if a Paper Card field needs disambiguation
  (rare; prefer the Paper Card).
- `_boilerplate_sections.md` — the canonical text for Sections 2-6 of
  the required instructions. **Copy it verbatim** into the output. Do
  not paraphrase, edit, or "improve" it.

## What you must produce

Write a single file: `generation_task/instructions.md`. The file's exact
top-level shape is:

The opening sentence must be **one single line** (no internal line wraps),
matching the required format exactly:

```text
You are to generate a complete, conference-quality academic slide deck suitable for an oral presentation at a top-tier AI conference (e.g., NeurIPS / ICML / ICLR / AAAI), based strictly on the paper. The slides must be accurate, well-structured, and **faithful to the original paper**, with no fabricated content.

---

# **Strict Constraints for the Slides**

Below are the **hard constraints** you MUST satisfy. Slides violating these constraints are considered **incorrect**.

## 1. Content Requirements

The slide deck must have **{lo}-{hi} slides**.

The slide deck must include the following sections, in the order listed below (the number of slides in each section may be determined as appropriate).

1.**Title Slide**

        Paper Title: {title}
        Author Team: {authors}
        Affiliation: {affiliation}
        Conference: {conference}

2.**Outline / Agenda**

3.**{section_3_title}**

        {bullet_1}
        {bullet_2}
        ...
        Design Constraint: {optional design constraint}

... (continue for every ordered_section in the Paper Card)

---

<<< paste verbatim Sections 2-6 from _boilerplate_sections.md here >>>

---

# **Output Expected**

A **complete slide deck** satisfying all constraints above.
```

## Rendering rules

1. **Numbering.** Sections in the `ordered_sections` list are numbered
   starting at 1 in the markdown output. The Title slide is `1.`,
   Outline is `2.`, and so on. Use the bold-on-same-line form
   `1.**Title Slide**` exactly as the well-formed tasks do (no space
   between the number period and the asterisks).
2. **Section titles.** Use the section's `title` field verbatim. Wrap
   it with `**...**`. If `title` is a kind like `Methodology`, you may
   keep it as-is, but the well-formed tasks tend to use paper-specific
   titles like `Methodology: Camera-Ray Conversion`. The Paper Card
   should already have a paper-specific title; do not invent one.
3. **Bullets.** Render each bullet as an indented line (8 spaces of
   leading whitespace, not a markdown list marker). This matches the
   required format. Do **not** add asterisks, dashes, or numbers in
   front of bullets.
4. **Design Constraint.** If the section has a non-empty
   `design_constraint`, render it as the last indented line, prefixed
   exactly with `Design Constraint: `. The line must reference *which*
   figure/table to display and *what topic* it covers — never a
   specific value. Form: `Display <Fig X> showing <topical
   description>.` Do not embed accuracy %, mAP, EM, CIDEr, `+/-Δ`
   gains, or any other `key_numbers` content here, even if the Paper
   Card's `design_constraint` accidentally included one — strip it.
5. **Title slide bullets.** Render the four bullets exactly as
   provided in the Paper Card (`Paper Title:`, `Author Team:`,
   `Affiliation:`, `Conference:`).
6. **Outline / Agenda.** No bullets at all underneath; just the
   bolded heading line.
7. **Page count.** Use the `page_count_range` from the Paper Card,
   e.g. `must have **16-20 slides**`.
8. **Boilerplate.** After the last `ordered_sections` entry, insert a
   blank line, then `---`, then a blank line, then the **verbatim**
   contents of `_boilerplate_sections.md`. Then a blank line, then
   `---`, then `# **Output Expected**`, then a blank line, then
   `A **complete slide deck** satisfying all constraints above.`
9. **No pipeline meta-language.** Never write `PPTSynth`,
   `self-check`, or "as required to satisfy". Words like *benchmark*,
   *rubric*, *checklist* may appear if the paper itself introduces such
   a thing (many AI papers do); the test is whether the sentence is
   describing the paper's content versus describing the deck-generation
   task. The well-formed tasks always read as a real conference commission.
10. **English only.** Even if the paper is partly Chinese, the deck
    instructions are English.

## Style notes (small but important)

- Per-bullet content should sound like the illustrative formatting:
  `Core Idea: Recast pose inference as patch-wise ray prediction, treating a camera as a bundle of rays represented in Plücker coordinates.`
  Do not write essays in a single bullet.
- "Design Constraint:" sentences cite figure or table identifiers
  exactly as they appear in the paper (`Fig 2` or `Figure 2`,
  matching the paper's own usage).
- Authors with `*` for equal contribution: keep the asterisk.

## Do not enrich bullets (critical anti-leakage rule)

Render `ordered_sections.bullets` and `design_constraint` exactly
as the Paper Card writes them. Do **not** inject specific
numerical results, theorem statements, dataset sizes, setup
constants, or any other content sourced from the Paper Card's
**answer fields** (`key_numbers`, `key_terms`, `traps`, the
captions in `key_figures`) — even if those fields are richly
populated.

The rule is structural: anything that lives in an answer field of
`_paper_card.json` is, by construction, the Stage 3 rubric's
score key. If it also lands in `instructions.md`, the
slide-generation model can copy the token onto a slide instead of
reading the paper, and the task degrades into fill-in-the-blank.

Concretely:

- A bullet describes *what the slide must address* (question,
  comparison, topic). Render it verbatim.
- A `Design Constraint:` line cites *which* figure/table and
  *what topic* it covers. Render it verbatim.
- If a Paper Card bullet or design_constraint accidentally
  contains content that overlaps with `key_numbers[*].claim`,
  `key_terms[*].definition`, `traps[*].correct_form`, or a
  numeric figure caption, **strip the answer content during
  rendering** — preserve the topical framing, drop the specific
  value/statement. Add a `warnings[]` entry noting the stripped
  content. This is the renderer's last-line defense; Stage 1
  should not produce such content in the first place.

Acceptance test for the rendered file: *a reader of
`instructions.md` alone must NOT be able to reconstruct the
paper's quantitative findings, theorem statements, complexity
bounds, dataset sizes, or setup constants.* If they can, the file
is over-enriched.

## Output discipline

After you have written `generation_task/instructions.md` with the Write
tool, **stop**. Emit a single JSON object as your final assistant
message:

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

`section_count` is the number of `ordered_sections` you rendered.
`design_constraint_count` is the number of sections that included a
`Design Constraint:` line. `warnings` lists any non-blocking concerns
(e.g. paper field looked truncated).

**Do not run validation commands.** Do not call Bash or Python to
check the file, count lines, grep for forbidden terms, or re-read it.
The harness validates after this stage; redundant checks waste turns.
One Read of `_paper_card.json`, one Read of `_boilerplate_sections.md`,
one Write of `instructions.md`, one final assistant message — that is
the entire stage.

If you cannot complete the task, return
`{"stage":"task","ok":false,"reason":"..."}`.

No prose before or after the JSON. No markdown code fence around it.

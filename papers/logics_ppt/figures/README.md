# Figure sources

`presentation-intelligence-overview.svg` is the editable method diagram;
`presentation-intelligence-overview.png` is the README export. The SVG keeps
all labels, card frames, captions, and arrows as editable vector elements. It
loads the three transparent PNG illustrations under `components/`.

The illustrations were generated with the built-in imagegen tool on
2026-09-22. Their [exact prompts](PROMPTS.md) request a hand-drawn technical
illustration with dark-navy outlines, teal/coral/amber accents, a transparent
background, and no text or arrows. Their respective subjects were:

- `data-synthesis.png`: source documents, structured evidence card, task and
  checklist rubric, with a research assistant inspecting the evidence.
- `guided-distillation.png`: two complementary trajectory stacks, filtered
  slide examples, a student training console, and a research assistant.
- `verifiable-rewards.png`: a rendered slide, visual-check pictograms, and
  a research assistant checking the rendered result.

The PNG overview is rendered from the SVG with CairoSVG using local image
references enabled. Labels and directional connectors were authored in the
SVG rather than generated into the illustrations.

The twelve images under `cases/` are direct image extractions from the local
technical report's Figures 1 and 2: three before/after SFT pairs and three
before/after RL pairs. They are illustrative results, not synthetic assets.
The technical-report PDF is not included in this repository.

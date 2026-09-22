# PPTSynth

PPTSynth creates a professional slide-generation task and an instance-specific
binary rubric from a source PDF. It automatically routes English academic
papers, Chinese academic papers, English finance/economics reports, and Chinese
general-domain documents to their appropriate synthesis profile.

PPTSynth is the public task and rubric synthesis component of the
[Logics-PPT presentation-intelligence research](../papers/logics_ppt/README.md).
The [repository overview](../README.md#cowork-research) links the released
SFT and RL model checkpoints separately.

## Requirements

- Python 3.10 or later
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) available as
  `claude` and authenticated using its standard login flow or environment
  variables
- A text-bearing PDF source document

Install the package in an isolated environment:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e '.[test,release]'
```

Authenticate the Claude Code CLI using one of its supported methods, or set
credentials in your shell or preferred secret manager. Do not commit a populated
`.env` file or any local configuration.

## Data and privacy boundary

This is a code-only release. It contains no source PDFs, generated tasks,
datasets, execution logs, model responses, or organization-specific adapters.

PPTSynth sends extracted PDF text and stage prompts to the locally configured
Claude Code CLI. Generated output may retain the original PDF, extracted facts,
model output, filesystem paths, and diagnostics. Review both the input and the
entire output directory before sharing it. Do not use this tool with material
that you are not authorized to transmit to the configured model provider.

See [DATA_POLICY.md](DATA_POLICY.md) and [SECURITY.md](SECURITY.md) before
processing non-public material.

## Usage

Route and synthesize one PDF:

```bash
pptsynth --input ./material.pdf --out-root ./output --skip-done
```

Process every PDF below a directory:

```bash
pptsynth --input ./materials --out-root ./output --concurrency 2 --effort low
```

Preview inputs with an explicit profile, without model calls or output files:

```bash
pptsynth --input ./material.pdf --out-root ./output --route academic_en --dry-run
```

The default router extracts a bounded text sample and asks the Claude CLI for a
JSON route. It writes `_routing.json` into every case. A low-confidence or
failed route intentionally falls back to the Chinese general-domain profile and
is marked as such in that file. Use `--route` to make a reproducible override.

## Output

Each case contains the copied `material.pdf`, `_routing.json`, a source card,
`research_notes.md`, `generation_task/instructions.md`,
`generation_task/judge_prompt.json`, audit artifacts, and deterministic package
metadata. The rubric has separate material-dependent completeness and correctness
checklists. When the 11-axis audit finds a weak rubric, conditional
verify-refine revises it and re-audits the result with regression protection.

Validate completed output without calling a model:

```bash
pptsynth-verify --out-root ./output
```

Only PDF material is accepted. Generated run logs and stage diagnostics belong
in the user-selected output directory and are excluded from this source package.

## Tests and release checks

Run the offline test suite without model credentials:

```bash
pytest -q
python tools/release_check.py --root .
```

For a release artifact, scan both the source tree and the built archive:

```bash
python -m build
python tools/release_check.py --root . --archive dist/pptsynth-*.tar.gz
```

The release checker is a guardrail, not a substitute for a human review of
every file and the Git history being published.

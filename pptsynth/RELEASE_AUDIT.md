# Public release checklist

## Included scope

This snapshot contains reusable source code, prompts, schemas, public-domain
taxonomy configuration, synthetic/offline tests, and package metadata for four
PPT synthesis profiles. It does not include source material, generated outputs,
datasets, private adapters, service configuration, credentials, caches, or logs.

## Required review before publishing

1. Start from a sanitized snapshot. Do not publish a private repository's Git
   history, because removed files may remain reachable through old commits.
2. Review every tracked file and every generated source distribution or wheel.
3. Run `python tools/release_check.py --root .` and scan each release archive.
4. Confirm the release has an approved software license and any required
   third-party notices.
5. Ensure no sample PDF or generated result is added without separate review of
   its provenance, redistribution rights, privacy impact, and model-use terms.

The automated checker detects common mistakes; it cannot establish ownership,
license compatibility, or the absence of context-specific sensitive data.

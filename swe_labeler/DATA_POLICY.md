# Data policy for this snapshot

This repository contains code, taxonomy definitions, prompts, tests, and
synthetic schema examples only. It does not contain real task instances,
training/evaluation datasets, user-agent trajectories, execution logs,
repository archives, object-storage locators, or model checkpoints.

The examples under `examples/` are fabricated for testing the input schemas and
must not be interpreted as released research data.

## Before processing or publishing data

1. Confirm that collection, processing, redistribution, and model use are
   allowed by the applicable licenses, terms, privacy rules, and organizational
   policy.
2. Remove credentials, signed URLs, internal hostnames, account or employee
   identifiers, proprietary source code, customer content, and sensitive tool
   outputs.
3. Treat trajectories as high-risk: messages and tool results can contain file
   contents, shell output, paths, environment variables, patches, and secrets.
4. Review generated JSONL separately. Labeling outputs may retain source text,
   trajectory summaries, rationales, and raw LLM responses.
5. Publish only an explicitly approved subset and document its provenance,
   inclusion criteria, transformations, and license.

Dataset cards, release manifests, and checksums should be created for any later
data release. They are deliberately not fabricated in this code-only snapshot.

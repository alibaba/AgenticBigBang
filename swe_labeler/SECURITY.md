# Security guidance

- Put API credentials in environment variables or a gitignored local config.
  Never store a real key in the tracked sample YAML files.
- Verify the configured LLM endpoint. Task descriptions, patches, and
  trajectories are transmitted to that endpoint for labeling.
- Keep TLS verification enabled. The sample configurations set
  `ssl_verify: true`.
- Use conservative concurrency and rate limits until the endpoint's behavior is
  understood.
- Inspect both inputs and outputs for secrets, internal paths, private hostnames,
  signed URLs, personal data, and proprietary source before sharing them.
- Start a fresh public Git repository from this sanitized snapshot. Do not push
  the private repository's `.git` history, because removed files and credentials
  may remain reachable from historical commits.

If a credential from the private workspace may have been copied, logged, or
shared, rotate or revoke it rather than relying on deletion alone.

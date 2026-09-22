# Security guidance

- Authenticate the Claude Code CLI through supported local mechanisms or
  environment variables. Never commit a real key, token, endpoint, or populated
  local configuration file.
- Verify the configured model provider before execution. The router receives a
  bounded text extraction from the input PDF, and synthesis stages receive
  prompts and case files derived from that input.
- Review source PDFs before processing and review generated output before
  sharing it. Outputs and diagnostics can preserve content, paths, command
  arguments, model responses, and metadata.
- Use an isolated output directory. Keep generated PDFs, logs, caches, and
  release artifacts out of version control unless they have independently been
  approved for publication.
- Run the release checker on both the source tree and release archive, then
  perform a human review. The checker is pattern-based and cannot detect every
  sensitive value.
- Publish from a new sanitized Git history. Removing a file from a private
  repository does not remove it from historical commits or reflogs.

If a credential or confidential artifact may have been copied, logged, or
shared, rotate or revoke it through the appropriate owner rather than relying
on deletion alone.

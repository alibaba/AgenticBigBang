# Benchmark evaluation parameter specifications

Two shared parameter specifications cover Pro-618 and SWE-bench Multilingual.
Model roles and evaluation rounds do not require separate copies when their
evaluation settings are identical. The task manifest is relative to the paper
package root; use its benchmark_id column to identify the population.

These files specify a maximum interaction budget of 150 actions per trajectory.
They are not runnable launch configurations or independently verified runtime
receipts. Unlisted defaults are unspecified. Model artifacts, credentials,
internal services, storage paths, user identifiers, tracking configuration,
and unused training-only settings are omitted. Locally defined token limits
are resolved instead of retaining unresolved variable references.

## Files

- pro618.yaml: 618 tasks, 200,000-token sequence limit, 150 actions,
  25,600 new tokens per action, temperature 1.0, top-p 0.95 and top-k 20;
  Pro anti-hacking enabled.
- multilingual.yaml: 300 tasks, 200,000-token sequence limit, 150 actions,
  12,280 new tokens per action, temperature 1.0, top-p 0.95 and top-k 20.

Both specify BF16 vLLM inference. Engine allocation settings reflect these
supplied configurations, not a requirement for every model architecture.
The original Pro configuration targets a MoE deployment; model identity has
been removed, and its engine layout is not independently verified for every
evaluated model.

## Dependencies and interpretation

Pro prompt templates are supplied in prompts/pro_r2e.yaml, including the
system and task prompts, observation/final-step templates, textual tool
specifications, and relative tool implementation references. Template content
is preserved; private launch settings are omitted. The referenced tool
implementation files and environment backend are not included.
Multilingual uses a SWE-agent adapter and a default scaffold;
the internal adapter and the resolved scaffold/prompt definitions are not
included. The dependency-mirror URL is deployment-specific and omitted, while
its affected public repository prefixes are retained.

max_env_time, task_timeout_sec, and rpc_timeout are separate settings and must
not be interpreted as interchangeable budgets. The task timeout is in seconds;
other field names and values are retained without inventing missing semantics.
Reset retries and verifier concurrency settings are not additional model
evaluation rounds.

## Pro anti-hacking configuration

The Pro specification incorporates the supplied anti-hacking overlay on its
base configuration. The root pro_antihack_enabled flag and its resolved
environment value are true. Both source environment sections specify
strict_eval_new_sandbox: true; their shared settings are represented once in
the environment section. Private launch references and experiment names are
omitted rather than distributed as unresolved configuration dependencies.

The inherited git_cleanup_level and git_remove_tags values remain the string
"none". These legacy fields are distinct from the enabled pro_antihack_enabled
flag; they must not be interpreted as disabling that flag. The overlay alone
does not establish the backend implementation, exact cleanup operations, or
their execution in historical runs. The released interaction limit remains
150 actions, as specified for this package.

The evaluation_runs.csv config_id fields link Pro-618 runs to pro618_eval and
Multilingual runs to multilingual_eval. They identify the released, shared
parameter specifications, not independent receipts of historical runtime
behavior. Anti-hacking runtime evidence, executable tool/backend dependencies,
and the resolved Multilingual scaffold remain outside this specification.

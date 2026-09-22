# Using Logics-SWE-Env-2.5K Instance Images

The [Logics-SWE-Env-2.5K](https://huggingface.co/datasets/Logics-MLLM/Logics-SWE-Env-2.5K) release pairs each dataset row with one self-contained development image. The image contains the repository at the task's base commit, its dependencies, the test patch, the reference fix, and a small test harness. This document describes the image contract and the exact evaluation sequence used by the ROLL instance rollout.

## 1. Download the dataset

Install the Hugging Face CLI and download the release:

```bash
pip install -U huggingface_hub
hf download Logics-MLLM/Logics-SWE-Env-2.5K \
  --repo-type dataset \
  --local-dir ./Logics-SWE-Env-2.5K
```

Set `DATA` to the downloaded JSONL file before using the commands below:

```bash
DATA=$(find ./Logics-SWE-Env-2.5K -type f -name '*.jsonl' -print -quit)
```

## 2. Dataset-to-image contract

Use these fields from each JSONL row:

| Field | Meaning |
| --- | --- |
| `instance_id` | Stable task identifier. It is also the GHCR tag. |
| `docker_image` | Full released GHCR environment-image reference. |
| `base_commit` | Expected Git `HEAD` before the agent starts. |
| `problem_statement` | Task given to the agent. |
| `image_info` | JSON object, or a JSON-encoded object, containing the paths and runtime user described below. |
| `patch` | Reference solution. It matches the image's `fix.patch`; do not expose it to an evaluated agent. |
| `test_patch` | Tests added for this task. It matches the image's `test.patch`. |

`image_info` contains:

```json
{
  "remote_user": "root",
  "project_path": "/workspaces/example-project",
  "script_folder": "/root",
  "remote_workspace_folder": "/workspaces/example-project"
}
```

Do not hard-code `/root` or a particular workspace. Most images use `root`, while a small number use `vscode` and keep the scripts under `/home/vscode`. Always read `project_path`, `script_folder`, and `remote_user` from the row.

For the released GHCR images, the mapping is:

```text
ghcr.io/jzwilliams07/logics-swe-env:<instance_id>
```

For example:

```text
ghcr.io/jzwilliams07/logics-swe-env:openhpi__poseidon-566
```

## 3. Files inside one image

The repository lives at `image_info.project_path`. The following assets live at `image_info.script_folder`:

| File | Purpose |
| --- | --- |
| `reset_project.sh` | Restores tracked files and removes untracked files before a new attempt. This deletes the current candidate changes. |
| `apply_test_patch.sh` | Applies `test.patch` to the repository. Run it once, after the agent or candidate patch has finished modifying the project. |
| `apply_fix_patch.sh` | Applies the reference solution `fix.patch`. Use only for a gold/oracle sanity check. |
| `run.sh` | Runs the task-specific build/test command and then checks the required tests. This is the authoritative evaluator entry point. |
| `swe` | Test adapter called by `run.sh`. It supports different build tools across images, such as Go and Python/pip. |
| `test.patch` | Test changes for the task. |
| `fix.patch` | Reference solution. This is label data. |
| `tests.json` | Required test suites and cases used by `swe check`. |

`run.sh` writes structured results to:

```text
<project_path>/test_result.json
```

The build tool and all task-specific arguments are already encoded in `run.sh`. Users should call `run.sh` instead of reconstructing the underlying test command.

The scripts follow this common pattern, with paths and `<tool>` specialized per image:

```bash
# reset_project.sh
cd <project_path>
git checkout -- .
git clean -fd -e .mvn node_modules

# apply_test_patch.sh / apply_fix_patch.sh
cd <project_path>
git apply --whitespace=fix <script_folder>/test.patch   # or fix.patch

# run.sh
<script_folder>/swe test \
  --workspace=<project_path> \
  --tool=<tool> \
  --test_patch=<script_folder>/test.patch \
  --fix_patch=<script_folder>/fix.patch \
  --output=<project_path>/test_result.json

<script_folder>/swe check \
  --expect_file=<script_folder>/tests.json \
  --result_file=<project_path>/test_result.json
```

The observed tool values include `go` and `pip`; other images may encode a different tool. The caller does not need to select it.

## 4. Correct execution order

### Evaluate an agent or candidate patch

1. Start a fresh container.
2. Verify that the repository `HEAD` equals `base_commit`.
3. Let the agent edit the repository, or apply a candidate patch.
4. Run `apply_test_patch.sh` once.
5. Run `run.sh`.
6. Treat exit status `0` as passed and retain `test_result.json` for analysis.

This matches the normal ROLL path: the agent edits first, then the reward code injects the test patch and executes the evaluator.

### Check the unsolved baseline

```bash
bash <script_folder>/reset_project.sh
bash <script_folder>/apply_test_patch.sh
bash <script_folder>/run.sh
```

The baseline is normally expected to fail because the issue has not been fixed.

### Check the reference solution

```bash
bash <script_folder>/reset_project.sh
bash <script_folder>/apply_test_patch.sh
bash <script_folder>/apply_fix_patch.sh
bash <script_folder>/run.sh
```

This order is the ROLL `golden_patch` path. It is a dataset/image integrity check, not a valid agent evaluation.

Do not run `reset_project.sh` after the agent has edited the repository: it uses `git checkout -- .` and `git clean`, so it removes the candidate work. Do not apply `test.patch` twice; the second `git apply` normally fails. To rerun only the tests, call `run.sh` again. To begin a clean attempt, reset and then reapply the patches in the sequence above.

## 5. Run one instance with Docker

Requirements:

- Docker
- the released JSONL file
- access to `ghcr.io/jzwilliams07/logics-swe-env`

Public GHCR packages can be pulled without authentication. While the package is private, authenticate first:

```bash
echo "$GHCR_TOKEN" | docker login ghcr.io --username "$GITHUB_USER" --password-stdin
```

The included helper reads the paths and user from the dataset row:

```bash
HELPER=instance_environment/run_instance_image.py
DATA=$(find ./Logics-SWE-Env-2.5K -type f -name '*.jsonl' -print -quit)
INSTANCE=openhpi__poseidon-566
IMAGE_REPO=ghcr.io/jzwilliams07/logics-swe-env
```

Inspect the resolved metadata without starting Docker:

```bash
python3 "$HELPER" \
  --dataset "$DATA" \
  --instance-id "$INSTANCE" \
  --image-repo "$IMAGE_REPO" \
  --mode inspect
```

Open an interactive shell at the project directory for development or training-data inspection:

```bash
python3 "$HELPER" \
  --dataset "$DATA" \
  --instance-id "$INSTANCE" \
  --image-repo "$IMAGE_REPO" \
  --mode shell
```

This shell can read the evaluator assets, including `fix.patch`. Do not use it as a leakage-controlled benchmark environment.

Evaluate a candidate patch:

```bash
python3 "$HELPER" \
  --dataset "$DATA" \
  --instance-id "$INSTANCE" \
  --image-repo "$IMAGE_REPO" \
  --mode candidate \
  --candidate-patch /path/to/candidate.patch \
  --output ./results/$INSTANCE.test_result.json
```

Run the baseline or gold integrity checks:

```bash
python3 "$HELPER" --dataset "$DATA" --instance-id "$INSTANCE" \
  --image-repo "$IMAGE_REPO" --mode baseline

python3 "$HELPER" --dataset "$DATA" --instance-id "$INSTANCE" \
  --image-repo "$IMAGE_REPO" --mode gold
```

If the released JSONL already points to GHCR, omit `--image-repo`.

## 6. Manual Docker workflow

The helper is optional. Read `PROJECT_PATH`, `SCRIPT_FOLDER`, and `REMOTE_USER` from `image_info`, then use the equivalent manual flow:

```bash
IMAGE="ghcr.io/jzwilliams07/logics-swe-env:$INSTANCE"
CONTAINER="logics-swe-${INSTANCE//[^a-zA-Z0-9_.-]/-}"

docker pull "$IMAGE"
docker run --detach --name "$CONTAINER" --user "$REMOTE_USER" \
  --entrypoint /bin/bash "$IMAGE" \
  -lc "trap 'exit 0' TERM INT; while :; do sleep 3600; done"
```

Run the candidate and evaluator commands as the same image user:

```bash
docker exec --user "$REMOTE_USER" "$CONTAINER" \
  git -C "$PROJECT_PATH" rev-parse HEAD

docker cp /path/to/candidate.patch "$CONTAINER":/tmp/candidate.patch
docker exec --user root "$CONTAINER" chmod 0644 /tmp/candidate.patch
docker exec --user "$REMOTE_USER" "$CONTAINER" \
  git -C "$PROJECT_PATH" apply --whitespace=nowarn /tmp/candidate.patch

docker exec --user "$REMOTE_USER" "$CONTAINER" \
  bash "$SCRIPT_FOLDER/apply_test_patch.sh"

docker exec --user "$REMOTE_USER" "$CONTAINER" \
  bash "$SCRIPT_FOLDER/run.sh"

docker cp "$CONTAINER:$PROJECT_PATH/test_result.json" ./test_result.json
docker rm --force "$CONTAINER"
```

## 7. Training use and leakage-controlled evaluation

The full image physically contains `fix.patch`, `test.patch`, and `tests.json`. This is appropriate for RL training, data inspection, and reproducibility, but an agent with unrestricted shell access to the full image can read those files.

For a blind evaluation, separate solving from grading:

1. Give the agent the problem statement and repository at `base_commit` in a workspace where the evaluator assets are absent or inaccessible.
2. Export only the agent's candidate Git patch.
3. Start a fresh, full environment image.
4. Grade the exported patch with the helper's `candidate` mode.

Do not include the dataset's `patch` field in the agent prompt. Do not report results from `shell` mode as leakage-controlled evaluation results.

## 8. Pass/fail semantics

`run.sh` has two stages:

1. `swe test` invokes the image-specific build tool and writes `test_result.json`.
2. `swe check` compares that file with `tests.json`.

The final `swe check` result is authoritative. A successful run exits with status `0` and prints:

```text
all test cases run successfully
```

Do not infer the final reward from an intermediate compiler/test log line. The current ROLL implementation assigns reward `1.0` only when the evaluator output contains the success marker above; otherwise it assigns `0.0`.

## 9. Verified example

The protocol was checked on the `openhpi__poseidon-566` image:

- the image Git `HEAD` matched the row's `base_commit`;
- the embedded `test.patch` and `fix.patch` matched the row's `test_patch` and `patch` byte-for-byte after line-ending normalization;
- baseline execution exited with status `1`;
- test patch plus reference fix exited with status `0` and printed the success marker.

It was also checked on a Python/pip image and on an image whose runtime user and script directory are `vscode` and `/home/vscode`. The file protocol is the same; only the paths, user, project, and build tool differ per row.

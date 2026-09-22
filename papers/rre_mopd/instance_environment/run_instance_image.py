#!/usr/bin/env python3
"""Run one released instance environment image with Docker.

The dataset row is the source of truth for the image, project directory,
script directory, runtime user, and base commit.  The helper deliberately
does not expose the reference fix to the agent in normal candidate mode.
"""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any


MODES = ("inspect", "shell", "baseline", "candidate", "gold")


def load_instance(dataset: Path, instance_id: str) -> dict[str, Any]:
    matches: list[dict[str, Any]] = []
    with dataset.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{dataset}:{line_number}: invalid JSON: {exc}") from exc
            if row.get("instance_id") == instance_id:
                matches.append(row)

    if not matches:
        raise ValueError(f"instance_id {instance_id!r} was not found in {dataset}")
    if len(matches) != 1:
        raise ValueError(f"instance_id {instance_id!r} appears {len(matches)} times in {dataset}")
    return matches[0]


def parse_image_info(row: dict[str, Any]) -> dict[str, str]:
    raw = row.get("image_info")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"image_info is not valid JSON: {exc}") from exc
    if not isinstance(raw, dict):
        raise ValueError("image_info must be an object or a JSON-encoded object")

    required = ("project_path", "script_folder", "remote_user")
    missing = [key for key in required if not isinstance(raw.get(key), str) or not raw[key]]
    if missing:
        raise ValueError(f"image_info is missing required fields: {', '.join(missing)}")
    return {key: str(value) for key, value in raw.items() if value is not None}


def resolve_image(row: dict[str, Any], image_repo: str | None) -> str:
    if image_repo:
        return f"{image_repo.rstrip(':')}:{row['instance_id']}"
    image = row.get("docker_image")
    if not isinstance(image, str) or not image:
        raise ValueError("the dataset row has no docker_image")
    return image


def show_command(command: list[str]) -> None:
    print("+ " + shlex.join(command), flush=True)


def run(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    show_command(command)
    return subprocess.run(command, check=check, text=True)


def capture(command: list[str]) -> str:
    show_command(command)
    return subprocess.check_output(command, text=True).strip()


def docker_exec(container: str, user: str, command: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run(["docker", "exec", "--user", user, container, *command], check=check)


def copy_test_result(container: str, project_path: str, output: Path) -> None:
    probe = subprocess.run(
        ["docker", "exec", container, "test", "-f", f"{project_path}/test_result.json"],
        check=False,
    )
    if probe.returncode == 0:
        output.parent.mkdir(parents=True, exist_ok=True)
        run(["docker", "cp", f"{container}:{project_path}/test_result.json", str(output)])
        print(f"Saved structured test results to {output}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True, help="Released JSONL dataset")
    parser.add_argument("--instance-id", required=True)
    parser.add_argument("--mode", choices=MODES, default="inspect")
    parser.add_argument(
        "--image-repo",
        help=(
            "Override the registry/repository and derive the tag from instance_id, "
            "for example ghcr.io/jzwilliams07/logics-swe-env"
        ),
    )
    parser.add_argument("--candidate-patch", type=Path, help="Required in candidate mode")
    parser.add_argument("--output", type=Path, help="Where to copy test_result.json")
    parser.add_argument("--container-name", help="Docker container name")
    parser.add_argument("--no-pull", action="store_true", help="Use the local image cache")
    parser.add_argument("--keep-container", action="store_true")
    args = parser.parse_args()

    if args.mode == "candidate" and args.candidate_patch is None:
        parser.error("--candidate-patch is required in candidate mode")
    if args.candidate_patch is not None and not args.candidate_patch.is_file():
        parser.error(f"candidate patch does not exist: {args.candidate_patch}")

    try:
        row = load_instance(args.dataset, args.instance_id)
        image_info = parse_image_info(row)
        image = resolve_image(row, args.image_repo)
    except (OSError, KeyError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    project_path = image_info["project_path"].rstrip("/") or "/"
    script_folder = image_info["script_folder"].rstrip("/") or "/"
    remote_user = image_info["remote_user"]
    base_commit = str(row.get("base_commit") or "")
    metadata = {
        "instance_id": args.instance_id,
        "image": image,
        "project_path": project_path,
        "script_folder": script_folder,
        "remote_user": remote_user,
        "base_commit": base_commit,
    }
    print(json.dumps(metadata, indent=2, ensure_ascii=False))
    if args.mode == "inspect":
        return 0

    container = args.container_name or f"logics-swe-{uuid.uuid4().hex[:10]}"
    output = args.output or Path(f"{args.instance_id}.test_result.json")
    started = False
    try:
        if not args.no_pull:
            run(["docker", "pull", image])
        run(
            [
                "docker",
                "run",
                "--detach",
                "--name",
                container,
                "--user",
                remote_user,
                "--entrypoint",
                "/bin/bash",
                image,
                "-lc",
                "trap 'exit 0' TERM INT; while :; do sleep 3600; done",
            ]
        )
        started = True

        required_files = (
            "reset_project.sh",
            "apply_test_patch.sh",
            "apply_fix_patch.sh",
            "run.sh",
            "swe",
            "test.patch",
            "fix.patch",
            "tests.json",
        )
        for name in required_files:
            docker_exec(container, remote_user, ["test", "-f", f"{script_folder}/{name}"])

        actual_commit = capture(
            ["docker", "exec", "--user", remote_user, container, "git", "-C", project_path, "rev-parse", "HEAD"]
        )
        if base_commit and actual_commit != base_commit:
            raise RuntimeError(f"base commit mismatch: dataset={base_commit}, image={actual_commit}")

        if args.mode == "shell":
            command = [
                "docker",
                "exec",
                "--interactive",
                "--tty",
                "--user",
                remote_user,
                "--workdir",
                project_path,
                container,
                "/bin/bash",
            ]
            show_command(command)
            return subprocess.run(command, check=False).returncode

        docker_exec(container, remote_user, ["bash", f"{script_folder}/reset_project.sh"])

        if args.mode == "candidate":
            candidate_in_container = "/tmp/candidate.patch"
            run(["docker", "cp", str(args.candidate_patch.resolve()), f"{container}:{candidate_in_container}"])
            # docker cp creates a root-owned file and preserves the local mode.
            # Make it readable when the image contract uses a non-root user.
            run(["docker", "exec", "--user", "root", container, "chmod", "0644", candidate_in_container])
            docker_exec(
                container,
                remote_user,
                ["git", "-C", project_path, "apply", "--whitespace=nowarn", candidate_in_container],
            )

        # ROLL injects the test patch only after the agent has finished editing.
        docker_exec(container, remote_user, ["bash", f"{script_folder}/apply_test_patch.sh"])
        if args.mode == "gold":
            # The reference fix is only an oracle/sanity check. Never expose it to
            # an evaluated agent or apply it in candidate mode.
            docker_exec(container, remote_user, ["bash", f"{script_folder}/apply_fix_patch.sh"])

        result = docker_exec(
            container,
            remote_user,
            ["bash", f"{script_folder}/run.sh"],
            check=False,
        )
        copy_test_result(container, project_path, output)
        if result.returncode == 0:
            print("PASS: run.sh exited with status 0")
        else:
            print(f"FAIL: run.sh exited with status {result.returncode}", file=sys.stderr)
        return result.returncode
    except (OSError, subprocess.CalledProcessError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    finally:
        if started and not args.keep_container:
            subprocess.run(["docker", "rm", "--force", container], check=False)
        elif started:
            print(f"Container kept: {container}")


if __name__ == "__main__":
    raise SystemExit(main())

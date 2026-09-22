"""Common claude -p invocation for any stage.

Design contract:
- Each stage runs in its own ``claude -p`` subprocess (own session_id, own
  context window).
- ``cwd`` is always the case directory so the model can only see files inside
  that case.
- ``--no-session-persistence`` keeps the host filesystem clean and prevents
  cross-case leakage via the user-level Claude CLI session store.
- ``--bare`` skips host CLAUDE.md, hooks, plugins, MCP — important for
  reproducibility across machines.
- Each invocation streams JSON stdout to ``_stage_logs/<stage>.stdout.json``
  for offline diagnosis.

We deliberately do *not* wrap the subprocess in shells. The stage prompt
goes via ``-p <prompt>`` and the system prompt via
``--append-system-prompt-file <file>``.
"""
from __future__ import annotations

import asyncio
import json
import shlex
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


_DEFAULT_TOOLS = ["Read", "Write", "Edit", "Bash", "Glob", "Grep"]


@dataclass
class StageOutcome:
    stage: str
    case_slug: str
    ok: bool
    duration_s: float
    cmd: list[str] = field(default_factory=list)
    session_id: str | None = None
    cost_usd: float | None = None
    parsed_payload: dict[str, Any] | None = None
    raw_result: str | None = None
    error: str | None = None
    stdout_log_path: Path | None = None


def build_cmd(
    *,
    stage_name: str,
    user_prompt: str,
    case_dir: Path,
    system_prompt_file: Path,
    allowed_tools: list[str],
    max_turns: int,
    model: str | None,
    max_budget_usd: float | None,
    extra_add_dirs: list[Path] | None = None,
    max_thinking_tokens: int | None = None,
) -> list[str]:
    cmd: list[str] = [
        "claude",
        "-p",
        user_prompt,
        "--add-dir",
        str(case_dir),
        "--append-system-prompt-file",
        str(system_prompt_file),
        "--permission-mode",
        "acceptEdits",
        "--allowedTools",
        ",".join(allowed_tools),
        "--max-turns",
        str(max_turns),
        "--output-format",
        "json",
        "--no-session-persistence",
        "--bare",
        # Exclude the user-level Claude CLI settings so its env block (ANTHROPIC_BASE_URL,
        # ANTHROPIC_AUTH_TOKEN, ANTHROPIC_MODEL, ...) cannot override the
        # per-batch env exported by the launcher script. Without this, the
        # host's interactive-session gateway silently captures every stage.
        "--setting-sources",
        "project,local",
    ]
    if extra_add_dirs:
        for p in extra_add_dirs:
            cmd += ["--add-dir", str(p)]
    if model:
        cmd += ["--model", model]
    if max_budget_usd is not None:
        cmd += ["--max-budget-usd", f"{max_budget_usd:.2f}"]
    if max_thinking_tokens is not None:
        cmd += ["--max-thinking-tokens", str(max_thinking_tokens)]
    return cmd


async def run_stage(
    *,
    stage_name: str,
    case_slug: str,
    case_dir: Path,
    user_prompt: str,
    system_prompt_file: Path,
    allowed_tools: list[str] | None = None,
    max_turns: int = 40,
    timeout_s: int = 1800,
    model: str | None = None,
    max_budget_usd: float | None = None,
    extra_add_dirs: list[Path] | None = None,
    max_thinking_tokens: int | None = None,
) -> StageOutcome:
    """Run one stage. Returns a StageOutcome. Never raises (except on truly
    pathological host errors like a missing claude binary)."""
    tools = list(allowed_tools or _DEFAULT_TOOLS)
    cmd = build_cmd(
        stage_name=stage_name,
        user_prompt=user_prompt,
        case_dir=case_dir,
        system_prompt_file=system_prompt_file,
        allowed_tools=tools,
        max_turns=max_turns,
        model=model,
        max_budget_usd=max_budget_usd,
        extra_add_dirs=extra_add_dirs,
        max_thinking_tokens=max_thinking_tokens,
    )

    logs_dir = case_dir / "_stage_logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    stdout_log = logs_dir / f"{stage_name}.stdout.json"
    stderr_log = logs_dir / f"{stage_name}.stderr.txt"
    cmd_log = logs_dir / f"{stage_name}.cmd.txt"
    cmd_log.write_text(" ".join(shlex.quote(c) for c in cmd) + "\n", encoding="utf-8")

    start = time.monotonic()
    proc: asyncio.subprocess.Process | None = None
    timed_out = False
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(case_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.DEVNULL,
        )
        # Independent watchdog: SIGKILL the child past the deadline even if
        # asyncio.wait_for fails to cancel proc.communicate() (observed with
        # network connection hangs on Python 3.12).
        async def _watchdog():
            nonlocal timed_out
            await asyncio.sleep(timeout_s)
            if proc.returncode is None:
                timed_out = True
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass
        watchdog = asyncio.create_task(_watchdog())
        try:
            stdout, stderr = await proc.communicate()
        finally:
            watchdog.cancel()
            try:
                await watchdog
            except (asyncio.CancelledError, Exception):
                pass
        if timed_out:
            return StageOutcome(
                stage=stage_name,
                case_slug=case_slug,
                ok=False,
                duration_s=time.monotonic() - start,
                cmd=cmd,
                error=f"timeout after {timeout_s}s (watchdog kill)",
                stdout_log_path=stdout_log,
            )
    except FileNotFoundError as e:
        return StageOutcome(
            stage=stage_name,
            case_slug=case_slug,
            ok=False,
            duration_s=time.monotonic() - start,
            cmd=cmd,
            error=f"claude CLI not found: {e}",
            stdout_log_path=stdout_log,
        )

    duration = time.monotonic() - start
    raw_stdout = stdout.decode("utf-8", errors="replace")
    raw_stderr = stderr.decode("utf-8", errors="replace")

    stdout_log.write_text(raw_stdout, encoding="utf-8")
    if raw_stderr.strip():
        stderr_log.write_text(raw_stderr, encoding="utf-8")

    if proc.returncode != 0:
        return StageOutcome(
            stage=stage_name,
            case_slug=case_slug,
            ok=False,
            duration_s=duration,
            cmd=cmd,
            error=f"claude exit {proc.returncode}; stderr tail: {raw_stderr[-400:]}",
            stdout_log_path=stdout_log,
        )

    try:
        payload = json.loads(raw_stdout)
    except json.JSONDecodeError as e:
        return StageOutcome(
            stage=stage_name,
            case_slug=case_slug,
            ok=False,
            duration_s=duration,
            cmd=cmd,
            error=f"non-JSON stdout: {e}",
            stdout_log_path=stdout_log,
        )

    return StageOutcome(
        stage=stage_name,
        case_slug=case_slug,
        ok=bool(payload.get("subtype") == "success" and not payload.get("is_error")),
        duration_s=duration,
        cmd=cmd,
        session_id=payload.get("session_id"),
        cost_usd=payload.get("total_cost_usd"),
        parsed_payload=payload,
        raw_result=payload.get("result"),
        error=None
        if payload.get("subtype") == "success" and not payload.get("is_error")
        else f"subtype={payload.get('subtype')!r} is_error={payload.get('is_error')!r}",
        stdout_log_path=stdout_log,
    )


def extract_final_json(raw_result: str | None) -> dict[str, Any] | None:
    """Pull the JSON object emitted as the agent's final assistant message.

    Strategy: agents are instructed to emit *only* one JSON object as the
    final message, no fences. But weak models occasionally wrap in fences or
    add prose. We try strict parse first, then fall back to extracting the
    largest balanced ``{...}`` substring.
    """
    if not raw_result:
        return None
    text = raw_result.strip()
    # Strip a leading/trailing markdown fence if present.
    if text.startswith("```"):
        # remove first line
        nl = text.find("\n")
        if nl > 0:
            text = text[nl + 1 :]
        if text.endswith("```"):
            text = text[: -3].rstrip()
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        pass

    # Find largest balanced { ... } block.
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(text)):
        c = text[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                fragment = text[start : i + 1]
                try:
                    obj = json.loads(fragment)
                    return obj if isinstance(obj, dict) else None
                except json.JSONDecodeError:
                    return None
    return None

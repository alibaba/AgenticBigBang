"""
Trajectory normalizer and summarizer.
Converts raw trajectory data into a format suitable for L2 labeling.

Strategy: Include as much trajectory content as the configured long-context model allows.
Only do light filtering: remove redundant system prompts and tool schema definitions.
"""
from __future__ import annotations
import json
import re
import os
import hashlib
import logging
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)

MAX_TRAJECTORY_CHARS = 3_000_000  # ~750K tokens, safe for 1M context models
MAX_SINGLE_CONTENT_CHARS = 50_000  # cap individual tool_result/message to avoid one giant blob
MAX_COMPACT_TRAJECTORY_CHARS = 200_000
MAX_COMPACT_MESSAGE_CHARS = 4_000
MAX_COMPACT_TOOL_RESULT_CHARS = 5_000
SKIP_SYSTEM_PROMPT = True  # system prompts are identical across instances, skip them

LOW_SIGNAL_RESULT_TOOLS = {"Read", "Grep", "Glob", "LS", "Search"}
HIGH_SIGNAL_RESULT_RE = re.compile(
    r"\b(error|failed|failure|passed|tests?|traceback|exception|exit code|"
    r"build|compiled|written|updated|success)\b",
    re.IGNORECASE,
)
SYSTEM_REMINDER_RE = re.compile(
    r"<system-reminder\b[^>]*>.*?</system-reminder>",
    re.IGNORECASE | re.DOTALL,
)
USER_QUERY_RE = re.compile(
    r"<user_query\b[^>]*>(.*?)</user_query>",
    re.IGNORECASE | re.DOTALL,
)
# System-generated compaction requests injected as user messages. They are not
# real user intent and can hijack downstream labeling LLMs into summarizing.
COMPACTION_QUERY_RE = re.compile(
    r"^\s*Your task is to create a detailed summary of the conversation",
    re.IGNORECASE,
)


@dataclass
class TrajectoryInstance:
    instance_id: str
    trajectory_id: str
    model: str
    scaffold: str

    # Existing L1 labels. They may be empty in the full L1+L2 pipeline.
    task_type_l1: str = ""
    domain_l1: str = ""
    code_language: str = ""
    task_spec_type: str = ""
    dependency_context: str = ""

    # Trajectory content (for prompt injection)
    trajectory_summary: str = ""

    # L2 labels (filled by labeler)
    labels: Optional[dict] = None

    # Existing L1 explanation fields, retained for preserve mode only.
    l1_rationales: dict[str, str] = field(default_factory=dict, repr=False)

    # Source locators used only by the new full pipeline.
    source_line_number: Optional[int] = field(default=None, repr=False)
    source_content_sha256: str = field(default="", repr=False)
    source_artifact_uri: str = field(default="", repr=False)

    def to_dict(self, include_source_metadata: bool = False) -> dict:
        result = asdict(self)
        result.pop("l1_rationales", None)
        source_fields = (
            "source_line_number",
            "source_content_sha256",
            "source_artifact_uri",
        )
        if not include_source_metadata:
            for key in source_fields:
                result.pop(key, None)
        return result

    def to_json_line(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)


def normalize_trajectory_jsonl(
    path: str,
    limit: Optional[int] = None,
    *,
    require_l1: bool = True,
    content_mode: str = "full",
    unique_instance_ids: bool = False,
) -> list[TrajectoryInstance]:
    if content_mode not in {"full", "compact"}:
        raise ValueError(f"Unsupported trajectory content mode: {content_mode}")

    instances = []
    seen_digests: dict[str, dict[str, str]] = {}
    used_instance_ids: dict[str, str] = {}
    with open(path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if limit and i >= limit:
                break
            source_line = line.rstrip("\r\n")
            line = source_line.strip()
            if not line:
                continue
            source_digest = hashlib.sha256(source_line.encode("utf-8")).hexdigest()
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                logger.warning(f"Line {i}: invalid JSON, skipping")
                continue
            if not isinstance(obj, dict):
                logger.warning(
                    "Line %s: expected a JSON object, got %s; skipping",
                    i + 1,
                    type(obj).__name__,
                )
                continue

            try:
                instance = _parse_trajectory(
                    obj,
                    require_l1=require_l1,
                    content_mode=content_mode,
                    source_line_number=i + 1,
                    source_content_sha256=source_digest,
                )
            except Exception:
                logger.exception("Line %s: unexpected trajectory schema, skipping", i + 1)
                continue
            if instance:
                if unique_instance_ids:
                    instance_id = _resolve_unique_instance_id(
                        instance.trajectory_id,
                        source_digest,
                        i + 1,
                        seen_digests,
                        used_instance_ids,
                    )
                    if instance_id is None:
                        logger.warning(
                            "Line %s: exact duplicate trajectory for request ID %r, skipping",
                            i + 1,
                            instance.trajectory_id,
                        )
                        continue
                    instance.instance_id = instance_id
                    if not instance.trajectory_id:
                        instance.trajectory_id = instance_id
                instances.append(instance)

    logger.info(f"Loaded {len(instances)} trajectory instances from {path}")
    return instances


# Mapping from old L1 names in source data to current L2 definition keys
DOMAIN_L1_RENAME = {
    "data_science_ml": "data_science",
}


def _decode_json_content(value) -> Optional[tuple[list[dict], dict]]:
    """Return messages and trajectory-level metadata for supported input shapes."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return None

    if isinstance(value, list):
        if not value:
            return None
        messages = [message for message in value if isinstance(message, dict)]
        return (messages, {}) if messages else None

    if isinstance(value, dict):
        messages = value.get("messages", [])
        if not isinstance(messages, list):
            return None
        messages = [message for message in messages if isinstance(message, dict)]
        return (messages, value) if messages else None

    return None


def _decode_optional_dict(value) -> dict:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return {}
    return value if isinstance(value, dict) else {}


def _extract_existing_l1(obj: dict, *, prefer_legacy: bool = False) -> dict[str, str]:
    """Read L1 fields from modern output or legacy label_result containers."""
    label_result = _decode_optional_dict(obj.get("label_result"))
    legacy_result = _decode_optional_dict(label_result.get("result"))
    candidates = [
        _decode_optional_dict(obj.get("labels")),
        _decode_optional_dict(label_result.get("labels")),
        legacy_result,
        label_result,
    ]

    source = {}
    if prefer_legacy and legacy_result:
        source = legacy_result
    else:
        # Prefer a complete five-dimensional set so a partial modern container
        # cannot hide a complete legacy result.
        for candidate in candidates:
            values = (
                candidate.get("task_type_l1", candidate.get("task_type", "")),
                candidate.get("domain_l1", candidate.get("application_domain", "")),
                candidate.get("code_language", ""),
                candidate.get("task_spec_type", ""),
                candidate.get("dependency_context", ""),
            )
            if all(values):
                source = candidate
                break
        if not source:
            for candidate in candidates:
                if candidate.get("task_type_l1") or candidate.get("task_type"):
                    source = candidate
                    break

    return {
        "task_type_l1": source.get("task_type_l1", source.get("task_type", "")),
        "domain_l1": source.get("domain_l1", source.get("application_domain", "")),
        "code_language": source.get("code_language", ""),
        "task_spec_type": source.get("task_spec_type", ""),
        "dependency_context": source.get("dependency_context", ""),
        "code_language_rationale": source.get("code_language_rationale", ""),
        "task_type_rationale": source.get("task_type_rationale", ""),
        "domain_rationale": source.get(
            "domain_rationale", source.get("application_domain_rationale", "")
        ),
        "task_spec_type_rationale": source.get("task_spec_type_rationale", ""),
        "dependency_context_rationale": source.get(
            "dependency_context_rationale", ""
        ),
    }


def _parse_trajectory(
    obj: dict,
    *,
    require_l1: bool = True,
    content_mode: str = "full",
    source_line_number: Optional[int] = None,
    source_content_sha256: str = "",
) -> Optional[TrajectoryInstance]:
    decoded = _decode_json_content(obj.get("json_content"))
    if decoded is None:
        # Fallback for schemas that store the conversation directly under
        # a top-level `messages` field.
        decoded = _decode_json_content(obj.get("messages"))
    if decoded is None:
        return None
    messages, metadata = decoded

    l1 = _extract_existing_l1(obj, prefer_legacy=require_l1)
    task_type_l1 = l1["task_type_l1"]
    domain_l1 = l1["domain_l1"]

    # Apply domain name mapping
    domain_l1 = DOMAIN_L1_RENAME.get(domain_l1, domain_l1)

    # Preserve the legacy L2-only gate: it only requires task and domain.
    if require_l1 and (not task_type_l1 or not domain_l1):
        return None

    if content_mode == "compact":
        trajectory_content = _build_compact_trajectory_content(messages)
    else:
        trajectory_content = _build_trajectory_content(messages)

    request_id = (
        metadata.get("requestid")
        or obj.get("trajectory_id")
        or obj.get("instance_id")
        or obj.get("request_id", "")
    )

    return TrajectoryInstance(
        instance_id=request_id,
        trajectory_id=request_id,
        model=metadata.get("model", obj.get("model", "")),
        scaffold=metadata.get("scaffold", obj.get("scaffold", "")),
        task_type_l1=task_type_l1,
        domain_l1=domain_l1,
        code_language=l1["code_language"],
        task_spec_type=l1["task_spec_type"],
        dependency_context=l1["dependency_context"],
        trajectory_summary=trajectory_content,
        l1_rationales={
            key: str(l1[key])
            for key in (
                "code_language_rationale",
                "task_type_rationale",
                "domain_rationale",
                "task_spec_type_rationale",
                "dependency_context_rationale",
            )
            if l1.get(key)
        },
        source_line_number=source_line_number,
        source_content_sha256=source_content_sha256,
        source_artifact_uri=str(obj.get("source_artifact_uri", "") or ""),
    )


def _resolve_unique_instance_id(
    source_id: str,
    digest: str,
    source_line_number: int,
    seen_digests: dict[str, dict[str, str]],
    used_instance_ids: dict[str, str],
) -> Optional[str]:
    """Return a repeatable resume ID, or None for an exact duplicate row."""
    if not source_id:
        candidate = f"line_{source_line_number}__{digest[:12]}"
        used_instance_ids[candidate] = digest
        return candidate

    digest_map = seen_digests.setdefault(source_id, {})
    if digest in digest_map:
        return None

    if not digest_map and source_id not in used_instance_ids:
        candidate = source_id
    else:
        prefix_length = 12
        candidate = f"{source_id}__{digest[:prefix_length]}"
        while candidate in used_instance_ids and used_instance_ids[candidate] != digest:
            prefix_length += 1
            candidate = f"{source_id}__{digest[:prefix_length]}"

    digest_map[digest] = candidate
    used_instance_ids[candidate] = digest
    return candidate


def _build_trajectory_content(messages: list[dict]) -> str:
    """
    Build full trajectory content with light filtering.
    Includes all user queries, assistant responses, tool calls, and tool results.
    Only skips: system prompts (redundant across all instances).
    """
    parts = []
    total_chars = 0

    for msg in messages:
        if total_chars >= MAX_TRAJECTORY_CHARS:
            parts.append("\n... [trajectory truncated due to length]")
            break

        role = msg.get("role", "")
        content = msg.get("content", "")

        # Skip system messages (identical boilerplate across all trajectories)
        if role == "system" and SKIP_SYSTEM_PROMPT:
            continue

        if isinstance(content, list):
            # Structured content: text blocks, tool_use, tool_result
            block_parts = []
            for block in content:
                if not isinstance(block, dict):
                    continue
                block_type = block.get("type", "")

                if block_type == "text":
                    text = block.get("text", "")
                    if text.strip():
                        text = _cap(text, MAX_SINGLE_CONTENT_CHARS)
                        block_parts.append(text)

                elif block_type == "tool_use":
                    tool_str = _format_tool_use(block)
                    block_parts.append(tool_str)

                elif block_type == "tool_result":
                    result_content = block.get("content", "")
                    if isinstance(result_content, list):
                        result_content = " ".join(
                            c.get("text", "") for c in result_content if isinstance(c, dict)
                        )
                    if result_content:
                        result_content = _cap(str(result_content), MAX_SINGLE_CONTENT_CHARS)
                        block_parts.append(f"[tool_result]: {result_content}")

            if block_parts:
                chunk = f"[{role}]:\n" + "\n".join(block_parts)
                parts.append(chunk)
                total_chars += len(chunk)

        elif isinstance(content, str) and content.strip():
            content = _cap(content, MAX_SINGLE_CONTENT_CHARS)
            chunk = f"[{role}]: {content}"
            parts.append(chunk)
            total_chars += len(chunk)

    return "\n\n".join(parts)


def _build_compact_trajectory_content(messages: list[dict]) -> str:
    """Build bounded classification evidence from user intent and agent actions."""
    parts: list[str] = []
    total_chars = 0
    tool_names: dict[str, str] = {}

    def add_part(chunk: str) -> bool:
        nonlocal total_chars
        chunk = chunk.strip()
        if not chunk:
            return True
        if total_chars >= MAX_COMPACT_TRAJECTORY_CHARS:
            return False
        remaining = MAX_COMPACT_TRAJECTORY_CHARS - total_chars
        if len(chunk) > remaining:
            chunk = chunk[:remaining] + "\n... [compact trajectory truncated]"
        parts.append(chunk)
        total_chars += len(chunk)
        return total_chars < MAX_COMPACT_TRAJECTORY_CHARS

    for message in messages:
        if total_chars >= MAX_COMPACT_TRAJECTORY_CHARS:
            break

        role = str(message.get("role", ""))
        content = message.get("content", "")

        if role == "system":
            continue

        if role == "user":
            for query in _extract_user_queries(content):
                if not add_part(f"[user_query]: {_cap(query, MAX_COMPACT_MESSAGE_CHARS)}"):
                    break

            if isinstance(content, list):
                for block in content:
                    if not isinstance(block, dict) or block.get("type") != "tool_result":
                        continue
                    call_id = str(block.get("tool_use_id", ""))
                    name = tool_names.get(call_id, "")
                    result_text = _structured_block_text(block.get("content", ""))
                    formatted = _format_compact_tool_result(name, result_text)
                    if formatted:
                        add_part(formatted)
            continue

        if role == "assistant":
            assistant_text = _content_text(content)
            if assistant_text:
                add_part(
                    f"[assistant]: {_cap(_clean_system_reminders(assistant_text), MAX_COMPACT_MESSAGE_CHARS)}"
                )

            if isinstance(content, list):
                for block in content:
                    if not isinstance(block, dict) or block.get("type") != "tool_use":
                        continue
                    call_id = str(block.get("id", ""))
                    name = str(block.get("name", ""))
                    if call_id:
                        tool_names[call_id] = name
                    add_part(_format_tool_use(block))

            for call in message.get("tool_calls", []) or []:
                call_id, name, formatted = _format_openai_tool_call(call)
                if call_id:
                    tool_names[call_id] = name
                if formatted:
                    add_part(formatted)
            continue

        if role == "tool":
            call_id = str(message.get("tool_call_id", ""))
            name = tool_names.get(call_id, str(message.get("name", "")))
            result_text = _structured_block_text(content)
            formatted = _format_compact_tool_result(name, result_text)
            if formatted:
                add_part(formatted)

    if total_chars >= MAX_COMPACT_TRAJECTORY_CHARS:
        parts.append("... [trajectory truncated due to compact evidence limit]")
    return "\n\n".join(parts)


def _extract_user_queries(content) -> list[str]:
    text = _clean_system_reminders(_content_text(content)).strip()
    if not text:
        return []
    tagged = [match.strip() for match in USER_QUERY_RE.findall(text) if match.strip()]
    if tagged:
        queries = tagged
    else:
        fallback = re.sub(r"</?user_query\b[^>]*>", "", text, flags=re.IGNORECASE).strip()
        queries = [fallback] if fallback else []
    return [
        query
        for query in queries
        if not COMPACTION_QUERY_RE.match(query)
    ]


def _clean_system_reminders(text: str) -> str:
    return SYSTEM_REMINDER_RE.sub("", text or "").strip()


def _content_text(content) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    texts = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            text = block.get("text", "")
            if text:
                texts.append(str(text))
    return "\n".join(texts)


def _structured_block_text(content) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return str(content) if content else ""
    return "\n".join(
        str(block.get("text", ""))
        for block in content
        if isinstance(block, dict) and block.get("text")
    )


def _format_openai_tool_call(call: dict) -> tuple[str, str, str]:
    if not isinstance(call, dict):
        return "", "", ""
    function = call.get("function", {})
    if not isinstance(function, dict):
        return str(call.get("id", "")), "", ""
    name = str(function.get("name", ""))
    arguments = function.get("arguments", {})
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError:
            arguments = {"raw_arguments": _cap(arguments, 1000)}
    if not isinstance(arguments, dict):
        arguments = {"arguments": arguments}
    formatted = _format_tool_use({"name": name, "input": arguments})
    return str(call.get("id", "")), name, formatted


def _format_compact_tool_result(name: str, content: str) -> str:
    content = (content or "").strip()
    if not content:
        return ""
    has_high_signal = bool(HIGH_SIGNAL_RESULT_RE.search(content))
    if name in LOW_SIGNAL_RESULT_TOOLS and not has_high_signal:
        return ""
    if name == "Bash" or has_high_signal or name not in LOW_SIGNAL_RESULT_TOOLS:
        label = name or "unknown"
        return f"[tool_result: {label}] {_cap(content, MAX_COMPACT_TOOL_RESULT_CHARS)}"
    return ""


def _format_tool_use(block: dict) -> str:
    """Format a tool_use block concisely."""
    name = block.get("name", "")
    inp = block.get("input", {})

    if name in ("Read", "Edit", "SearchReplace", "Write"):
        path = inp.get("file_path", inp.get("path", ""))
        if name in ("Edit", "SearchReplace"):
            old = _cap(inp.get("old_string", inp.get("old_str", "")), 500)
            new = _cap(inp.get("new_string", inp.get("new_str", "")), 500)
            return f"[tool: {name}] file={path}\n  old: {old}\n  new: {new}"
        elif name == "Write":
            content = _cap(inp.get("content", ""), 2000)
            return f"[tool: {name}] file={path}\n  content: {content}"
        else:
            return f"[tool: {name}] file={path}"

    elif name == "Bash":
        cmd = _cap(inp.get("command", ""), 2000)
        return f"[tool: Bash] {cmd}"

    elif name in ("Glob", "Grep"):
        pattern = inp.get("pattern", "")
        path = inp.get("path", "")
        return f"[tool: {name}] pattern={pattern} path={path}"

    else:
        inp_str = _cap(json.dumps(inp, ensure_ascii=False), 1000)
        return f"[tool: {name}] {inp_str}"


def _cap(text, max_chars: int) -> str:
    """Truncate text if exceeds max_chars, tolerating null/non-string values."""
    if text is None:
        return ""
    if not isinstance(text, str):
        text = json.dumps(text, ensure_ascii=False) if isinstance(text, (dict, list)) else str(text)
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "..."

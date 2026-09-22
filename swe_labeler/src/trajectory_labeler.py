"""
Trajectory Labeler - Phase 2 only (L2 + orthogonal).
Uses existing L1 labels + trajectory summary to produce L2 labels.
"""
from __future__ import annotations
import json
import re
import time
import logging
from pathlib import Path

from .llm_client import LLMClient
from .trajectory_normalizer import TrajectoryInstance
from .utils import load_yaml

logger = logging.getLogger(__name__)

PROMPT_DIR = Path(__file__).parent.parent / "prompt"
DEFINITION_DIR = Path(__file__).parent.parent / "definition"


class TrajectoryLabeler:
    def __init__(self, llm_client: LLMClient, max_tokens: int = 12800):
        self.llm = llm_client
        self.max_tokens = max_tokens
        self._prompt_config = load_yaml(str(PROMPT_DIR / "trajectory_L2_prompt.yaml"))
        self._task_type_l2_defs = load_yaml(str(DEFINITION_DIR / "task_type_l2.yaml"))
        self._domain_l2_defs = load_yaml(str(DEFINITION_DIR / "domain_l2.yaml"))

    async def label_instance(self, instance: TrajectoryInstance) -> dict:
        t0 = time.monotonic()

        messages = self._build_prompt(instance)
        response = await self.llm.chat_completion(messages, max_tokens=self.max_tokens)
        content = self.llm.extract_content(response)

        t1 = time.monotonic()

        if not content:
            error_msg = response.get("error", "empty response")
            logger.error(f"Failed to label trajectory {instance.instance_id}: {error_msg}")
            return {"error": error_msg}

        result = self._parse_response(content)

        # Auto-retry with larger max_tokens if parse failed (reasoning model truncation)
        if "_raw" in result and self.max_tokens < 16384:
            logger.info(f"Retrying {instance.instance_id} with max_tokens={self.max_tokens * 2}")
            response = await self.llm.chat_completion(messages, max_tokens=self.max_tokens * 2)
            content = self.llm.extract_content(response)
            if content:
                result = self._parse_response(content)
            t1 = time.monotonic()

        # Corrective retry: the model sometimes invents L2 values outside the
        # allowed candidate list (e.g. domain-flavored task types).
        if "_raw" not in result:
            corrections = self._invalid_l2_corrections(result, instance)
            if corrections:
                logger.info(
                    "Retrying %s with L2 correction: %s",
                    instance.instance_id,
                    "; ".join(corrections),
                )
                retry_messages = messages + [
                    {"role": "assistant", "content": content},
                    {
                        "role": "user",
                        "content": (
                            "Your previous answer used L2 values that are NOT in the "
                            "allowed options:\n- " + "\n- ".join(corrections) + "\n\n"
                            "Re-output the complete corrected JSON in <label> ... </label>. "
                            "Every task_type_l2 / domain_l2 value must be copied verbatim "
                            'from its own "Available L2 options" list above (or use '
                            '["unspecified"] if none fits). Do not mix task type and '
                            "domain values."
                        ),
                    },
                ]
                retry_response = await self.llm.chat_completion(
                    retry_messages, max_tokens=self.max_tokens
                )
                retry_content = self.llm.extract_content(retry_response)
                if retry_content:
                    retry_result = self._parse_response(retry_content)
                    if "_raw" not in retry_result and not self._invalid_l2_corrections(
                        retry_result, instance
                    ):
                        result = retry_result
                t1 = time.monotonic()

        logger.debug(
            f"Labeled trajectory {instance.instance_id}: {t1-t0:.1f}s "
            f"→ task_l2={result.get('task_type_l2')} domain_l2={result.get('domain_l2')}"
        )
        return result

    def _invalid_l2_corrections(self, result: dict, instance: TrajectoryInstance) -> list[str]:
        corrections = []
        for field, defs, l1_key in (
            ("task_type_l2", self._task_type_l2_defs, instance.task_type_l1),
            ("domain_l2", self._domain_l2_defs, instance.domain_l1),
        ):
            l1_data = defs.get(l1_key)
            if not isinstance(l1_data, dict):
                continue
            candidates = {
                str(item.get("name"))
                for item in l1_data.get("l2", []) or []
                if isinstance(item, dict) and item.get("name")
            }
            if not candidates:
                continue
            values = result.get(field)
            values = values if isinstance(values, list) else [values]
            invalid = [
                str(v) for v in values if v != "unspecified" and v not in candidates
            ]
            if invalid:
                corrections.append(
                    f"{field}: {invalid} — allowed options: {sorted(candidates)}"
                )
        return corrections

    def _build_prompt(self, instance: TrajectoryInstance) -> list[dict]:
        config = self._prompt_config

        task_type_l2_section = self._build_focused_l2_section(
            self._task_type_l2_defs, instance.task_type_l1
        )
        domain_l2_section = self._build_focused_l2_section(
            self._domain_l2_defs, instance.domain_l1
        )

        user_prompt = config["phase2_user_prompt_template"].format(
            task_type_l1=instance.task_type_l1,
            domain_l1=instance.domain_l1,
            code_language=instance.code_language,
            task_spec_type=instance.task_spec_type,
            dependency_context=instance.dependency_context,
            trajectory_summary=instance.trajectory_summary,
            task_type_l2_section=task_type_l2_section,
            domain_l2_section=domain_l2_section,
        )

        return [
            {"role": "system", "content": config["phase2_system_prompt"]},
            {"role": "user", "content": user_prompt},
        ]

    def _build_focused_l2_section(self, defs: dict, l1_key: str) -> str:
        l1_data = defs.get(l1_key)
        if not l1_data or not isinstance(l1_data, dict):
            return f"*(No L2 sub-categories defined for `{l1_key}`)*"

        l2_list = l1_data.get("l2")
        if not l2_list:
            return f"*(No L2 sub-categories for `{l1_key}` — use 'unspecified')*"

        source = l1_data.get("source_framework", "")
        lines = [f"**Source:** {source}", ""]
        lines.append("**Available L2 options:**")
        lines.append("")

        for item in l2_list:
            name = item.get("name", "")
            op_def = item.get("operational_definition", "").strip().replace("\n", " ")[:300]
            signals = item.get("signals", [])
            if isinstance(signals, list):
                sig_str = ", ".join(f"`{s}`" for s in signals[:5])
            else:
                sig_str = str(signals)[:200]

            lines.append(f"- **`{name}`**: {op_def}")
            lines.append(f"  - Signals: {sig_str}")
            lines.append("")

        return "\n".join(lines)

    def _parse_response(self, content: str) -> dict:
        # Try 1: <label> tags
        label_match = re.search(r"<label>\s*(\{.*?\})\s*</label>", content, re.DOTALL)
        if label_match:
            json_str = label_match.group(1)
            return self._try_parse_json(json_str, content)

        # Try 2: JSON with task_type_l2 field anywhere in content
        json_match = re.search(r"\{[^{}]*\"task_type_l2\"[^{}]*\}", content, re.DOTALL)
        if json_match:
            return self._try_parse_json(json_match.group(0), content)

        # Try 3: look for JSON block after reasoning markers
        for marker in ["</analysis>", "</think>", "</reasoning>", "```json", "```"]:
            idx = content.find(marker)
            if idx >= 0:
                after = content[idx + len(marker):]
                brace_match = re.search(r"\{[^{}]{20,}\}", after, re.DOTALL)
                if brace_match:
                    return self._try_parse_json(brace_match.group(0), content)

        # Try 4: any substantial JSON object
        brace_match = re.search(r"\{[^{}]{50,}\}", content, re.DOTALL)
        if brace_match:
            return self._try_parse_json(brace_match.group(0), content)

        logger.warning("Could not extract JSON from trajectory label response")
        return {"_raw": content[:1500]}

    def _try_parse_json(self, json_str: str, full_content: str) -> dict:
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            cleaned = re.sub(r",\s*}", "}", json_str)
            cleaned = re.sub(r",\s*]", "]", cleaned)
            try:
                data = json.loads(cleaned)
            except json.JSONDecodeError:
                return {"_raw": full_content[:1500]}

        # Normalize L2 to list
        for key in ("task_type_l2", "domain_l2"):
            val = data.get(key)
            if isinstance(val, str):
                data[key] = [val] if val else ["unspecified"]
            elif not val:
                data[key] = ["unspecified"]

        return data

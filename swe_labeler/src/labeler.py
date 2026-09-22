from __future__ import annotations
import json
import re
import logging
import time
from pathlib import Path
from typing import Optional

from .schema import UnifiedInstance, LabelResult
from .llm_client import LLMClient
from .utils import load_yaml, truncate_text

logger = logging.getLogger(__name__)

PROMPT_DIR = Path(__file__).parent.parent / "prompt"
DEFINITION_DIR = Path(__file__).parent.parent / "definition"


class Labeler:
    def __init__(self, llm_client: LLMClient, prompt_version: str = "default", max_tokens: int = 4096):
        self.llm = llm_client
        self.max_tokens = max_tokens
        self.prompt_version = prompt_version
        if prompt_version == "fast":
            self._prompt_config = load_yaml(str(PROMPT_DIR / "L2_tag_prompt_fast.yaml"))
            if max_tokens == 4096:
                self.max_tokens = 512
        else:
            self._prompt_config = load_yaml(str(PROMPT_DIR / "L2_tag_prompt.yaml"))
        self._task_type_l2_defs = load_yaml(str(DEFINITION_DIR / "task_type_l2.yaml"))
        self._domain_l2_defs = load_yaml(str(DEFINITION_DIR / "domain_l2.yaml"))

    # ─────────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────────

    async def label_instance(self, instance: UnifiedInstance) -> LabelResult:
        t0 = time.monotonic()

        # Phase 1: L1 classification
        phase1_result = await self._run_phase1(instance)
        t1 = time.monotonic()

        if not phase1_result.get("task_type_l1") or not phase1_result.get("domain_l1"):
            logger.error(f"Phase 1 failed for {instance.instance_id}")
            return LabelResult(
                raw_response=json.dumps(phase1_result, ensure_ascii=False)[:1000]
            )

        # Phase 2: L2 refinement + orthogonal dimensions
        phase2_result = await self._run_phase2(instance, phase1_result)
        t2 = time.monotonic()

        logger.debug(
            f"Labeled {instance.instance_id}: P1={t1-t0:.1f}s P2={t2-t1:.1f}s total={t2-t0:.1f}s "
            f"→ {phase1_result.get('task_type_l1')}/{phase1_result.get('domain_l1')}"
        )

        return self._merge_results(phase1_result, phase2_result)

    # ─────────────────────────────────────────────────────────────────────────
    # Phase 1: L1 Classification
    # ─────────────────────────────────────────────────────────────────────────

    def build_phase1_prompt(self, instance: UnifiedInstance) -> list[dict]:
        config = self._prompt_config

        repo_info_section = self._build_repo_info_section(instance)
        user_prompt = config["phase1_user_prompt_template"].format(
            repo=instance.repo,
            instance_id=instance.instance_id,
            repo_info_section=repo_info_section,
            problem_statement=truncate_text(instance.problem_statement, max_lines=80, max_chars=3000),
            patch=truncate_text(instance.patch, max_lines=150, max_chars=8000),
            test_patch=truncate_text(instance.test_patch, max_lines=50, max_chars=3000),
        )

        return [
            {"role": "system", "content": config["phase1_system_prompt"]},
            {"role": "user", "content": user_prompt},
        ]

    async def _run_phase1(self, instance: UnifiedInstance) -> dict:
        messages = self.build_phase1_prompt(instance)
        response = await self.llm.chat_completion(messages, max_tokens=self.max_tokens)
        content = self.llm.extract_content(response)

        if not content:
            error_msg = response.get("error", "empty response")
            logger.error(f"Phase 1 empty response for {instance.instance_id}: {error_msg}")
            return {"_error": error_msg, "_raw": json.dumps(response, ensure_ascii=False)[:500]}

        return self._parse_json_response(content, required_field="task_type_l1")

    # ─────────────────────────────────────────────────────────────────────────
    # Phase 2: L2 Refinement + Orthogonal
    # ─────────────────────────────────────────────────────────────────────────

    def build_phase2_prompt(
        self, instance: UnifiedInstance, task_type_l1: str, domain_l1: str
    ) -> list[dict]:
        config = self._prompt_config

        task_type_l2_section = self._build_focused_l2_section(
            self._task_type_l2_defs, task_type_l1, "task_type"
        )
        domain_l2_section = self._build_focused_l2_section(
            self._domain_l2_defs, domain_l1, "domain"
        )

        repo_info_section = self._build_repo_info_section(instance)
        user_prompt = config["phase2_user_prompt_template"].format(
            repo=instance.repo,
            instance_id=instance.instance_id,
            repo_info_section=repo_info_section,
            problem_statement=truncate_text(instance.problem_statement, max_lines=80, max_chars=3000),
            patch=truncate_text(instance.patch, max_lines=150, max_chars=8000),
            test_patch=truncate_text(instance.test_patch, max_lines=50, max_chars=3000),
            task_type_l1=task_type_l1,
            domain_l1=domain_l1,
            task_type_l2_section=task_type_l2_section,
            domain_l2_section=domain_l2_section,
        )

        return [
            {"role": "system", "content": config["phase2_system_prompt"]},
            {"role": "user", "content": user_prompt},
        ]

    async def _run_phase2(self, instance: UnifiedInstance, phase1_result: dict) -> dict:
        task_type_l1 = phase1_result["task_type_l1"]
        domain_l1 = phase1_result["domain_l1"]

        messages = self.build_phase2_prompt(instance, task_type_l1, domain_l1)
        response = await self.llm.chat_completion(messages, max_tokens=self.max_tokens)
        content = self.llm.extract_content(response)

        if not content:
            error_msg = response.get("error", "empty response")
            logger.warning(f"Phase 2 empty response for {instance.instance_id}: {error_msg}")
            return {"task_type_l2": "unspecified", "domain_l2": "unspecified"}

        result = self._parse_json_response(content, required_field="task_type_l2")
        result["_phase2_raw"] = content[:1500]
        return result

    # ─────────────────────────────────────────────────────────────────────────
    # L2 Section Builder — Only injects candidates for the chosen L1
    # ─────────────────────────────────────────────────────────────────────────

    def _build_focused_l2_section(self, defs: dict, l1_key: str, dimension: str) -> str:
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

            boundary = item.get("boundary_notes", "").strip().replace("\n", " ")[:150]

            lines.append(f"- **`{name}`**: {op_def}")
            lines.append(f"  - Signals: {sig_str}")
            if boundary:
                lines.append(f"  - Boundary: {boundary}")
            lines.append("")

        return "\n".join(lines)

    # ─────────────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _build_repo_info_section(self, instance: UnifiedInstance) -> str:
        if not (instance.repo_description or instance.repo_primary_language or instance.repo_topics):
            return (
                "**⚠️ Repo metadata is unavailable for this instance.** "
                "The domain prompt's preferred decision procedure (read description+topics first) "
                "cannot be applied. Fall back to inferring domain from the repo name and PR content, "
                "and append `(metadata-absent fallback)` to your domain rationale so it can be audited."
            )
        parts = []
        if instance.repo_primary_language:
            parts.append(f"**Language:** {instance.repo_primary_language}")
        if instance.repo_description:
            parts.append(f"**Description:** {instance.repo_description}")
        if instance.repo_topics:
            parts.append(f"**Topics:** {', '.join(instance.repo_topics)}")
        return "\n".join(parts)

    def _parse_json_response(self, content: str, required_field: str = "") -> dict:
        label_match = re.search(r"<label>\s*(\{.*?\})\s*</label>", content, re.DOTALL)
        if label_match:
            json_str = label_match.group(1)
        else:
            json_match = re.search(
                r"\{[^{}]*\"" + re.escape(required_field) + r"\"[^{}]*\}",
                content, re.DOTALL
            ) if required_field else None

            if json_match:
                json_str = json_match.group(0)
            else:
                brace_match = re.search(r"\{[^{}]{20,}\}", content, re.DOTALL)
                if brace_match:
                    json_str = brace_match.group(0)
                else:
                    logger.warning(f"Could not extract JSON (looking for '{required_field}')")
                    return {"_raw": content[:1000]}

        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            cleaned = re.sub(r",\s*}", "}", json_str)
            cleaned = re.sub(r",\s*]", "]", cleaned)
            try:
                return json.loads(cleaned)
            except json.JSONDecodeError:
                logger.warning("JSON parse failed after cleanup")
                return {"_raw": content[:1000]}

    def _merge_results(self, phase1: dict, phase2: dict) -> LabelResult:
        raw_parts = []
        if phase1.get("_raw"):
            raw_parts.append(f"[P1] {phase1['_raw']}")
        if phase2.get("_phase2_raw"):
            raw_parts.append(f"[P2] {phase2['_phase2_raw']}")
        raw_response = "\n".join(raw_parts) if raw_parts else ""

        return LabelResult(
            code_language=phase1.get("code_language", ""),
            task_type_l1=phase1.get("task_type_l1", ""),
            domain_l1=phase1.get("domain_l1", ""),
            task_spec_type=phase1.get("task_spec_type", ""),
            dependency_context=phase1.get("dependency_context", ""),
            task_type_l2=self._validate_l2_against_l1(
                self._normalize_l2_value(phase2.get("task_type_l2")),
                "task_type",
                phase1.get("task_type_l1", ""),
            ),
            domain_l2=self._validate_l2_against_l1(
                self._normalize_l2_value(phase2.get("domain_l2")),
                "domain",
                phase1.get("domain_l1", ""),
            ),
            scope=phase2.get("scope", ""),
            cognitive_complexity=phase2.get("cognitive_complexity", ""),
            time_estimate=phase2.get("time_estimate", ""),
            task_type_rationale=phase1.get("task_type_rationale", phase1.get("code_language_rationale", "")),
            domain_rationale=phase1.get("domain_rationale", ""),
            l2_task_type_rationale=phase2.get("task_type_l2_rationale", ""),
            l2_domain_rationale=phase2.get("domain_l2_rationale", ""),
            raw_response=raw_response[:2000],
        )

    @staticmethod
    def _normalize_l2_value(value) -> list[str]:
        if value is None:
            return ["unspecified"]
        if isinstance(value, list):
            return value if value else ["unspecified"]
        if isinstance(value, str):
            return [value] if value else ["unspecified"]
        return ["unspecified"]

    def _validate_l2_against_l1(self, l2_values: list[str], dimension: str, l1: str) -> list[str]:
        """
        Hard guarantee: any L2 value not in the valid candidate set for the given L1
        (other than the literal "unspecified") is replaced with "unspecified".

        Catches the rare case where the LLM hallucinates an L2 name or returns an L2
        that belongs to a different L1 (the prompt only shows valid candidates, so
        this is mostly a safety net).
        """
        if not l1:
            return l2_values  # no L1 to validate against; pass through
        valid = set(self.get_valid_l2_for_l1(dimension, l1))
        if not valid:
            # L1 has no L2 sub-categories defined; only "unspecified" is allowed.
            return ["unspecified"]
        cleaned = [v for v in l2_values if v in valid or v == "unspecified"]
        if not cleaned:
            return ["unspecified"]
        return cleaned

    def get_valid_l2_for_l1(self, dimension: str, l1: str) -> list[str]:
        if dimension == "task_type":
            defs = self._task_type_l2_defs
        elif dimension == "domain":
            defs = self._domain_l2_defs
        else:
            return []

        l1_data = defs.get(l1)
        if not l1_data or not isinstance(l1_data, dict):
            return []
        l2_list = l1_data.get("l2")
        if not l2_list:
            return []
        return [item["name"] for item in l2_list if "name" in item]

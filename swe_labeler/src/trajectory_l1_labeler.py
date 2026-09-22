"""Trajectory-specific L1 classification with strict taxonomy validation."""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from .llm_client import LLMClient
from .trajectory_normalizer import DOMAIN_L1_RENAME, TrajectoryInstance

logger = logging.getLogger(__name__)

PROMPT_DIR = Path(__file__).parent.parent / "prompt"

CODE_LANGUAGES = frozenset(
    {
        "go",
        "c",
        "c++",
        "python",
        "java",
        "js/ts",
        "php",
        "shell",
        "c#",
        "html/css",
        "sql",
        "rust",
        "kotlin",
        "swift",
        "ruby",
        "lua",
        "dart",
        "scala",
        "r",
        "other",
        "unknown",
    }
)

TASK_TYPES = frozenset(
    {
        "bug-fix",
        "performance-fix",
        "compatibility-fix",
        "feature",
        "enhancement",
        "backward-compatibility",
        "from_scratch",
        "test-add",
        "test-fix",
        "coverage",
        "debug-support",
        "refactor",
        "style",
        "deprecation",
        "build-fix",
        "ci-fix",
        "deployment",
        "packaging",
        "config",
        "user-docs",
        "design-spec",
        "diagram",
        "code-explanation",
        "security-fix",
        "auth",
        "privacy",
    }
)

DOMAINS = frozenset(
    {
        "web_frontend",
        "mobile_dev",
        "desktop_gui",
        "web_backend",
        "database_storage",
        "data_science",
        "data_engineering",
        "os_system",
        "iot_embedded",
        "devops_infra",
        "media_graphics",
        "game_dev",
        "devtools_test",
        "lang_runtime",
        "pkg_manager_cli",
        "cms_ecommerce",
        "blockchain_web3",
        "security_auth",
        "docs_knowledge",
        "non_coding",
        "other",
    }
)

TASK_SPEC_TYPES = frozenset({"fuzzy", "specific"})
DEPENDENCY_CONTEXTS = frozenset({"codebase", "env", "codebase+env", "none"})

L1_FIELDS = (
    "code_language",
    "task_type_l1",
    "domain_l1",
    "task_spec_type",
    "dependency_context",
)


def normalize_l1_result(data: dict) -> dict:
    """Map legacy prompt keys and known aliases into the canonical L1 schema."""
    if not isinstance(data, dict):
        data = {}

    domain = data.get("domain_l1", data.get("application_domain", ""))
    domain = DOMAIN_L1_RENAME.get(domain, domain)

    return {
        "code_language_rationale": str(data.get("code_language_rationale", "") or ""),
        "code_language": str(data.get("code_language", "") or ""),
        "task_type_rationale": str(data.get("task_type_rationale", "") or ""),
        "task_type_l1": str(data.get("task_type_l1", data.get("task_type", "")) or ""),
        "domain_rationale": str(
            data.get(
                "domain_rationale",
                data.get("application_domain_rationale", ""),
            )
            or ""
        ),
        "domain_l1": str(domain or ""),
        "task_spec_type_rationale": str(
            data.get("task_spec_type_rationale", "") or ""
        ),
        "task_spec_type": str(data.get("task_spec_type", "") or ""),
        "dependency_context_rationale": str(
            data.get("dependency_context_rationale", "") or ""
        ),
        "dependency_context": str(data.get("dependency_context", "") or ""),
    }


def validate_l1_result(data: dict) -> tuple[bool, list[str]]:
    """Validate all five canonical L1 dimensions and report invalid fields."""
    allowed = {
        "code_language": CODE_LANGUAGES,
        "task_type_l1": TASK_TYPES,
        "domain_l1": DOMAINS,
        "task_spec_type": TASK_SPEC_TYPES,
        "dependency_context": DEPENDENCY_CONTEXTS,
    }
    errors = [field for field in L1_FIELDS if data.get(field) not in allowed[field]]
    return not errors, errors


class TrajectoryL1Labeler:
    def __init__(self, llm_client: LLMClient, max_tokens: int = 4096):
        self.llm = llm_client
        self.max_tokens = max_tokens
        raw_prompt = (PROMPT_DIR / "L1_tag_prompt.yaml").read_text(encoding="utf-8")
        # The file was authored for str.format(), so make its JSON example valid
        # when it is used directly as a system prompt.
        self._prompt_text = raw_prompt.replace("{{", "{").replace("}}", "}")

    def build_prompt(self, instance: TrajectoryInstance) -> list[dict]:
        return [
            {"role": "system", "content": self._prompt_text},
            {
                "role": "user",
                "content": f"<trajectory>\n{instance.trajectory_summary}\n</trajectory>",
            },
        ]

    async def label_instance(self, instance: TrajectoryInstance) -> dict:
        messages = self.build_prompt(instance)
        budgets = [self.max_tokens]
        retry_budget = min(self.max_tokens * 2, 16384)
        if retry_budget > self.max_tokens:
            budgets.append(retry_budget)

        last_content = ""
        last_errors = list(L1_FIELDS)
        last_transport_error = ""

        for attempt, budget in enumerate(budgets):
            response = await self.llm.chat_completion(messages, max_tokens=budget)
            content = self.llm.extract_content(response)
            last_content = content or last_content
            if not content:
                last_transport_error = str(response.get("error", "empty response"))
            else:
                parsed = self._parse_response(content)
                normalized = normalize_l1_result(parsed)
                valid, last_errors = validate_l1_result(normalized)
                if valid:
                    return normalized

            if attempt + 1 < len(budgets):
                logger.info(
                    "Retrying trajectory L1 %s with max_tokens=%s",
                    instance.instance_id,
                    budgets[attempt + 1],
                )

        logger.error(
            "Failed L1 validation for trajectory %s: %s",
            instance.instance_id,
            ", ".join(last_errors),
        )
        result = {
            "error": "invalid_l1_response",
            "details": last_errors,
            "_raw": last_content[:1500],
        }
        if last_transport_error:
            result["transport_error"] = last_transport_error
        return result

    @staticmethod
    def _parse_response(content: str) -> dict:
        for tag in ("comment", "label"):
            match = re.search(
                rf"<{tag}>\s*(\{{.*?\}})\s*</{tag}>",
                content,
                re.DOTALL | re.IGNORECASE,
            )
            if match:
                parsed = _try_parse_json(match.group(1))
                if parsed is not None:
                    return parsed

        start = content.find("{")
        end = content.rfind("}")
        if start >= 0 and end > start:
            parsed = _try_parse_json(content[start : end + 1])
            if parsed is not None:
                return parsed
        return {}


def _try_parse_json(value: str) -> dict | None:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        cleaned = re.sub(r",\s*([}\]])", r"\1", value)
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            return None
    return parsed if isinstance(parsed, dict) else None

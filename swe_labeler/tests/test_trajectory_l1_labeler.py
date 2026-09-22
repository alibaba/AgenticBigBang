import asyncio
import json
from pathlib import Path

from src.trajectory_l1_labeler import (
    CODE_LANGUAGES,
    DEPENDENCY_CONTEXTS,
    DOMAINS,
    TASK_SPEC_TYPES,
    TASK_TYPES,
    TrajectoryL1Labeler,
    normalize_l1_result,
    validate_l1_result,
)
from src.trajectory_normalizer import TrajectoryInstance


VALID_LEGACY_L1 = {
    "code_language_rationale": "Python files are central.",
    "code_language": "python",
    "task_type_rationale": "The user asks for a defect fix.",
    "task_type": "bug-fix",
    "application_domain_rationale": "The repository is a backend service.",
    "application_domain": "web_backend",
    "task_spec_type_rationale": "The request is concrete.",
    "task_spec_type": "specific",
    "dependency_context_rationale": "Existing source is required.",
    "dependency_context": "codebase",
}


class FakeLLMClient:
    def __init__(self, contents=None):
        self.contents = list(contents or [])
        self.calls = []

    async def chat_completion(self, messages, max_tokens=4096, **kwargs):
        self.calls.append({"messages": messages, "max_tokens": max_tokens})
        index = min(len(self.calls) - 1, len(self.contents) - 1)
        if index < 0:
            return {"error": "no fake response configured"}
        return {"fake_content": self.contents[index]}

    @staticmethod
    def extract_content(response):
        return response.get("fake_content", "")


def _instance():
    return TrajectoryInstance(
        instance_id="trajectory-1",
        trajectory_id="trajectory-1",
        model="test-model",
        scaffold="test-agent",
        trajectory_summary="[user_query]: Fix parser.py\n\n[tool: Read] file=parser.py",
    )


def _tagged(tag, data):
    return f"<{tag}>\n{json.dumps(data, ensure_ascii=False)}\n</{tag}>"


def test_build_prompt_wraps_compact_evidence_in_trajectory_tags():
    labeler = TrajectoryL1Labeler(FakeLLMClient())

    messages = labeler.build_prompt(_instance())

    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1] == {
        "role": "user",
        "content": (
            "<trajectory>\n"
            "[user_query]: Fix parser.py\n\n[tool: Read] file=parser.py\n"
            "</trajectory>"
        ),
    }


def test_build_prompt_unescapes_json_example_braces():
    labeler = TrajectoryL1Labeler(FakeLLMClient())

    system_prompt = labeler.build_prompt(_instance())[0]["content"]

    assert "{{" not in system_prompt
    assert "}}" not in system_prompt
    assert '<comment>\n{' in system_prompt


def test_parses_comment_with_legacy_l1_keys():
    client = FakeLLMClient([_tagged("comment", VALID_LEGACY_L1)])

    result = asyncio.run(TrajectoryL1Labeler(client).label_instance(_instance()))

    assert result["task_type_l1"] == "bug-fix"
    assert result["domain_l1"] == "web_backend"
    assert result["code_language"] == "python"
    assert result["domain_rationale"] == VALID_LEGACY_L1["application_domain_rationale"]
    assert "error" not in result


def test_accepts_label_tag_with_modern_l1_keys():
    modern = normalize_l1_result(VALID_LEGACY_L1)
    client = FakeLLMClient([_tagged("label", modern)])

    result = asyncio.run(TrajectoryL1Labeler(client).label_instance(_instance()))

    assert result["task_type_l1"] == "bug-fix"
    assert result["domain_l1"] == "web_backend"
    assert len(client.calls) == 1


def test_normalizes_data_science_alias():
    legacy = dict(VALID_LEGACY_L1, application_domain="data_science_ml")
    client = FakeLLMClient([_tagged("comment", legacy)])

    result = asyncio.run(TrajectoryL1Labeler(client).label_instance(_instance()))

    assert result["domain_l1"] == "data_science"


def test_rejects_partial_or_out_of_taxonomy_l1():
    partial = {"task_type": "invented-task", "application_domain": "web_backend"}
    client = FakeLLMClient([_tagged("comment", partial), _tagged("comment", partial)])

    result = asyncio.run(TrajectoryL1Labeler(client).label_instance(_instance()))

    assert result["error"] == "invalid_l1_response"
    assert "task_type_l1" in result["details"]
    assert len(client.calls) == 2


def test_retries_once_after_malformed_response():
    client = FakeLLMClient(["not JSON", _tagged("comment", VALID_LEGACY_L1)])

    result = asyncio.run(
        TrajectoryL1Labeler(client, max_tokens=4096).label_instance(_instance())
    )

    assert result["task_type_l1"] == "bug-fix"
    assert [call["max_tokens"] for call in client.calls] == [4096, 8192]


def test_validator_reports_each_invalid_dimension():
    invalid = {
        "code_language": "braincode",
        "task_type_l1": "invented-task",
        "domain_l1": "invented-domain",
        "task_spec_type": "maybe",
        "dependency_context": "sometimes",
    }

    valid, errors = validate_l1_result(invalid)

    assert valid is False
    assert errors == [
        "code_language",
        "task_type_l1",
        "domain_l1",
        "task_spec_type",
        "dependency_context",
    ]


def test_validator_allowlists_are_advertised_by_authoritative_prompt():
    prompt = (
        Path(__file__).parents[1] / "prompt" / "L1_tag_prompt.yaml"
    ).read_text(encoding="utf-8")

    assert len(CODE_LANGUAGES) == 21
    assert len(TASK_TYPES) == 26
    assert len(DOMAINS) == 21
    for value in (
        CODE_LANGUAGES | TASK_TYPES | DOMAINS | TASK_SPEC_TYPES | DEPENDENCY_CONTEXTS
    ):
        assert value in prompt

import asyncio

import pytest

from src.trajectory_normalizer import TrajectoryInstance
from src.trajectory_pipeline import TrajectoryPipeline


VALID_L1 = {
    "code_language": "python",
    "task_type_l1": "bug-fix",
    "domain_l1": "web_backend",
    "task_spec_type": "specific",
    "dependency_context": "codebase",
    "task_type_rationale": "A defect is being fixed.",
    "domain_rationale": "This is a backend repository.",
}

VALID_L2 = {
    "task_type_l2": ["logic_error"],
    "domain_l2": ["django_python"],
    "task_type_l2_rationale": "The logic returns the wrong value.",
    "domain_l2_rationale": "The trajectory shows Django files.",
    "scope": "single_file",
    "cognitive_complexity": "local_reasoning",
    "time_estimate": "small_1h",
}


class RecordingLabeler:
    def __init__(self, result):
        self.result = result
        self.calls = []

    async def label_instance(self, instance):
        self.calls.append(instance)
        return dict(self.result)


def _instance(**overrides):
    values = {
        "instance_id": "trajectory-1",
        "trajectory_id": "trajectory-1",
        "model": "test-model",
        "scaffold": "test-agent",
        "trajectory_summary": "[user_query]: Fix parser.py",
        "source_line_number": 7,
        "source_content_sha256": "a" * 64,
        "source_artifact_uri": "artifact://synthetic/source",
        **{
            key: VALID_L1[key]
            for key in (
                "code_language",
                "task_type_l1",
                "domain_l1",
                "task_spec_type",
                "dependency_context",
            )
        },
    }
    values.update(overrides)
    return TrajectoryInstance(**values)


def _run(instance, l1_result=VALID_L1, l2_result=VALID_L2, mode="preserve"):
    l1 = RecordingLabeler(l1_result)
    l2 = RecordingLabeler(l2_result)
    pipeline = TrajectoryPipeline(l1, l2)
    result = asyncio.run(pipeline.label_instance(instance, l1_mode=mode))
    return result, l1, l2


def test_preserve_skips_l1_for_complete_valid_existing_labels():
    result, l1, l2 = _run(_instance())

    assert l1.calls == []
    assert len(l2.calls) == 1
    assert result["l1_source"] == "preserved"
    assert result["labels"]["task_type_l1"] == "bug-fix"


def test_preserve_keeps_existing_l1_rationales():
    rationales = {
        "task_type_rationale": "Existing task rationale.",
        "domain_rationale": "Existing domain rationale.",
    }

    result, l1, _ = _run(_instance(l1_rationales=rationales))

    assert l1.calls == []
    assert result["labels"]["task_type_rationale"] == rationales["task_type_rationale"]
    assert result["labels"]["domain_rationale"] == rationales["domain_rationale"]


@pytest.mark.parametrize(
    "overrides",
    [
        {
            "code_language": "",
            "task_type_l1": "",
            "domain_l1": "",
            "task_spec_type": "",
            "dependency_context": "",
        },
        {"dependency_context": ""},
        {"task_type_l1": "invented-task"},
    ],
)
def test_preserve_generates_for_missing_partial_or_invalid_l1(overrides):
    result, l1, l2 = _run(_instance(**overrides))

    assert len(l1.calls) == 1
    assert len(l2.calls) == 1
    assert result["l1_source"] == "generated"
    assert result["labels"]["task_type_l1"] == "bug-fix"


def test_relabel_always_calls_l1():
    relabeled = dict(VALID_L1, task_type_l1="enhancement")
    l2_result = dict(VALID_L2, task_type_l2=["internal_improvement"])

    result, l1, l2 = _run(
        _instance(), l1_result=relabeled, l2_result=l2_result, mode="relabel"
    )

    assert len(l1.calls) == 1
    assert len(l2.calls) == 1
    assert result["l1_source"] == "relabeled"
    assert result["labels"]["task_type_l1"] == "enhancement"


def test_l1_failure_prevents_l2_call():
    result, l1, l2 = _run(
        _instance(task_type_l1=""),
        l1_result={"error": "invalid_l1_response", "details": ["task_type_l1"]},
    )

    assert len(l1.calls) == 1
    assert l2.calls == []
    assert result["error"] == "l1_labeling_failed"


def test_success_merges_l1_l2_orthogonal_and_source_metadata():
    result, _, _ = _run(_instance())

    assert result["source_line_number"] == 7
    assert result["source_content_sha256"] == "a" * 64
    assert result["source_artifact_uri"] == "artifact://synthetic/source"
    assert result["labels"]["code_language"] == "python"
    assert result["labels"]["task_type_l2"] == ["logic_error"]
    assert result["labels"]["domain_l2"] == ["django_python"]
    assert result["labels"]["scope"] == "single_file"


def test_invalid_l2_candidate_is_rejected():
    result, _, _ = _run(_instance(), l2_result=dict(VALID_L2, task_type_l2=["made_up"]))

    assert result["error"] == "invalid_l2_response"
    assert "task_type_l2" in result["details"]


@pytest.mark.parametrize("values", [[], ["logic_error"] * 4, "logic_error"])
def test_l2_cardinality_must_be_one_to_three(values):
    result, _, _ = _run(_instance(), l2_result=dict(VALID_L2, task_type_l2=values))

    assert result["error"] == "invalid_l2_response"
    assert "task_type_l2" in result["details"]


def test_unspecified_is_valid_for_either_l2_dimension():
    l2_result = dict(
        VALID_L2,
        task_type_l2=["unspecified"],
        domain_l2=["unspecified"],
    )

    result, _, _ = _run(_instance(), l2_result=l2_result)

    assert "error" not in result
    assert result["labels"]["task_type_l2"] == ["unspecified"]


def test_unspecified_cannot_be_mixed_with_concrete_l2_values():
    result, _, _ = _run(
        _instance(),
        l2_result=dict(VALID_L2, task_type_l2=["unspecified", "logic_error"]),
    )

    assert result["error"] == "invalid_l2_response"
    assert "task_type_l2" in result["details"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("scope", "everywhere"),
        ("cognitive_complexity", "impossible"),
        ("time_estimate", "tomorrow"),
        ("scope", ""),
    ],
)
def test_missing_or_invalid_orthogonal_value_is_rejected(field, value):
    result, _, _ = _run(_instance(), l2_result=dict(VALID_L2, **{field: value}))

    assert result["error"] == "invalid_l2_response"
    assert field in result["details"]

"""Orchestration for full L1 + L2 trajectory labeling."""
from __future__ import annotations

from pathlib import Path

from .trajectory_l1_labeler import normalize_l1_result, validate_l1_result
from .trajectory_normalizer import TrajectoryInstance
from .utils import load_yaml

DEFINITION_DIR = Path(__file__).parent.parent / "definition"

SCOPE_VALUES = frozenset(
    {"single_file", "multi_file_same_module", "cross_module", "cross_repo"}
)
COMPLEXITY_VALUES = frozenset(
    {"mechanical", "local_reasoning", "global_reasoning", "design_decision"}
)
TIME_VALUES = frozenset(
    {"trivial_15min", "small_1h", "medium_4h", "large_4h_plus"}
)

L1_VALUE_FIELDS = (
    "code_language",
    "task_type_l1",
    "domain_l1",
    "task_spec_type",
    "dependency_context",
)


def _l2_candidates(definitions: dict, l1_value: str) -> set[str]:
    l1_data = definitions.get(l1_value, {})
    if not isinstance(l1_data, dict):
        return set()
    items = l1_data.get("l2", [])
    if not isinstance(items, list):
        return set()
    return {
        str(item.get("name"))
        for item in items
        if isinstance(item, dict) and item.get("name")
    }


def _valid_l2_values(value, candidates: set[str]) -> bool:
    if not isinstance(value, list) or not 1 <= len(value) <= 3:
        return False
    if not all(isinstance(item, str) and item for item in value):
        return False
    if "unspecified" in value:
        return value == ["unspecified"]
    return all(item in candidates for item in value)


def validate_l2_result(
    result: dict,
    task_type_l1: str,
    domain_l1: str,
    task_defs: dict,
    domain_defs: dict,
) -> tuple[bool, list[str]]:
    """Validate L2 hierarchy, cardinality, and all orthogonal dimensions."""
    if not isinstance(result, dict):
        return False, ["response"]

    errors = []
    if result.get("error") or result.get("_raw"):
        errors.append("response")

    if not _valid_l2_values(
        result.get("task_type_l2"), _l2_candidates(task_defs, task_type_l1)
    ):
        errors.append("task_type_l2")
    if not _valid_l2_values(
        result.get("domain_l2"), _l2_candidates(domain_defs, domain_l1)
    ):
        errors.append("domain_l2")

    allowed_orthogonal = {
        "scope": SCOPE_VALUES,
        "cognitive_complexity": COMPLEXITY_VALUES,
        "time_estimate": TIME_VALUES,
    }
    for field, allowed in allowed_orthogonal.items():
        if result.get(field) not in allowed:
            errors.append(field)

    return not errors, errors


class TrajectoryPipeline:
    def __init__(self, l1_labeler, l2_labeler):
        self.l1_labeler = l1_labeler
        self.l2_labeler = l2_labeler
        self._task_defs = load_yaml(str(DEFINITION_DIR / "task_type_l2.yaml"))
        self._domain_defs = load_yaml(str(DEFINITION_DIR / "domain_l2.yaml"))

    async def label_instance(
        self,
        instance: TrajectoryInstance,
        l1_mode: str = "preserve",
    ) -> dict:
        if l1_mode not in {"preserve", "relabel"}:
            return {
                "error": "invalid_l1_mode",
                "details": [f"unsupported mode: {l1_mode}"],
            }

        existing_l1 = normalize_l1_result(
            {
                **{field: getattr(instance, field, "") for field in L1_VALUE_FIELDS},
                **instance.l1_rationales,
            }
        )
        existing_valid, _ = validate_l1_result(existing_l1)

        if l1_mode == "preserve" and existing_valid:
            resolved_l1 = existing_l1
            l1_source = "preserved"
        else:
            generated = await self.l1_labeler.label_instance(instance)
            if generated.get("error"):
                return {
                    "error": "l1_labeling_failed",
                    "details": generated.get("details", []),
                    "cause": generated.get("error"),
                }
            resolved_l1 = normalize_l1_result(generated)
            valid, errors = validate_l1_result(resolved_l1)
            if not valid:
                return {
                    "error": "l1_labeling_failed",
                    "details": errors,
                    "cause": "invalid_l1_result",
                }
            l1_source = "relabeled" if l1_mode == "relabel" else "generated"

        for field in L1_VALUE_FIELDS:
            setattr(instance, field, resolved_l1[field])

        l2_result = await self.l2_labeler.label_instance(instance)
        valid_l2, l2_errors = validate_l2_result(
            l2_result,
            resolved_l1["task_type_l1"],
            resolved_l1["domain_l1"],
            self._task_defs,
            self._domain_defs,
        )
        if not valid_l2:
            return {
                "error": "invalid_l2_response",
                "details": l2_errors,
            }

        clean_l2 = {
            key: value for key, value in l2_result.items() if not key.startswith("_")
        }
        labels = {**resolved_l1, **clean_l2}
        instance.labels = labels

        output = instance.to_dict(include_source_metadata=True)
        output["labels"] = labels
        output["l1_source"] = l1_source
        return output

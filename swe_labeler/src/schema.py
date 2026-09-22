from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Optional
import json


@dataclass
class LabelResult:
    code_language: str = ""
    task_type_l1: str = ""
    domain_l1: str = ""
    task_spec_type: str = ""
    dependency_context: str = ""

    task_type_l2: list[str] = field(default_factory=lambda: ["unspecified"])
    domain_l2: list[str] = field(default_factory=lambda: ["unspecified"])

    scope: str = ""
    cognitive_complexity: str = ""
    time_estimate: str = ""

    task_type_rationale: str = ""
    domain_rationale: str = ""
    l2_task_type_rationale: str = ""
    l2_domain_rationale: str = ""

    raw_response: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> LabelResult:
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in d.items() if k in valid_fields}
        # backward compat: old format stored L2 as string
        for key in ("task_type_l2", "domain_l2"):
            if key in filtered and isinstance(filtered[key], str):
                filtered[key] = [filtered[key]] if filtered[key] else ["unspecified"]
        return cls(**filtered)


@dataclass
class UnifiedInstance:
    instance_id: str
    dataset_source: str
    repo: str

    problem_statement: str
    patch: str
    test_patch: str = ""
    hints_text: str = ""

    language: Optional[str] = None
    created_at: Optional[str] = None
    base_commit: Optional[str] = None

    repo_description: Optional[str] = None
    repo_topics: Optional[list[str]] = None
    repo_primary_language: Optional[str] = None

    instruction: Optional[str] = None
    workspace_tree: Optional[str] = None
    tests_content: Optional[dict] = None
    task_metadata: Optional[dict] = None

    labels: Optional[LabelResult] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        if self.labels:
            d["labels"] = self.labels.to_dict()
        return d

    def to_json_line(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, d: dict) -> UnifiedInstance:
        labels_data = d.pop("labels", None)
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        instance = cls(**{k: v for k, v in d.items() if k in valid_fields})
        if labels_data and isinstance(labels_data, dict):
            instance.labels = LabelResult.from_dict(labels_data)
        return instance

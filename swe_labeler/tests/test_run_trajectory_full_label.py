import asyncio
import json
import logging
from pathlib import Path

import yaml
import pytest

from scripts.run_trajectory_full_label import (
    ResumeStateError,
    _label_and_save,
    default_output_path,
    filter_unlabeled_instances,
    load_completed_source_hashes,
    resolve_l1_mode,
)
from src.trajectory_normalizer import TrajectoryInstance, normalize_trajectory_jsonl


class FakePipeline:
    def __init__(self, result=None, error=None):
        self.result = result or {}
        self.error = error
        self.calls = []

    async def label_instance(self, instance, l1_mode="preserve"):
        self.calls.append((instance.instance_id, l1_mode))
        if self.error:
            raise self.error
        return dict(self.result)


def _instance(instance_id="item-1"):
    return TrajectoryInstance(
        instance_id=instance_id,
        trajectory_id=instance_id,
        model="test-model",
        scaffold="test-agent",
        trajectory_summary="[user_query]: Fix parser.py",
    )


def _save(pipeline, instance, output_path, l1_mode):
    async def run():
        return await _label_and_save(
            pipeline,
            instance,
            output_path,
            l1_mode,
            asyncio.Lock(),
        )

    return asyncio.run(run())


def test_default_output_name_is_l1_l2_labeled(tmp_path):
    base_dir = tmp_path / "repo"
    config = {"pipeline": {"output_dir": "./output/trajectory_full"}}

    output = default_output_path("raw-sessions.jsonl", config, str(base_dir))

    assert output == str(
        base_dir / "output" / "trajectory_full" / "raw-sessions_l1_l2_labeled.jsonl"
    )


def test_config_l1_mode_is_used_when_cli_omits_it():
    config = {"labeling": {"l1_mode": "relabel"}}

    assert resolve_l1_mode(None, config) == "relabel"


def test_cli_l1_mode_overrides_config():
    config = {"labeling": {"l1_mode": "relabel"}}

    assert resolve_l1_mode("preserve", config) == "preserve"


def test_label_and_save_appends_only_success(tmp_path):
    output = tmp_path / "labels.jsonl"
    pipeline = FakePipeline(
        {
            "instance_id": "item-1",
            "trajectory_id": "item-1",
            "labels": {"task_type_l1": "bug-fix"},
        }
    )

    ok = _save(pipeline, _instance(), str(output), "preserve")

    assert ok is True
    assert json.loads(output.read_text(encoding="utf-8"))["instance_id"] == "item-1"
    assert pipeline.calls == [("item-1", "preserve")]


def test_label_and_save_does_not_append_error(tmp_path):
    output = tmp_path / "labels.jsonl"
    pipeline = FakePipeline({"error": "invalid_l2_response"})

    ok = _save(pipeline, _instance(), str(output), "preserve")

    assert ok is False
    assert not output.exists()


def test_label_and_save_isolates_a_raising_pipeline(tmp_path, caplog):
    output = tmp_path / "labels.jsonl"
    pipeline = FakePipeline(error=RuntimeError("broken row"))

    with caplog.at_level(logging.ERROR):
        ok = _save(pipeline, _instance(), str(output), "relabel")

    assert ok is False
    assert not output.exists()
    assert "item-1" in caplog.text
    assert "broken row" in caplog.text


def test_resume_ids_match_unique_normalized_instance_ids(tmp_path):
    source = tmp_path / "duplicates.jsonl"
    rows = []
    for content in ("first", "second"):
        rows.append(
            {
                "trajectory_id": "duplicate",
                "json_content": json.dumps([{"role": "user", "content": content}]),
            }
        )
    source.write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
    )
    instances = normalize_trajectory_jsonl(
        str(source), require_l1=False, unique_instance_ids=True
    )

    remaining = filter_unlabeled_instances(
        instances,
        {instances[0].instance_id: instances[0].source_content_sha256},
    )

    assert [instance.instance_id for instance in remaining] == [instances[1].instance_id]
    assert instances[1].instance_id.startswith("duplicate__")


def test_resume_rejects_changed_content_for_completed_instance(tmp_path):
    source = tmp_path / "changed.jsonl"
    source.write_text(
        json.dumps(
            {
                "trajectory_id": "stable-id",
                "json_content": json.dumps([{"role": "user", "content": "new"}]),
            }
        )
        + "\n",
        encoding="utf-8",
    )
    [instance] = normalize_trajectory_jsonl(
        str(source), require_l1=False, unique_instance_ids=True
    )

    with pytest.raises(ResumeStateError, match="source content changed"):
        filter_unlabeled_instances([instance], {"stable-id": "0" * 64})


def test_resume_rejects_reordered_duplicate_request_ids(tmp_path):
    def write_rows(path, contents):
        rows = [
            {
                "trajectory_id": "duplicate",
                "json_content": json.dumps([{"role": "user", "content": content}]),
            }
            for content in contents
        ]
        path.write_text(
            "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
        )

    original = tmp_path / "original.jsonl"
    reordered = tmp_path / "reordered.jsonl"
    write_rows(original, ["first", "second"])
    write_rows(reordered, ["second", "first"])
    original_instances = normalize_trajectory_jsonl(
        str(original), require_l1=False, unique_instance_ids=True
    )
    reordered_instances = normalize_trajectory_jsonl(
        str(reordered), require_l1=False, unique_instance_ids=True
    )
    completed = {
        instance.instance_id: instance.source_content_sha256
        for instance in original_instances
    }

    with pytest.raises(ResumeStateError, match="source content changed"):
        filter_unlabeled_instances(reordered_instances, completed)


def test_resume_loader_rejects_truncated_output_tail(tmp_path):
    output = tmp_path / "truncated.jsonl"
    complete = {
        "instance_id": "complete",
        "source_content_sha256": "a" * 64,
    }
    output.write_text(
        json.dumps(complete) + '\n{"instance_id":"partial"', encoding="utf-8"
    )

    with pytest.raises(ResumeStateError, match="invalid JSON"):
        load_completed_source_hashes(str(output))


def test_resume_loader_makes_valid_unterminated_tail_appendable(tmp_path):
    output = tmp_path / "unterminated.jsonl"
    complete = {
        "instance_id": "complete",
        "source_content_sha256": "a" * 64,
    }
    output.write_text(json.dumps(complete), encoding="utf-8")

    completed = load_completed_source_hashes(str(output))

    assert completed == {"complete": "a" * 64}
    assert output.read_bytes().endswith(b"\n")


def test_resume_loader_rejects_records_without_source_hash(tmp_path):
    output = tmp_path / "missing-hash.jsonl"
    output.write_text(json.dumps({"instance_id": "old"}) + "\n", encoding="utf-8")

    with pytest.raises(ResumeStateError, match="source_content_sha256"):
        load_completed_source_hashes(str(output))


def test_public_full_config_uses_conservative_concurrency():
    config_path = (
        Path(__file__).parents[1] / "config" / "labeler_config_trajectory_full.yaml"
    )

    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    assert config["llm"]["max_concurrent"] == 4
    assert config["pipeline"]["batch_size"] == 4
    assert config["labeling"]["l1_mode"] == "preserve"
    assert config["input"]["path"] is None


def test_readme_documents_both_trajectory_workflows_and_l1_modes():
    readme = (Path(__file__).parents[1] / "README.md").read_text(encoding="utf-8")

    assert "run_trajectory_label.py" in readme
    assert "run_trajectory_full_label.py" in readme
    assert "--l1-mode preserve" in readme
    assert "--l1-mode relabel" in readme

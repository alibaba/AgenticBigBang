import json
import hashlib
import logging
import re

from src.trajectory_normalizer import normalize_trajectory_jsonl


RAW_MESSAGES = [
    {"role": "system", "content": "shared boilerplate"},
    {"role": "user", "content": "<user_query>Fix parser.py</user_query>"},
    {"role": "assistant", "content": "I will inspect the parser."},
]


def _write_jsonl(path, rows):
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _raw_row(request_id="request-1", messages=None, **extra):
    row = {
        "trajectory_id": request_id,
        "json_content": json.dumps(messages or RAW_MESSAGES, ensure_ascii=False),
        "source_artifact_uri": f"artifact://synthetic/{request_id}",
    }
    row.update(extra)
    return row


def _legacy_row(request_id="legacy-1"):
    return {
        "trajectory_id": request_id,
        "json_content": json.dumps(
            {
                "requestid": request_id,
                "model": "example-model",
                "scaffold": "legacy-agent",
                "messages": RAW_MESSAGES,
            },
            ensure_ascii=False,
        ),
        "label_result": {
            "result": {
                "task_type": "bug-fix",
                "application_domain": "web_backend",
                "code_language": "python",
                "task_spec_type": "specific",
                "dependency_context": "codebase",
            }
        },
    }


def test_list_json_content_is_retained_when_l1_is_optional(tmp_path):
    source = tmp_path / "raw.jsonl"
    _write_jsonl(source, [_raw_row()])

    instances = normalize_trajectory_jsonl(str(source), require_l1=False)

    assert len(instances) == 1
    assert instances[0].instance_id == "request-1"
    assert instances[0].trajectory_id == "request-1"
    assert instances[0].task_type_l1 == ""
    assert "Fix parser.py" in instances[0].trajectory_summary
    assert "shared boilerplate" not in instances[0].trajectory_summary


def test_default_normalizer_still_rejects_missing_l1(tmp_path):
    source = tmp_path / "raw.jsonl"
    _write_jsonl(source, [_raw_row()])

    assert normalize_trajectory_jsonl(str(source)) == []


def test_dictionary_json_content_and_legacy_l1_keep_old_shape(tmp_path):
    source = tmp_path / "legacy.jsonl"
    _write_jsonl(source, [_legacy_row()])

    instances = normalize_trajectory_jsonl(str(source))

    assert len(instances) == 1
    instance = instances[0]
    assert instance.model == "example-model"
    assert instance.scaffold == "legacy-agent"
    assert instance.task_type_l1 == "bug-fix"
    assert instance.domain_l1 == "web_backend"
    assert set(instance.to_dict()) == {
        "instance_id",
        "trajectory_id",
        "model",
        "scaffold",
        "task_type_l1",
        "domain_l1",
        "code_language",
        "task_spec_type",
        "dependency_context",
        "trajectory_summary",
        "labels",
    }


def test_default_legacy_path_prefers_label_result_over_conflicting_top_level_labels(
    tmp_path,
):
    source = tmp_path / "conflicting-labels.jsonl"
    row = _legacy_row()
    row["labels"] = {
        "task_type_l1": "feature",
        "domain_l1": "web_frontend",
        "code_language": "js/ts",
        "task_spec_type": "fuzzy",
        "dependency_context": "env",
    }
    _write_jsonl(source, [row])

    [instance] = normalize_trajectory_jsonl(str(source))

    assert instance.task_type_l1 == "bug-fix"
    assert instance.domain_l1 == "web_backend"
    assert instance.code_language == "python"


def test_modern_labels_container_is_extracted(tmp_path):
    source = tmp_path / "modern.jsonl"
    row = _raw_row(
        labels={
            "task_type_l1": "feature",
            "domain_l1": "devtools_test",
            "code_language": "python",
            "task_spec_type": "specific",
            "dependency_context": "codebase",
            "task_type_rationale": "A new capability is requested.",
            "domain_rationale": "The repository is developer tooling.",
        }
    )
    _write_jsonl(source, [row])

    instances = normalize_trajectory_jsonl(str(source), require_l1=False)

    assert len(instances) == 1
    assert instances[0].task_type_l1 == "feature"
    assert instances[0].domain_l1 == "devtools_test"
    assert instances[0].l1_rationales == {
        "task_type_rationale": "A new capability is requested.",
        "domain_rationale": "The repository is developer tooling.",
    }
    assert "l1_rationales" not in instances[0].to_dict(include_source_metadata=True)


def test_legacy_l1_rationales_are_retained_as_internal_metadata(tmp_path):
    source = tmp_path / "legacy-rationales.jsonl"
    row = _legacy_row()
    row["label_result"]["result"].update(
        {
            "task_type_rationale": "The trajectory fixes a defect.",
            "application_domain_rationale": "The project is a backend service.",
        }
    )
    _write_jsonl(source, [row])

    [instance] = normalize_trajectory_jsonl(str(source))

    assert instance.l1_rationales == {
        "task_type_rationale": "The trajectory fixes a defect.",
        "domain_rationale": "The project is a backend service.",
    }


def test_malformed_json_content_skips_only_bad_row(tmp_path):
    source = tmp_path / "mixed.jsonl"
    bad = _raw_row("bad")
    bad["json_content"] = "not-json"
    _write_jsonl(source, [bad, _raw_row("good")])

    instances = normalize_trajectory_jsonl(str(source), require_l1=False)

    assert [instance.instance_id for instance in instances] == ["good"]


def test_non_object_outer_json_skips_only_bad_rows(tmp_path, caplog):
    source = tmp_path / "non-objects.jsonl"
    with source.open("w", encoding="utf-8") as handle:
        for value in (None, [], "scalar", 42):
            handle.write(json.dumps(value) + "\n")
        handle.write(json.dumps(_raw_row("good")) + "\n")

    with caplog.at_level(logging.WARNING):
        instances = normalize_trajectory_jsonl(str(source), require_l1=False)

    assert [instance.instance_id for instance in instances] == ["good"]
    assert caplog.text.lower().count("object") >= 4


def test_empty_or_non_message_content_is_skipped(tmp_path):
    source = tmp_path / "empty-messages.jsonl"
    rows = [
        _raw_row("empty-list", messages=[]),
        _raw_row("non-messages", messages=[1, "two", None]),
        {
            "trajectory_id": "empty-wrapped",
            "json_content": json.dumps({"messages": []}),
        },
        _raw_row("good"),
    ]
    # _raw_row treats [] as false and substitutes RAW_MESSAGES, so set it explicitly.
    rows[0]["json_content"] = "[]"
    _write_jsonl(source, rows)

    instances = normalize_trajectory_jsonl(str(source), require_l1=False)

    assert [instance.instance_id for instance in instances] == ["good"]


def test_unique_mode_suffixes_distinct_duplicate_request_ids(tmp_path):
    source = tmp_path / "duplicates.jsonl"
    first = _raw_row("duplicate", messages=[{"role": "user", "content": "first"}])
    second = _raw_row("duplicate", messages=[{"role": "user", "content": "second"}])
    _write_jsonl(source, [first, second])

    instances = normalize_trajectory_jsonl(
        str(source), require_l1=False, unique_instance_ids=True
    )

    assert len(instances) == 2
    assert instances[0].instance_id == "duplicate"
    assert re.fullmatch(r"duplicate__[0-9a-f]{12}", instances[1].instance_id)
    assert [instance.trajectory_id for instance in instances] == [
        "duplicate",
        "duplicate",
    ]


def test_unique_mode_skips_exact_duplicate_lines(tmp_path, caplog):
    source = tmp_path / "exact-duplicates.jsonl"
    row = _raw_row("same")
    _write_jsonl(source, [row, row])

    with caplog.at_level(logging.WARNING):
        instances = normalize_trajectory_jsonl(
            str(source), require_l1=False, unique_instance_ids=True
        )

    assert [instance.instance_id for instance in instances] == ["same"]
    assert "duplicate" in caplog.text.lower()


def test_unique_mode_is_repeatable_for_same_input_order(tmp_path):
    source = tmp_path / "repeatable.jsonl"
    _write_jsonl(
        source,
        [
            _raw_row("repeat", messages=[{"role": "user", "content": "a"}]),
            _raw_row("repeat", messages=[{"role": "user", "content": "b"}]),
        ],
    )

    first = normalize_trajectory_jsonl(
        str(source), require_l1=False, unique_instance_ids=True
    )
    second = normalize_trajectory_jsonl(
        str(source), require_l1=False, unique_instance_ids=True
    )

    assert [item.instance_id for item in first] == [item.instance_id for item in second]


def test_full_output_can_include_line_hash_and_source_locator(tmp_path):
    source = tmp_path / "source-metadata.jsonl"
    row = _raw_row("located")
    serialized = json.dumps(row, ensure_ascii=False)
    source.write_text(serialized + "\n", encoding="utf-8")

    [instance] = normalize_trajectory_jsonl(
        str(source), require_l1=False, unique_instance_ids=True
    )
    output = instance.to_dict(include_source_metadata=True)

    assert output["source_line_number"] == 1
    assert output["source_content_sha256"] == hashlib.sha256(
        serialized.encode("utf-8")
    ).hexdigest()
    assert output["source_artifact_uri"] == "artifact://synthetic/located"
    assert "source_line_number" not in instance.to_dict()


def test_compact_mode_formats_openai_tool_calls_and_bash_results(tmp_path):
    source = tmp_path / "openai-tools.jsonl"
    messages = [
        {"role": "user", "content": "<user_query>Fix and test parser.py</user_query>"},
        {
            "role": "assistant",
            "content": "Inspecting and testing.",
            "tool_calls": [
                {
                    "id": "read-1",
                    "type": "function",
                    "function": {
                        "name": "Read",
                        "arguments": json.dumps({"file_path": "parser.py"}),
                    },
                },
                {
                    "id": "bash-1",
                    "type": "function",
                    "function": {
                        "name": "Bash",
                        "arguments": json.dumps({"command": "pytest -q"}),
                    },
                },
            ],
        },
        {"role": "tool", "tool_call_id": "read-1", "content": "BULK_READ_RESULT" * 1000},
        {"role": "tool", "tool_call_id": "bash-1", "content": "2 passed in 0.04s"},
    ]
    _write_jsonl(source, [_raw_row("tools", messages=messages)])

    [instance] = normalize_trajectory_jsonl(
        str(source), require_l1=False, content_mode="compact"
    )

    assert "[tool: Read] file=parser.py" in instance.trajectory_summary
    assert "[tool: Bash] pytest -q" in instance.trajectory_summary
    assert "2 passed in 0.04s" in instance.trajectory_summary
    assert "BULK_READ_RESULT" not in instance.trajectory_summary


def test_compact_mode_formats_anthropic_tool_use_blocks(tmp_path):
    source = tmp_path / "anthropic-tools.jsonl"
    messages = [
        {"role": "user", "content": "Create a config"},
        {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "Writing the file."},
                {
                    "type": "tool_use",
                    "id": "write-1",
                    "name": "Write",
                    "input": {"file_path": "config.yaml", "content": "enabled: true"},
                },
            ],
        },
        {
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": "write-1", "content": "written"}
            ],
        },
    ]
    _write_jsonl(source, [_raw_row("anthropic", messages=messages)])

    [instance] = normalize_trajectory_jsonl(
        str(source), require_l1=False, content_mode="compact"
    )

    assert "[tool: Write] file=config.yaml" in instance.trajectory_summary
    assert "enabled: true" in instance.trajectory_summary


def test_compact_mode_removes_system_reminders(tmp_path):
    source = tmp_path / "reminders.jsonl"
    messages = [
        {"role": "system", "content": "SYSTEM BOILERPLATE"},
        {
            "role": "user",
            "content": (
                "<system-reminder>PRIVATE BOILERPLATE</system-reminder>"
                "<user_query>Implement the cache</user_query>"
            ),
        },
    ]
    _write_jsonl(source, [_raw_row("reminder", messages=messages)])

    [instance] = normalize_trajectory_jsonl(
        str(source), require_l1=False, content_mode="compact"
    )

    assert "Implement the cache" in instance.trajectory_summary
    assert "PRIVATE BOILERPLATE" not in instance.trajectory_summary
    assert "SYSTEM BOILERPLATE" not in instance.trajectory_summary


def test_compact_mode_falls_back_to_untagged_user_content(tmp_path):
    source = tmp_path / "untagged.jsonl"
    _write_jsonl(
        source,
        [_raw_row("untagged", messages=[{"role": "user", "content": "Explain this code"}])],
    )

    [instance] = normalize_trajectory_jsonl(
        str(source), require_l1=False, content_mode="compact"
    )

    assert "Explain this code" in instance.trajectory_summary

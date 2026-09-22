from __future__ import annotations
import json
import glob
import os
import logging
from pathlib import Path
from typing import Iterator

from .schema import UnifiedInstance

logger = logging.getLogger(__name__)


def normalize_all(datasets_config: list[dict], base_dir: str = ".") -> list[UnifiedInstance]:
    instances = []
    for ds in datasets_config:
        path = os.path.join(base_dir, ds["path"]) if not os.path.isabs(ds["path"]) else ds["path"]
        fmt = ds["format"]
        name = ds["name"]
        logger.info(f"Normalizing dataset: {name} (format={fmt}, path={path})")

        if fmt == "swe_bench_jsonl":
            batch = list(normalize_swe_bench_jsonl(path, name))
        elif fmt == "swe_bench_pro_jsonl":
            batch = list(normalize_swe_bench_pro(path, name))
        elif fmt == "huggingface_arrow":
            batch = list(normalize_huggingface_arrow(path, name))
        elif fmt == "deepswe_json":
            batch = list(normalize_deepswe(path, name))
        elif fmt == "generic_swe_jsonl":
            batch = list(normalize_training_data_jsonl(path, name))
        else:
            logger.warning(f"Unknown format '{fmt}' for dataset '{name}', skipping.")
            continue

        logger.info(f"  -> {len(batch)} instances loaded from {name}")
        instances.extend(batch)

    logger.info(f"Total normalized instances: {len(instances)}")
    return instances


def normalize_swe_bench_jsonl(path: str, dataset_name: str) -> Iterator[UnifiedInstance]:
    part_files = sorted(glob.glob(os.path.join(path, "part_*.jsonl")))
    if not part_files:
        jsonl_files = sorted(glob.glob(os.path.join(path, "*.jsonl")))
        part_files = [f for f in jsonl_files if "extracted_ids" not in f]

    for fpath in part_files:
        with open(fpath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                raw = json.loads(line)
                yield UnifiedInstance(
                    instance_id=raw["instance_id"],
                    dataset_source=dataset_name,
                    repo=raw["repo"],
                    problem_statement=raw.get("problem_statement", ""),
                    patch=raw.get("patch", ""),
                    test_patch=raw.get("test_patch", ""),
                    hints_text=raw.get("hints_text", ""),
                    language=None,
                    created_at=raw.get("created_at"),
                    base_commit=raw.get("base_commit"),
                )

def normalize_swe_bench_pro(path: str, dataset_name: str) -> Iterator[UnifiedInstance]:
    part_files = sorted(glob.glob(os.path.join(path, "part_*.jsonl")))

    for fpath in part_files:
        with open(fpath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                raw = json.loads(line)
                yield UnifiedInstance(
                    instance_id=raw["instance_id"],
                    dataset_source=dataset_name,
                    repo=raw["repo"],
                    problem_statement=raw.get("problem_statement", ""),
                    patch=raw.get("patch", ""),
                    test_patch=raw.get("test_patch", ""),
                    hints_text="",
                    language=raw.get("repo_language"),
                    created_at=None,
                    base_commit=raw.get("base_commit"),
                )


def normalize_huggingface_arrow(path: str, dataset_name: str) -> Iterator[UnifiedInstance]:
    try:
        from datasets import load_from_disk
        ds = load_from_disk(path)
        if "test" in ds:
            split = ds["test"]
        else:
            split = ds
    except Exception:
        import pyarrow as pa
        arrow_files = glob.glob(os.path.join(path, "test", "*.arrow"))
        if not arrow_files:
            arrow_files = glob.glob(os.path.join(path, "**", "*.arrow"), recursive=True)
        if not arrow_files:
            logger.error(f"No arrow files found in {path}")
            return

        tables = []
        for af in arrow_files:
            with open(af, "rb") as f:
                reader = pa.ipc.open_file(f)
                tables.append(reader.read_all())
        table = pa.concat_tables(tables)
        split = table.to_pydict()
        n = len(split[list(split.keys())[0]])
        for i in range(n):
            row = {k: v[i] for k, v in split.items()}
            yield _arrow_row_to_instance(row, dataset_name)
        return

    for row in split:
        yield _arrow_row_to_instance(row, dataset_name)


def _arrow_row_to_instance(row: dict, dataset_name: str) -> UnifiedInstance:
    fail_to_pass = row.get("FAIL_TO_PASS", [])
    if isinstance(fail_to_pass, str):
        try:
            fail_to_pass = json.loads(fail_to_pass)
        except (json.JSONDecodeError, TypeError):
            pass

    return UnifiedInstance(
        instance_id=row["instance_id"],
        dataset_source=dataset_name,
        repo=row["repo"],
        problem_statement=row.get("problem_statement", ""),
        patch=row.get("patch", ""),
        test_patch=row.get("test_patch", ""),
        hints_text=row.get("hints_text", ""),
        language=None,
        created_at=row.get("created_at"),
        base_commit=row.get("base_commit"),
    )


def normalize_deepswe(path: str, dataset_name: str) -> Iterator[UnifiedInstance]:
    json_file = os.path.join(path, "test.json")
    if not os.path.exists(json_file):
        json_files = glob.glob(os.path.join(path, "*.json"))
        if json_files:
            json_file = json_files[0]
        else:
            logger.error(f"No JSON file found in {path}")
            return

    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    for raw in data:
        repo_url = raw.get("repo", "")
        repo_name = _extract_repo_from_url(repo_url)

        yield UnifiedInstance(
            instance_id=raw.get("instance_id", raw.get("task_id", "")),
            dataset_source=dataset_name,
            repo=repo_name,
            problem_statement=raw.get("problem_statement", ""),
            patch=raw.get("reference_patch", raw.get("patch", "")),
            test_patch=raw.get("test_patch", ""),
            hints_text="",
            language=raw.get("language"),
            created_at=None,
            base_commit=raw.get("base_commit"),
        )


def _extract_repo_from_url(url: str) -> str:
    if not url:
        return ""
    url = url.rstrip("/")
    if "github.com" in url:
        parts = url.split("github.com/")[-1].split("/")
        if len(parts) >= 2:
            return f"{parts[0]}/{parts[1]}"
    return url


LANG_NORMALIZE = {
    "js": "js/ts",
    "default": None,
    "other": None,
}


def _normalize_language(lang: str | None) -> str | None:
    if not lang:
        return None
    return LANG_NORMALIZE.get(lang, lang)


def normalize_training_data_jsonl(path: str, dataset_name: str = "") -> Iterator[UnifiedInstance]:
    if os.path.isdir(path):
        files = sorted(glob.glob(os.path.join(path, "*.jsonl")))
    else:
        files = [path]

    for fpath in files:
        fname = os.path.basename(fpath)
        ds_name = dataset_name or fname
        with open(fpath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    raw = json.loads(line)
                except json.JSONDecodeError:
                    continue
                split = raw.get("split", "")
                instance_id = raw.get("instance_id", "")
                unique_id = f"{split}__{instance_id}" if split else instance_id

                yield UnifiedInstance(
                    instance_id=unique_id,
                    dataset_source=ds_name,
                    repo=raw.get("repo") or raw.get("repo_name") or "",
                    problem_statement=raw.get("problem_statement", ""),
                    patch=raw.get("patch", ""),
                    test_patch=raw.get("test_patch", ""),
                    hints_text=raw.get("hints_text", ""),
                    language=_normalize_language(raw.get("language")),
                    created_at=raw.get("created_at"),
                    base_commit=raw.get("base_commit"),
                )

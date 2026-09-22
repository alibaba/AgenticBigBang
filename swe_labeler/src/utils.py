from __future__ import annotations
import json
import os
import logging
import time
import yaml
from pathlib import Path
from typing import Any

from .schema import UnifiedInstance, LabelResult

logger = logging.getLogger(__name__)


def load_config(config_path: str) -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if config.get("llm", {}).get("api_key", "").startswith("${"):
        env_var = config["llm"]["api_key"].strip("${}")
        config["llm"]["api_key"] = os.environ.get(env_var, "")

    return config


def read_jsonl(path: str) -> list[dict]:
    results = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                results.append(json.loads(line))
    return results


def write_jsonl(path: str, items: list[dict], mode: str = "w"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, mode, encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")


def append_jsonl(path: str, item: dict):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")


def load_labeled_ids(output_path: str) -> set[str]:
    if not os.path.exists(output_path):
        return set()
    ids = set()
    with open(output_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    obj = json.loads(line)
                    ids.add(obj.get("instance_id", ""))
                except json.JSONDecodeError:
                    continue
    return ids


def load_yaml(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def truncate_text(text: str, max_lines: int = 150, max_chars: int = 8000) -> str:
    if not text:
        return ""
    lines = text.split("\n")
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines.append(f"\n... [truncated, {len(text.split(chr(10))) - max_lines} more lines]")
    result = "\n".join(lines)
    if len(result) > max_chars:
        result = result[:max_chars] + f"\n... [truncated at {max_chars} chars]"
    return result


def setup_logging(level: str = "INFO"):
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

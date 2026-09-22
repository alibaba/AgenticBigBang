#!/usr/bin/env python3
"""Run full L1 + L2 labeling for raw user/agent trajectories."""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.llm_client import LLMClient
from src.trajectory_l1_labeler import TrajectoryL1Labeler
from src.trajectory_labeler import TrajectoryLabeler
from src.trajectory_normalizer import TrajectoryInstance, normalize_trajectory_jsonl
from src.trajectory_pipeline import TrajectoryPipeline
from src.utils import append_jsonl, load_config, setup_logging

logger = logging.getLogger(__name__)

L1_MODES = {"preserve", "relabel"}


class ResumeStateError(RuntimeError):
    """The existing output cannot be safely matched or appended to."""


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Full trajectory L1 + L2 labeling pipeline"
    )
    parser.add_argument(
        "--input", type=str, default=None, help="Input JSONL file (overrides config)"
    )
    parser.add_argument(
        "--output", type=str, default=None, help="Output JSONL file (overrides config)"
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config/labeler_config_trajectory_full.yaml",
        help="Config file",
    )
    parser.add_argument(
        "--limit", type=int, default=None, help="Process only the first N source lines"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help="Maximum concurrent trajectories (bounded by llm.max_concurrent)",
    )
    parser.add_argument(
        "--l1-mode",
        choices=sorted(L1_MODES),
        default=None,
        help="Preserve complete valid L1 or relabel every trajectory",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Do not skip instance IDs already present in the output",
    )
    parser.add_argument("--log-level", type=str, default=None)
    return parser.parse_args(argv)


def resolve_l1_mode(cli_mode: str | None, config: dict) -> str:
    mode = cli_mode or config.get("labeling", {}).get("l1_mode", "preserve")
    if mode not in L1_MODES:
        raise ValueError(f"Unsupported L1 mode: {mode}")
    return mode


def default_output_path(input_path: str, config: dict, base_dir: str) -> str:
    output_dir = config.get("pipeline", {}).get(
        "output_dir", "./output/trajectory_full"
    )
    if not os.path.isabs(output_dir):
        output_dir = os.path.join(base_dir, output_dir)
    input_stem = os.path.splitext(os.path.basename(input_path))[0]
    return os.path.normpath(
        os.path.join(output_dir, f"{input_stem}_l1_l2_labeled.jsonl")
    )


def filter_unlabeled_instances(
    instances: list[TrajectoryInstance], completed_hashes: dict[str, str]
) -> list[TrajectoryInstance]:
    remaining = []
    for instance in instances:
        completed_hash = completed_hashes.get(instance.instance_id)
        if completed_hash is None:
            remaining.append(instance)
            continue
        if completed_hash != instance.source_content_sha256:
            raise ResumeStateError(
                f"source content changed for completed instance {instance.instance_id!r}; "
                "use a new output path or restore the original input ordering"
            )
    return remaining


def load_completed_source_hashes(output_path: str) -> dict[str, str]:
    """Load verified resume state and make a valid final record appendable."""
    if not os.path.exists(output_path):
        return {}

    completed = {}
    try:
        with open(output_path, "r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ResumeStateError(
                        f"invalid JSON in existing output at line {line_number}; "
                        "refusing to append to a possibly truncated file"
                    ) from exc
                if not isinstance(record, dict):
                    raise ResumeStateError(
                        f"existing output line {line_number} is not a JSON object"
                    )
                instance_id = record.get("instance_id")
                source_hash = record.get("source_content_sha256")
                if not isinstance(instance_id, str) or not instance_id:
                    raise ResumeStateError(
                        f"existing output line {line_number} has no instance_id"
                    )
                if (
                    not isinstance(source_hash, str)
                    or len(source_hash) != 64
                    or any(char not in "0123456789abcdef" for char in source_hash.lower())
                ):
                    raise ResumeStateError(
                        f"existing output line {line_number} has no valid "
                        "source_content_sha256"
                    )
                previous = completed.get(instance_id)
                if previous is not None and previous != source_hash:
                    raise ResumeStateError(
                        f"existing output contains conflicting source hashes for "
                        f"instance {instance_id!r}"
                    )
                completed[instance_id] = source_hash
    except UnicodeDecodeError as exc:
        raise ResumeStateError("existing output is not valid UTF-8") from exc

    if os.path.getsize(output_path) > 0:
        with open(output_path, "rb") as handle:
            handle.seek(-1, os.SEEK_END)
            has_final_newline = handle.read(1) in {b"\n", b"\r"}
        if not has_final_newline:
            # Every record parsed successfully, so adding the JSONL delimiter is safe.
            with open(output_path, "ab") as handle:
                handle.write(b"\n")

    return completed


async def _label_and_save(
    pipeline: TrajectoryPipeline,
    instance: TrajectoryInstance,
    output_path: str,
    l1_mode: str,
    write_lock: asyncio.Lock,
) -> bool:
    try:
        result = await pipeline.label_instance(instance, l1_mode=l1_mode)
        if result.get("error"):
            logger.error(
                "Failed trajectory %s: %s (%s)",
                instance.instance_id,
                result.get("error"),
                result.get("details", []),
            )
            return False
        async with write_lock:
            append_jsonl(output_path, result)
        return True
    except Exception:
        logger.exception("Error labeling trajectory %s", instance.instance_id)
        return False


async def main(argv=None):
    args = parse_args(argv)
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = args.config
    if not os.path.isabs(config_path):
        config_path = os.path.join(base_dir, config_path)
    config = load_config(config_path)

    log_level = args.log_level or config.get("pipeline", {}).get("log_level", "INFO")
    setup_logging(log_level)

    input_path = args.input or config.get("input", {}).get("path")
    if not input_path:
        logger.error("No input path. Use --input or set input.path in config")
        return 2
    if not os.path.isabs(input_path):
        input_path = os.path.join(base_dir, input_path)

    try:
        l1_mode = resolve_l1_mode(args.l1_mode, config)
    except ValueError as exc:
        logger.error("%s", exc)
        return 2

    output_path = args.output or default_output_path(input_path, config, base_dir)
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    logger.info("Loading trajectories from %s", input_path)
    instances = normalize_trajectory_jsonl(
        input_path,
        limit=args.limit,
        require_l1=False,
        content_mode="compact",
        unique_instance_ids=True,
    )
    if not instances:
        logger.warning("No valid instances loaded")
        return 0

    try:
        completed_hashes = load_completed_source_hashes(output_path)
        if args.no_resume:
            to_label = instances
        else:
            to_label = filter_unlabeled_instances(instances, completed_hashes)
    except ResumeStateError as exc:
        logger.error("Unsafe resume state: %s", exc)
        return 2
    if completed_hashes and not args.no_resume:
        logger.info(
            "Resuming: %s verified instance IDs already labeled",
            len(completed_hashes),
        )
    logger.info("To label: %s / %s normalized trajectories", len(to_label), len(instances))
    if not to_label:
        logger.info("All normalized trajectories are already labeled")
        return 0

    llm_config = config["llm"]
    if not llm_config.get("api_key"):
        logger.error("LLM API key is empty; set the configured environment variable")
        return 2

    llm_client = LLMClient(
        base_url=llm_config["base_url"],
        api_key=llm_config["api_key"],
        model=llm_config["model"],
        max_concurrent=llm_config.get("max_concurrent", 30),
        requests_per_minute=llm_config.get("requests_per_minute", 100),
        timeout=llm_config.get("timeout", 120),
        max_retries=llm_config.get("max_retries", 3),
        ssl_verify=llm_config.get("ssl_verify", True),
    )

    labeling_config = config.get("labeling", {})
    l1_labeler = TrajectoryL1Labeler(
        llm_client,
        max_tokens=labeling_config.get("l1_max_tokens", 4096),
    )
    l2_labeler = TrajectoryLabeler(
        llm_client,
        max_tokens=labeling_config.get("l2_max_tokens", 12800),
    )
    pipeline = TrajectoryPipeline(l1_labeler, l2_labeler)

    configured_batch = config.get("pipeline", {}).get("batch_size", 30)
    requested_batch = args.batch_size or configured_batch
    concurrency = min(requested_batch, llm_config.get("max_concurrent", 30))
    if concurrency < 1:
        logger.error("Concurrency must be at least 1")
        await llm_client.close()
        return 2

    semaphore = asyncio.Semaphore(concurrency)
    write_lock = asyncio.Lock()
    start_time = time.monotonic()
    completed = 0
    failed = 0
    counter_lock = asyncio.Lock()
    progress_interval = min(50, max(10, len(to_label) // 20))

    async def process_one(instance: TrajectoryInstance):
        nonlocal completed, failed
        async with semaphore:
            ok = await _label_and_save(
                pipeline, instance, output_path, l1_mode, write_lock
            )
        async with counter_lock:
            if ok:
                completed += 1
            else:
                failed += 1
            done = completed + failed
            if done % progress_interval == 0 or done == len(to_label):
                elapsed = max(time.monotonic() - start_time, 0.001)
                per_minute = done / elapsed * 60
                logger.info(
                    "Progress: %s/%s | %s ok, %s failed | %.1f/min",
                    done,
                    len(to_label),
                    completed,
                    failed,
                    per_minute,
                )

    try:
        await asyncio.gather(*(process_one(instance) for instance in to_label))
    finally:
        await llm_client.close()

    elapsed = time.monotonic() - start_time
    logger.info(
        "Complete: %s labeled, %s failed in %.1fs | output=%s | LLM=%s",
        completed,
        failed,
        elapsed,
        output_path,
        llm_client.stats,
    )
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

#!/usr/bin/env python3
"""
SWE Labeler - Trajectory L2 Labeling Pipeline

Labels real user-AI interaction trajectories with L2 + orthogonal dimensions,
using existing L1 labels from label_result field.

Usage:
    python scripts/run_trajectory_label.py --input /path/to/data.jsonl --output ./output/trajectory_l2.jsonl
    python scripts/run_trajectory_label.py --input /path/to/data.jsonl --limit 10 --log-level DEBUG
"""
import argparse
import asyncio
import os
import sys
import time
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.trajectory_normalizer import normalize_trajectory_jsonl, TrajectoryInstance
from src.trajectory_labeler import TrajectoryLabeler
from src.llm_client import LLMClient
from src.utils import setup_logging, load_config, append_jsonl, load_labeled_ids

logger = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(description="Trajectory L2 labeling pipeline")
    parser.add_argument("--input", type=str, default=None, help="Input JSONL file (overrides config)")
    parser.add_argument("--output", type=str, default=None, help="Output JSONL file (overrides config)")
    parser.add_argument("--config", type=str, default="config/labeler_config_trajectory.yaml", help="Config file")
    parser.add_argument("--limit", type=int, default=None, help="Process only N trajectories")
    parser.add_argument("--batch-size", type=int, default=None, help="Batch size (overrides config)")
    parser.add_argument("--no-resume", action="store_true", help="Don't skip already labeled instances")
    parser.add_argument("--log-level", type=str, default=None)
    return parser.parse_args()


async def main():
    args = parse_args()

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(base_dir, args.config) if not os.path.isabs(args.config) else args.config
    config = load_config(config_path)

    log_level = args.log_level or config.get("pipeline", {}).get("log_level", "INFO")
    setup_logging(log_level)

    # Input path: CLI > config
    input_path = args.input or config.get("input", {}).get("path")
    if not input_path:
        logger.error("No input path. Use --input or set input.path in config")
        return
    if not os.path.isabs(input_path):
        input_path = os.path.join(base_dir, input_path)

    # Output path: CLI > config
    if args.output:
        output_path = args.output
    else:
        output_dir = config.get("pipeline", {}).get("output_dir", "./output/trajectory")
        output_dir = os.path.join(base_dir, output_dir) if not os.path.isabs(output_dir) else output_dir
        input_stem = os.path.splitext(os.path.basename(input_path))[0]
        output_path = os.path.join(output_dir, f"{input_stem}_l2_labeled.jsonl")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Load and normalize trajectories
    logger.info(f"Loading trajectories from {input_path}")
    instances = normalize_trajectory_jsonl(input_path, limit=args.limit)

    if not instances:
        logger.warning("No valid instances loaded")
        return

    # Resume: skip already labeled
    labeled_ids = set()
    if not args.no_resume:
        labeled_ids = load_labeled_ids(output_path)
        if labeled_ids:
            logger.info(f"Resuming: {len(labeled_ids)} already labeled, skipping")

    to_label = [inst for inst in instances if inst.instance_id not in labeled_ids]
    logger.info(f"To label: {len(to_label)} / {len(instances)} total")

    if not to_label:
        logger.info("All instances already labeled")
        return

    # Create LLM client and labeler
    llm_cfg = config["llm"]
    llm_client = LLMClient(
        base_url=llm_cfg["base_url"],
        api_key=llm_cfg["api_key"],
        model=llm_cfg["model"],
        max_concurrent=llm_cfg.get("max_concurrent", 30),
        requests_per_minute=llm_cfg.get("requests_per_minute", 99999),
        timeout=llm_cfg.get("timeout", 120),
        max_retries=llm_cfg.get("max_retries", 3),
        ssl_verify=llm_cfg.get("ssl_verify", True),
    )
    labeler = TrajectoryLabeler(llm_client)

    # Run labeling - streaming mode (no batch blocking)
    start_time = time.time()
    total_labeled = 0
    total_failed = 0
    total_todo = len(to_label)
    concurrency = llm_cfg.get("max_concurrent", 100)
    sem = asyncio.Semaphore(concurrency)
    progress_interval = min(50, max(10, total_todo // 20))

    async def _process_one(inst):
        nonlocal total_labeled, total_failed
        async with sem:
            ok = await _label_and_save(labeler, inst, output_path)
        if ok:
            total_labeled += 1
        else:
            total_failed += 1
        done = total_labeled + total_failed
        if done % progress_interval == 0 or done == total_todo:
            elapsed = time.time() - start_time
            speed = done / elapsed * 60 if elapsed > 0 else 0
            remaining = (total_todo - done) / (speed / 60) if speed > 0 else 0
            logger.info(
                f"Progress: {done}/{total_todo} ({done/total_todo*100:.1f}%) | "
                f"{total_labeled} ok, {total_failed} fail | "
                f"Speed: {speed:.1f}/min | ETA: {remaining:.0f}s"
            )

    tasks = [_process_one(inst) for inst in to_label]
    await asyncio.gather(*tasks)

    elapsed = time.time() - start_time
    logger.info("=" * 60)
    logger.info(f"Complete: {total_labeled} labeled, {total_failed} failed")
    logger.info(f"Time: {elapsed:.1f}s | LLM stats: {llm_client.stats}")
    logger.info(f"Output: {output_path}")
    logger.info("=" * 60)

    await llm_client.close()


async def _label_and_save(labeler: TrajectoryLabeler, instance: TrajectoryInstance, output_path: str) -> bool:
    try:
        result = await labeler.label_instance(instance)
        instance.labels = result
        append_jsonl(output_path, instance.to_dict())
        return True
    except Exception as e:
        logger.error(f"Error labeling {instance.instance_id}: {e}")
        return False


if __name__ == "__main__":
    asyncio.run(main())

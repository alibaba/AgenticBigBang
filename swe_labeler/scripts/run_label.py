#!/usr/bin/env python3
"""
SWE Labeler - CLI Entry Point

Usage:
    python scripts/run_label.py --config config/labeler_config.yaml
    python scripts/run_label.py --config config/labeler_config.yaml --dataset swe_bench_verified_500 --limit 10
    python scripts/run_label.py --config config/labeler_config.yaml --skip-enrich --no-resume
"""
import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils import load_config, setup_logging
from src.pipeline import Pipeline


def parse_args():
    parser = argparse.ArgumentParser(description="SWE Labeler - L1+L2 classification pipeline")
    parser.add_argument(
        "--config", type=str, default="config/labeler_config.yaml",
        help="Path to config YAML file"
    )
    parser.add_argument(
        "--dataset", type=str, default=None,
        help="Label only this specific dataset (by name in config)"
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Process only N instances (for testing)"
    )
    parser.add_argument(
        "--skip-enrich", action="store_true",
        help="Skip GitHub metadata enrichment"
    )
    parser.add_argument(
        "--no-resume", action="store_true",
        help="Do not skip already-labeled instances"
    )
    parser.add_argument(
        "--log-level", type=str, default=None,
        help="Override log level (DEBUG, INFO, WARNING, ERROR)"
    )
    return parser.parse_args()


async def main():
    args = parse_args()

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(base_dir, args.config) if not os.path.isabs(args.config) else args.config

    config = load_config(config_path)
    config["_base_dir"] = base_dir

    log_level = args.log_level or config.get("pipeline", {}).get("log_level", "INFO")
    setup_logging(log_level)

    pipeline = Pipeline(config)
    await pipeline.run(
        dataset_filter=args.dataset,
        limit=args.limit,
        skip_enrich=args.skip_enrich,
        resume=not args.no_resume,
    )


if __name__ == "__main__":
    asyncio.run(main())

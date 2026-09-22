from __future__ import annotations
import asyncio
import logging
import os
import time
from typing import Optional

from .schema import UnifiedInstance
from .normalizer import normalize_all
from .enricher import GitHubEnricher
from .labeler import Labeler
from .llm_client import LLMClient
from .utils import load_labeled_ids, append_jsonl

logger = logging.getLogger(__name__)


class Pipeline:
    def __init__(self, config: dict):
        self.config = config
        self.base_dir = config.get("_base_dir", ".")

        llm_cfg = config["llm"]
        self.llm_client = LLMClient(
            base_url=llm_cfg["base_url"],
            api_key=llm_cfg["api_key"],
            model=llm_cfg["model"],
            max_concurrent=llm_cfg.get("max_concurrent", 30),
            requests_per_minute=llm_cfg.get("requests_per_minute", 100),
            timeout=llm_cfg.get("timeout", 60),
            max_retries=llm_cfg.get("max_retries", 3),
            ssl_verify=llm_cfg.get("ssl_verify", True),
        )
        prompt_version = config.get("pipeline", {}).get("prompt_version", "default")
        self.labeler = Labeler(self.llm_client, prompt_version=prompt_version)

        github_cfg = config.get("github", {})
        self.enricher = GitHubEnricher(
            tokens=github_cfg.get("tokens", []),
            max_concurrent=github_cfg.get("max_concurrent", 5),
            cache_dir=os.path.join(self.base_dir, github_cfg.get("cache_dir", "./cache/github")),
            ssl_verify=github_cfg.get("ssl_verify", True),
        )

        self.output_dir = os.path.join(self.base_dir, config["pipeline"]["output_dir"])
        os.makedirs(self.output_dir, exist_ok=True)

    async def run(
        self,
        dataset_filter: Optional[str] = None,
        limit: Optional[int] = None,
        skip_enrich: bool = False,
        resume: bool = True,
    ):
        start_time = time.time()

        datasets_cfg = self.config["datasets"]
        if dataset_filter:
            datasets_cfg = [d for d in datasets_cfg if d["name"] == dataset_filter]
            if not datasets_cfg:
                logger.error(f"Dataset '{dataset_filter}' not found in config")
                return

        logger.info("=" * 60)
        logger.info("SWE Labeler Pipeline - Starting")
        logger.info("=" * 60)

        instances = normalize_all(datasets_cfg, base_dir=self.base_dir)

        if not instances:
            logger.warning("No instances loaded. Check dataset paths.")
            return

        if not skip_enrich:
            instances = await self.enricher.enrich_instances(instances)

        if limit:
            instances = instances[:limit]
            logger.info(f"Limited to {limit} instances")

        by_dataset: dict[str, list[UnifiedInstance]] = {}
        for inst in instances:
            by_dataset.setdefault(inst.dataset_source, []).append(inst)

        total_labeled = 0
        total_skipped = 0

        for dataset_name, dataset_instances in by_dataset.items():
            output_path = os.path.join(self.output_dir, f"{dataset_name}_labeled.jsonl")

            labeled_ids = set()
            if resume:
                labeled_ids = load_labeled_ids(output_path)
                if labeled_ids:
                    logger.info(f"Resuming {dataset_name}: {len(labeled_ids)} already labeled")

            to_label = [inst for inst in dataset_instances if inst.instance_id not in labeled_ids]
            total_skipped += len(dataset_instances) - len(to_label)

            if not to_label:
                logger.info(f"Dataset {dataset_name}: all instances already labeled")
                continue

            logger.info(f"Labeling {len(to_label)} instances from {dataset_name}")

            batch_size = self.config["pipeline"].get("batch_size", 50)
            total_batches = (len(to_label) + batch_size - 1) // batch_size
            dataset_start_time = time.time()

            for batch_start in range(0, len(to_label), batch_size):
                batch = to_label[batch_start:batch_start + batch_size]
                tasks = [self._label_and_save(inst, output_path) for inst in batch]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                success = sum(1 for r in results if r is True)
                failed = sum(1 for r in results if r is not True)
                total_labeled += success

                batch_num = batch_start // batch_size + 1
                done_in_dataset = batch_start + len(batch)
                pct = done_in_dataset / len(to_label) * 100
                elapsed = time.time() - start_time
                dataset_elapsed = time.time() - dataset_start_time

                speed = done_in_dataset / dataset_elapsed * 60 if dataset_elapsed > 0 else 0
                remaining = (len(to_label) - done_in_dataset) / (speed / 60) if speed > 0 else 0

                logger.info(
                    f"  [{dataset_name}] Batch {batch_num}/{total_batches} | "
                    f"{done_in_dataset}/{len(to_label)} ({pct:.1f}%) | "
                    f"{success} ok, {failed} fail | "
                    f"Speed: {speed:.1f}/min | ETA: {remaining:.0f}s | "
                    f"Total elapsed: {elapsed:.1f}s"
                )

        elapsed = time.time() - start_time
        logger.info("=" * 60)
        logger.info(f"Pipeline complete: {total_labeled} labeled, {total_skipped} skipped")
        logger.info(f"Total time: {elapsed:.1f}s")
        logger.info(f"LLM stats: {self.llm_client.stats}")
        logger.info("=" * 60)

        await self.close()

    async def _label_and_save(self, instance: UnifiedInstance, output_path: str) -> bool:
        try:
            label_result = await self.labeler.label_instance(instance)
            instance.labels = label_result
            append_jsonl(output_path, instance.to_dict())
            return True
        except Exception as e:
            logger.error(f"Error labeling {instance.instance_id}: {e}")
            return False

    async def close(self):
        await self.llm_client.close()
        await self.enricher.close()

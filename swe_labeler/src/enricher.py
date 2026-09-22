from __future__ import annotations
import asyncio
import json
import os
import logging
import base64
from typing import Optional

import ssl
import aiohttp

from .schema import UnifiedInstance

logger = logging.getLogger(__name__)


class GitHubEnricher:
    def __init__(self, tokens: list[str], max_concurrent: int = 5, cache_dir: str = "./cache/github", ssl_verify: bool = True):
        self.tokens = tokens
        self.max_concurrent = max_concurrent
        self.cache_dir = cache_dir
        self.ssl_verify = ssl_verify
        self._token_idx = 0
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._session: Optional[aiohttp.ClientSession] = None
        self._cache: dict[str, dict] = {}

        os.makedirs(cache_dir, exist_ok=True)

    def _get_token(self) -> str:
        if not self.tokens:
            return ""
        token = self.tokens[self._token_idx % len(self.tokens)]
        self._token_idx += 1
        return token

    def _cache_path(self, repo: str) -> str:
        safe_name = repo.replace("/", "__")
        return os.path.join(self.cache_dir, f"{safe_name}.json")

    def _load_cache(self, repo: str) -> Optional[dict]:
        if repo in self._cache:
            return self._cache[repo]
        path = self._cache_path(repo)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._cache[repo] = data
                return data
        return None

    def _save_cache(self, repo: str, data: dict):
        self._cache[repo] = data
        path = self._cache_path(repo)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            if not self.ssl_verify:
                connector = aiohttp.TCPConnector(ssl=False)
            else:
                connector = aiohttp.TCPConnector()
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                connector=connector,
            )
        return self._session

    async def _fetch_repo_info(self, repo: str) -> dict:
        cached = self._load_cache(repo)
        if cached:
            return cached

        if not self.tokens:
            logger.debug(f"No GitHub token, skipping enrichment for {repo}")
            return {}

        async with self._semaphore:
            session = await self._get_session()
            token = self._get_token()
            headers = {
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github.v3+json",
            }

            result = {}

            try:
                async with session.get(
                    f"https://api.github.com/repos/{repo}", headers=headers
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        result["description"] = data.get("description", "")
                        result["topics"] = data.get("topics", [])
                        result["language"] = data.get("language", "")
                        result["stars"] = data.get("stargazers_count", 0)
                    elif resp.status == 403:
                        remaining = resp.headers.get("X-RateLimit-Remaining", "0")
                        if remaining == "0":
                            reset_time = int(resp.headers.get("X-RateLimit-Reset", "0"))
                            logger.warning(f"Rate limited on {repo}, reset at {reset_time}")
                        return {}
                    else:
                        logger.debug(f"Failed to fetch repo info for {repo}: HTTP {resp.status}")
                        return {}
            except Exception as e:
                logger.warning(f"Error fetching repo info for {repo}: {e}")
                return {}

            try:
                async with session.get(
                    f"https://api.github.com/repos/{repo}/readme", headers=headers
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        content = data.get("content", "")
                        if content:
                            decoded = base64.b64decode(content).decode("utf-8", errors="replace")
                            result["readme"] = decoded[:2000]
                    else:
                        result["readme"] = ""
            except Exception:
                result["readme"] = ""

            self._save_cache(repo, result)
            return result

    async def enrich_instances(self, instances: list[UnifiedInstance]) -> list[UnifiedInstance]:
        unique_repos = list(set(inst.repo for inst in instances if inst.repo))
        logger.info(f"Enriching {len(unique_repos)} unique repos for {len(instances)} instances")

        repo_info_map: dict[str, dict] = {}

        tasks = [self._fetch_repo_info(repo) for repo in unique_repos]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for repo, result in zip(unique_repos, results):
            if isinstance(result, Exception):
                logger.warning(f"Exception enriching {repo}: {result}")
                repo_info_map[repo] = {}
            else:
                repo_info_map[repo] = result

        enriched_count = 0
        for inst in instances:
            info = repo_info_map.get(inst.repo, {})
            if info:
                inst.repo_description = info.get("description")
                inst.repo_topics = info.get("topics")
                inst.repo_primary_language = info.get("language")
                if not inst.language and info.get("language"):
                    inst.language = info["language"].lower()
                enriched_count += 1

        logger.info(f"Enriched {enriched_count}/{len(instances)} instances with repo metadata")
        return instances

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

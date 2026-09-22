from __future__ import annotations
import asyncio
import time
import json
import logging
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)


class TokenBucket:
    def __init__(self, rate: float, capacity: float):
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self):
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_refill
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            self.last_refill = now

            if self.tokens >= 1:
                self.tokens -= 1
                return
        while True:
            await asyncio.sleep(1.0 / self.rate)
            async with self._lock:
                now = time.monotonic()
                elapsed = now - self.last_refill
                self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
                self.last_refill = now
                if self.tokens >= 1:
                    self.tokens -= 1
                    return


class LLMClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        max_concurrent: int = 30,
        requests_per_minute: int = 100,
        timeout: int = 60,
        max_retries: int = 3,
        ssl_verify: bool = True,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.ssl_verify = ssl_verify

        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._rate_limiter = TokenBucket(
            rate=requests_per_minute / 60.0,
            capacity=min(max_concurrent, requests_per_minute // 2),
        )
        self._session: Optional[aiohttp.ClientSession] = None
        self._total_requests = 0
        self._total_tokens = 0

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            if not self.ssl_verify:
                connector = aiohttp.TCPConnector(ssl=False)
            else:
                connector = aiohttp.TCPConnector()
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout),
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                connector=connector,
            )
        return self._session

    async def chat_completion(
        self,
        messages: list[dict],
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> dict:
        t0 = time.monotonic()
        async with self._semaphore:
            t1 = time.monotonic()
            await self._rate_limiter.acquire()
            t2 = time.monotonic()
            result = await self._request_with_retry(messages, temperature, max_tokens)
            t3 = time.monotonic()

        wait_sem = t1 - t0
        wait_rate = t2 - t1
        api_time = t3 - t2
        total = t3 - t0

        usage = result.get("usage", {}) if "error" not in result else {}
        in_tok = usage.get("prompt_tokens", 0)
        out_tok = usage.get("completion_tokens", 0)

        logger.debug(
            f"LLM call: total={total:.1f}s (sem={wait_sem:.1f}s rate={wait_rate:.1f}s api={api_time:.1f}s) "
            f"tokens_in={in_tok} tokens_out={out_tok}"
        )

        if wait_sem > 2.0:
            logger.info(f"⚠ Semaphore wait: {wait_sem:.1f}s (concurrency bottleneck)")
        if wait_rate > 2.0:
            logger.info(f"⚠ Rate limiter wait: {wait_rate:.1f}s (rate limit bottleneck)")

        return result

    async def _request_with_retry(
        self, messages: list[dict], temperature: float, max_tokens: int
    ) -> dict:
        last_error = None
        for attempt in range(self.max_retries):
            try:
                session = await self._get_session()
                payload = {
                    "model": self.model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                }

                url = f"{self.base_url}/chat/completions"
                async with session.post(url, json=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        self._total_requests += 1
                        usage = data.get("usage", {})
                        self._total_tokens += usage.get("total_tokens", 0)
                        return data
                    elif resp.status == 429:
                        retry_after = int(resp.headers.get("Retry-After", 5))
                        logger.warning(f"Rate limited, waiting {retry_after}s (attempt {attempt+1})")
                        await asyncio.sleep(retry_after)
                    elif resp.status >= 500:
                        body = await resp.text()
                        logger.warning(f"Server error {resp.status}: {body[:200]} (attempt {attempt+1})")
                        await asyncio.sleep(2 ** attempt)
                    else:
                        body = await resp.text()
                        last_error = f"HTTP {resp.status}: {body[:500]}"
                        logger.error(f"Request failed: {last_error}")
                        break

            except asyncio.TimeoutError:
                last_error = "Timeout"
                logger.warning(f"Request timeout (attempt {attempt+1})")
                await asyncio.sleep(2 ** attempt)
            except aiohttp.ClientError as e:
                last_error = str(e)
                logger.warning(f"Client error: {e} (attempt {attempt+1})")
                await asyncio.sleep(2 ** attempt)

        return {"error": last_error or "max retries exceeded"}

    def extract_content(self, response: dict) -> str:
        if "error" in response:
            return ""
        try:
            return response["choices"][0]["message"]["content"]
        except (KeyError, IndexError):
            return ""

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    @property
    def stats(self) -> dict:
        return {
            "total_requests": self._total_requests,
            "total_tokens": self._total_tokens,
        }

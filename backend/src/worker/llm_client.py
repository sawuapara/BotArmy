"""Thin async HTTP wrapper over the Anthropic Messages API."""

import logging
from collections.abc import Awaitable, Callable

import httpx

logger = logging.getLogger("jarvis.worker.llm")


class LLMClient:
    """Async client for LLM chat completions (Anthropic-compatible endpoint)."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        default_model: str,
        credential_provider: Callable[[], Awaitable[str]] | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self._api_key = api_key
        self.default_model = default_model
        self._credential_provider = credential_provider
        self._client = httpx.AsyncClient(timeout=120.0)

    async def _get_api_key(self, force_refresh: bool = False) -> str:
        """Return cached API key, or fetch from provider if empty/forced."""
        if self._api_key and not force_refresh:
            return self._api_key

        if self._credential_provider:
            logger.info("Fetching API key from credential provider")
            self._api_key = await self._credential_provider()

        return self._api_key

    async def close(self):
        await self._client.aclose()

    async def chat(
        self,
        messages: list[dict],
        *,
        model: str | None = None,
        system: str | None = None,
        tools: list[dict] | None = None,
        max_tokens: int = 4096,
    ) -> dict:
        """Send a chat completion request and return parsed response.

        Returns dict with keys: stop_reason, content, usage
        On 401 with a credential provider, refreshes the key and retries once.
        """
        model = model or self.default_model

        body: dict = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        if system:
            body["system"] = system
        if tools:
            body["tools"] = tools

        for attempt in range(2):
            api_key = await self._get_api_key(force_refresh=(attempt > 0))

            headers = {
                "Content-Type": "application/json",
                "anthropic-version": "2023-06-01",
            }
            if api_key:
                headers["x-api-key"] = api_key

            resp = await self._client.post(
                f"{self.base_url}/v1/messages",
                json=body,
                headers=headers,
            )

            if resp.status_code == 401 and attempt == 0 and self._credential_provider:
                logger.warning("Got 401 from LLM API, refreshing credentials and retrying")
                continue

            resp.raise_for_status()
            data = resp.json()

            return {
                "stop_reason": data.get("stop_reason"),
                "content": data.get("content", []),
                "usage": data.get("usage", {}),
            }

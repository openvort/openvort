"""Aliyun DashScope Embedding Provider (text-embedding-v3)."""

import asyncio

from openvort.services.embedding.providers.base import EmbeddingProviderBase
from openvort.utils.logging import get_logger

log = get_logger("services.embedding.dashscope")

# DashScope batch limit
_BATCH_SIZE = 25


class DashScopeEmbeddingProvider(EmbeddingProviderBase):
    """Aliyun DashScope text-embedding-v3 via dashscope SDK."""

    platform = "dashscope"
    dimensions = 1024

    def __init__(self, api_key: str, config: dict | None = None):
        config = config or {}
        self.api_key = api_key
        self.model = config.get("model", "text-embedding-v3")
        self.dimensions = config.get("dimensions", 1024)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        all_embeddings: list[list[float]] = []
        for i in range(0, len(texts), _BATCH_SIZE):
            batch = texts[i : i + _BATCH_SIZE]
            embeddings = await self._embed_batch(batch)
            all_embeddings.extend(embeddings)

        return all_embeddings

    async def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        import dashscope

        dashscope.api_key = self.api_key

        def _call():
            resp = dashscope.TextEmbedding.call(
                model=self.model,
                input=texts,
                dimension=self.dimensions,
            )
            if resp.status_code != 200:
                raise RuntimeError(
                    f"DashScope embedding failed: {resp.code} {resp.message}"
                )
            return [item["embedding"] for item in resp.output["embeddings"]]

        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, _call)

        log.debug(f"Embedded {len(texts)} texts, dim={self.dimensions}")
        return result

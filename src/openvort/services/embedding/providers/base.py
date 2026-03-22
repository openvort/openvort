"""Embedding Provider abstract base class."""

from abc import ABC, abstractmethod


class EmbeddingProviderBase(ABC):
    """Embedding provider interface."""

    platform: str = ""
    dimensions: int = 1024

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Batch embed texts into vectors.

        Args:
            texts: List of text strings to embed.

        Returns:
            List of embedding vectors (each a list of floats).
        """
        ...

    async def close(self) -> None:
        """Release provider resources."""

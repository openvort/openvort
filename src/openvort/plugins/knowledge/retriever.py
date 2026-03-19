"""Vector retriever — pgvector similarity search for knowledge base."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from openvort.plugins.knowledge.models import KBChunk, KBDocument
from openvort.services.embedding import EmbeddingService
from openvort.utils.logging import get_logger

log = get_logger("plugins.knowledge.retriever")


@dataclass
class SearchResult:
    """A single search result with relevance score."""
    chunk_id: str
    document_id: str
    document_title: str
    chunk_index: int
    content: str
    score: float


class KBRetriever:
    """Knowledge base retriever using pgvector cosine similarity."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        embedding_service: EmbeddingService,
    ):
        self._session_factory = session_factory
        self._embedding_service = embedding_service

    async def search(self, query: str, top_k: int = 5) -> list[SearchResult]:
        """Search knowledge base for relevant chunks.

        Args:
            query: Natural language query.
            top_k: Number of top results to return.

        Returns:
            List of SearchResult sorted by relevance (highest first).
        """
        if not self._embedding_service.available:
            log.warning("Embedding service not available, cannot search")
            return []

        query_vectors = await self._embedding_service.embed([query])
        if not query_vectors:
            return []

        query_vector = query_vectors[0]

        async with self._session_factory() as session:
            # pgvector cosine distance: 1 - cosine_similarity
            # Lower distance = more similar, so we ORDER BY distance ASC
            stmt = text("""
                SELECT c.id, c.document_id, c.chunk_index, c.content,
                       c.embedding <=> :query_vec AS distance,
                       d.title AS document_title
                FROM kb_chunks c
                JOIN kb_documents d ON d.id = c.document_id
                WHERE d.status = 'ready'
                  AND c.embedding IS NOT NULL
                ORDER BY distance ASC
                LIMIT :top_k
            """)

            result = await session.execute(
                stmt,
                {"query_vec": str(query_vector), "top_k": top_k},
            )
            rows = result.fetchall()

        results = []
        for row in rows:
            score = 1.0 - float(row.distance) if row.distance is not None else 0.0
            results.append(SearchResult(
                chunk_id=row.id,
                document_id=row.document_id,
                document_title=row.document_title,
                chunk_index=row.chunk_index,
                content=row.content,
                score=round(score, 4),
            ))

        log.debug(f"Search '{query[:50]}...' returned {len(results)} results")
        return results

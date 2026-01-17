"""
Semantic Search for MemoryLane

Optional module that provides semantic similarity search using sentence-transformers.
Falls back gracefully if dependencies are not installed.

Install with: pip install sentence-transformers torch
"""

from typing import List, Dict, Tuple, Optional
from functools import lru_cache


class SemanticSearcher:
    """
    Semantic search using sentence embeddings.
    Uses all-MiniLM-L6-v2 model (~80MB, runs on CPU).
    """

    def __init__(self, model_name: str = 'all-MiniLM-L6-v2', cache_size: int = 1000):
        """
        Initialize the semantic searcher.

        Args:
            model_name: Sentence transformer model to use
            cache_size: LRU cache size for embeddings
        """
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(model_name)
            self._embed = lru_cache(maxsize=cache_size)(self._embed_uncached)
            self.available = True
        except ImportError:
            self.model = None
            self.available = False
            raise ImportError(
                "Semantic search requires sentence-transformers. "
                "Install with: pip install sentence-transformers torch"
            )

    def _embed_uncached(self, text: str) -> Tuple[float, ...]:
        """Generate embedding for text (returns tuple for hashability)"""
        embedding = self.model.encode(text, convert_to_numpy=True)
        return tuple(embedding.tolist())

    def embed(self, text: str) -> List[float]:
        """Generate embedding for text with caching"""
        return list(self._embed(text))

    def similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """Calculate cosine similarity between two embeddings"""
        import math

        # Cosine similarity
        dot_product = sum(a * b for a, b in zip(embedding1, embedding2))
        norm1 = math.sqrt(sum(a * a for a in embedding1))
        norm2 = math.sqrt(sum(b * b for b in embedding2))

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)

    def search(
        self,
        query: str,
        memories: List[Dict],
        limit: int = 10,
        min_similarity: float = 0.3
    ) -> List[Tuple[Dict, float]]:
        """
        Search memories by semantic similarity to query.

        Args:
            query: Search query
            memories: List of memory dictionaries with 'content' field
            limit: Maximum results to return
            min_similarity: Minimum similarity threshold

        Returns:
            List of (memory, similarity_score) tuples, sorted by score descending
        """
        if not memories:
            return []

        query_embedding = self.embed(query)

        scored = []
        for memory in memories:
            content = memory.get('content', '')
            if not content:
                continue

            memory_embedding = self.embed(content)
            score = self.similarity(query_embedding, memory_embedding)

            if score >= min_similarity:
                scored.append((memory, score))

        # Sort by similarity score descending
        scored.sort(key=lambda x: x[1], reverse=True)

        return scored[:limit]


def is_available() -> bool:
    """Check if semantic search is available"""
    try:
        import sentence_transformers
        return True
    except ImportError:
        return False


# Convenience function for one-off searches
def semantic_search(
    query: str,
    memories: List[Dict],
    limit: int = 10
) -> List[Tuple[Dict, float]]:
    """
    Convenience function for semantic search.
    Raises ImportError if dependencies not installed.
    """
    searcher = SemanticSearcher()
    return searcher.search(query, memories, limit=limit)

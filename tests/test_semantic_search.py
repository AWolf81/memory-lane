"""
Tests for Semantic Search module.

Note: These tests mock the sentence-transformers dependency to run in CI.
For tests that actually use the model, mark with @pytest.mark.local_only.
"""

import sys
import math
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestSemanticSearcherInit:
    """Test SemanticSearcher initialization."""

    def test_raises_import_error_without_dependencies(self):
        """Should raise ImportError when sentence-transformers not available."""
        with patch.dict('sys.modules', {'sentence_transformers': None}):
            # Force reimport
            import importlib
            import semantic_search
            importlib.reload(semantic_search)

            with pytest.raises(ImportError) as excinfo:
                semantic_search.SemanticSearcher()

            assert "sentence-transformers" in str(excinfo.value)

    def test_initializes_with_mocked_model(self):
        """Should initialize when dependencies available."""
        mock_st = MagicMock()
        mock_model = MagicMock()
        mock_st.SentenceTransformer.return_value = mock_model

        with patch.dict('sys.modules', {'sentence_transformers': mock_st}):
            import importlib
            import semantic_search
            importlib.reload(semantic_search)

            searcher = semantic_search.SemanticSearcher()

            assert searcher.available is True
            assert searcher.model == mock_model


class TestSimilarityCalculation:
    """Test cosine similarity calculation."""

    @pytest.fixture
    def searcher(self):
        """Create searcher with mocked dependencies."""
        mock_st = MagicMock()
        mock_model = MagicMock()
        mock_st.SentenceTransformer.return_value = mock_model

        with patch.dict('sys.modules', {'sentence_transformers': mock_st}):
            import importlib
            import semantic_search
            importlib.reload(semantic_search)

            searcher = semantic_search.SemanticSearcher()
            yield searcher

    def test_identical_vectors_similarity_one(self, searcher):
        """Identical vectors should have similarity 1.0."""
        vec = [1.0, 2.0, 3.0]

        result = searcher.similarity(vec, vec)

        assert abs(result - 1.0) < 0.0001

    def test_orthogonal_vectors_similarity_zero(self, searcher):
        """Orthogonal vectors should have similarity 0.0."""
        vec1 = [1.0, 0.0]
        vec2 = [0.0, 1.0]

        result = searcher.similarity(vec1, vec2)

        assert abs(result) < 0.0001

    def test_opposite_vectors_similarity_negative(self, searcher):
        """Opposite vectors should have negative similarity."""
        vec1 = [1.0, 1.0]
        vec2 = [-1.0, -1.0]

        result = searcher.similarity(vec1, vec2)

        assert result < 0

    def test_zero_vector_returns_zero(self, searcher):
        """Zero vectors should return 0 similarity."""
        vec1 = [0.0, 0.0, 0.0]
        vec2 = [1.0, 2.0, 3.0]

        result = searcher.similarity(vec1, vec2)

        assert result == 0.0


class TestEmbedding:
    """Test embedding generation."""

    @pytest.fixture
    def searcher(self):
        """Create searcher with mocked model."""
        mock_st = MagicMock()
        mock_model = MagicMock()
        # Return a numpy-like array
        mock_array = MagicMock()
        mock_array.tolist.return_value = [0.1, 0.2, 0.3]
        mock_model.encode.return_value = mock_array
        mock_st.SentenceTransformer.return_value = mock_model

        with patch.dict('sys.modules', {'sentence_transformers': mock_st}):
            import importlib
            import semantic_search
            importlib.reload(semantic_search)

            searcher = semantic_search.SemanticSearcher()
            yield searcher

    def test_embed_returns_list(self, searcher):
        """embed should return a list of floats."""
        result = searcher.embed("test text")

        assert isinstance(result, list)
        assert all(isinstance(x, float) for x in result)

    def test_embed_calls_model_encode(self, searcher):
        """embed should call model.encode."""
        searcher.embed("test text")

        searcher.model.encode.assert_called()


class TestSearch:
    """Test memory search functionality."""

    @pytest.fixture
    def searcher(self):
        """Create searcher with predictable embeddings."""
        mock_st = MagicMock()
        mock_model = MagicMock()

        # Return different embeddings based on input
        def mock_encode(text, **kwargs):
            mock_array = MagicMock()
            if 'query' in text.lower():
                mock_array.tolist.return_value = [1.0, 0.0, 0.0]
            elif 'relevant' in text.lower():
                mock_array.tolist.return_value = [0.9, 0.1, 0.0]  # Similar to query
            else:
                mock_array.tolist.return_value = [0.0, 1.0, 0.0]  # Orthogonal
            return mock_array

        mock_model.encode = mock_encode
        mock_st.SentenceTransformer.return_value = mock_model

        with patch.dict('sys.modules', {'sentence_transformers': mock_st}):
            import importlib
            import semantic_search
            importlib.reload(semantic_search)

            searcher = semantic_search.SemanticSearcher()
            yield searcher

    def test_search_empty_memories(self, searcher):
        """Should return empty list for empty memories."""
        result = searcher.search("query", [])

        assert result == []

    def test_search_filters_by_similarity(self, searcher):
        """Should filter results by minimum similarity."""
        memories = [
            {'content': 'relevant content'},
            {'content': 'unrelated stuff'}
        ]

        result = searcher.search("query", memories, min_similarity=0.5)

        # Only relevant should pass threshold
        assert len(result) == 1
        assert result[0][0]['content'] == 'relevant content'

    def test_search_respects_limit(self, searcher):
        """Should respect limit parameter."""
        memories = [
            {'content': f'relevant item {i}'} for i in range(10)
        ]

        result = searcher.search("query", memories, limit=3, min_similarity=0.0)

        assert len(result) <= 3

    def test_search_skips_empty_content(self, searcher):
        """Should skip memories with empty content."""
        memories = [
            {'content': ''},
            {'content': 'relevant content'}
        ]

        result = searcher.search("query", memories, min_similarity=0.0)

        assert all(m['content'] for m, _ in result)

    def test_search_returns_tuples_with_scores(self, searcher):
        """Should return (memory, score) tuples."""
        memories = [{'content': 'relevant content'}]

        result = searcher.search("query", memories, min_similarity=0.0)

        assert len(result) == 1
        memory, score = result[0]
        assert isinstance(memory, dict)
        assert isinstance(score, float)


class TestIsAvailable:
    """Test availability check."""

    def test_returns_true_when_installed(self):
        """Should return True when sentence-transformers installed."""
        mock_st = MagicMock()

        with patch.dict('sys.modules', {'sentence_transformers': mock_st}):
            import importlib
            import semantic_search
            importlib.reload(semantic_search)

            result = semantic_search.is_available()

            assert result is True

    def test_returns_false_when_not_installed(self):
        """Should return False when sentence-transformers not installed."""
        # Remove from modules
        import sys as sys_module
        original = sys_module.modules.get('sentence_transformers')

        try:
            if 'sentence_transformers' in sys_module.modules:
                del sys_module.modules['sentence_transformers']

            import importlib
            import semantic_search
            importlib.reload(semantic_search)

            # Mock the import to fail
            with patch('builtins.__import__', side_effect=ImportError):
                result = semantic_search.is_available()

            assert result is False
        finally:
            if original:
                sys_module.modules['sentence_transformers'] = original


class TestConvenienceFunction:
    """Test semantic_search convenience function."""

    def test_raises_import_error_without_dependencies(self):
        """Should raise ImportError when dependencies not available."""
        with patch.dict('sys.modules', {'sentence_transformers': None}):
            import importlib
            import semantic_search
            importlib.reload(semantic_search)

            with pytest.raises(ImportError):
                semantic_search.semantic_search("query", [])

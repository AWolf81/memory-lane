"""
Tests for Context Compression Engine.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from compressor import ContextCompressor, CompressedContext


class TestTokenEstimation:
    """Test token estimation."""

    def test_estimate_tokens_empty_string(self):
        """Empty string should have 0 tokens."""
        compressor = ContextCompressor()
        assert compressor.estimate_tokens("") == 0

    def test_estimate_tokens_single_word(self):
        """Single word should estimate correctly."""
        compressor = ContextCompressor()
        # 1 word * 1.3 = 1.3 -> 1
        assert compressor.estimate_tokens("hello") == 1

    def test_estimate_tokens_sentence(self):
        """Sentence should estimate based on word count."""
        compressor = ContextCompressor()
        text = "This is a test sentence with seven words"
        # 8 words * 1.3 = 10.4 -> 10
        tokens = compressor.estimate_tokens(text)
        assert tokens == 10


class TestCompression:
    """Test compression functionality."""

    @pytest.fixture
    def sample_context(self):
        """Sample context for testing."""
        return """# Project Overview

This is a sample project.

## Authentication

The project uses JWT tokens.
Users login with email.

## Database

We use PostgreSQL.
Connection string in .env file.

## Testing

We use pytest for testing.
"""

    def test_compression_under_target_returns_original(self):
        """Text under target tokens should not be compressed."""
        compressor = ContextCompressor(target_tokens=1000)
        text = "Short text"

        result = compressor.compress(text)

        assert result.compressed_text == text
        assert result.compression_ratio == 1.0

    def test_compression_over_target_reduces_tokens(self, sample_context):
        """Text over target should be compressed."""
        compressor = ContextCompressor(target_tokens=20)

        result = compressor.compress(sample_context)

        assert result.compressed_tokens <= result.original_tokens
        assert result.compression_ratio > 1.0

    def test_compression_returns_compressed_context_object(self, sample_context):
        """Compression should return CompressedContext dataclass."""
        compressor = ContextCompressor(target_tokens=50)

        result = compressor.compress(sample_context)

        assert isinstance(result, CompressedContext)
        assert result.original_text == sample_context
        assert isinstance(result.original_tokens, int)
        assert isinstance(result.compressed_tokens, int)
        assert isinstance(result.compression_ratio, float)

    def test_compression_tracks_sections(self, sample_context):
        """Compression should track kept and removed sections."""
        compressor = ContextCompressor(target_tokens=30)

        result = compressor.compress(sample_context)

        # Should have some sections kept and some removed
        assert isinstance(result.sections_kept, list)
        assert isinstance(result.sections_removed, list)


class TestSectionParsing:
    """Test markdown section parsing."""

    def test_parse_sections_empty_input(self):
        """Empty input should return no sections."""
        compressor = ContextCompressor()
        sections = compressor._parse_sections("")
        assert sections == []

    def test_parse_sections_single_header(self):
        """Single header should create one section."""
        compressor = ContextCompressor()
        text = "# Header\n\nSome content"

        sections = compressor._parse_sections(text)

        assert len(sections) == 1
        assert sections[0]['title'] == 'Header'
        assert sections[0]['level'] == 1

    def test_parse_sections_multiple_levels(self):
        """Should parse multiple heading levels."""
        compressor = ContextCompressor()
        text = """# Level 1

Content 1

## Level 2

Content 2

### Level 3

Content 3
"""

        sections = compressor._parse_sections(text)

        assert len(sections) == 3
        assert sections[0]['level'] == 1
        assert sections[1]['level'] == 2
        assert sections[2]['level'] == 3

    def test_parse_sections_calculates_tokens(self):
        """Each section should have token count."""
        compressor = ContextCompressor()
        text = "# Header\n\nThis is content with several words"

        sections = compressor._parse_sections(text)

        assert sections[0]['tokens'] > 0


class TestDeduplication:
    """Test section deduplication."""

    def test_deduplicate_removes_exact_duplicates(self):
        """Exact duplicate sections should be removed."""
        compressor = ContextCompressor()
        sections = [
            {'title': 'Section 1', 'content': ['Same content'], 'level': 1, 'tokens': 2},
            {'title': 'Section 2', 'content': ['Same content'], 'level': 1, 'tokens': 2}
        ]

        deduplicated = compressor._deduplicate_sections(sections)

        assert len(deduplicated) == 1

    def test_deduplicate_keeps_unique_sections(self):
        """Unique sections should be preserved."""
        compressor = ContextCompressor()
        sections = [
            {'title': 'Section 1', 'content': ['Unique content A'], 'level': 1, 'tokens': 3},
            {'title': 'Section 2', 'content': ['Different content B'], 'level': 1, 'tokens': 3}
        ]

        deduplicated = compressor._deduplicate_sections(sections)

        assert len(deduplicated) == 2


class TestRanking:
    """Test section ranking by importance."""

    def test_rank_sections_important_keywords_boost(self):
        """Sections with important keywords should rank higher."""
        compressor = ContextCompressor()
        sections = [
            {'title': 'Random', 'content': ['Some text'], 'level': 1, 'tokens': 10},
            {'title': 'Authentication', 'content': ['Auth text'], 'level': 1, 'tokens': 10},
            {'title': 'Error Handling', 'content': ['Error text'], 'level': 1, 'tokens': 10}
        ]

        ranked = compressor._rank_sections(sections, preserve=[])

        # Authentication and Error should rank higher due to keywords
        titles = [s['title'] for s in ranked]
        auth_idx = titles.index('Authentication')
        random_idx = titles.index('Random')
        assert auth_idx < random_idx

    def test_rank_sections_preserves_specified(self):
        """Sections in preserve list should rank highest."""
        compressor = ContextCompressor()
        sections = [
            {'title': 'Low Priority', 'content': ['text'], 'level': 1, 'tokens': 10},
            {'title': 'Preserve Me', 'content': ['text'], 'level': 1, 'tokens': 10}
        ]

        ranked = compressor._rank_sections(sections, preserve=['Preserve Me'])

        assert ranked[0]['title'] == 'Preserve Me'


class TestSectionSelection:
    """Test section selection within token budget."""

    def test_select_sections_respects_budget(self):
        """Should not exceed token budget."""
        compressor = ContextCompressor()
        sections = [
            {'title': 'A', 'content': ['text'], 'level': 1, 'tokens': 50, 'importance_score': 1.0},
            {'title': 'B', 'content': ['text'], 'level': 1, 'tokens': 50, 'importance_score': 0.9},
            {'title': 'C', 'content': ['text'], 'level': 1, 'tokens': 50, 'importance_score': 0.8}
        ]

        kept, removed = compressor._select_sections(sections, target_tokens=100)

        total_tokens = sum(s['tokens'] for s in kept)
        assert total_tokens <= 100

    def test_select_sections_prioritizes_high_importance(self):
        """Higher importance sections should be kept."""
        compressor = ContextCompressor()
        sections = [
            {'title': 'High', 'content': ['text'], 'level': 1, 'tokens': 40, 'importance_score': 1.0},
            {'title': 'Low', 'content': ['text'], 'level': 1, 'tokens': 40, 'importance_score': 0.3}
        ]

        kept, removed = compressor._select_sections(sections, target_tokens=50)

        kept_titles = [s['title'] for s in kept]
        assert 'High' in kept_titles


class TestReconstruction:
    """Test text reconstruction from sections."""

    def test_reconstruct_includes_headers(self):
        """Reconstructed text should include headers."""
        compressor = ContextCompressor()
        sections = [
            {'title': 'Test Section', 'content': ['Line 1', 'Line 2'], 'level': 2}
        ]

        result = compressor._reconstruct(sections)

        assert '## Test Section' in result

    def test_reconstruct_includes_content(self):
        """Reconstructed text should include content."""
        compressor = ContextCompressor()
        sections = [
            {'title': 'Section', 'content': ['Content line'], 'level': 1}
        ]

        result = compressor._reconstruct(sections)

        assert 'Content line' in result


class TestSummarization:
    """Test section summarization."""

    def test_summarize_truncates_long_sections(self):
        """Long sections should be truncated."""
        compressor = ContextCompressor()
        section = {
            'title': 'Long Section',
            'content': [f'Line {i}' for i in range(10)],
            'level': 1,
            'tokens': 50,
            'importance_score': 0.8
        }

        summarized = compressor._summarize_section(section)

        assert len(summarized['content']) < len(section['content'])
        assert summarized['tokens'] < section['tokens']

    def test_summarize_adds_truncation_indicator(self):
        """Summarized sections should indicate truncation."""
        compressor = ContextCompressor()
        section = {
            'title': 'Section',
            'content': [f'Line {i}' for i in range(10)],
            'level': 1,
            'tokens': 50,
            'importance_score': 0.8
        }

        summarized = compressor._summarize_section(section)

        # Should have "... more lines" indicator
        has_indicator = any('more lines' in line for line in summarized['content'])
        assert has_indicator


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_compress_no_headers(self):
        """Text without headers should still work."""
        compressor = ContextCompressor(target_tokens=10)
        text = "Just plain text without any markdown headers."

        result = compressor.compress(text)

        # Should return something reasonable
        assert result.original_text == text

    def test_compress_only_headers(self):
        """Text with only headers (no content) should work."""
        compressor = ContextCompressor(target_tokens=100)
        text = "# Header 1\n\n## Header 2\n\n### Header 3"

        result = compressor.compress(text)

        assert isinstance(result, CompressedContext)

    def test_compress_very_small_target(self):
        """Very small target should still produce output."""
        compressor = ContextCompressor(target_tokens=1)
        text = "# Header\n\nSome content here"

        result = compressor.compress(text)

        # Should produce some output even with tiny budget
        assert result is not None

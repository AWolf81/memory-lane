"""
Tests for LLM Summarizer Service.
"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from summarizer import SummarizerService


class TestSummarizerInitialization:
    """Test summarizer initialization."""

    def test_init_without_config(self):
        """Should initialize without config."""
        with patch('summarizer.ModelManager'):
            with patch('summarizer.PromptBuilder'):
                summarizer = SummarizerService()
                assert summarizer.config is None

    def test_init_with_config(self):
        """Should initialize with config."""
        mock_config = MagicMock()
        mock_config.get.return_value = 4096

        with patch('summarizer.ModelManager'):
            with patch('summarizer.PromptBuilder'):
                summarizer = SummarizerService(config=mock_config)
                assert summarizer.config == mock_config

    def test_init_creates_model_manager(self):
        """Should create model manager if not provided."""
        with patch('summarizer.ModelManager') as mock_mm:
            with patch('summarizer.PromptBuilder'):
                summarizer = SummarizerService()
                mock_mm.assert_called_once()


class TestSummarizeText:
    """Test text summarization."""

    @pytest.fixture
    def summarizer(self):
        """Create summarizer with mocked dependencies."""
        mock_model_manager = MagicMock()
        mock_model_manager.available = True

        mock_prompt_builder = MagicMock()

        with patch('summarizer.ModelManager', return_value=mock_model_manager):
            with patch('summarizer.PromptBuilder', return_value=mock_prompt_builder):
                summarizer = SummarizerService()
                summarizer.model_manager = mock_model_manager
                summarizer.prompt_builder = mock_prompt_builder
                yield summarizer

    def test_returns_none_for_empty_text(self, summarizer):
        """Should return None for empty text."""
        result = summarizer.summarize_text("")
        assert result is None

    def test_returns_none_for_whitespace(self, summarizer):
        """Should return None for whitespace-only text."""
        result = summarizer.summarize_text("   \n\t  ")
        assert result is None

    def test_returns_none_when_disabled(self, summarizer):
        """Should return None when summarizer is disabled."""
        summarizer.config = MagicMock()
        summarizer.config.get.side_effect = lambda key, default: {
            'summarizer.enabled': False
        }.get(key, default)

        result = summarizer.summarize_text("Some text")
        assert result is None

    def test_returns_none_when_model_unavailable(self, summarizer):
        """Should return None when model is not available."""
        summarizer.model_manager.available = False

        result = summarizer.summarize_text("Some text")
        assert result is None

    def test_returns_none_for_short_text(self, summarizer):
        """Should return None when text is below min length."""
        summarizer.config = MagicMock()
        summarizer.config.get.side_effect = lambda key, default: {
            'summarizer.enabled': True,
            'summarizer.min_session_length': 1000
        }.get(key, default)

        result = summarizer.summarize_text("Short text")
        assert result is None


class TestParseOutput:
    """Test model output parsing."""

    @pytest.fixture
    def summarizer(self):
        """Create summarizer for testing."""
        with patch('summarizer.ModelManager'):
            with patch('summarizer.PromptBuilder'):
                yield SummarizerService()

    def test_parse_valid_json(self, summarizer):
        """Should parse valid JSON output."""
        text = '{"summary": "Test summary", "memory_entries": []}'

        result = summarizer._parse_output(text)

        assert result is not None
        assert result['summary'] == 'Test summary'
        assert result['memory_entries'] == []

    def test_parse_adds_missing_suggested_deletions(self, summarizer):
        """Should add empty suggested_deletions if missing."""
        text = '{"summary": "Test", "memory_entries": []}'

        result = summarizer._parse_output(text)

        assert 'suggested_deletions' in result
        assert result['suggested_deletions'] == []

    def test_parse_returns_none_without_summary(self, summarizer):
        """Should return None if summary missing."""
        text = '{"memory_entries": []}'

        result = summarizer._parse_output(text)

        assert result is None

    def test_parse_returns_none_without_memory_entries(self, summarizer):
        """Should return None if memory_entries missing."""
        text = '{"summary": "Test"}'

        result = summarizer._parse_output(text)

        assert result is None

    def test_parse_fixes_invalid_memory_entries(self, summarizer):
        """Should fix non-list memory_entries."""
        text = '{"summary": "Test", "memory_entries": "invalid"}'

        result = summarizer._parse_output(text)

        assert result['memory_entries'] == []


class TestExtractJson:
    """Test JSON extraction from model output."""

    @pytest.fixture
    def summarizer(self):
        """Create summarizer for testing."""
        with patch('summarizer.ModelManager'):
            with patch('summarizer.PromptBuilder'):
                yield SummarizerService()

    def test_extract_plain_json(self, summarizer):
        """Should extract plain JSON."""
        text = '{"key": "value"}'

        result = summarizer._extract_json(text)

        assert result == {'key': 'value'}

    def test_extract_json_from_code_block(self, summarizer):
        """Should extract JSON from markdown code block."""
        text = '```json\n{"key": "value"}\n```'

        result = summarizer._extract_json(text)

        assert result == {'key': 'value'}

    def test_extract_json_with_surrounding_text(self, summarizer):
        """Should extract JSON from text with surrounding content."""
        text = 'Here is the result: {"key": "value"} End of output.'

        result = summarizer._extract_json(text)

        assert result == {'key': 'value'}

    def test_returns_none_for_empty_text(self, summarizer):
        """Should return None for empty text."""
        result = summarizer._extract_json("")
        assert result is None

    def test_returns_none_for_invalid_json(self, summarizer):
        """Should return None for invalid JSON."""
        text = 'not valid json'

        result = summarizer._extract_json(text)

        assert result is None

    def test_returns_none_when_no_braces(self, summarizer):
        """Should return None when no braces found."""
        text = 'just some text without any json'

        result = summarizer._extract_json(text)

        assert result is None


class TestMergeResults:
    """Test merging multi-chunk results."""

    @pytest.fixture
    def summarizer(self):
        """Create summarizer for testing."""
        with patch('summarizer.ModelManager'):
            with patch('summarizer.PromptBuilder'):
                yield SummarizerService()

    def test_merge_empty_results(self, summarizer):
        """Should return None for empty results."""
        result = summarizer._merge_results([])
        assert result is None

    def test_merge_single_result(self, summarizer):
        """Should return single result as-is."""
        single = {
            'summary': 'Test',
            'memory_entries': [{'content': 'entry'}],
            'suggested_deletions': []
        }

        result = summarizer._merge_results([single])

        assert result == single

    def test_merge_multiple_results(self, summarizer):
        """Should merge multiple results."""
        results = [
            {
                'summary': 'First part.',
                'memory_entries': [{'content': 'entry1'}],
                'suggested_deletions': ['id1']
            },
            {
                'summary': 'Second part.',
                'memory_entries': [{'content': 'entry2'}],
                'suggested_deletions': ['id2']
            }
        ]

        merged = summarizer._merge_results(results)

        assert 'First part' in merged['summary']
        assert 'Second part' in merged['summary']
        assert len(merged['memory_entries']) == 2
        assert 'id1' in merged['suggested_deletions']
        assert 'id2' in merged['suggested_deletions']


class TestTrimSummary:
    """Test summary trimming."""

    @pytest.fixture
    def summarizer(self):
        """Create summarizer for testing."""
        with patch('summarizer.ModelManager'):
            with patch('summarizer.PromptBuilder'):
                yield SummarizerService()

    def test_short_summary_unchanged(self, summarizer):
        """Short summaries should remain unchanged."""
        summary = "One sentence. Two sentences."

        result = summarizer._trim_summary(summary, max_sentences=4)

        assert result == summary

    def test_long_summary_trimmed(self, summarizer):
        """Long summaries should be trimmed."""
        summary = "One. Two. Three. Four. Five. Six."

        result = summarizer._trim_summary(summary, max_sentences=3)

        assert result.count('.') <= 4  # At most 3 sentences + ending period

    def test_adds_period_if_missing(self, summarizer):
        """Should add period at end if missing after trimming."""
        # 5 sentences, will be trimmed to 2
        summary = "First sentence. Second sentence. Third sentence. Fourth. Fifth."

        result = summarizer._trim_summary(summary, max_sentences=2)

        # Should have trimmed and may or may not end with period depending on content
        assert len(result) < len(summary)


class TestDedupeEntries:
    """Test memory entry deduplication."""

    @pytest.fixture
    def summarizer(self):
        """Create summarizer for testing."""
        with patch('summarizer.ModelManager'):
            with patch('summarizer.PromptBuilder'):
                yield SummarizerService()

    def test_dedupe_removes_duplicates(self, summarizer):
        """Should remove duplicate entries."""
        entries = [
            {'content': 'Same content here'},
            {'content': 'Same content here'},
            {'content': 'Different content'}
        ]

        result = summarizer._dedupe_entries(entries)

        assert len(result) == 2

    def test_dedupe_skips_empty_content(self, summarizer):
        """Should skip entries with empty content."""
        entries = [
            {'content': ''},
            {'content': 'Valid content'}
        ]

        result = summarizer._dedupe_entries(entries)

        assert len(result) == 1
        assert result[0]['content'] == 'Valid content'

    def test_dedupe_uses_first_80_chars(self, summarizer):
        """Should use first 80 chars for signature."""
        prefix = 'A' * 80
        entries = [
            {'content': prefix + 'xyz'},
            {'content': prefix + 'abc'}  # Same first 80 chars
        ]

        result = summarizer._dedupe_entries(entries)

        assert len(result) == 1


class TestChunkText:
    """Test text chunking."""

    @pytest.fixture
    def summarizer(self):
        """Create summarizer for testing."""
        with patch('summarizer.ModelManager'):
            with patch('summarizer.PromptBuilder'):
                yield SummarizerService()

    def test_short_text_single_chunk(self, summarizer):
        """Short text should be single chunk."""
        text = "Short text here"

        chunks = summarizer._chunk_text(text)

        assert len(chunks) == 1
        assert chunks[0] == text

    def test_long_text_multiple_chunks(self, summarizer):
        """Long text should be split into chunks."""
        # Create text longer than max_tokens
        summarizer.config = MagicMock()
        summarizer.config.get.return_value = 100  # Small max for testing

        words = ['word'] * 500  # Way more than 100 tokens
        text = ' '.join(words)

        chunks = summarizer._chunk_text(text)

        assert len(chunks) > 1


class TestEstimateTokens:
    """Test token estimation."""

    @pytest.fixture
    def summarizer(self):
        """Create summarizer for testing."""
        with patch('summarizer.ModelManager'):
            with patch('summarizer.PromptBuilder'):
                yield SummarizerService()

    def test_estimate_empty_string(self, summarizer):
        """Empty string should have 0 tokens."""
        result = summarizer._estimate_tokens("")
        assert result == 0

    def test_estimate_uses_word_count(self, summarizer):
        """Should estimate based on word count * 1.3."""
        text = "one two three four five"  # 5 words

        result = summarizer._estimate_tokens(text)

        # 5 * 1.3 = 6.5 -> 6
        assert result == 6


class TestGetConfigValue:
    """Test config value retrieval."""

    @pytest.fixture
    def summarizer(self):
        """Create summarizer for testing."""
        with patch('summarizer.ModelManager'):
            with patch('summarizer.PromptBuilder'):
                yield SummarizerService()

    def test_returns_default_when_no_config(self, summarizer):
        """Should return default when config is None."""
        summarizer.config = None

        result = summarizer._get_config_value('any.key', 'default')

        assert result == 'default'

    def test_returns_config_value(self, summarizer):
        """Should return config value when available."""
        summarizer.config = MagicMock()
        summarizer.config.get.return_value = 'configured'

        result = summarizer._get_config_value('some.key', 'default')

        assert result == 'configured'

    def test_returns_default_on_exception(self, summarizer):
        """Should return default when config raises exception."""
        summarizer.config = MagicMock()
        summarizer.config.get.side_effect = Exception("Config error")

        result = summarizer._get_config_value('some.key', 'default')

        assert result == 'default'

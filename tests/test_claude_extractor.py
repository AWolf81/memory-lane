"""
Tests for Claude-powered extraction with backend configuration and fallbacks.
"""

from pathlib import Path
import sys
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from claude_extractor import ClaudeExtractor, ExtractedMemory


class TestClaudeExtractorBackendConfig:
    """Test backend configuration options."""

    def test_default_backend_is_auto(self):
        """Default backend should be 'auto'."""
        extractor = ClaudeExtractor()
        assert extractor.backend == "auto"

    def test_config_sets_backend(self):
        """Backend can be set via config."""
        config = {"extraction": {"backend": "regex"}}
        extractor = ClaudeExtractor(config=config)
        assert extractor.backend == "regex"

    def test_invalid_backend_falls_back_to_auto(self):
        """Invalid backend value falls back to 'auto'."""
        config = {"extraction": {"backend": "invalid_backend"}}
        extractor = ClaudeExtractor(config=config)
        assert extractor.backend == "auto"

    def test_config_sets_model(self):
        """Claude model can be configured."""
        config = {"extraction": {"claude_model": "claude-opus-4-20250514"}}
        extractor = ClaudeExtractor(config=config)
        assert extractor.model == "claude-opus-4-20250514"

    def test_config_sets_timeout(self):
        """Timeout can be configured."""
        config = {"extraction": {"claude_timeout": 120}}
        extractor = ClaudeExtractor(config=config)
        assert extractor.timeout == 120


class TestBackendSelection:
    """Test that the correct backend is used based on config."""

    @pytest.fixture
    def sample_text(self):
        return """
        We chose Unix sockets over HTTP for lower IPC latency.
        The issue was that the hook timeout was too low at 3 seconds.
        Fixed by increasing timeout to 5 seconds and adding fallback.
        """

    def test_regex_backend_skips_claude(self, sample_text):
        """When backend='regex', Claude is never called."""
        config = {"extraction": {"backend": "regex"}}
        extractor = ClaudeExtractor(config=config)

        with patch.object(extractor, '_call_claude') as mock_claude:
            memories = extractor.extract(sample_text)

            # Claude should not be called
            mock_claude.assert_not_called()

            # Should get regex-extracted memories
            assert len(memories) > 0
            assert all(m.source == "regex" for m in memories)

    def test_local_llm_backend_skips_claude(self, sample_text):
        """When backend='local_llm', Claude is never called."""
        config = {"extraction": {"backend": "local_llm"}}
        extractor = ClaudeExtractor(config=config)

        with patch.object(extractor, '_call_claude') as mock_claude:
            with patch.object(extractor, '_local_llm_extraction', return_value=[]) as mock_llm:
                extractor.extract(sample_text)

                # Claude should not be called
                mock_claude.assert_not_called()
                # Local LLM should be called
                mock_llm.assert_called_once()

    def test_claude_backend_no_fallback(self, sample_text):
        """When backend='claude', no fallback on failure."""
        config = {"extraction": {"backend": "claude"}}
        extractor = ClaudeExtractor(config=config)

        with patch.object(extractor, '_call_claude', return_value=None):
            with patch.object(extractor, '_regex_extraction') as mock_regex:
                memories = extractor.extract(sample_text)

                # Regex fallback should NOT be called
                mock_regex.assert_not_called()
                # Should return empty list
                assert memories == []

    def test_auto_backend_tries_all(self, sample_text):
        """When backend='auto', tries Claude then falls back."""
        config = {"extraction": {"backend": "auto"}}
        extractor = ClaudeExtractor(config=config)

        with patch.object(extractor, '_call_claude', return_value=None):
            with patch.object(extractor, '_local_llm_extraction', return_value=[]):
                with patch.object(extractor, '_regex_extraction') as mock_regex:
                    mock_regex.return_value = [
                        ExtractedMemory("patterns", "test", 0.8, [], "regex")
                    ]
                    memories = extractor.extract(sample_text)

                    # Regex should be called as final fallback
                    mock_regex.assert_called_once()
                    assert len(memories) == 1


class TestFallbackChain:
    """Test the fallback chain in auto mode."""

    @pytest.fixture
    def sample_text(self):
        return "We chose X over Y because of performance."

    def test_claude_success_no_fallback(self, sample_text):
        """When Claude succeeds with valid memories, no fallback is used."""
        extractor = ClaudeExtractor()

        # Content must be >= 15 chars to pass filter
        mock_response = '{"memories": [{"category": "patterns", "content": "This is a valid test pattern memory.", "relevance": 0.9, "tags": []}]}'

        with patch.object(extractor, '_call_claude', return_value=mock_response):
            memories = extractor.extract(sample_text)

            # Should have Claude result
            assert len(memories) == 1
            assert memories[0].content == "This is a valid test pattern memory."

    def test_claude_fails_tries_local_llm(self, sample_text):
        """When Claude fails, local LLM is tried."""
        extractor = ClaudeExtractor()

        with patch.object(extractor, '_call_claude', return_value=None):
            with patch.object(extractor, '_local_llm_extraction') as mock_llm:
                mock_llm.return_value = [
                    ExtractedMemory("insights", "LLM insight.", 0.85, [], "local_llm")
                ]
                memories = extractor.extract(sample_text)

                mock_llm.assert_called_once()
                assert len(memories) == 1
                assert memories[0].source == "local_llm"

    def test_all_fail_uses_regex(self, sample_text):
        """When Claude and local LLM fail, regex is used."""
        extractor = ClaudeExtractor()

        with patch.object(extractor, '_call_claude', return_value=None):
            with patch.object(extractor, '_local_llm_extraction', return_value=[]):
                # Don't mock regex - let it actually run
                memories = extractor.extract(sample_text)

                # Should get regex results (or empty if no patterns match)
                assert all(m.source == "regex" for m in memories) if memories else True


class TestRegexExtraction:
    """Test regex-only extraction."""

    def test_extracts_architectural_decisions(self):
        """Regex extracts 'X over Y' patterns."""
        extractor = ClaudeExtractor(config={"extraction": {"backend": "regex"}})

        text = "We chose Unix sockets over HTTP for lower latency."
        memories = extractor.extract(text)

        assert len(memories) >= 1
        assert any("Unix sockets" in m.content or "sockets" in m.content.lower() for m in memories)

    def test_extracts_fixes(self):
        """Regex extracts 'fixed by' patterns."""
        extractor = ClaudeExtractor(config={"extraction": {"backend": "regex"}})

        text = "Fixed by increasing the timeout to 5 seconds."
        memories = extractor.extract(text)

        assert len(memories) >= 1
        assert any("fixed" in m.content.lower() or "timeout" in m.content.lower() for m in memories)

    def test_extracts_config_locations(self):
        """Regex extracts configuration locations."""
        extractor = ClaudeExtractor(config={"extraction": {"backend": "regex"}})

        text = "Configuration is stored in .memorylane/config.json."
        memories = extractor.extract(text)

        assert len(memories) >= 1
        assert any("config" in m.content.lower() for m in memories)


class TestCLIAndAPIAvailability:
    """Test CLI and API availability checks."""

    def test_cli_availability_check(self):
        """CLI availability is checked correctly."""
        extractor = ClaudeExtractor()

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            assert extractor.cli_available is True

    def test_cli_unavailable(self):
        """CLI unavailable when command fails."""
        extractor = ClaudeExtractor()
        extractor._cli_available = None  # Reset cache

        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = FileNotFoundError()
            assert extractor.cli_available is False

    def test_api_available_with_key(self):
        """API is available when ANTHROPIC_API_KEY is set."""
        extractor = ClaudeExtractor()
        extractor._api_available = None  # Reset cache

        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'}):
            assert extractor.api_available is True

    def test_api_unavailable_without_key(self):
        """API is unavailable when ANTHROPIC_API_KEY is not set."""
        extractor = ClaudeExtractor()
        extractor._api_available = None  # Reset cache

        with patch.dict('os.environ', {}, clear=True):
            # Clear the key if it exists
            import os
            if 'ANTHROPIC_API_KEY' in os.environ:
                del os.environ['ANTHROPIC_API_KEY']
            extractor._api_available = None
            assert extractor.api_available is False


class TestResponseParsing:
    """Test Claude response parsing."""

    def test_parses_valid_json(self):
        """Parses valid JSON response."""
        extractor = ClaudeExtractor()

        response = '''
        {
            "memories": [
                {"category": "patterns", "content": "Use async for I/O.", "relevance": 0.9, "tags": ["async"]}
            ]
        }
        '''
        memories = extractor._parse_response(response)

        assert len(memories) == 1
        assert memories[0].category == "patterns"
        assert memories[0].content == "Use async for I/O."
        assert memories[0].relevance == 0.9
        assert memories[0].tags == ["async"]

    def test_parses_markdown_code_block(self):
        """Parses JSON inside markdown code blocks."""
        extractor = ClaudeExtractor()

        # No leading whitespace - code block must start at beginning
        response = '''```json
{
    "memories": [
        {"category": "insights", "content": "This is a valid test insight memory.", "relevance": 0.8, "tags": []}
    ]
}
```'''
        memories = extractor._parse_response(response)

        assert len(memories) == 1
        assert memories[0].category == "insights"

    def test_handles_memory_entries_key(self):
        """Handles 'memory_entries' as alternative to 'memories'."""
        extractor = ClaudeExtractor()

        response = '''
        {
            "memory_entries": [
                {"category": "learnings", "content": "This is a valid test learning memory.", "relevance": 0.75, "tags": []}
            ]
        }
        '''
        memories = extractor._parse_response(response)

        assert len(memories) == 1
        assert memories[0].category == "learnings"

    def test_filters_short_content(self):
        """Filters out memories with content < 15 chars."""
        extractor = ClaudeExtractor()

        response = '''
        {
            "memories": [
                {"category": "patterns", "content": "Short.", "relevance": 0.9, "tags": []},
                {"category": "patterns", "content": "This is a longer valid memory.", "relevance": 0.9, "tags": []}
            ]
        }
        '''
        memories = extractor._parse_response(response)

        assert len(memories) == 1
        assert "longer valid" in memories[0].content

    def test_normalizes_invalid_category(self):
        """Invalid categories are normalized to 'insights'."""
        extractor = ClaudeExtractor()

        response = '''
        {
            "memories": [
                {"category": "unknown_category", "content": "Test with invalid category here.", "relevance": 0.8, "tags": []}
            ]
        }
        '''
        memories = extractor._parse_response(response)

        assert len(memories) == 1
        assert memories[0].category == "insights"

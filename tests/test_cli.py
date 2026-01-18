"""
Tests for MemoryLane CLI.
"""

import json
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cli import MemoryLaneCLI


class TestCLIInitialization:
    """Test CLI initialization."""

    def test_cli_creates_store_and_config(self, tmp_path):
        """CLI should initialize store and config."""
        with patch('cli.ConfigManager') as mock_config:
            mock_config.return_value.get_path.return_value = tmp_path / "memories.json"
            with patch('cli.MemoryStore'):
                with patch('cli.ProjectRegistry'):
                    with patch('cli.ensure_registered'):
                        cli = MemoryLaneCLI(auto_register=False)
                        assert cli.config is not None
                        assert cli.store is not None


class TestStatusCommand:
    """Test the status command."""

    @pytest.fixture
    def cli_with_mocks(self, tmp_path):
        """Create CLI with mocked dependencies."""
        with patch('cli.ConfigManager') as mock_config:
            mock_config.return_value.get_path.side_effect = lambda key: {
                'memories_file': tmp_path / "memories.json",
                'metrics_file': tmp_path / "metrics.json"
            }.get(key, tmp_path / key)

            with patch('cli.MemoryStore') as mock_store:
                mock_store.return_value.get_stats.return_value = {
                    'total_memories': 10,
                    'total_retrievals': 5,
                    'categories': {
                        'patterns': {'count': 3, 'avg_relevance': 0.8},
                        'insights': {'count': 4, 'avg_relevance': 0.9},
                        'learnings': {'count': 3, 'avg_relevance': 0.7}
                    }
                }

                with patch('cli.ProjectRegistry'):
                    with patch('cli.ensure_registered'):
                        cli = MemoryLaneCLI(auto_register=False)
                        yield cli, tmp_path

    def test_status_shows_memory_count(self, cli_with_mocks, capsys):
        """Status should show total memory count."""
        cli, tmp_path = cli_with_mocks

        args = MagicMock()
        cli.cmd_status(args)

        captured = capsys.readouterr()
        assert "Total Memories: 10" in captured.out
        assert "Total Retrievals: 5" in captured.out

    def test_status_shows_categories(self, cli_with_mocks, capsys):
        """Status should show category breakdown."""
        cli, tmp_path = cli_with_mocks

        args = MagicMock()
        cli.cmd_status(args)

        captured = capsys.readouterr()
        assert "patterns" in captured.out
        assert "insights" in captured.out

    def test_status_shows_cost_savings_when_available(self, cli_with_mocks, capsys):
        """Status should show cost savings when metrics file exists."""
        cli, tmp_path = cli_with_mocks

        # Create metrics file
        metrics_file = tmp_path / "metrics.json"
        metrics_file.write_text(json.dumps({
            'cost_savings': {'week': 10.50, 'month': 42.00, 'total': 100.00},
            'compression': {'avg_ratio': 6.4, 'avg_before': 2000, 'avg_after': 312}
        }))

        args = MagicMock()
        cli.cmd_status(args)

        captured = capsys.readouterr()
        assert "Cost Savings" in captured.out


class TestRecallCommand:
    """Test the recall command."""

    @pytest.fixture
    def cli_with_memories(self, tmp_path):
        """Create CLI with sample memories."""
        with patch('cli.ConfigManager') as mock_config:
            mock_config.return_value.get_path.return_value = tmp_path / "memories.json"

            with patch('cli.MemoryStore') as mock_store:
                mock_store.return_value.get_memories.return_value = [
                    {
                        'id': 'patt-001',
                        'category': 'patterns',
                        'content': 'Use Unix sockets for IPC',
                        'relevance_score': 0.9,
                        'source': 'manual',
                        'usage_count': 3
                    },
                    {
                        'id': 'patt-002',
                        'category': 'patterns',
                        'content': 'Use async/await for IO operations',
                        'relevance_score': 0.8,
                        'source': 'git',
                        'usage_count': 1
                    }
                ]

                with patch('cli.ProjectRegistry'):
                    with patch('cli.ensure_registered'):
                        cli = MemoryLaneCLI(auto_register=False)
                        yield cli

    def test_recall_finds_matching_memories(self, cli_with_memories, capsys):
        """Recall should find memories matching query."""
        args = MagicMock()
        args.query = "Unix"
        args.show_ids = False
        args.show_stars = False

        cli_with_memories.cmd_recall(args)

        captured = capsys.readouterr()
        assert "Unix sockets" in captured.out

    def test_recall_shows_no_results_message(self, tmp_path, capsys):
        """Recall should show message when no matches found."""
        with patch('cli.ConfigManager') as mock_config:
            mock_config.return_value.get_path.return_value = tmp_path / "memories.json"

            with patch('cli.MemoryStore') as mock_store:
                mock_store.return_value.get_memories.return_value = []

                with patch('cli.ProjectRegistry'):
                    with patch('cli.ensure_registered'):
                        cli = MemoryLaneCLI(auto_register=False)

                        args = MagicMock()
                        args.query = "nonexistent"
                        args.show_ids = False
                        args.show_stars = False

                        cli.cmd_recall(args)

                        captured = capsys.readouterr()
                        assert "No memories found" in captured.out


class TestConfigCommand:
    """Test the config command."""

    @pytest.fixture
    def cli_instance(self, tmp_path):
        """Create CLI instance for testing."""
        with patch('cli.ConfigManager') as mock_config:
            mock_config.return_value.get_path.return_value = tmp_path / "memories.json"
            mock_config.return_value.get.return_value = "test_value"
            mock_config.return_value.config = {"memory": {"max_tokens": 2000}}

            with patch('cli.MemoryStore'):
                with patch('cli.ProjectRegistry'):
                    with patch('cli.ensure_registered'):
                        cli = MemoryLaneCLI(auto_register=False)
                        yield cli

    def test_config_get(self, cli_instance, capsys):
        """Config get should display config value."""
        args = MagicMock()
        args.action = 'get'
        args.key = 'memory.max_tokens'

        cli_instance.cmd_config(args)

        captured = capsys.readouterr()
        assert "memory.max_tokens" in captured.out

    def test_config_list(self, cli_instance, capsys):
        """Config list should display all config."""
        args = MagicMock()
        args.action = 'list'

        cli_instance.cmd_config(args)

        captured = capsys.readouterr()
        assert "Current Configuration" in captured.out

    def test_config_set(self, cli_instance, capsys):
        """Config set should update config value."""
        args = MagicMock()
        args.action = 'set'
        args.key = 'memory.max_tokens'
        args.value = '3000'

        cli_instance.cmd_config(args)

        captured = capsys.readouterr()
        assert "Set memory.max_tokens" in captured.out


class TestBackupRestore:
    """Test backup and restore commands."""

    @pytest.fixture
    def cli_instance(self, tmp_path):
        """Create CLI instance for testing."""
        with patch('cli.ConfigManager') as mock_config:
            mock_config.return_value.get_path.return_value = tmp_path / "memories.json"

            with patch('cli.MemoryStore') as mock_store:
                mock_store.return_value.export_backup.return_value = tmp_path / "backup.json"

                with patch('cli.ProjectRegistry'):
                    with patch('cli.ensure_registered'):
                        cli = MemoryLaneCLI(auto_register=False)
                        yield cli, tmp_path

    def test_backup_creates_file(self, cli_instance, capsys):
        """Backup command should create backup file."""
        cli, tmp_path = cli_instance

        args = MagicMock()
        args.output = None

        cli.cmd_backup(args)

        captured = capsys.readouterr()
        assert "Backup created" in captured.out

    def test_restore_requires_existing_file(self, cli_instance):
        """Restore should fail if backup file doesn't exist."""
        cli, tmp_path = cli_instance

        args = MagicMock()
        args.backup_file = str(tmp_path / "nonexistent.json")

        with pytest.raises(SystemExit):
            cli.cmd_restore(args)


class TestLearnCommand:
    """Test the learn command."""

    @pytest.fixture
    def cli_instance(self, tmp_path):
        """Create CLI instance for testing."""
        with patch('cli.ConfigManager') as mock_config:
            mock_config.return_value.get_path.return_value = tmp_path / "memories.json"

            with patch('cli.MemoryStore') as mock_store:
                mock_store.return_value.get_memories.return_value = []
                mock_store.return_value.add_memory.return_value = "test-id"

                with patch('cli.ProjectRegistry'):
                    with patch('cli.ensure_registered'):
                        cli = MemoryLaneCLI(auto_register=False)
                        yield cli

    def test_learn_from_text(self, cli_instance, capsys):
        """Learn should extract memories from text."""
        with patch('cli.ConversationLearner') as mock_learner:
            from dataclasses import dataclass

            @dataclass
            class MockMemory:
                category: str = 'patterns'
                content: str = 'Test pattern'
                source: str = 'manual'
                relevance_score: float = 0.8
                metadata: dict = None

            mock_learner.return_value.extract_from_text.return_value = [MockMemory()]

            args = MagicMock()
            args.text = "We use Unix sockets for lower latency"
            args.transcript = None
            args.quiet = False

            cli_instance.cmd_learn(args)

            captured = capsys.readouterr()
            assert "Learned" in captured.out or "patterns" in captured.out

    def test_learn_no_input_shows_error(self, cli_instance, capsys):
        """Learn with no input should show error message."""
        args = MagicMock()
        args.text = None
        args.transcript = None

        # Mock stdin to have no data
        with patch('select.select', return_value=([], [], [])):
            cli_instance.cmd_learn(args)

        captured = capsys.readouterr()
        assert "No input provided" in captured.out


class TestMemoryCommand:
    """Test individual memory operations."""

    @pytest.fixture
    def cli_instance(self, tmp_path):
        """Create CLI instance for testing."""
        with patch('cli.ConfigManager') as mock_config:
            mock_config.return_value.get_path.return_value = tmp_path / "memories.json"

            with patch('cli.MemoryStore') as mock_store:
                mock_store.return_value.get_memory_by_id.return_value = {
                    'id': 'patt-001',
                    'category': 'patterns',
                    'content': 'Test content'
                }
                mock_store.return_value.delete_memory.return_value = True
                mock_store.return_value.update_memory.return_value = True

                with patch('cli.ProjectRegistry'):
                    with patch('cli.ensure_registered'):
                        cli = MemoryLaneCLI(auto_register=False)
                        yield cli

    def test_memory_get(self, cli_instance, capsys):
        """Memory get should display memory details."""
        args = MagicMock()
        args.action = 'get'
        args.id = 'patt-001'

        cli_instance.cmd_memory(args)

        captured = capsys.readouterr()
        assert "patt-001" in captured.out

    def test_memory_delete(self, cli_instance, capsys):
        """Memory delete should remove memory."""
        args = MagicMock()
        args.action = 'delete'
        args.id = 'patt-001'

        cli_instance.cmd_memory(args)

        captured = capsys.readouterr()
        assert "Deleted" in captured.out

    def test_memory_update(self, cli_instance, capsys):
        """Memory update should modify content."""
        args = MagicMock()
        args.action = 'update'
        args.id = 'patt-001'
        args.content = 'Updated content'

        cli_instance.cmd_memory(args)

        captured = capsys.readouterr()
        assert "Updated" in captured.out

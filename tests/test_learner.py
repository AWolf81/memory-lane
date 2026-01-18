"""
Tests for Passive Learning Layer.
"""

import sys
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from learner import (
    GitParser, FileWatcher, PassiveLearner,
    FileChange, GitCommit
)


class TestGitParser:
    """Test Git history parsing."""

    def test_is_git_repo_true(self, tmp_path):
        """Should detect git repository."""
        (tmp_path / ".git").mkdir()
        parser = GitParser(str(tmp_path))

        assert parser.is_git_repo() is True

    def test_is_git_repo_false(self, tmp_path):
        """Should detect non-git directory."""
        parser = GitParser(str(tmp_path))

        assert parser.is_git_repo() is False

    def test_get_recent_commits_not_git_repo(self, tmp_path):
        """Should return empty list for non-git repo."""
        parser = GitParser(str(tmp_path))

        commits = parser.get_recent_commits()

        assert commits == []

    def test_get_recent_commits_handles_error(self, tmp_path):
        """Should handle git command errors gracefully."""
        (tmp_path / ".git").mkdir()
        parser = GitParser(str(tmp_path))

        with patch('subprocess.run', side_effect=Exception("git error")):
            commits = parser.get_recent_commits()

        assert commits == []

    def test_parse_git_log_empty(self):
        """Should handle empty log output."""
        parser = GitParser()

        commits = parser._parse_git_log("")

        assert commits == []

    def test_parse_git_log_single_commit(self):
        """Should parse single commit."""
        parser = GitParser()
        log_output = "abc123|John Doe|1609459200|Initial commit\n1\t0\tfile.py"

        commits = parser._parse_git_log(log_output)

        assert len(commits) == 1
        assert commits[0].hash == "abc123"
        assert commits[0].author == "John Doe"
        assert commits[0].message == "Initial commit"
        assert commits[0].additions == 1
        assert commits[0].deletions == 0
        assert "file.py" in commits[0].files_changed

    def test_parse_git_log_multiple_commits(self):
        """Should parse multiple commits."""
        parser = GitParser()
        log_output = """abc123|John|1609459200|First commit
1\t0\tfile1.py

def456|Jane|1609545600|Second commit
2\t1\tfile2.py"""

        commits = parser._parse_git_log(log_output)

        assert len(commits) == 2


class TestExtractPatterns:
    """Test pattern extraction from commits."""

    def test_extract_patterns_empty_commits(self):
        """Should return empty list for no commits."""
        parser = GitParser()

        patterns = parser.extract_patterns([])

        assert patterns == []

    def test_extract_patterns_detects_frameworks(self):
        """Should detect framework mentions in commits."""
        parser = GitParser()
        commits = [
            GitCommit(
                hash="abc",
                author="dev",
                timestamp=datetime.now(),
                message="Add react component",
                files_changed=["App.jsx"],
                additions=10,
                deletions=0
            )
        ]

        patterns = parser.extract_patterns(commits)

        assert any("react" in p.lower() for p in patterns)

    def test_extract_patterns_detects_bug_fixes(self):
        """Should detect bug fixes."""
        parser = GitParser()
        commits = [
            GitCommit(
                hash="abc",
                author="dev",
                timestamp=datetime.now(),
                message="fix: resolve login bug",
                files_changed=["auth.py"],
                additions=5,
                deletions=3
            )
        ]

        patterns = parser.extract_patterns(commits)

        assert any("fix" in p.lower() or "bug" in p.lower() for p in patterns)

    def test_extract_patterns_detects_file_types(self):
        """Should detect primary file extensions."""
        parser = GitParser()
        commits = [
            GitCommit(
                hash="abc",
                author="dev",
                timestamp=datetime.now(),
                message="Update code",
                files_changed=["app.py", "utils.py", "main.py"],
                additions=50,
                deletions=10
            )
        ]

        patterns = parser.extract_patterns(commits)

        assert any(".py" in p for p in patterns)


class TestFileWatcher:
    """Test file watching functionality."""

    @pytest.fixture
    def watcher(self, tmp_path):
        """Create file watcher for testing."""
        mock_config = MagicMock()
        mock_config.is_file_excluded.return_value = False

        with patch('learner.Path') as mock_path:
            mock_path.cwd.return_value = tmp_path
            watcher = FileWatcher(mock_config)
            watcher.workspace_root = tmp_path
            yield watcher

    def test_scan_workspace_finds_files(self, watcher, tmp_path):
        """Should find code files in workspace."""
        # Create test files
        (tmp_path / "app.py").write_text("print('hello')")
        (tmp_path / "utils.js").write_text("console.log('hi')")

        files = watcher.scan_workspace(extensions=['.py', '.js'])

        assert len(files) == 2

    def test_scan_workspace_respects_exclusions(self, tmp_path):
        """Should exclude files based on config."""
        mock_config = MagicMock()
        mock_config.is_file_excluded.side_effect = lambda p: 'excluded' in p

        watcher = FileWatcher(mock_config)
        watcher.workspace_root = tmp_path

        # Create files
        (tmp_path / "app.py").write_text("code")
        (tmp_path / "excluded.py").write_text("excluded code")

        files = watcher.scan_workspace(extensions=['.py'])

        file_names = [f.name for f in files]
        assert "app.py" in file_names
        assert "excluded.py" not in file_names

    def test_get_changed_files_detects_new(self, watcher, tmp_path):
        """Should detect new files."""
        # First scan - no files
        watcher.get_changed_files()

        # Create new file
        (tmp_path / "new_file.py").write_text("new code")

        changes = watcher.get_changed_files()

        created = [c for c in changes if c.change_type == 'created']
        assert len(created) == 1
        assert "new_file.py" in created[0].path

    def test_get_changed_files_detects_modified(self, watcher, tmp_path):
        """Should detect modified files."""
        # Create file
        test_file = tmp_path / "test.py"
        test_file.write_text("original")

        # First scan
        watcher.get_changed_files()

        # Modify file (need to change mtime)
        import time
        time.sleep(0.1)
        test_file.write_text("modified")

        changes = watcher.get_changed_files()

        modified = [c for c in changes if c.change_type == 'modified']
        assert len(modified) == 1

    def test_get_changed_files_detects_deleted(self, watcher, tmp_path):
        """Should detect deleted files."""
        # Create and scan file
        test_file = tmp_path / "delete_me.py"
        test_file.write_text("to delete")
        watcher.get_changed_files()

        # Delete file
        test_file.unlink()

        changes = watcher.get_changed_files()

        deleted = [c for c in changes if c.change_type == 'deleted']
        assert len(deleted) == 1


class TestPassiveLearner:
    """Test passive learning orchestration."""

    @pytest.fixture
    def learner(self, tmp_path):
        """Create passive learner for testing."""
        mock_config = MagicMock()
        mock_config.get.return_value = True
        mock_config.is_file_excluded.return_value = False

        mock_store = MagicMock()
        mock_store.add_memory.return_value = "test-id"

        learner = PassiveLearner(mock_config, mock_store)
        learner.file_watcher.workspace_root = tmp_path
        yield learner

    def test_initial_learning_from_git(self, learner, capsys):
        """Initial learning should analyze git history."""
        # Mock git parser to return commits
        learner.git_parser.get_recent_commits = MagicMock(return_value=[
            GitCommit(
                hash="abc",
                author="dev",
                timestamp=datetime.now(),
                message="Add feature",
                files_changed=["app.py"],
                additions=10,
                deletions=0
            )
        ])

        learner.initial_learning()

        captured = capsys.readouterr()
        assert "Initial learning" in captured.out

    def test_initial_learning_indexes_workspace(self, learner, tmp_path, capsys):
        """Initial learning should index workspace files."""
        # Create some files
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.py").write_text("code")

        learner.git_parser.get_recent_commits = MagicMock(return_value=[])

        learner.initial_learning()

        captured = capsys.readouterr()
        assert "Initial learning" in captured.out

    def test_initial_learning_skips_git_if_disabled(self, learner):
        """Should skip git learning if disabled in config."""
        learner.config.get.side_effect = lambda key, default=None: {
            'learning.watch_git_commits': False,
            'learning.index_on_startup': False
        }.get(key, default)

        learner.git_parser.get_recent_commits = MagicMock()

        learner.initial_learning()

        # Git should not be called
        learner.git_parser.get_recent_commits.assert_not_called()


class TestFileChangeDataclass:
    """Test FileChange dataclass."""

    def test_file_change_creation(self):
        """Should create FileChange with all fields."""
        change = FileChange(
            path="/path/to/file.py",
            change_type="modified",
            timestamp=datetime.now(),
            content_preview="preview"
        )

        assert change.path == "/path/to/file.py"
        assert change.change_type == "modified"
        assert change.content_preview == "preview"

    def test_file_change_optional_preview(self):
        """Content preview should be optional."""
        change = FileChange(
            path="/path/to/file.py",
            change_type="created",
            timestamp=datetime.now()
        )

        assert change.content_preview is None


class TestGitCommitDataclass:
    """Test GitCommit dataclass."""

    def test_git_commit_creation(self):
        """Should create GitCommit with all fields."""
        commit = GitCommit(
            hash="abc123",
            author="John Doe",
            timestamp=datetime.now(),
            message="Test commit",
            files_changed=["file1.py", "file2.py"],
            additions=10,
            deletions=5
        )

        assert commit.hash == "abc123"
        assert commit.author == "John Doe"
        assert len(commit.files_changed) == 2
        assert commit.additions == 10
        assert commit.deletions == 5


class TestGitParserTimeout:
    """Test git command timeout handling."""

    def test_handles_timeout(self, tmp_path):
        """Should handle subprocess timeout."""
        (tmp_path / ".git").mkdir()
        parser = GitParser(str(tmp_path))

        import subprocess
        with patch('subprocess.run', side_effect=subprocess.TimeoutExpired("git", 5)):
            commits = parser.get_recent_commits()

        assert commits == []


class TestPatternDeduplication:
    """Test pattern deduplication in extraction."""

    def test_removes_duplicate_patterns(self):
        """Should remove duplicate framework detection patterns."""
        parser = GitParser()
        commits = [
            GitCommit(
                hash="abc",
                author="dev",
                timestamp=datetime.now(),
                message="Add react component",
                files_changed=["App.jsx"],
                additions=10,
                deletions=0
            ),
            GitCommit(
                hash="def",
                author="dev",
                timestamp=datetime.now(),
                message="Add another react component",
                files_changed=["Button.jsx"],
                additions=5,
                deletions=0
            )
        ]

        patterns = parser.extract_patterns(commits)

        # Should not have duplicate "Project uses react" (exact match)
        project_uses_react = [p for p in patterns if p == "Project uses react"]
        assert len(project_uses_react) == 1

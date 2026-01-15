"""
Passive Learning Layer for MemoryLane
Watches file changes, git commits, and learns from patterns
"""

import os
import subprocess
import time
from pathlib import Path
from typing import List, Dict, Optional, Set
from datetime import datetime
from dataclasses import dataclass

from config_manager import ConfigManager
from memory_store import MemoryStore


@dataclass
class FileChange:
    """Represents a file change event"""
    path: str
    change_type: str  # 'created', 'modified', 'deleted'
    timestamp: datetime
    content_preview: Optional[str] = None


@dataclass
class GitCommit:
    """Represents a git commit"""
    hash: str
    author: str
    timestamp: datetime
    message: str
    files_changed: List[str]
    additions: int
    deletions: int


class GitParser:
    """Parse git history to learn project patterns"""

    def __init__(self, repo_path: str = "."):
        self.repo_path = Path(repo_path)

    def is_git_repo(self) -> bool:
        """Check if directory is a git repository"""
        return (self.repo_path / ".git").exists()

    def get_recent_commits(self, count: int = 10) -> List[GitCommit]:
        """Get recent commits with details"""
        if not self.is_git_repo():
            return []

        try:
            # Get commit log with stats
            result = subprocess.run(
                [
                    'git', 'log',
                    f'-{count}',
                    '--pretty=format:%H|%an|%at|%s',
                    '--numstat'
                ],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode != 0:
                return []

            return self._parse_git_log(result.stdout)

        except (subprocess.TimeoutExpired, Exception):
            return []

    def _parse_git_log(self, log_output: str) -> List[GitCommit]:
        """Parse git log output into commit objects"""
        commits = []
        lines = log_output.strip().split('\n')

        i = 0
        while i < len(lines):
            line = lines[i].strip()

            if '|' in line:
                # Commit header
                parts = line.split('|')
                if len(parts) < 4:
                    i += 1
                    continue

                commit_hash = parts[0]
                author = parts[1]
                timestamp = datetime.fromtimestamp(int(parts[2]))
                message = parts[3]

                # Parse file stats
                i += 1
                files_changed = []
                additions = 0
                deletions = 0

                while i < len(lines) and lines[i].strip() and '|' not in lines[i]:
                    stat_line = lines[i].strip()
                    parts = stat_line.split('\t')

                    if len(parts) >= 3:
                        try:
                            adds = int(parts[0]) if parts[0] != '-' else 0
                            dels = int(parts[1]) if parts[1] != '-' else 0
                            filepath = parts[2]

                            additions += adds
                            deletions += dels
                            files_changed.append(filepath)
                        except ValueError:
                            pass

                    i += 1

                commits.append(GitCommit(
                    hash=commit_hash,
                    author=author,
                    timestamp=timestamp,
                    message=message,
                    files_changed=files_changed,
                    additions=additions,
                    deletions=deletions
                ))
            else:
                i += 1

        return commits

    def extract_patterns(self, commits: List[GitCommit]) -> List[str]:
        """Extract patterns from commit history"""
        patterns = []

        # Analyze commit messages
        for commit in commits:
            msg = commit.message.lower()

            # Pattern: Framework/library mentions
            frameworks = ['react', 'vue', 'django', 'flask', 'fastapi', 'express', 'next.js']
            for fw in frameworks:
                if fw in msg:
                    patterns.append(f"Project uses {fw}")

            # Pattern: Common operations
            if 'fix' in msg or 'bug' in msg:
                patterns.append(f"Bug fix in {', '.join(commit.files_changed[:3])}")
            elif 'add' in msg or 'feature' in msg:
                patterns.append(f"Feature added: {commit.message[:50]}")
            elif 'refactor' in msg:
                patterns.append(f"Refactoring: {commit.message[:50]}")

        # File patterns
        file_extensions = {}
        for commit in commits:
            for filepath in commit.files_changed:
                ext = Path(filepath).suffix
                if ext:
                    file_extensions[ext] = file_extensions.get(ext, 0) + 1

        # Most common extensions
        if file_extensions:
            sorted_exts = sorted(file_extensions.items(), key=lambda x: x[1], reverse=True)
            top_ext = sorted_exts[0][0]
            patterns.append(f"Primary language: {top_ext} files")

        return list(set(patterns))  # Remove duplicates


class FileWatcher:
    """Watch file changes in the workspace"""

    def __init__(self, config: ConfigManager):
        self.config = config
        self.watched_files: Dict[str, float] = {}  # path -> last_modified
        self.workspace_root = Path.cwd()

    def scan_workspace(self, extensions: Optional[List[str]] = None) -> List[Path]:
        """Scan workspace for relevant files"""
        if extensions is None:
            extensions = ['.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.cpp', '.c', '.go', '.rs']

        files = []
        for ext in extensions:
            files.extend(self.workspace_root.rglob(f'*{ext}'))

        # Filter excluded files
        filtered = []
        for file in files:
            rel_path = str(file.relative_to(self.workspace_root))
            if not self.config.is_file_excluded(rel_path):
                filtered.append(file)

        return filtered

    def get_changed_files(self) -> List[FileChange]:
        """Get files that changed since last check"""
        changes = []
        current_files = self.scan_workspace()

        current_paths = {str(f): f for f in current_files}

        # Check for new/modified files
        for path_str, file_path in current_paths.items():
            try:
                mtime = file_path.stat().st_mtime

                if path_str in self.watched_files:
                    # Check if modified
                    if mtime > self.watched_files[path_str]:
                        changes.append(FileChange(
                            path=path_str,
                            change_type='modified',
                            timestamp=datetime.fromtimestamp(mtime)
                        ))
                else:
                    # New file
                    changes.append(FileChange(
                        path=path_str,
                        change_type='created',
                        timestamp=datetime.fromtimestamp(mtime)
                    ))

                self.watched_files[path_str] = mtime

            except (OSError, Exception):
                continue

        # Check for deleted files
        watched_paths = set(self.watched_files.keys())
        current_path_strs = set(current_paths.keys())
        deleted = watched_paths - current_path_strs

        for path_str in deleted:
            changes.append(FileChange(
                path=path_str,
                change_type='deleted',
                timestamp=datetime.now()
            ))
            del self.watched_files[path_str]

        return changes


class PassiveLearner:
    """
    Main passive learning orchestrator
    Watches workspace and learns patterns automatically
    """

    def __init__(self, config: ConfigManager, store: MemoryStore):
        self.config = config
        self.store = store
        self.git_parser = GitParser()
        self.file_watcher = FileWatcher(config)
        self.last_learning_time = datetime.now()

    def initial_learning(self):
        """Perform initial learning from git history and workspace"""
        print("🧠 MemoryLane: Initial learning...")

        # Learn from git history
        if self.config.get('learning.watch_git_commits', True):
            commits = self.git_parser.get_recent_commits(count=20)
            if commits:
                print(f"  📚 Analyzing {len(commits)} recent commits...")

                # Extract patterns
                patterns = self.git_parser.extract_patterns(commits)

                for pattern in patterns:
                    self.store.add_memory(
                        category='patterns',
                        content=pattern,
                        source='git_history',
                        relevance_score=0.8
                    )

                print(f"  ✓ Learned {len(patterns)} patterns from git history")

        # Index workspace structure
        if self.config.get('learning.index_on_startup', True):
            files = self.file_watcher.scan_workspace()
            print(f"  📂 Indexed {len(files)} files in workspace")

            # Learn project structure
            directories = set()
            for file in files:
                directories.add(file.parent)

            # Common directory patterns
            common_dirs = ['src', 'lib', 'app', 'components', 'utils', 'tests', 'api']
            for dir_name in common_dirs:
                matching = [d for d in directories if dir_name in str(d)]
                if matching:
                    self.store.add_memory(
                        category='context',
                        content=f"Project has {dir_name}/ directory for organization",
                        source='workspace_scan',
                        relevance_score=0.7
                    )

        print("  ✓ Initial learning complete")

    def watch_and_learn(self, interval: int = 30):
        """Continuous learning loop (runs in background)"""
        print(f"👀 Watching for changes (checking every {interval}s)...")

        while True:
            try:
                # Check file changes
                if self.config.get('learning.watch_file_changes', True):
                    changes = self.file_watcher.get_changed_files()

                    for change in changes:
                        # Learn from significant changes
                        if change.change_type == 'created':
                            self.store.add_memory(
                                category='learnings',
                                content=f"New file created: {change.path}",
                                source='file_watcher',
                                relevance_score=0.6,
                                metadata={'change_type': 'created'}
                            )

                # Check for new commits periodically (every 5 minutes)
                elapsed = (datetime.now() - self.last_learning_time).total_seconds()
                if elapsed > 300 and self.config.get('learning.watch_git_commits', True):
                    commits = self.git_parser.get_recent_commits(count=5)
                    if commits:
                        patterns = self.git_parser.extract_patterns(commits)
                        for pattern in patterns:
                            self.store.add_memory(
                                category='patterns',
                                content=pattern,
                                source='git_monitor',
                                relevance_score=0.8
                            )

                    self.last_learning_time = datetime.now()

                time.sleep(interval)

            except KeyboardInterrupt:
                print("\n👋 Stopping learning...")
                break
            except Exception as e:
                print(f"⚠️  Learning error: {e}")
                time.sleep(interval)


def main():
    """CLI for testing learner"""
    import argparse

    parser = argparse.ArgumentParser(description='MemoryLane Learner')
    parser.add_argument(
        'command',
        choices=['scan', 'git', 'watch', 'initial'],
        help='Learner command'
    )

    args = parser.parse_args()

    config = ConfigManager()
    store = MemoryStore(str(config.get_path('memories_file')))
    learner = PassiveLearner(config, store)

    if args.command == 'initial':
        learner.initial_learning()

    elif args.command == 'scan':
        files = learner.file_watcher.scan_workspace()
        print(f"Found {len(files)} files:")
        for f in files[:10]:
            print(f"  {f}")
        if len(files) > 10:
            print(f"  ... and {len(files) - 10} more")

    elif args.command == 'git':
        commits = learner.git_parser.get_recent_commits()
        print(f"Found {len(commits)} recent commits:")
        for commit in commits:
            print(f"  {commit.hash[:8]} - {commit.message}")
            print(f"    {commit.additions}+ {commit.deletions}- in {len(commit.files_changed)} files")

        patterns = learner.git_parser.extract_patterns(commits)
        print(f"\nExtracted patterns:")
        for pattern in patterns:
            print(f"  - {pattern}")

    elif args.command == 'watch':
        learner.watch_and_learn()


if __name__ == '__main__':
    main()

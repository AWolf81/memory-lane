"""
Project Registry for MemoryLane
Manages global registration of projects for cross-project memory search.
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any

from memory_store import MemoryStore


class ProjectRegistry:
    """
    Manages a global registry of MemoryLane-enabled projects.
    Enables cross-project memory search while keeping data per-project.
    """

    def __init__(self, registry_path: Optional[Path] = None):
        self.registry_path = registry_path or (Path.home() / ".memorylane" / "projects.json")
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        self._registry: Optional[Dict] = None

    def _load(self) -> Dict:
        """Load registry from disk"""
        if self._registry is not None:
            return self._registry

        if self.registry_path.exists():
            try:
                with open(self.registry_path, 'r') as f:
                    self._registry = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._registry = self._create_empty()
        else:
            self._registry = self._create_empty()

        return self._registry

    def _create_empty(self) -> Dict:
        """Create empty registry structure"""
        return {
            "version": "1.0",
            "created_at": datetime.now().isoformat(),
            "projects": []
        }

    def _save(self):
        """Save registry to disk"""
        if self._registry is None:
            return

        self._registry["last_updated"] = datetime.now().isoformat()

        with open(self.registry_path, 'w') as f:
            json.dump(self._registry, f, indent=2)

    def register(self, project_path: Path, name: Optional[str] = None) -> bool:
        """
        Register a project in the global registry.
        Returns True if newly registered, False if already existed.
        """
        registry = self._load()
        project_path = project_path.resolve()
        path_str = str(project_path)

        # Check if already registered
        for project in registry["projects"]:
            if project["path"] == path_str:
                # Update last_accessed
                project["last_accessed"] = datetime.now().isoformat()
                self._save()
                return False

        # Add new project
        registry["projects"].append({
            "path": path_str,
            "name": name or project_path.name,
            "registered_at": datetime.now().isoformat(),
            "last_accessed": datetime.now().isoformat()
        })

        self._save()
        return True

    def unregister(self, project_path: Path) -> bool:
        """Remove a project from the registry"""
        registry = self._load()
        path_str = str(project_path.resolve())

        original_count = len(registry["projects"])
        registry["projects"] = [
            p for p in registry["projects"]
            if p["path"] != path_str
        ]

        if len(registry["projects"]) < original_count:
            self._save()
            return True
        return False

    def list_projects(self, validate: bool = True) -> List[Dict]:
        """
        List all registered projects.
        If validate=True, checks if projects still exist.
        """
        registry = self._load()
        projects = registry["projects"]

        if validate:
            valid_projects = []
            for project in projects:
                memories_file = Path(project["path"]) / ".memorylane" / "memories.json"
                project["valid"] = memories_file.exists()
                if project["valid"]:
                    valid_projects.append(project)
            return valid_projects

        return projects

    def get_project(self, name_or_path: str) -> Optional[Dict]:
        """Get a specific project by name or path"""
        registry = self._load()

        for project in registry["projects"]:
            if project["name"] == name_or_path or project["path"] == name_or_path:
                return project

        return None

    def search_all(
        self,
        query: str,
        exclude_current: bool = False,
        current_path: Optional[Path] = None,
        limit_per_project: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search memories across all registered projects.
        Returns memories tagged with their source project.
        """
        projects = self.list_projects(validate=True)
        all_memories = []

        current_path_str = str(current_path.resolve()) if current_path else None

        for project in projects:
            if exclude_current and project["path"] == current_path_str:
                continue

            memories_file = Path(project["path"]) / ".memorylane" / "memories.json"
            if not memories_file.exists():
                continue

            try:
                store = MemoryStore(memories_file)
                memories = store.get_memories(limit=limit_per_project)

                # Tag each memory with its project
                for memory in memories:
                    memory["_project_name"] = project["name"]
                    memory["_project_path"] = project["path"]

                all_memories.extend(memories)
            except Exception as e:
                # Skip projects with errors
                continue

        # Now search/filter
        if query:
            # Try semantic search if available
            try:
                from semantic_search import SemanticSearcher
                searcher = SemanticSearcher()
                scored = searcher.search(query, all_memories, limit=50)
                return [m for m, score in scored]
            except ImportError:
                # Fall back to keyword matching
                query_words = set(query.lower().split())
                scored = []
                for memory in all_memories:
                    content_words = set(memory['content'].lower().split())
                    overlap = len(query_words & content_words)
                    if overlap > 0:
                        scored.append((memory, overlap))

                scored.sort(key=lambda x: (-x[1], -x[0].get('relevance_score', 0)))
                return [m for m, _ in scored[:50]]

        return all_memories

    def get_all_memories(
        self,
        project_names: Optional[List[str]] = None,
        limit_per_project: int = 50
    ) -> Dict[str, List[Dict]]:
        """
        Get memories from all (or specified) projects.
        Returns dict mapping project name to its memories.
        """
        projects = self.list_projects(validate=True)
        result = {}

        for project in projects:
            if project_names and project["name"] not in project_names:
                continue

            memories_file = Path(project["path"]) / ".memorylane" / "memories.json"
            if not memories_file.exists():
                continue

            try:
                store = MemoryStore(memories_file)
                memories = store.get_memories(limit=limit_per_project)
                result[project["name"]] = memories
            except Exception:
                continue

        return result

    def cleanup_stale(self) -> int:
        """Remove projects that no longer exist. Returns count removed."""
        registry = self._load()
        original_count = len(registry["projects"])

        registry["projects"] = [
            p for p in registry["projects"]
            if (Path(p["path"]) / ".memorylane" / "memories.json").exists()
        ]

        removed = original_count - len(registry["projects"])
        if removed > 0:
            self._save()

        return removed


def ensure_registered(project_path: Optional[Path] = None) -> bool:
    """
    Convenience function to ensure current project is registered.
    Call this on CLI/extension startup.
    """
    project_path = project_path or Path.cwd()
    memories_file = project_path / ".memorylane" / "memories.json"

    # Only register if project has memories
    if not memories_file.exists():
        return False

    registry = ProjectRegistry()
    return registry.register(project_path)

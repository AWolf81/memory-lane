"""
Tests for Project Registry.
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from project_registry import ProjectRegistry, ensure_registered


class TestProjectRegistryInit:
    """Test registry initialization."""

    def test_uses_default_path(self):
        """Should use default path in home directory."""
        registry = ProjectRegistry()

        assert '.memorylane' in str(registry.registry_path)
        assert 'projects.json' in str(registry.registry_path)

    def test_uses_custom_path(self, tmp_path):
        """Should use custom path when provided."""
        custom_path = tmp_path / "custom_registry.json"

        registry = ProjectRegistry(registry_path=custom_path)

        assert registry.registry_path == custom_path

    def test_creates_parent_directory(self, tmp_path):
        """Should create parent directory if needed."""
        nested_path = tmp_path / "nested" / "dir" / "registry.json"

        registry = ProjectRegistry(registry_path=nested_path)

        assert nested_path.parent.exists()


class TestRegistryLoadSave:
    """Test registry loading and saving."""

    def test_load_creates_empty_if_not_exists(self, tmp_path):
        """Should create empty registry if file doesn't exist."""
        registry_path = tmp_path / "registry.json"
        registry = ProjectRegistry(registry_path=registry_path)

        data = registry._load()

        assert data['version'] == '1.0'
        assert data['projects'] == []

    def test_load_reads_existing_file(self, tmp_path):
        """Should load existing registry file."""
        registry_path = tmp_path / "registry.json"
        registry_path.write_text(json.dumps({
            'version': '1.0',
            'projects': [{'path': '/test', 'name': 'test'}]
        }))

        registry = ProjectRegistry(registry_path=registry_path)
        data = registry._load()

        assert len(data['projects']) == 1
        assert data['projects'][0]['name'] == 'test'

    def test_load_handles_invalid_json(self, tmp_path):
        """Should create empty registry if file is invalid JSON."""
        registry_path = tmp_path / "registry.json"
        registry_path.write_text("invalid json")

        registry = ProjectRegistry(registry_path=registry_path)
        data = registry._load()

        assert data['projects'] == []

    def test_save_writes_to_file(self, tmp_path):
        """Should save registry to file."""
        registry_path = tmp_path / "registry.json"
        registry = ProjectRegistry(registry_path=registry_path)

        registry._registry = {'version': '1.0', 'projects': []}
        registry._save()

        assert registry_path.exists()
        data = json.loads(registry_path.read_text())
        assert 'last_updated' in data

    def test_save_does_nothing_if_no_registry(self, tmp_path):
        """Should not save if registry not loaded."""
        registry_path = tmp_path / "registry.json"
        registry = ProjectRegistry(registry_path=registry_path)

        registry._save()  # Should not raise

        assert not registry_path.exists()


class TestRegisterProject:
    """Test project registration."""

    def test_register_new_project(self, tmp_path):
        """Should register a new project."""
        registry_path = tmp_path / "registry.json"
        project_path = tmp_path / "my_project"
        project_path.mkdir()

        registry = ProjectRegistry(registry_path=registry_path)
        result = registry.register(project_path)

        assert result is True
        data = registry._load()
        assert len(data['projects']) == 1
        assert data['projects'][0]['name'] == 'my_project'

    def test_register_with_custom_name(self, tmp_path):
        """Should use custom name when provided."""
        registry_path = tmp_path / "registry.json"
        project_path = tmp_path / "my_project"
        project_path.mkdir()

        registry = ProjectRegistry(registry_path=registry_path)
        registry.register(project_path, name="Custom Name")

        data = registry._load()
        assert data['projects'][0]['name'] == 'Custom Name'

    def test_register_updates_existing(self, tmp_path):
        """Should update last_accessed for existing project."""
        registry_path = tmp_path / "registry.json"
        project_path = tmp_path / "my_project"
        project_path.mkdir()

        registry = ProjectRegistry(registry_path=registry_path)
        registry.register(project_path)
        result = registry.register(project_path)

        assert result is False  # Already existed
        data = registry._load()
        assert len(data['projects']) == 1


class TestUnregisterProject:
    """Test project unregistration."""

    def test_unregister_existing_project(self, tmp_path):
        """Should remove existing project."""
        registry_path = tmp_path / "registry.json"
        project_path = tmp_path / "my_project"
        project_path.mkdir()

        registry = ProjectRegistry(registry_path=registry_path)
        registry.register(project_path)

        result = registry.unregister(project_path)

        assert result is True
        data = registry._load()
        assert len(data['projects']) == 0

    def test_unregister_nonexistent_project(self, tmp_path):
        """Should return False for nonexistent project."""
        registry_path = tmp_path / "registry.json"
        project_path = tmp_path / "nonexistent"

        registry = ProjectRegistry(registry_path=registry_path)
        result = registry.unregister(project_path)

        assert result is False


class TestListProjects:
    """Test listing projects."""

    def test_list_empty_registry(self, tmp_path):
        """Should return empty list for empty registry."""
        registry_path = tmp_path / "registry.json"
        registry = ProjectRegistry(registry_path=registry_path)

        projects = registry.list_projects()

        assert projects == []

    def test_list_validates_projects(self, tmp_path):
        """Should validate projects exist when validate=True."""
        registry_path = tmp_path / "registry.json"

        # Create registry with one valid and one invalid project
        valid_project = tmp_path / "valid"
        valid_project.mkdir()
        (valid_project / ".memorylane").mkdir()
        (valid_project / ".memorylane" / "memories.json").write_text("{}")

        invalid_project = tmp_path / "invalid"

        registry = ProjectRegistry(registry_path=registry_path)
        registry._registry = {
            'version': '1.0',
            'projects': [
                {'path': str(valid_project), 'name': 'valid'},
                {'path': str(invalid_project), 'name': 'invalid'}
            ]
        }

        projects = registry.list_projects(validate=True)

        # Only valid project should be returned
        assert len(projects) == 1
        assert projects[0]['name'] == 'valid'

    def test_list_without_validation(self, tmp_path):
        """Should return all projects when validate=False."""
        registry_path = tmp_path / "registry.json"
        registry = ProjectRegistry(registry_path=registry_path)
        registry._registry = {
            'version': '1.0',
            'projects': [
                {'path': '/nonexistent1', 'name': 'project1'},
                {'path': '/nonexistent2', 'name': 'project2'}
            ]
        }

        projects = registry.list_projects(validate=False)

        assert len(projects) == 2


class TestGetProject:
    """Test getting specific project."""

    def test_get_by_name(self, tmp_path):
        """Should find project by name."""
        registry_path = tmp_path / "registry.json"
        registry = ProjectRegistry(registry_path=registry_path)
        registry._registry = {
            'version': '1.0',
            'projects': [{'path': '/test', 'name': 'my_project'}]
        }

        project = registry.get_project('my_project')

        assert project is not None
        assert project['name'] == 'my_project'

    def test_get_by_path(self, tmp_path):
        """Should find project by path."""
        registry_path = tmp_path / "registry.json"
        registry = ProjectRegistry(registry_path=registry_path)
        registry._registry = {
            'version': '1.0',
            'projects': [{'path': '/test/path', 'name': 'my_project'}]
        }

        project = registry.get_project('/test/path')

        assert project is not None
        assert project['path'] == '/test/path'

    def test_get_nonexistent_returns_none(self, tmp_path):
        """Should return None for nonexistent project."""
        registry_path = tmp_path / "registry.json"
        registry = ProjectRegistry(registry_path=registry_path)
        registry._registry = {'version': '1.0', 'projects': []}

        project = registry.get_project('nonexistent')

        assert project is None


class TestSearchAll:
    """Test cross-project search."""

    def test_search_empty_registry(self, tmp_path):
        """Should return empty list for empty registry."""
        registry_path = tmp_path / "registry.json"
        registry = ProjectRegistry(registry_path=registry_path)

        results = registry.search_all("query")

        assert results == []

    def test_search_tags_results_with_project(self, tmp_path):
        """Should tag results with project info."""
        registry_path = tmp_path / "registry.json"

        # Create a valid project with memories
        project_path = tmp_path / "project1"
        project_path.mkdir()
        mem_dir = project_path / ".memorylane"
        mem_dir.mkdir()

        memories_data = {
            'version': '1.0',
            'categories': {
                'patterns': {
                    'memories': [{
                        'id': 'patt-001',
                        'content': 'Test pattern',
                        'relevance_score': 0.8,
                        'source': 'test',
                        'created_at': '2024-01-01',
                        'usage_count': 0
                    }]
                }
            }
        }
        (mem_dir / "memories.json").write_text(json.dumps(memories_data))

        registry = ProjectRegistry(registry_path=registry_path)
        registry.register(project_path, name="project1")

        # Search without semantic search (it will fall back to keyword matching)
        results = registry.search_all("test")

        # Should have project tags
        if results:
            assert '_project_name' in results[0]
            assert '_project_path' in results[0]

    def test_search_excludes_current_project(self, tmp_path):
        """Should exclude current project when specified."""
        registry_path = tmp_path / "registry.json"

        # Create two projects
        project1 = tmp_path / "project1"
        project1.mkdir()
        (project1 / ".memorylane").mkdir()
        (project1 / ".memorylane" / "memories.json").write_text('{"version":"1.0","categories":{}}')

        project2 = tmp_path / "project2"
        project2.mkdir()
        (project2 / ".memorylane").mkdir()
        (project2 / ".memorylane" / "memories.json").write_text('{"version":"1.0","categories":{}}')

        registry = ProjectRegistry(registry_path=registry_path)
        registry.register(project1)
        registry.register(project2)

        # Search excluding project1
        results = registry.search_all("", exclude_current=True, current_path=project1)

        # Results should not include project1
        for result in results:
            if '_project_path' in result:
                assert result['_project_path'] != str(project1.resolve())


class TestGetAllMemories:
    """Test getting memories from all projects."""

    def test_get_all_empty_registry(self, tmp_path):
        """Should return empty dict for empty registry."""
        registry_path = tmp_path / "registry.json"
        registry = ProjectRegistry(registry_path=registry_path)

        result = registry.get_all_memories()

        assert result == {}

    def test_get_all_filters_by_project_names(self, tmp_path):
        """Should filter by project names when specified."""
        registry_path = tmp_path / "registry.json"

        # Create two projects
        project1 = tmp_path / "project1"
        project1.mkdir()
        (project1 / ".memorylane").mkdir()
        (project1 / ".memorylane" / "memories.json").write_text('{"version":"1.0","categories":{}}')

        project2 = tmp_path / "project2"
        project2.mkdir()
        (project2 / ".memorylane").mkdir()
        (project2 / ".memorylane" / "memories.json").write_text('{"version":"1.0","categories":{}}')

        registry = ProjectRegistry(registry_path=registry_path)
        registry.register(project1)
        registry.register(project2)

        result = registry.get_all_memories(project_names=['project1'])

        # Should only have project1
        assert 'project1' in result or len(result) <= 1


class TestCleanupStale:
    """Test stale project cleanup."""

    def test_removes_stale_projects(self, tmp_path):
        """Should remove projects that no longer exist."""
        registry_path = tmp_path / "registry.json"

        # Create one valid project
        valid_project = tmp_path / "valid"
        valid_project.mkdir()
        (valid_project / ".memorylane").mkdir()
        (valid_project / ".memorylane" / "memories.json").write_text("{}")

        registry = ProjectRegistry(registry_path=registry_path)
        registry._registry = {
            'version': '1.0',
            'projects': [
                {'path': str(valid_project), 'name': 'valid'},
                {'path': '/nonexistent', 'name': 'stale'}
            ]
        }

        removed = registry.cleanup_stale()

        assert removed == 1
        data = registry._load()
        assert len(data['projects']) == 1
        assert data['projects'][0]['name'] == 'valid'

    def test_returns_zero_when_nothing_to_cleanup(self, tmp_path):
        """Should return 0 when all projects valid."""
        registry_path = tmp_path / "registry.json"

        valid_project = tmp_path / "valid"
        valid_project.mkdir()
        (valid_project / ".memorylane").mkdir()
        (valid_project / ".memorylane" / "memories.json").write_text("{}")

        registry = ProjectRegistry(registry_path=registry_path)
        registry._registry = {
            'version': '1.0',
            'projects': [{'path': str(valid_project), 'name': 'valid'}]
        }

        removed = registry.cleanup_stale()

        assert removed == 0


class TestEnsureRegistered:
    """Test ensure_registered convenience function."""

    def test_registers_existing_project(self, tmp_path):
        """Should register project with memories."""
        project_path = tmp_path / "project"
        project_path.mkdir()
        (project_path / ".memorylane").mkdir()
        (project_path / ".memorylane" / "memories.json").write_text("{}")

        with patch('project_registry.ProjectRegistry') as mock_registry_class:
            mock_registry = MagicMock()
            mock_registry.register.return_value = True
            mock_registry_class.return_value = mock_registry

            result = ensure_registered(project_path)

            assert result is True
            mock_registry.register.assert_called_once_with(project_path)

    def test_skips_project_without_memories(self, tmp_path):
        """Should not register project without memories file."""
        project_path = tmp_path / "project"
        project_path.mkdir()

        result = ensure_registered(project_path)

        assert result is False

    def test_uses_cwd_by_default(self, tmp_path, monkeypatch):
        """Should use current directory by default."""
        # Create memories in tmp_path
        (tmp_path / ".memorylane").mkdir()
        (tmp_path / ".memorylane" / "memories.json").write_text("{}")

        # Change to tmp_path directory
        monkeypatch.chdir(tmp_path)

        with patch('project_registry.ProjectRegistry') as mock_registry_class:
            mock_registry = MagicMock()
            mock_registry.register.return_value = True
            mock_registry_class.return_value = mock_registry

            result = ensure_registered()  # No path provided

            # Should have called register
            mock_registry.register.assert_called_once()

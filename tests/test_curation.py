"""Tests for memory curation feature"""

import pytest
import json
import tempfile
from pathlib import Path
from datetime import datetime

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from memory_store import MemoryStore
from curation_manager import CurationManager


class TestCurationManager:
    """Tests for CurationManager"""

    @pytest.fixture
    def temp_curator(self):
        """Create a temporary curation manager"""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "curation_state.json"
            yield CurationManager(str(state_path))

    def test_default_state(self, temp_curator):
        """Test default state initialization"""
        state = temp_curator.load_state()
        assert state['last_curated'] is None
        assert state['memories_reviewed'] == []
        assert state['curation_count'] == 0

    def test_needs_curation_disabled(self, temp_curator):
        """Test that curation doesn't trigger when disabled"""
        config = {"curation": {"enabled": False}}
        assert temp_curator.needs_curation(config, 100) is False

    def test_needs_curation_first_time(self, temp_curator):
        """Test curation triggers on first time with enough memories"""
        config = {"curation": {"enabled": True, "trigger_memory_count": 15}}
        # Should trigger with enough memories
        assert temp_curator.needs_curation(config, 20) is True
        # Should not trigger with few memories
        assert temp_curator.needs_curation(config, 5) is False

    def test_needs_curation_threshold(self, temp_curator):
        """Test curation triggers based on uncurated count"""
        config = {"curation": {"enabled": True, "trigger_memory_count": 10}}

        # Mark some as reviewed
        temp_curator.mark_curated(["mem-001", "mem-002", "mem-003"])

        # 13 total - 3 reviewed = 10 uncurated = threshold met
        assert temp_curator.needs_curation(config, 13) is True

        # 12 total - 3 reviewed = 9 uncurated = below threshold
        assert temp_curator.needs_curation(config, 12) is False

    def test_mark_curated(self, temp_curator):
        """Test marking memories as curated"""
        temp_curator.mark_curated(["patt-001", "patt-002"])

        state = temp_curator.load_state()
        assert state['last_curated'] is not None
        assert "patt-001" in state['memories_reviewed']
        assert "patt-002" in state['memories_reviewed']
        assert state['curation_count'] == 1

    def test_mark_curated_no_duplicates(self, temp_curator):
        """Test that marking same memory twice doesn't duplicate"""
        temp_curator.mark_curated(["patt-001", "patt-002"])
        temp_curator.mark_curated(["patt-002", "patt-003"])

        state = temp_curator.load_state()
        assert state['memories_reviewed'].count("patt-002") == 1
        assert len(state['memories_reviewed']) == 3

    def test_get_reviewed_ids(self, temp_curator):
        """Test getting reviewed IDs as a set"""
        temp_curator.mark_curated(["patt-001", "lear-001"])

        reviewed = temp_curator.get_reviewed_ids()
        assert isinstance(reviewed, set)
        assert "patt-001" in reviewed
        assert "lear-001" in reviewed

    def test_reset(self, temp_curator):
        """Test resetting curation state"""
        temp_curator.mark_curated(["patt-001"])
        temp_curator.reset()

        state = temp_curator.load_state()
        assert state['last_curated'] is None
        assert state['memories_reviewed'] == []


class TestMemoryStoreExtensions:
    """Tests for new MemoryStore methods"""

    @pytest.fixture
    def temp_store(self):
        """Create a temporary memory store"""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "test_memories.json"
            yield MemoryStore(str(store_path))

    def test_get_memory_by_id(self, temp_store):
        """Test getting a memory by ID"""
        memory_id = temp_store.add_memory('patterns', 'Test content', 'manual')

        memory = temp_store.get_memory_by_id(memory_id)
        assert memory is not None
        assert memory['content'] == 'Test content'
        assert memory['category'] == 'patterns'

    def test_get_memory_by_id_not_found(self, temp_store):
        """Test getting a non-existent memory"""
        memory = temp_store.get_memory_by_id('nonexistent-001')
        assert memory is None

    def test_delete_memory(self, temp_store):
        """Test deleting a memory"""
        memory_id = temp_store.add_memory('patterns', 'To delete', 'manual')

        result = temp_store.delete_memory(memory_id)
        assert result is True

        # Verify it's gone
        memory = temp_store.get_memory_by_id(memory_id)
        assert memory is None

    def test_delete_memory_not_found(self, temp_store):
        """Test deleting a non-existent memory"""
        result = temp_store.delete_memory('nonexistent-001')
        assert result is False

    def test_update_memory_content(self, temp_store):
        """Test updating memory content"""
        memory_id = temp_store.add_memory('patterns', 'Old content', 'manual')

        result = temp_store.update_memory(memory_id, content='New content')
        assert result is True

        memory = temp_store.get_memory_by_id(memory_id)
        assert memory['content'] == 'New content'

    def test_update_memory_relevance(self, temp_store):
        """Test updating memory relevance score"""
        memory_id = temp_store.add_memory('patterns', 'Test', 'manual', relevance_score=0.5)

        result = temp_store.update_memory(memory_id, relevance_score=0.9)
        assert result is True

        memory = temp_store.get_memory_by_id(memory_id)
        assert memory['relevance_score'] == 0.9

    def test_update_memory_not_found(self, temp_store):
        """Test updating a non-existent memory"""
        result = temp_store.update_memory('nonexistent-001', content='New')
        assert result is False

    def test_get_uncurated_memories(self, temp_store):
        """Test getting uncurated memories"""
        # Add some memories
        id1 = temp_store.add_memory('patterns', 'Memory 1', 'manual')
        id2 = temp_store.add_memory('insights', 'Memory 2', 'manual')
        id3 = temp_store.add_memory('learnings', 'Memory 3', 'manual')

        # Get uncurated with none reviewed
        uncurated = temp_store.get_uncurated_memories(set(), limit=10)
        assert len(uncurated) == 3

        # Get uncurated with some reviewed
        uncurated = temp_store.get_uncurated_memories({id1, id2}, limit=10)
        assert len(uncurated) == 1
        assert uncurated[0]['id'] == id3

    def test_get_uncurated_memories_limit(self, temp_store):
        """Test limit on uncurated memories"""
        # Add many memories
        for i in range(10):
            temp_store.add_memory('patterns', f'Memory {i}', 'manual')

        uncurated = temp_store.get_uncurated_memories(set(), limit=5)
        assert len(uncurated) == 5

    def test_get_uncurated_memories_sorted_by_timestamp(self, temp_store):
        """Test that uncurated memories are sorted oldest first"""
        import time

        id1 = temp_store.add_memory('patterns', 'First', 'manual')
        time.sleep(0.01)  # Small delay to ensure different timestamps
        id2 = temp_store.add_memory('patterns', 'Second', 'manual')
        time.sleep(0.01)
        id3 = temp_store.add_memory('patterns', 'Third', 'manual')

        uncurated = temp_store.get_uncurated_memories(set(), limit=10)

        # Should be sorted oldest first
        assert uncurated[0]['id'] == id1
        assert uncurated[1]['id'] == id2
        assert uncurated[2]['id'] == id3

"""
Tests for MemoryStore
"""

import pytest
import json
import tempfile
from pathlib import Path
from datetime import datetime

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from memory_store import MemoryStore, Memory


class TestMemoryStore:
    """Test cases for MemoryStore"""

    @pytest.fixture
    def temp_store(self):
        """Create a temporary memory store for testing"""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "test_memories.json"
            yield MemoryStore(str(store_path))

    def test_create_empty_memory(self, temp_store):
        """Test empty memory creation"""
        empty = temp_store.create_empty_memory()

        assert 'memory_id' in empty
        assert 'categories' in empty
        assert 'metadata' in empty
        assert len(empty['categories']) == 4
        assert 'patterns' in empty['categories']
        assert empty['metadata']['total_memories'] == 0

    def test_add_memory(self, temp_store):
        """Test adding a memory"""
        memory_id = temp_store.add_memory(
            category='patterns',
            content='Use async/await for API calls',
            source='file_edit',
            relevance_score=0.9
        )

        assert memory_id.startswith('pattern-')

        # Verify it was saved
        data = temp_store.load()
        assert data['metadata']['total_memories'] == 1
        assert len(data['categories']['patterns']) == 1
        assert data['categories']['patterns'][0]['content'] == 'Use async/await for API calls'

    def test_get_memories_by_category(self, temp_store):
        """Test retrieving memories by category"""
        temp_store.add_memory('patterns', 'Pattern 1', 'manual', 1.0)
        temp_store.add_memory('insights', 'Insight 1', 'manual', 0.8)
        temp_store.add_memory('patterns', 'Pattern 2', 'manual', 0.9)

        patterns = temp_store.get_memories(category='patterns')
        assert len(patterns) == 2

        insights = temp_store.get_memories(category='insights')
        assert len(insights) == 1

    def test_get_memories_filtered_by_relevance(self, temp_store):
        """Test filtering memories by relevance score"""
        temp_store.add_memory('patterns', 'High relevance', 'manual', 0.9)
        temp_store.add_memory('patterns', 'Low relevance', 'manual', 0.3)

        high_rel = temp_store.get_memories(min_relevance=0.7)
        assert len(high_rel) == 1
        assert high_rel[0]['content'] == 'High relevance'

    def test_update_memory_usage(self, temp_store):
        """Test updating memory usage statistics"""
        memory_id = temp_store.add_memory('patterns', 'Test pattern', 'manual')

        # Update usage
        temp_store.update_memory_usage(memory_id)
        temp_store.update_memory_usage(memory_id)

        # Verify counts
        data = temp_store.load()
        memory = data['categories']['patterns'][0]
        assert memory['usage_count'] == 2
        assert memory['last_used'] is not None
        assert data['metadata']['total_retrievals'] == 2

    def test_prune_low_relevance(self, temp_store):
        """Test pruning low-relevance memories"""
        temp_store.add_memory('patterns', 'High relevance', 'manual', 0.9)
        temp_store.add_memory('patterns', 'Low relevance', 'manual', 0.2)
        temp_store.add_memory('patterns', 'Medium relevance', 'manual', 0.5)

        pruned = temp_store.prune_low_relevance(threshold=0.4)
        assert pruned == 1

        remaining = temp_store.get_memories(category='patterns')
        assert len(remaining) == 2

    def test_to_markdown(self, temp_store):
        """Test markdown export"""
        temp_store.add_memory('patterns', 'Pattern 1', 'manual', 1.0)
        temp_store.add_memory('insights', 'Insight 1', 'manual', 0.8)

        markdown = temp_store.to_markdown()

        assert '# MemoryLane Context' in markdown
        assert '## Patterns' in markdown
        assert '## Insights' in markdown
        assert 'Pattern 1' in markdown
        assert 'Insight 1' in markdown

    def test_get_stats(self, temp_store):
        """Test statistics generation"""
        temp_store.add_memory('patterns', 'P1', 'manual', 0.9)
        temp_store.add_memory('patterns', 'P2', 'manual', 0.7)
        temp_store.add_memory('insights', 'I1', 'manual', 0.8)

        stats = temp_store.get_stats()

        assert stats['total_memories'] == 3
        assert stats['categories']['patterns']['count'] == 2
        assert stats['categories']['insights']['count'] == 1
        assert stats['categories']['patterns']['avg_relevance'] == 0.8

    def test_backup_and_restore(self, temp_store):
        """Test backup and restore functionality"""
        # Add some memories
        temp_store.add_memory('patterns', 'Pattern 1', 'manual', 0.9)
        temp_store.add_memory('insights', 'Insight 1', 'manual', 0.8)

        # Create backup
        backup_path = temp_store.export_backup()
        assert backup_path.exists()

        # Modify store
        temp_store.add_memory('patterns', 'Pattern 2', 'manual', 0.7)

        # Restore
        temp_store.import_backup(backup_path)

        # Verify restoration
        data = temp_store.load()
        assert data['metadata']['total_memories'] == 2
        assert len(data['categories']['patterns']) == 1

    def test_invalid_category_raises_error(self, temp_store):
        """Test that invalid category raises ValueError"""
        with pytest.raises(ValueError):
            temp_store.add_memory('invalid_category', 'Test', 'manual')

    def test_memory_limit_per_category(self, temp_store):
        """Test retrieving limited number of memories"""
        for i in range(10):
            temp_store.add_memory('patterns', f'Pattern {i}', 'manual', 1.0 - i * 0.1)

        limited = temp_store.get_memories(category='patterns', limit=5)
        assert len(limited) == 5

        # Should be sorted by relevance
        assert limited[0]['relevance_score'] == 1.0

"""
Memory storage system for MemoryLane
Adapted from ace-system-skill playbook_manager.py pattern
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict


@dataclass
class Memory:
    """Individual memory entry"""
    id: str
    content: str
    category: str  # patterns, insights, learnings, context
    source: str  # file_edit, git_commit, manual, inference
    timestamp: str
    relevance_score: float = 1.0
    usage_count: int = 0
    last_used: Optional[str] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class MemoryStore:
    """
    Manages persistent memory storage using JSON
    Pattern adapted from ace-system-skill PlaybookManager
    """

    def __init__(self, memory_path: str = ".memorylane/memories.json"):
        self.memory_path = Path(memory_path)
        self.memory_path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> Dict:
        """Load memories from JSON file"""
        if not self.memory_path.exists():
            return self.create_empty_memory()

        try:
            with open(self.memory_path, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"Warning: Corrupted memory file, creating backup and starting fresh")
            self._backup_corrupted()
            return self.create_empty_memory()

    def save(self, memory_data: Dict):
        """Save memories to JSON file"""
        memory_data['last_updated'] = datetime.now().isoformat()

        with open(self.memory_path, 'w') as f:
            json.dump(memory_data, f, indent=2)

    def create_empty_memory(self) -> Dict:
        """Create empty memory structure"""
        return {
            "memory_id": f"memorylane-{datetime.now().strftime('%Y%m%d')}",
            "created_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat(),
            "version": "0.1.0",
            "categories": {
                "patterns": [],      # Code patterns, project structure
                "insights": [],      # Learned insights about the project
                "learnings": [],     # What worked/didn't work
                "context": []        # General project context
            },
            "metadata": {
                "total_memories": 0,
                "total_retrievals": 0,
                "last_compression": None,
                "avg_relevance": 0.0
            }
        }

    def add_memory(
        self,
        category: str,
        content: str,
        source: str,
        relevance_score: float = 1.0,
        metadata: Optional[Dict] = None
    ) -> str:
        """Add a new memory to the specified category"""
        memory_data = self.load()

        if category not in memory_data['categories']:
            raise ValueError(f"Invalid category: {category}")

        # Generate unique ID
        category_short = category[:4]
        memory_id = f"{category_short}-{len(memory_data['categories'][category]) + 1:03d}"

        # Create memory entry
        memory = Memory(
            id=memory_id,
            content=content,
            category=category,
            source=source,
            timestamp=datetime.now().isoformat(),
            relevance_score=relevance_score,
            metadata=metadata or {}
        )

        # Add to category
        memory_data['categories'][category].append(asdict(memory))
        memory_data['metadata']['total_memories'] += 1

        self.save(memory_data)
        return memory_id

    def get_memories(
        self,
        category: Optional[str] = None,
        min_relevance: float = 0.0,
        limit: Optional[int] = None
    ) -> List[Dict]:
        """Retrieve memories filtered by category and relevance"""
        memory_data = self.load()

        if category:
            memories = memory_data['categories'].get(category, [])
        else:
            # Get all memories from all categories
            memories = []
            for cat_memories in memory_data['categories'].values():
                memories.extend(cat_memories)

        # Filter by relevance
        filtered = [m for m in memories if m['relevance_score'] >= min_relevance]

        # Sort by relevance score (descending)
        filtered.sort(key=lambda m: m['relevance_score'], reverse=True)

        # Apply limit
        if limit:
            filtered = filtered[:limit]

        return filtered

    def update_memory_usage(self, memory_id: str):
        """Update usage statistics for a memory"""
        memory_data = self.load()

        for category in memory_data['categories'].values():
            for memory in category:
                if memory['id'] == memory_id:
                    memory['usage_count'] += 1
                    memory['last_used'] = datetime.now().isoformat()
                    memory_data['metadata']['total_retrievals'] += 1
                    self.save(memory_data)
                    return

        raise ValueError(f"Memory not found: {memory_id}")

    def prune_low_relevance(self, threshold: float = 0.3, max_age_days: int = 30):
        """Remove low-relevance memories that haven't been used recently"""
        memory_data = self.load()
        cutoff_date = datetime.now().timestamp() - (max_age_days * 24 * 60 * 60)

        pruned_count = 0
        for category in memory_data['categories']:
            original_count = len(memory_data['categories'][category])

            # Keep memories that are either:
            # 1. High relevance (>= threshold)
            # 2. Recently used (within max_age_days)
            memory_data['categories'][category] = [
                m for m in memory_data['categories'][category]
                if m['relevance_score'] >= threshold or
                   (m['last_used'] and
                    datetime.fromisoformat(m['last_used']).timestamp() > cutoff_date)
            ]

            pruned_count += original_count - len(memory_data['categories'][category])

        memory_data['metadata']['total_memories'] -= pruned_count
        self.save(memory_data)

        return pruned_count

    def to_markdown(self, category: Optional[str] = None) -> str:
        """Export memories as markdown for context injection"""
        memory_data = self.load()

        md_lines = ["# MemoryLane Context", ""]

        categories = [category] if category else memory_data['categories'].keys()

        for cat in categories:
            memories = memory_data['categories'].get(cat, [])
            if not memories:
                continue

            md_lines.append(f"## {cat.title()}")
            md_lines.append("")

            # Sort by relevance
            sorted_memories = sorted(
                memories,
                key=lambda m: m['relevance_score'],
                reverse=True
            )

            for memory in sorted_memories:
                # Show relevance as a visual indicator
                stars = "⭐" * int(memory['relevance_score'] * 5)
                md_lines.append(f"- {memory['content']} {stars}")

            md_lines.append("")

        return "\n".join(md_lines)

    def get_stats(self) -> Dict[str, Any]:
        """Get memory store statistics"""
        memory_data = self.load()

        stats = {
            "total_memories": memory_data['metadata']['total_memories'],
            "total_retrievals": memory_data['metadata']['total_retrievals'],
            "categories": {}
        }

        for category, memories in memory_data['categories'].items():
            if memories:
                avg_relevance = sum(m['relevance_score'] for m in memories) / len(memories)
                total_usage = sum(m['usage_count'] for m in memories)
            else:
                avg_relevance = 0.0
                total_usage = 0

            stats['categories'][category] = {
                "count": len(memories),
                "avg_relevance": round(avg_relevance, 2),
                "total_usage": total_usage
            }

        return stats

    def _backup_corrupted(self):
        """Backup corrupted memory file"""
        if self.memory_path.exists():
            backup_path = self.memory_path.parent / f"memories.corrupted.{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak"
            self.memory_path.rename(backup_path)
            print(f"Corrupted file backed up to: {backup_path}")

    def export_backup(self, backup_path: Optional[Path] = None) -> Path:
        """Create a backup of current memories"""
        memory_data = self.load()

        if backup_path is None:
            backup_dir = self.memory_path.parent / "backups"
            backup_dir.mkdir(exist_ok=True)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_path = backup_dir / f"memories.{timestamp}.json"

        with open(backup_path, 'w') as f:
            json.dump(memory_data, f, indent=2)

        return backup_path

    def import_backup(self, backup_path: Path):
        """Restore memories from a backup"""
        with open(backup_path, 'r') as f:
            memory_data = json.load(f)

        # Create backup of current state first
        self.export_backup()

        # Restore from backup
        self.save(memory_data)

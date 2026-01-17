"""
Curation state management for MemoryLane

Tracks when curation happened and which memories were reviewed to avoid
re-curating the same memories repeatedly.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set, Any, Optional


class CurationManager:
    """Manages memory curation state and decisions"""

    def __init__(self, state_path: Optional[str] = None):
        if state_path:
            self.state_path = Path(state_path)
        else:
            self.state_path = Path(".memorylane/curation_state.json")
        self.state_path.parent.mkdir(parents=True, exist_ok=True)

    def load_state(self) -> Dict[str, Any]:
        """Load curation state from file"""
        if not self.state_path.exists():
            return self._default_state()
        try:
            with open(self.state_path, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return self._default_state()

    def save_state(self, state: Dict[str, Any]):
        """Save curation state to file"""
        state['last_modified'] = datetime.now().isoformat()
        with open(self.state_path, 'w') as f:
            json.dump(state, f, indent=2)

    def _default_state(self) -> Dict[str, Any]:
        """Default state for new installations"""
        return {
            "last_curated": None,
            "memories_reviewed": [],
            "curation_count": 0,
            "created_at": datetime.now().isoformat()
        }

    def needs_curation(self, config: Dict, memory_count: int) -> bool:
        """
        Determine if curation should trigger.

        Args:
            config: Full configuration dict
            memory_count: Total number of memories in store

        Returns:
            True if curation should be triggered
        """
        curation_config = config.get('curation', {})

        # Check if curation is enabled
        if not curation_config.get('enabled', False):
            return False

        state = self.load_state()

        # Get threshold for new memories
        threshold = curation_config.get('trigger_memory_count', 15)

        # Count how many memories haven't been reviewed
        reviewed_count = len(state.get('memories_reviewed', []))
        uncurated_count = memory_count - reviewed_count

        # Trigger if we have enough uncurated memories
        return uncurated_count >= threshold

    def mark_curated(self, memory_ids: List[str]):
        """
        Mark memories as reviewed.

        Args:
            memory_ids: List of memory IDs that were reviewed
        """
        state = self.load_state()
        state['last_curated'] = datetime.now().isoformat()

        # Add new IDs to reviewed list (avoid duplicates)
        existing = set(state.get('memories_reviewed', []))
        existing.update(memory_ids)
        state['memories_reviewed'] = list(existing)

        state['curation_count'] = state.get('curation_count', 0) + 1
        self.save_state(state)

    def get_reviewed_ids(self) -> Set[str]:
        """Get set of already-reviewed memory IDs"""
        state = self.load_state()
        return set(state.get('memories_reviewed', []))

    def reset(self):
        """Reset curation state (for testing or fresh start)"""
        self.save_state(self._default_state())

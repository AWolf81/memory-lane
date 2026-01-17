"""
Tests for LLM-backed conversation learning.
"""

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from conversation_learner import ConversationLearner


class FakeSummarizer:
    """Simple stub for SummarizerService."""

    def summarize_text(self, raw_text, project_name=None, context_hints=None):
        return {
            "summary": "Test summary.",
            "memory_entries": [
                {
                    "type": "design_decision",
                    "content": "Chose SQLite over JSON for ACID guarantees",
                    "tags": ["db", "storage"],
                    "confidence": 0.9,
                },
                {
                    "type": "problem_solved",
                    "content": "Race condition fixed by adding per-file asyncio.Lock",
                    "tags": ["async", "debugging"],
                    "confidence": 0.8,
                },
                {
                    "type": "future_consideration",
                    "content": "Consider sharding for very large datasets",
                    "tags": ["scaling"],
                    "confidence": 0.6,
                },
            ],
            "suggested_deletions": [],
        }


def test_llm_extraction_maps_categories_and_filters_low_confidence():
    learner = ConversationLearner(summarizer=FakeSummarizer())
    memories = learner.extract_from_text("dummy transcript", source="manual")

    assert len(memories) == 2

    categories = {m.category for m in memories}
    assert "insights" in categories
    assert "learnings" in categories
    assert "context" not in categories  # low-confidence entry filtered out

    for memory in memories:
        assert memory.strategy == "llm"
        assert memory.metadata.get("llm_type") in {"design_decision", "problem_solved"}
        assert isinstance(memory.metadata.get("tags"), list)
        assert memory.content.endswith(".")
        assert 0.5 <= memory.relevance_score <= 1.0

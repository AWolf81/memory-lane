"""
Prompt builder for MemoryLane LLM summarization.
"""

import json
from typing import Dict, List


SYSTEM_PROMPT = (
    "You are a memory extraction assistant for MemoryLane, a developer knowledge management tool.\n\n"
    "Your task: Analyze development sessions and extract KNOWLEDGE, not actions.\n\n"
    "Extract:\n"
    "- Design decisions (why X was chosen over Y)\n"
    "- Problems solved (root cause + solution)\n"
    "- Patterns established (reusable approaches)\n"
    "- Constraints discovered (technical limitations)\n"
    "- Future considerations (TODOs, improvements)\n\n"
    "Do NOT extract:\n"
    "- Individual actions taken (\"user ran npm install\")\n"
    "- File names/paths unless architecturally significant\n"
    "- Code snippets (only describe patterns/decisions)\n"
    "- Generic advice or best practices\n\n"
    "Output format: JSON with 'summary' and 'memory_entries' array.\n"
    "Each entry has: type, content (2-3 sentences max), tags, confidence.\n\n"
    "Be concise. Focus on WHY and WHAT WAS LEARNED."
)


FEW_SHOT_EXAMPLES = [
    {
        "input": (
            "Implemented cross-project search. Created project_registry.py with auto-registration. "
            "Projects stored in ~/.memorylane/projects.json. CLI commands: list, add, remove, cleanup, search."
        ),
        "output": {
            "summary": (
                "Cross-project search implemented using central registry pattern for fast lookups and automatic "
                "project discovery."
            ),
            "memory_entries": [
                {
                    "type": "design_decision",
                    "content": (
                        "Central registry pattern chosen over distributed discovery. Single source of truth at "
                        "~/.memorylane/projects.json enables fast cross-project queries without network overhead."
                    ),
                    "tags": ["architecture", "registry", "cross-project"],
                    "confidence": 0.90
                },
                {
                    "type": "pattern_established",
                    "content": (
                        "Auto-registration pattern eliminates manual configuration. Projects self-register on first "
                        "CLI/extension use."
                    ),
                    "tags": ["ux", "automation", "configuration"],
                    "confidence": 0.88
                }
            ]
        }
    }
]


class PromptBuilder:
    """Builds prompts for LLM-based summarization."""

    def __init__(self, max_input_tokens: int = 4096):
        self.max_input_tokens = max_input_tokens

    def build_messages(self, payload: Dict) -> List[Dict[str, str]]:
        """Build chat-style messages for instruct models."""
        user_prompt = self._build_user_prompt(payload)
        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

    def build_prompt_text(self, payload: Dict) -> str:
        """Build a plain-text prompt when chat templates are unavailable."""
        user_prompt = self._build_user_prompt(payload)
        return f"{SYSTEM_PROMPT}\n\n{user_prompt}"

    def _build_user_prompt(self, payload: Dict) -> str:
        """Construct the user prompt with examples and input payload."""
        examples_json = json.dumps(FEW_SHOT_EXAMPLES, indent=2)
        payload_json = json.dumps(payload, indent=2)

        return (
            "Examples:\n"
            f"{examples_json}\n\n"
            "Input:\n"
            f"{payload_json}\n\n"
            "Return JSON only with keys: summary, memory_entries, suggested_deletions."
        )

"""
Learning prompts for MemoryLane's Claude-powered extraction.

Different triggers need different extraction strategies:
- Session end: comprehensive extraction of all valuable insights
- Task completion: capture what was built, decisions made, patterns used
- Error resolution: capture the problem, root cause, and solution
- Feature implementation: capture architecture, design rationale, gotchas
"""

from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class LearningPrompt:
    """A specialized prompt for a specific learning trigger."""
    name: str
    system_prompt: str
    extraction_focus: List[str]
    output_schema: Dict


# Base extraction principles shared across all prompts
BASE_PRINCIPLES = """
Core principles:
1. Extract KNOWLEDGE, not actions. "We use X" not "I ran X"
2. Capture the WHY behind decisions, not just the WHAT
3. Focus on reusable insights that help future work
4. Be concise - 1-2 sentences per insight maximum
5. Skip generic advice or obvious best practices
6. Extract project-specific knowledge that isn't in documentation
"""

# Output format shared across prompts
OUTPUT_SCHEMA = {
    "memories": [
        {
            "category": "patterns | insights | learnings | context",
            "content": "The actual insight (1-2 sentences)",
            "relevance": 0.0,  # 0.0-1.0, how valuable for future work
            "tags": ["tag1", "tag2"]
        }
    ]
}


SESSION_END_PROMPT = LearningPrompt(
    name="session_end",
    system_prompt=f"""You are a knowledge extractor for MemoryLane, analyzing a completed Claude Code session.

Your task: Extract ALL valuable knowledge from this session that would help a future developer (or Claude) working on this project.

{BASE_PRINCIPLES}

Categories to extract:

**patterns** - Reusable approaches, conventions, architectural decisions
- "We use Unix sockets over HTTP for lower IPC latency"
- "Context injection uses a 1500 token budget to prevent overflow"

**insights** - Discovered learnings, aha moments, non-obvious findings
- "The hook timeout was too low at 3s, causing silent failures"
- "Claude Code transcripts use JSONL with nested content arrays"

**learnings** - Bug fixes, solutions, error resolutions with root cause
- "Fixed memory corruption by deduplicating before storage, not after"
- "The issue was async timing - hooks fire before tool output is available"

**context** - Project structure, config locations, API details, dependencies
- "Memories stored in .memorylane/memories.json with ID format prefix-NNN"
- "VS Code extension communicates with Python sidecar via Unix socket"

Extract 3-10 memories. Focus on what would be most useful 6 months from now.
Skip: individual file edits, test runs, obvious fixes, conversational filler.

Return ONLY valid JSON matching this schema:
{OUTPUT_SCHEMA}""",
    extraction_focus=["decisions", "patterns", "solutions", "architecture", "gotchas"],
    output_schema=OUTPUT_SCHEMA
)


TASK_COMPLETION_PROMPT = LearningPrompt(
    name="task_completion",
    system_prompt=f"""You are a knowledge extractor for MemoryLane, analyzing a completed task.

A task was just completed. Extract the knowledge that makes this work understandable and reproducible.

{BASE_PRINCIPLES}

Focus on:
1. **What was built** - High-level summary of the feature/fix
2. **Key decisions** - Why this approach? What alternatives were considered?
3. **Integration points** - How does this connect to existing code?
4. **Gotchas encountered** - What was tricky? What might break?
5. **Patterns used** - What conventions were followed or established?

Categories:
- **patterns**: Architectural patterns, coding conventions, design decisions
- **insights**: Non-obvious discoveries, "aha" moments, things that weren't obvious
- **learnings**: Problems solved, bugs fixed, root causes identified
- **context**: File locations, config, dependencies, API contracts

Extract 2-5 memories. Each should be independently valuable.

Return ONLY valid JSON:
{OUTPUT_SCHEMA}""",
    extraction_focus=["feature_summary", "decisions", "integration", "gotchas"],
    output_schema=OUTPUT_SCHEMA
)


ERROR_RESOLUTION_PROMPT = LearningPrompt(
    name="error_resolution",
    system_prompt=f"""You are a knowledge extractor for MemoryLane, analyzing an error that was just resolved.

An error occurred and was fixed. Capture the knowledge so this mistake is never repeated.

{BASE_PRINCIPLES}

Focus on:
1. **Root cause** - What actually caused the error (not just symptoms)
2. **The fix** - What change resolved it
3. **Prevention** - How to avoid this in the future
4. **Related risks** - Similar patterns that might cause the same issue

Format each learning as:
"[Problem]: [Root cause]. [Solution/Prevention]."

Example:
"Hook timeout causing silent failures: 3s was too short for semantic search. Increased to 5s with fallback to keyword search."

Extract 1-3 memories focused on the root cause and fix.

Return ONLY valid JSON:
{OUTPUT_SCHEMA}""",
    extraction_focus=["root_cause", "fix", "prevention"],
    output_schema=OUTPUT_SCHEMA
)


FEATURE_IMPLEMENTATION_PROMPT = LearningPrompt(
    name="feature_implementation",
    system_prompt=f"""You are a knowledge extractor for MemoryLane, analyzing a feature implementation.

A new feature was just implemented. Extract knowledge that helps understand and maintain it.

{BASE_PRINCIPLES}

Focus on:
1. **Architecture** - How is this structured? What components are involved?
2. **Design rationale** - Why this design? What constraints drove it?
3. **API/Interface** - How do other parts of the system interact with this?
4. **Edge cases** - What edge cases were handled? What might break?
5. **Dependencies** - What does this depend on? What depends on this?

Categories:
- **patterns**: Architectural patterns, integration patterns, conventions followed
- **insights**: Non-obvious design decisions, trade-offs made
- **learnings**: Problems encountered during implementation, solutions
- **context**: File structure, config, environment requirements

Extract 3-6 memories. Focus on what a new developer would need to know.

Return ONLY valid JSON:
{OUTPUT_SCHEMA}""",
    extraction_focus=["architecture", "rationale", "interface", "edge_cases"],
    output_schema=OUTPUT_SCHEMA
)


REFACTOR_PROMPT = LearningPrompt(
    name="refactor",
    system_prompt=f"""You are a knowledge extractor for MemoryLane, analyzing a refactoring session.

Code was just refactored. Capture what changed and why.

{BASE_PRINCIPLES}

Focus on:
1. **Before/After** - What was the old pattern? What's the new pattern?
2. **Motivation** - Why was this change needed?
3. **Impact** - What else was affected by this change?
4. **Migration** - If there's old code elsewhere, how should it be updated?

Example:
"Migrated from callback-based hooks to Promise-based. Callbacks caused race conditions in parallel tool calls."

Extract 1-4 memories focused on the pattern change and rationale.

Return ONLY valid JSON:
{OUTPUT_SCHEMA}""",
    extraction_focus=["before_after", "motivation", "impact"],
    output_schema=OUTPUT_SCHEMA
)


DEBUGGING_PROMPT = LearningPrompt(
    name="debugging",
    system_prompt=f"""You are a knowledge extractor for MemoryLane, analyzing a debugging session.

A bug was investigated and (possibly) fixed. Extract debugging knowledge.

{BASE_PRINCIPLES}

Focus on:
1. **Symptoms** - What was observed? How did the bug manifest?
2. **Investigation** - What was checked? What was ruled out?
3. **Root cause** - What was actually wrong?
4. **Fix** - What change resolved it (if fixed)?
5. **Diagnostic tips** - How to debug similar issues faster next time?

Example:
"Hook not firing: Checked settings.json path, verified hook registration. Root cause was MEMORYLANE_ROOT not set in subprocess. Fix: Use script directory instead of env var."

Extract 1-3 memories. Focus on root cause and diagnostic approach.

Return ONLY valid JSON:
{OUTPUT_SCHEMA}""",
    extraction_focus=["symptoms", "root_cause", "diagnostics"],
    output_schema=OUTPUT_SCHEMA
)


# Registry of all prompts by trigger type
LEARNING_PROMPTS: Dict[str, LearningPrompt] = {
    "session_end": SESSION_END_PROMPT,
    "task_completion": TASK_COMPLETION_PROMPT,
    "error_resolution": ERROR_RESOLUTION_PROMPT,
    "feature_implementation": FEATURE_IMPLEMENTATION_PROMPT,
    "refactor": REFACTOR_PROMPT,
    "debugging": DEBUGGING_PROMPT,
}


def get_prompt_for_trigger(trigger: str) -> LearningPrompt:
    """Get the appropriate prompt for a learning trigger."""
    return LEARNING_PROMPTS.get(trigger, SESSION_END_PROMPT)


def detect_trigger_type(context: Dict) -> str:
    """
    Detect the appropriate trigger type from context.

    Args:
        context: Dict with keys like 'tool_name', 'has_error', 'task_completed', etc.

    Returns:
        Trigger type string
    """
    # Error resolution takes priority
    if context.get('has_error') and context.get('was_fixed'):
        return 'error_resolution'

    # Debugging if there was investigation
    if context.get('has_error') and not context.get('was_fixed'):
        return 'debugging'

    # Feature implementation if new files were created
    if context.get('new_files_created') and context.get('task_completed'):
        return 'feature_implementation'

    # Refactor if mostly edits to existing files
    if context.get('files_edited', 0) > context.get('files_created', 0) and context.get('task_completed'):
        return 'refactor'

    # Task completion is the general case for completed work
    if context.get('task_completed'):
        return 'task_completion'

    # Default to session end for full transcript analysis
    return 'session_end'


def format_extraction_request(
    prompt: LearningPrompt,
    transcript_text: str,
    project_name: Optional[str] = None,
    additional_context: Optional[str] = None
) -> str:
    """
    Format a complete extraction request for Claude.

    Args:
        prompt: The LearningPrompt to use
        transcript_text: The conversation/transcript to analyze
        project_name: Optional project name for context
        additional_context: Optional additional context (recent changes, etc.)

    Returns:
        The formatted user message
    """
    parts = []

    if project_name:
        parts.append(f"Project: {project_name}")

    if additional_context:
        parts.append(f"Context: {additional_context}")

    parts.append(f"Session transcript:\n{transcript_text}")

    return "\n\n".join(parts)

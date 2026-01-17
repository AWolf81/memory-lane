#!/usr/bin/env python3
"""
MemoryLane Session Start Curation Hook

This hook runs on SessionStart to check if memory curation is needed.
If there are new memories since the last curation, it outputs a prompt
asking Claude to review and curate them.

Input (stdin): JSON with session_id, transcript_path, cwd, etc.
Output (stdout): Curation prompt if needed, empty otherwise
Exit codes:
  0 = success
  1 = error (non-blocking)
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import List, Dict, Tuple


def check_memory_quality(memory: dict) -> List[str]:
    """
    Check a single memory for quality issues.
    Returns list of issue descriptions (empty if no issues).
    """
    issues = []
    content = memory.get('content', '')

    # Check for truncated content (ends with ... or mid-sentence)
    if content.rstrip().endswith('...'):
        issues.append("truncated (ends with ...)")

    # Check for raw code snippets (line numbers like "123→" or code patterns)
    if re.search(r'\d+→', content):
        issues.append("contains raw code line numbers")

    # Check for very short content (likely missing context)
    if len(content) < 20:
        issues.append("too short (missing context)")

    # Check for incomplete JSON or markdown artifacts
    if content.count('```') % 2 != 0:
        issues.append("incomplete code block")
    if content.count('{') != content.count('}'):
        issues.append("unbalanced braces")

    # Check for web search result artifacts
    if 'Links: [{"title"' in content or '"url":"http' in content:
        issues.append("raw web search results")

    # Check for transcript/debug artifacts
    if '"stop_reason"' in content or '"stop_se...' in content:
        issues.append("contains transcript artifacts")

    return issues


def is_obviously_corrupted(issues: List[str]) -> bool:
    """Check if issues indicate obvious corruption that should be auto-deleted."""
    corrupted_markers = [
        'raw code line numbers',
        'raw web search',
        'transcript artifacts',
        'incomplete code block',
    ]
    return any(marker in str(issues) for marker in corrupted_markers)


def auto_cleanup_corrupted(memories: list, store, curator) -> Tuple[int, list]:
    """
    Automatically delete obviously corrupted memories.
    Returns (count_deleted, remaining_memories)
    """
    deleted = 0
    remaining = []

    for m in memories:
        issues = check_memory_quality(m)
        if issues and is_obviously_corrupted(issues):
            # Auto-delete corrupted memory
            if store.delete_memory(m['id']):
                deleted += 1
                curator.mark_curated([m['id']])
        else:
            remaining.append(m)

    return deleted, remaining


def analyze_memories_quality(memories: list) -> Tuple[List[Dict], bool]:
    """
    Analyze all memories for quality issues.
    Returns (memories_with_issues, has_critical_issues)
    """
    memories_with_issues = []
    critical_count = 0

    for m in memories:
        issues = check_memory_quality(m)
        if issues:
            memories_with_issues.append({
                'memory': m,
                'issues': issues
            })
            # Consider truncated as needing review (not auto-deleted)
            if 'truncated' in str(issues):
                critical_count += 1

    # Has critical issues if more than 20% of memories have problems
    has_critical = critical_count > 0 or len(memories_with_issues) > len(memories) * 0.2

    return memories_with_issues, has_critical


def get_memorylane_root() -> Path:
    """Find the MemoryLane installation directory"""
    if 'MEMORYLANE_ROOT' in os.environ:
        return Path(os.environ['MEMORYLANE_ROOT'])

    script_dir = Path(__file__).parent
    memorylane_root = script_dir.parent.parent

    if (memorylane_root / 'src' / 'cli.py').exists():
        return memorylane_root

    project_dir = os.environ.get('CLAUDE_PROJECT_DIR', '')
    if project_dir:
        return Path(project_dir)

    return Path.cwd()


def build_curation_prompt(memories: list, quality_issues: List[Dict], has_critical: bool) -> str:
    """Build the curation prompt for Claude with quality awareness"""

    # Build issue lookup for quick access
    issue_lookup = {item['memory']['id']: item['issues'] for item in quality_issues}

    # Header varies based on quality
    if has_critical:
        lines = [
            "# Memory Curation Required - Quality Issues Detected",
            "",
            "**WARNING:** Some memories have quality issues that need attention.",
            "Please review and fix these before proceeding with other tasks.",
            "",
            "For each memory, decide: **KEEP**, **DELETE**, or **REWRITE** (with improved content).",
            "",
        ]
    else:
        lines = [
            "# Memory Curation Available",
            "",
            "Before we begin, please review these memories from previous sessions.",
            "For each memory, decide: **KEEP**, **DELETE**, or **REWRITE** (with improved content).",
            "",
        ]

    # Show quality summary if issues exist
    if quality_issues:
        lines.extend([
            "## Quality Issues Found",
            "",
        ])
        for item in quality_issues:
            m = item['memory']
            issues_str = ", ".join(item['issues'])
            lines.append(f"- **{m['id']}**: {issues_str}")
        lines.append("")

    lines.append("## Memories to Review")
    lines.append("")

    # Group by category
    by_category = {}
    for m in memories:
        cat = m['category']
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(m)

    for category, mems in by_category.items():
        lines.append(f"### {category.title()} ({len(mems)})")
        lines.append("")
        for m in mems:
            # Mark memories with issues
            issue_marker = ""
            if m['id'] in issue_lookup:
                issue_marker = " ⚠️ NEEDS ATTENTION"

            lines.append(f"- **{m['id']}** (relevance: {m['relevance_score']:.2f}){issue_marker}")
            lines.append(f"  {m['content']}")
            lines.append("")

    # Instructions for Claude - direct action required
    if has_critical:
        lines.extend([
            "## Action Required",
            "",
            "Automatically curate these memories NOW by running the curate command with your decisions.",
            "DELETE corrupted memories (raw code, truncated, duplicates) and KEEP valid insights.",
            "",
        ])
    else:
        lines.extend([
            "## Action",
            "",
            "Review and curate these memories, or continue with the user's task if no issues.",
            "",
        ])

    lines.append("")

    return "\n".join(lines)


def log_debug(msg: str):
    """Write debug log to help diagnose hook issues"""
    try:
        log_file = Path(__file__).parent.parent.parent / '.memorylane' / 'hook-debug.log'
        log_file.parent.mkdir(parents=True, exist_ok=True)
        from datetime import datetime
        with open(log_file, 'a') as f:
            f.write(f"[{datetime.now().isoformat()}] SessionStart: {msg}\n")
    except:
        pass


def main():
    try:
        log_debug("Hook triggered")

        # Read input from stdin
        input_data = sys.stdin.read()
        log_debug(f"Input received: {input_data[:200]}...")

        # Find MemoryLane root
        memorylane_root = get_memorylane_root()

        # Add src to path for imports
        sys.path.insert(0, str(memorylane_root / 'src'))

        from config_manager import ConfigManager
        from memory_store import MemoryStore
        from curation_manager import CurationManager

        # Load configuration
        config = ConfigManager()

        # Check if curation is enabled
        curation_enabled = config.get('curation.enabled', False)
        log_debug(f"Curation enabled: {curation_enabled}")
        if not curation_enabled:
            sys.exit(0)

        # Load memory store and curation manager
        store = MemoryStore(str(config.get_path('memories_file')))
        curator = CurationManager()

        # Get stats and check if curation is needed
        stats = store.get_stats()
        needs_curation = curator.needs_curation(config.config, stats['total_memories'])
        log_debug(f"Total memories: {stats['total_memories']}, needs_curation: {needs_curation}")
        if not needs_curation:
            sys.exit(0)

        # Get uncurated memories
        reviewed_ids = curator.get_reviewed_ids()
        max_review = config.get('curation.max_memories_per_review', 20)
        uncurated = store.get_uncurated_memories(reviewed_ids, limit=max_review)

        log_debug(f"Uncurated memories: {len(uncurated)}")
        if not uncurated:
            sys.exit(0)

        # Auto-cleanup obviously corrupted memories (raw code, artifacts, etc.)
        auto_deleted, remaining = auto_cleanup_corrupted(uncurated, store, curator)
        if auto_deleted > 0:
            log_debug(f"Auto-deleted {auto_deleted} corrupted memories")

        # If nothing left after cleanup, we're done
        if not remaining:
            if auto_deleted > 0:
                print(f"Auto-cleaned {auto_deleted} corrupted memories.")
            sys.exit(0)

        # Analyze remaining memories for issues needing human review
        quality_issues, has_critical = analyze_memories_quality(remaining)
        log_debug(f"Remaining: {len(remaining)}, quality issues: {len(quality_issues)}, critical: {has_critical}")

        # Only show prompt if there are issues needing review
        if not quality_issues and not has_critical:
            # Mark clean memories as reviewed
            curator.mark_curated([m['id'] for m in remaining])
            if auto_deleted > 0:
                print(f"Auto-cleaned {auto_deleted} corrupted memories.")
            sys.exit(0)

        # Output curation prompt for memories needing human review
        prompt = build_curation_prompt(remaining, quality_issues, has_critical)
        if auto_deleted > 0:
            prompt = f"Auto-cleaned {auto_deleted} corrupted memories.\n\n" + prompt
        log_debug(f"Outputting curation prompt ({len(prompt)} chars)")
        print(prompt)

        sys.exit(0)

    except Exception as e:
        # Log error but don't block session start
        try:
            log_file = Path(__file__).parent.parent.parent / '.memorylane' / 'hook-debug.log'
            log_file.parent.mkdir(parents=True, exist_ok=True)
            from datetime import datetime
            with open(log_file, 'a') as f:
                f.write(f"[{datetime.now().isoformat()}] SessionStart curation error: {e}\n")
        except:
            pass
        sys.exit(0)


if __name__ == '__main__':
    main()

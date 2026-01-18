#!/usr/bin/env python3
"""
MemoryLane Session Learning Hook for Claude Code

This hook runs on Stop event to extract and store learnings from the session.
Uses Claude-powered extraction for high-quality memory capture.

Input (stdin): JSON with session_id, transcript_path
Output: None (memories are stored directly)
Exit codes:
  0 = success (always, to avoid blocking Claude Code)
"""

import json
import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime


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


def log_debug(msg: str):
    """Write debug log to help diagnose hook issues"""
    log_file = Path(__file__).parent.parent.parent / '.memorylane' / 'hook-debug.log'
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with open(log_file, 'a') as f:
        f.write(f"[{datetime.now().isoformat()}] {msg}\n")


def extract_with_claude(transcript_path: str, memorylane_root: Path) -> bool:
    """
    Use Claude-powered extraction for high-quality memories.

    Returns True if extraction succeeded, False to fall back to regex.
    """
    try:
        # Add src to path for imports
        src_dir = memorylane_root / 'src'
        if str(src_dir) not in sys.path:
            sys.path.insert(0, str(src_dir))

        from claude_extractor import extract_from_transcript
        from memory_store import MemoryStore

        log_debug("Using Claude-powered extraction")

        # Extract memories using Claude
        project_name = memorylane_root.name
        memories = extract_from_transcript(
            transcript_path=transcript_path,
            trigger="session_end",
            project_name=project_name,
        )

        if not memories:
            log_debug("No memories extracted by Claude, falling back to regex")
            return False

        log_debug(f"Claude extracted {len(memories)} memories")

        # Store memories
        store = MemoryStore(memorylane_root / '.memorylane' / 'memories.json')

        stored_count = 0
        for memory in memories:
            # Check for duplicates
            existing = store.get_memories(category=memory.category)
            content_lower = memory.content.lower()[:50]
            is_duplicate = any(
                content_lower in m.get('content', '').lower()
                for m in existing
            )

            if not is_duplicate:
                store.add_memory(
                    category=memory.category,
                    content=memory.content,
                    relevance_score=memory.relevance,
                    source="claude_extraction",
                    metadata={"tags": memory.tags},
                )
                stored_count += 1

        log_debug(f"Stored {stored_count} new memories (skipped {len(memories) - stored_count} duplicates)")
        return True

    except ImportError as e:
        log_debug(f"Import error for Claude extraction: {e}")
        return False
    except Exception as e:
        log_debug(f"Claude extraction failed: {e}")
        return False


def extract_with_regex(transcript_path: str, memorylane_root: Path):
    """Fall back to CLI-based regex extraction."""
    cli_path = memorylane_root / 'src' / 'cli.py'

    if not cli_path.exists():
        log_debug(f"CLI not found at {cli_path}")
        return

    log_debug(f"Falling back to regex extraction via CLI")
    result = subprocess.run(
        [
            sys.executable,
            str(cli_path),
            'learn',
            '--transcript', transcript_path,
            '--quiet'
        ],
        cwd=str(memorylane_root),
        capture_output=True,
        text=True,
        timeout=10
    )
    log_debug(f"CLI result: returncode={result.returncode}")


def main():
    try:
        log_debug("Stop hook triggered")

        # Read input from stdin
        input_data = sys.stdin.read()
        log_debug(f"Input received: {input_data[:200]}..." if len(input_data) > 200 else f"Input received: {input_data}")

        if not input_data.strip():
            log_debug("Empty input, exiting")
            sys.exit(0)

        # Parse JSON input
        try:
            request = json.loads(input_data)
        except json.JSONDecodeError as e:
            log_debug(f"JSON decode error: {e}")
            sys.exit(0)

        # Get transcript path
        transcript_path = request.get('transcript_path', '')
        log_debug(f"Transcript path: {transcript_path}")

        if not transcript_path:
            log_debug("No transcript_path in request")
            sys.exit(0)

        if not Path(transcript_path).exists():
            log_debug(f"Transcript file does not exist: {transcript_path}")
            sys.exit(0)

        # Find MemoryLane root
        memorylane_root = get_memorylane_root()
        log_debug(f"MemoryLane root: {memorylane_root}")

        # Try Claude-powered extraction first, fall back to regex
        if not extract_with_claude(transcript_path, memorylane_root):
            extract_with_regex(transcript_path, memorylane_root)

        # Exit silently regardless of result
        sys.exit(0)

    except Exception as e:
        log_debug(f"Exception: {e}")
        sys.exit(0)


if __name__ == '__main__':
    main()

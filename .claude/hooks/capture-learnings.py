#!/usr/bin/env python3
"""
MemoryLane Session Learning Hook for Claude Code

This hook runs on Stop event to extract and store learnings from the session.

Input (stdin): JSON with session_id, transcript_path
Output: None (memories are stored directly)
Exit codes:
  0 = success
  1 = error (non-blocking)
"""

import json
import os
import sys
import subprocess
from pathlib import Path


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
    from datetime import datetime
    with open(log_file, 'a') as f:
        f.write(f"[{datetime.now().isoformat()}] {msg}\n")


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
        cli_path = memorylane_root / 'src' / 'cli.py'
        log_debug(f"MemoryLane root: {memorylane_root}, CLI exists: {cli_path.exists()}")

        if not cli_path.exists():
            log_debug(f"CLI not found at {cli_path}")
            sys.exit(0)

        # Call MemoryLane CLI to learn from transcript
        log_debug(f"Calling: {sys.executable} {cli_path} learn --transcript {transcript_path}")
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
        log_debug(f"CLI result: returncode={result.returncode}, stdout={result.stdout[:200] if result.stdout else 'empty'}, stderr={result.stderr[:200] if result.stderr else 'empty'}")

        # Exit silently regardless of result
        sys.exit(0)

    except Exception as e:
        log_debug(f"Exception: {e}")
        sys.exit(0)


if __name__ == '__main__':
    main()

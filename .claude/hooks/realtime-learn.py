#!/usr/bin/env python3
"""
MemoryLane Real-Time Learning Hook for Claude Code

Runs on PostToolUse to capture learnings as they happen, not just at session end.
Captures both action-based learning (errors, fixes) and knowledge-based learning (reading docs).

Input (stdin): JSON with tool_name, tool_input, tool_response
Output: None (memories stored directly)
"""

import json
import os
import re
import sys
import subprocess
from pathlib import Path
from typing import List, Tuple


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


def extract_decisions_from_content(content: str, file_path: str = '') -> List[str]:
    """
    Extract architectural decisions and rationale from document content.

    Looks for patterns like:
    - "X over Y: reason" in bullet points
    - Architecture decision sections
    """
    learnings = []

    # Pattern 1: "**X over Y**: reason" or "- X over Y: reason" (clean decision format)
    decision_pattern = r'[-•*]\s*\*?\*?([A-Za-z][A-Za-z0-9 _-]{1,30}?)\s+over\s+([A-Za-z][A-Za-z0-9 _-]{1,30}?)\*?\*?\s*[:\-–]\s*([^\n]{10,80})'
    for match in re.finditer(decision_pattern, content, re.IGNORECASE):
        choice, alternative, reason = match.groups()
        choice = choice.strip('*_ ')
        alternative = alternative.strip('*_ ')
        reason = reason.strip('*_ ')
        if choice and alternative and reason:
            statement = f"Chose {choice} over {alternative}: {reason}"
            learnings.append(statement)

    # Pattern 2: Explicit architecture decision headers followed by bullets
    arch_section = re.search(
        r'#+\s*(?:Architecture|Design)\s*(?:Decisions?|Choices?)?\s*\n((?:[-•*]\s*[^\n]+\n?)+)',
        content,
        re.IGNORECASE
    )
    if arch_section:
        bullets = re.findall(r'[-•*]\s*\*?\*?([^\n*]{20,100})', arch_section.group(1))
        for bullet in bullets[:3]:  # Max 3 from this section
            bullet = bullet.strip('*_ :')
            if bullet and 'over' in bullet.lower():
                learnings.append(bullet)

    # Pattern 3: Key configuration/location info
    config_pattern = r'[-•*]\s*(?:stored|saved|located|config\w*)\s+(?:in|at)\s+([^\n]{10,60})'
    for match in re.finditer(config_pattern, content, re.IGNORECASE):
        learnings.append(f"Configuration: {match.group(1).strip()}")

    # Deduplicate
    seen = set()
    unique = []
    for l in learnings:
        # Normalize for dedup
        sig = re.sub(r'[^a-z0-9]', '', l.lower())[:30]
        if sig not in seen and len(l) > 20:
            seen.add(sig)
            unique.append(l)

    return unique[:5]  # Max 5 learnings per Read


def is_high_value_event(tool_name: str, tool_input: dict, tool_response: str) -> Tuple[bool, List[str]]:
    """
    Determine if this tool use is worth learning from.

    Returns (should_learn, list_of_extracted_texts)
    """
    learnings = []
    response_lower = tool_response.lower() if tool_response else ''

    # ===== READ TOOL: Extract knowledge from documents =====
    if tool_name == 'Read':
        file_path = tool_input.get('file_path', '')

        # Only process knowledge-rich files
        knowledge_files = ['readme', 'claude.md', 'contributing', 'architecture',
                          'design', 'adr', 'decision', 'changelog', 'config']
        is_knowledge_file = any(kf in file_path.lower() for kf in knowledge_files)

        if is_knowledge_file and tool_response:
            decisions = extract_decisions_from_content(tool_response, file_path)
            learnings.extend(decisions)

    # ===== BASH TOOL: Errors and test results =====
    elif tool_name == 'Bash':
        # Learn from errors
        if any(err in response_lower for err in ['error', 'failed', 'exception', 'traceback']):
            lines = tool_response.split('\n')
            error_lines = [l for l in lines if any(e in l.lower() for e in ['error', 'failed', 'exception'])]
            if error_lines:
                learnings.append(f"Error encountered: {error_lines[-1][:150]}")

        # Learn from successful test runs
        command = tool_input.get('command', '')
        if 'pytest' in command or 'npm test' in command or 'test' in command:
            if 'passed' in response_lower and 'failed' not in response_lower:
                match = re.search(r'(\d+)\s*passed', response_lower)
                if match:
                    learnings.append(f"All {match.group(1)} tests passing after changes")

    # ===== EDIT TOOL: Fixes =====
    elif tool_name == 'Edit':
        if 'fix' in str(tool_input).lower():
            old_string = tool_input.get('old_string', '')[:50]
            new_string = tool_input.get('new_string', '')[:50]
            if old_string and new_string:
                learnings.append(f"Fixed by changing '{old_string}...' to '{new_string}...'")

    # ===== WRITE TOOL: New configurations =====
    elif tool_name == 'Write':
        file_path = tool_input.get('file_path', '')
        if file_path:
            if any(p in file_path for p in ['/hooks/', '/src/', 'config', 'settings']):
                learnings.append(f"Created {Path(file_path).name} for project configuration")

    return bool(learnings), learnings


def main():
    try:
        input_data = sys.stdin.read()

        if not input_data.strip():
            sys.exit(0)

        try:
            request = json.loads(input_data)
        except json.JSONDecodeError:
            sys.exit(0)

        tool_name = request.get('tool_name', '')
        tool_input = request.get('tool_input', {})
        tool_response = request.get('tool_response', '')

        # Check if this is worth learning from
        should_learn, learnings = is_high_value_event(tool_name, tool_input, tool_response)

        if not should_learn or not learnings:
            sys.exit(0)

        # Find MemoryLane and store the learnings
        memorylane_root = get_memorylane_root()
        cli_path = memorylane_root / 'src' / 'cli.py'

        if not cli_path.exists():
            sys.exit(0)

        # Learn each extracted piece
        for learning in learnings:
            subprocess.run(
                [
                    sys.executable,
                    str(cli_path),
                    'learn',
                    '--text', learning,
                    '--quiet'
                ],
                cwd=str(memorylane_root),
                capture_output=True,
                timeout=3
            )

        sys.exit(0)

    except Exception:
        sys.exit(0)


if __name__ == '__main__':
    main()

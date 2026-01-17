#!/usr/bin/env python3
"""
MemoryLane Context Injection Hook for Claude Code

This hook runs on UserPromptSubmit to inject relevant project context
from MemoryLane memories into Claude's context.

Input (stdin): JSON with prompt field
Output (stdout): Context to inject (plain text)
Exit codes:
  0 = success, stdout added as context
  1 = error (logged, non-blocking)
  2 = block prompt (show stderr to user)
"""

import json
import os
import sys
import subprocess
from pathlib import Path


DEFAULT_MAX_CONTEXT_TOKENS = 2000
DEFAULT_CONTEXT_ROT = {
    "enabled": True,
    "model_context_tokens": 200000,
    "safe_fraction": 0.5,
    "reserve_tokens": 1200,
    "min_injection_tokens": 200
}


def get_memorylane_root() -> Path:
    """Find the MemoryLane installation directory"""
    # Check environment variable first
    if 'MEMORYLANE_ROOT' in os.environ:
        return Path(os.environ['MEMORYLANE_ROOT'])

    # Check relative to this script (hooks are in .claude/hooks/)
    script_dir = Path(__file__).parent
    memorylane_root = script_dir.parent.parent

    # Verify it's the right directory
    if (memorylane_root / 'src' / 'cli.py').exists():
        return memorylane_root

    # Fall back to CLAUDE_PROJECT_DIR
    project_dir = os.environ.get('CLAUDE_PROJECT_DIR', '')
    if project_dir:
        return Path(project_dir)

    return Path.cwd()


def estimate_tokens(text: str) -> int:
    """Rough token estimate using word count."""
    words = text.split()
    return int(len(words) * 1.3)


def load_config(memorylane_root: Path) -> dict:
    """Load config from .memorylane/config.json if present."""
    config_path = memorylane_root / ".memorylane" / "config.json"
    if not config_path.exists():
        return {}

    try:
        with open(config_path, "r") as config_file:
            data = json.load(config_file)
            return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def get_config_value(config: dict, key_path: str, default):
    """Get a nested config value using dot notation."""
    value = config
    for key in key_path.split("."):
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return default
    return value


def extract_keywords(prompt: str) -> str:
    """Extract meaningful keywords from the prompt for search"""
    # Domain-specific terms to always keep (high value for this project)
    domain_terms = {
        'memory', 'memories', 'context', 'compression', 'hook', 'hooks',
        'socket', 'sidecar', 'server', 'cli', 'api', 'ipc', 'unix',
        'relevance', 'threshold', 'semantic', 'embedding', 'embeddings',
        'token', 'tokens', 'cost', 'savings', 'injection', 'inject',
        'learner', 'learning', 'adaptive', 'surprise', 'compressor',
        'vscode', 'extension', 'typescript', 'python', 'json', 'jsonl',
        'store', 'backup', 'config', 'configuration', 'settings',
        'test', 'tests', 'pytest', 'error', 'debug', 'fix', 'bug'
    }

    # Common words to filter out
    stop_words = {
        'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
        'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
        'would', 'could', 'should', 'may', 'might', 'must', 'shall',
        'can', 'need', 'dare', 'ought', 'used', 'to', 'of', 'in',
        'for', 'on', 'with', 'at', 'by', 'from', 'as', 'into',
        'through', 'during', 'before', 'after', 'above', 'below',
        'between', 'under', 'again', 'further', 'then', 'once',
        'here', 'there', 'when', 'where', 'why', 'how', 'all',
        'each', 'few', 'more', 'most', 'other', 'some', 'such',
        'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'than',
        'too', 'very', 'just', 'and', 'but', 'if', 'or', 'because',
        'until', 'while', 'this', 'that', 'these', 'those', 'i',
        'me', 'my', 'myself', 'we', 'our', 'ours', 'ourselves',
        'you', 'your', 'yours', 'yourself', 'yourselves', 'he',
        'him', 'his', 'himself', 'she', 'her', 'hers', 'herself',
        'it', 'its', 'itself', 'they', 'them', 'their', 'theirs',
        'themselves', 'what', 'which', 'who', 'whom', 'please',
        'help', 'want', 'like', 'make', 'get', 'let', 'know'
    }

    words = prompt.lower().split()
    keywords = []

    for w in words:
        clean_word = w.strip('.,!?()[]{}":;\'')
        # Keep domain terms regardless of length
        if clean_word in domain_terms:
            keywords.append(clean_word)
        # Keep other words if not stop words and long enough
        elif clean_word not in stop_words and len(clean_word) > 2:
            keywords.append(clean_word)

    return ' '.join(keywords[:20])  # Limit to 20 keywords


def main():
    try:
        # Read input from stdin
        input_data = sys.stdin.read()

        if not input_data.strip():
            # No input, nothing to do
            sys.exit(0)

        # Parse JSON input
        try:
            request = json.loads(input_data)
        except json.JSONDecodeError:
            # Not JSON, treat as raw prompt
            request = {'prompt': input_data}

        prompt = request.get('prompt', '')

        if not prompt:
            sys.exit(0)

        memorylane_root = get_memorylane_root()
        config = load_config(memorylane_root)

        max_context_tokens = get_config_value(
            config,
            "memory.max_context_tokens",
            DEFAULT_MAX_CONTEXT_TOKENS
        )

        rot_enabled = get_config_value(
            config,
            "context_rot.enabled",
            DEFAULT_CONTEXT_ROT["enabled"]
        )

        if rot_enabled:
            model_context_tokens = get_config_value(
                config,
                "context_rot.model_context_tokens",
                DEFAULT_CONTEXT_ROT["model_context_tokens"]
            )
            safe_fraction = get_config_value(
                config,
                "context_rot.safe_fraction",
                DEFAULT_CONTEXT_ROT["safe_fraction"]
            )
            reserve_tokens = get_config_value(
                config,
                "context_rot.reserve_tokens",
                DEFAULT_CONTEXT_ROT["reserve_tokens"]
            )
            min_injection_tokens = get_config_value(
                config,
                "context_rot.min_injection_tokens",
                DEFAULT_CONTEXT_ROT["min_injection_tokens"]
            )

            safe_budget = int(model_context_tokens * safe_fraction)
            prompt_tokens = estimate_tokens(prompt)
            available_tokens = safe_budget - prompt_tokens - reserve_tokens

            if available_tokens < min_injection_tokens:
                sys.exit(0)

            max_context_tokens = min(max_context_tokens, available_tokens)

        if max_context_tokens <= 0:
            sys.exit(0)

        # Extract keywords from prompt
        query = extract_keywords(prompt)

        if not query:
            sys.exit(0)

        cli_path = memorylane_root / 'src' / 'cli.py'

        if not cli_path.exists():
            # MemoryLane not found, exit silently
            sys.exit(0)

        # Check if memories exist
        memories_file = memorylane_root / '.memorylane' / 'memories.json'
        if not memories_file.exists():
            # No memories yet, exit silently
            sys.exit(0)

        # Call MemoryLane CLI to get context
        result = subprocess.run(
            [
                sys.executable,  # Use same Python interpreter
                str(cli_path),
                'context',
                query,
                '--max-tokens', str(max_context_tokens),
                '--min-relevance', '0.6',  # Higher threshold for focused results
                '--limit', '10'
            ],
            cwd=str(memorylane_root),
            capture_output=True,
            text=True,
            timeout=5  # 5 second timeout
        )

        if result.returncode == 0 and result.stdout.strip():
            # Output context for injection
            context = result.stdout.strip()
            if context and not context.startswith('# Project Context'):
                # Add header if not present
                print("# Project Context (from MemoryLane)\n")
            print(context)

            # Add quality check instruction for Claude
            print("\n---")
            print("If memories above appear truncated (...), meta/self-referential, or low-quality, offer to curate them.")

        sys.exit(0)

    except subprocess.TimeoutExpired:
        # Timeout - don't block, just skip
        sys.exit(0)
    except Exception as e:
        # Log error but don't block
        print(f"MemoryLane hook error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()

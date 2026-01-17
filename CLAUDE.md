# MemoryLane

Zero-config persistent memory for Claude with automatic cost savings.

## Project Overview

MemoryLane gives AI assistants persistent memory through adaptive learning, reducing API costs by 84%+ while improving code suggestions through project context awareness. Local-first, privacy-focused.

## Tech Stack

- **Python Sidecar**: Core memory engine, CLI, server (src/)
- **TypeScript Extension**: VS Code integration (vscode-extension/)
- **No Production Dependencies**: Pure Python 3.8+
- **Testing**: pytest (requirements-dev.txt)

## Key Directories

```
src/                    # Python core (memory, CLI, server, compression)
vscode-extension/       # VS Code extension (TypeScript)
tests/                  # pytest tests
docs/                   # Documentation and decision records
.planning/              # Project planning files
```

## Core Components

| File | Purpose |
|------|---------|
| `src/memory_store.py` | JSON-based persistent memory storage |
| `src/config_manager.py` | Configuration with smart defaults |
| `src/cli.py` | Command-line interface |
| `src/server.py` | Unix socket IPC sidecar server |
| `src/learner.py` | Passive learning from git/files |
| `src/compressor.py` | Context compression engine |
| `src/semantic_search.py` | Optional semantic similarity search |
| `src/conversation_learner.py` | Extracts memories from conversations |
| `.claude/hooks/inject-context.py` | UserPromptSubmit: inject context before prompts |
| `.claude/hooks/realtime-learn.py` | PostToolUse: learn from errors/fixes as they happen |
| `.claude/hooks/capture-learnings.py` | Stop: extract learnings from full transcript |

## Commands

```bash
# Run tests
pytest

# CLI usage
python3 src/cli.py status
python3 src/cli.py recall "query"
python3 src/cli.py insights
python3 src/cli.py costs
python3 src/cli.py context "query"  # Get context for injection
python3 src/cli.py learn --text "..."  # Learn from conversation

# Server
python3 src/server.py start
python3 src/server.py stop

# Learning
python3 src/learner.py initial
```

## Automatic Context Injection

MemoryLane uses Claude Code hooks to automatically inject relevant context into every prompt.

**How it works:**
1. `UserPromptSubmit` hook triggers on each prompt
2. Hook extracts keywords from the prompt
3. Queries MemoryLane for relevant memories (semantic search if available, keyword fallback)
4. Compresses context to ~1500 tokens
5. Injects context before Claude processes the prompt

**Configuration:** `.claude/settings.json`
```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"$CLAUDE_PROJECT_DIR/.claude/hooks/inject-context.py\"",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

**Hook location:** `.claude/hooks/inject-context.py`

**Disable temporarily:** Remove or rename `.claude/settings.json`

## Data Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                         LEARNING PIPELINE                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  User Prompt ──▶ [UserPromptSubmit Hook] ──▶ Inject Context         │
│                         │                          │                 │
│                         ▼                          ▼                 │
│              inject-context.py           Claude sees memories        │
│              - Extract keywords                    │                 │
│              - Query memories                      ▼                 │
│              - Compress to 1500 tokens    Claude Response            │
│                                                    │                 │
│                                                    ▼                 │
│                                          [PostToolUse Hook]         │
│                                                    │                 │
│                                                    ▼                 │
│                                          realtime-learn.py          │
│                                          - Capture errors            │
│                                          - Capture fixes             │
│                                          - Learn immediately         │
│                                                    │                 │
│                                                    ▼                 │
│                                             Session End              │
│                                                    │                 │
│                                                    ▼                 │
│                                            [Stop Hook]               │
│                                                    │                 │
│                                                    ▼                 │
│                                          capture-learnings.py        │
│                                          - Parse full transcript     │
│                                          - Extract remaining insights│
│                                                    │                 │
│                                                    ▼                 │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │              .memorylane/memories.json                        │   │
│  │  patterns | insights | learnings | context                    │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

## Conversation Learning

MemoryLane automatically learns from conversations via three mechanisms:

**1. Real-Time Learning (PostToolUse)** - Learns immediately after Bash/Edit/Write
```json
"PostToolUse": [{"matcher": "Bash|Edit|Write", "hooks": [...realtime-learn.py]}]
```
Captures: errors, fixes, successful test runs, new config files

**2. Session End Learning (Stop)** - Extracts from full transcript
```json
"Stop": [{"hooks": [...capture-learnings.py]}]
```
Captures: architectural decisions, patterns, insights missed by real-time

**3. Manual Learning** - Extract insights from text or transcripts
```bash
# Learn from text
python3 src/cli.py learn --text "The fix was to capture stderr..."

# Learn from transcript file
python3 src/cli.py learn --transcript /path/to/transcript.jsonl

# Pipe text to learn
echo "We use Unix sockets for lower latency" | python3 src/cli.py learn
```

**What gets extracted:**
- Bug patterns and solutions ("fixed by...", "the issue was...")
- Architectural decisions ("chose X over Y because...")
- Configuration knowledge ("config at...", "file location...")
- Code patterns ("pattern:", "always/never when...")

## Architecture Decisions

- **Unix sockets over HTTP**: Lower latency for IPC
- **JSON over SQLite**: Simpler for MVP
- **pip over Poetry**: Zero production dependencies
- **Local-first**: All data stays on machine, encrypted at rest

## Current Status

MVP Complete with:
- 84.3% validated cost savings
- 6.4x compression ratio
- 21/21 tests passing
- VS Code extension scaffolded

## Code Patterns

- Timestamped backups in .memorylane/backups/
- Configuration stored in .memorylane/config.json
- Memories stored in .memorylane/memories.json

## Semantic Search (Opt-in)

Enable smarter memory recall by installing optional dependencies:

```bash
pip install sentence-transformers torch
```

When installed:
- Uses `all-MiniLM-L6-v2` model (80MB, runs on any modern CPU)
- LRU cache for repeated queries (1000 entries default)
- ~50ms embedding time on CPU
- Cosine similarity for relevance scoring

When not installed:
- Falls back to keyword-based search
- Zero additional dependencies

## Adaptive Threshold System

Pure Python algorithm that determines what's worth remembering:

- **Surprise-based learning**: Only memorize unexpected/important content
- **Dynamic thresholds**: Start permissive (learn everything), become selective as memory grows
- **Warmup period**: First ~100 interactions establish baseline patterns
- **Percentile-based cutoff**: Uses 75th percentile of surprise distribution after warmup
- **EMA smoothing**: Prevents threshold oscillation

```python
# Core logic
if num_updates < warmup:
    threshold = low  # Learn everything initially
else:
    threshold = percentile_75(surprise_history)  # Be selective

should_learn = surprise > threshold
```

## Session Capture Format

JSONL-based interaction logging:

- Append-only format (one JSON object per line)
- Fields: turn_id (UUID), user_prompt, assistant_response, timestamp, surprise_score, was_learned
- Efficient for streaming and incremental writes
- Session statistics: learned turns count, average surprise

## Optional Dependencies

| Package | Purpose | Size | CPU OK |
|---------|---------|------|--------|
| `sentence-transformers` | Semantic search | ~80MB | Yes |
| `torch` | Tensor ops for embeddings | ~150MB | Yes |

Core functionality works without these - they enable "smart recall" mode.

## Internal References

*For future development context:*

| Feature | Inspired By | Notes |
|---------|-------------|-------|
| Memory storage patterns | ace-system-skill | JSON storage, backup system, CLI structure |
| Semantic embeddings | MaaS-self-learning | AdaptiveEmbedder with LRU cache |
| Adaptive thresholds | MaaS-self-learning | AdaptiveThresholdManager |
| Session capture | MaaS-self-learning | JSONL format, SessionTurn dataclass |
| Surprise-based learning | Titans architecture | Learn what's unexpected |

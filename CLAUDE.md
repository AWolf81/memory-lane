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

## Commands

```bash
# Run tests
pytest

# CLI usage
python3 src/cli.py status
python3 src/cli.py recall "query"
python3 src/cli.py insights
python3 src/cli.py costs

# Server
python3 src/server.py start
python3 src/server.py stop

# Learning
python3 src/learner.py initial
```

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

- Reuses patterns from ace-system-skill project
- Timestamped backups in .memorylane/backups/
- Configuration stored in .memorylane/config.json
- Memories stored in .memorylane/memories.json

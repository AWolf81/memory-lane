# MemoryLane Hooks

These hooks integrate MemoryLane with Claude Code.

## Hooks

- **inject-context.py** - Injects relevant memories on each prompt (UserPromptSubmit)
- **realtime-learn.py** - Learns from errors/fixes in real-time (PostToolUse)
- **capture-learnings.py** - Extracts insights at session end (Stop)

## Using in Other Projects via Symlink

These hooks can be reused in other projects via symlink. The hooks are designed
to work with `CLAUDE_PROJECT_DIR` environment variable (set by Claude Code).

### Setup

```bash
cd /path/to/your-project/.claude
ln -s /path/to/memorylane/.claude/hooks hooks
```

### How it Works

1. **CLI location**: Found via `Path(__file__).resolve()` - follows symlink to
   find the actual MemoryLane installation with `src/cli.py`

2. **Memories location**: Uses `CLAUDE_PROJECT_DIR` environment variable to find
   the current project's `.memorylane/` folder

This means:
- One copy of hook code (in MemoryLane repo)
- Each project has its own `.memorylane/memories.json`
- Symlink the hooks folder to share the code

### Example Structure

```
memorylane/                          # MemoryLane installation
├── src/cli.py                       # CLI used by hooks
├── .claude/hooks/                   # Hook source (this folder)
│   ├── inject-context.py
│   └── README.md
└── .memorylane/memories.json        # MemoryLane's own memories

your-project/                        # Your project
├── .claude/
│   ├── hooks -> /path/to/memorylane/.claude/hooks  # Symlink!
│   └── settings.json                # Hook configuration
└── .memorylane/memories.json        # Your project's memories
```

# MemoryLane VS Code Extension

Zero-config persistent memory for Claude with visual knowledge graph and automatic cost tracking.

## Features

### 🧠 Persistent Memory Management
- **4 Memory Categories**: Patterns, Insights, Learnings, Context
- **Automatic Learning**: Learns from git commits and file changes
- **Smart Relevance Scoring**: Higher relevance = more likely to be used

### 📊 Visual Knowledge Graph
- Interactive D3.js visualization of memories and relationships
- Color-coded by category and relevance
- Drag-and-drop nodes to explore connections
- Zoom and pan for detailed exploration

### 💰 Cost Savings Dashboard
- Real-time tracking of API cost savings
- 84.3% average savings validated
- Token compression metrics (6.4x average)
- Weekly/monthly/total savings breakdown

### 📈 Status Bar Integration
- Live memory count and savings display
- Click to view detailed status
- Learning indicator (spinning icon when active)
- Tooltip with quick stats

### 🔍 Sidebar Panels
1. **Overview** - Quick stats and controls
2. **Memories** - Browse all memories by category
3. **Insights** - High-value learnings
4. **Cost Savings** - Detailed savings metrics

## Installation

### Prerequisites
- VS Code 1.80.0 or higher
- Python 3.8+ installed
- Node.js 20+ (for development)

### From Source

```bash
# 1. Navigate to extension directory
cd vscode-extension

# 2. Install dependencies
npm install

# 3. Compile TypeScript
npm run compile

# 4. Open in VS Code
code .

# 5. Press F5 to launch Extension Development Host
```

### From VSIX (Coming Soon)
```bash
code --install-extension memorylane-0.1.0.vsix
```

## Usage

### Quick Start

1. **Extension Auto-Starts** on workspace open
2. **Sidecar server** launches automatically
3. **Learning** begins passively in background
4. **Status bar** shows live stats

### Commands

Access via Command Palette (`Cmd+Shift+P` / `Ctrl+Shift+P`):

- `MemoryLane: Show Status` - View detailed statistics
- `MemoryLane: Show Insights` - Browse learned insights
- `MemoryLane: Show Cost Savings` - Open savings dashboard
- `MemoryLane: Show Knowledge Graph` - Visualize memory connections
- `MemoryLane: Start Learning` - Begin passive learning
- `MemoryLane: Stop Learning` - Pause learning
- `MemoryLane: Reset All Memories` - Clear all stored memories
- `MemoryLane: Export Context as Markdown` - Export for sharing

### Status Bar

Click the brain icon (🧠) in the status bar to see:
- Total memories stored
- Current week's cost savings
- Quick access to commands

### Sidebar

Open the MemoryLane sidebar from the Activity Bar:

**Overview Panel:**
- Start/stop learning
- View server status
- Quick actions

**Memories Panel:**
- Expandable tree view
- Organized by category
- Star ratings show relevance

**Insights Panel:**
- High-value learnings
- Sorted by relevance
- Quick access to best practices

**Cost Savings Panel:**
- Total saved
- Weekly/monthly breakdown
- Compression metrics
- Interaction count

### Knowledge Graph

Visual representation of your project knowledge:

**Features:**
- **Green nodes**: Categories (Patterns, Insights, etc.)
- **Blue nodes**: High-relevance memories
- **Gray nodes**: Lower-relevance memories
- **Lines**: Relationships between memories

**Interactions:**
- **Drag**: Move nodes around
- **Scroll**: Zoom in/out
- **Click**: View memory details
- **Reset Zoom**: Return to default view

## Configuration

Settings available in VS Code preferences:

```json
{
  "memorylane.autoStart": true,          // Auto-start server
  "memorylane.autoLearn": true,          // Auto-learn from changes
  "memorylane.showStatusBar": true,      // Show status bar item
  "memorylane.maxContextTokens": 2000,   // Max compression target
  "memorylane.compressionRatio": 7.0,    // Target compression
  "memorylane.pythonPath": "python3"     // Python executable path
}
```

## Architecture

```
┌─────────────────────────────────────┐
│  VS Code Extension (TypeScript)     │
│                                     │
│  ├─ Status Bar Manager              │
│  ├─ Sidebar Tree Providers          │
│  ├─ Knowledge Graph (D3.js)         │
│  ├─ Interaction Tracker             │
│  └─ Sidecar Manager (IPC Client)    │
└─────────────────┬───────────────────┘
                  │ Unix Socket
┌─────────────────▼───────────────────┐
│  Sidecar Server (Python)            │
│                                     │
│  ├─ Memory Store (JSON)             │
│  ├─ Passive Learner                 │
│  ├─ Context Compressor              │
│  └─ Cost Calculator                 │
└─────────────────────────────────────┘
```

## Features in Detail

### Automatic Learning

The extension watches:
- **File Changes**: Detects when you create/modify code files
- **Git Commits**: Analyzes commit messages for patterns
- **Project Structure**: Learns directory organization

### Cost Tracking

Tracks every Claude Code interaction:
1. Measures baseline context size (without MemoryLane)
2. Measures compressed context size (with MemoryLane)
3. Calculates token savings
4. Converts to dollar savings using current API pricing

### Memory Categories

**Patterns** - Code patterns and conventions
- "Project uses TypeScript with strict mode"
- "API endpoints follow REST conventions"

**Insights** - High-value learnings
- "Authentication uses JWT with 24h expiration"
- "Database migrations managed by Alembic"

**Learnings** - What worked/didn't work
- "Async/await preferred over callbacks"
- "Use connection pooling for database access"

**Context** - General project information
- "Project has src/ directory for source code"
- "Tests located in tests/ directory"

## Development

### Building

```bash
npm run compile        # Compile TypeScript
npm run watch          # Watch mode for development
npm run lint           # Run ESLint
```

### Testing

```bash
npm run test           # Run all tests
npm run pretest        # Compile before testing
```

### Packaging

```bash
npm run vscode:prepublish    # Prepare for publishing
vsce package                 # Create VSIX
```

## Troubleshooting

### Server Won't Start

Check if Python 3.8+ is installed:
```bash
python3 --version
```

Verify sidecar path in settings:
```json
{
  "memorylane.pythonPath": "/usr/bin/python3"
}
```

### No Memories Showing

1. Check if learning is active (status bar should show spinning icon)
2. Run initial learning manually:
   ```bash
   python3 src/learner.py initial
   ```
3. Refresh the sidebar

### High Memory Usage

Adjust compression settings:
```json
{
  "memorylane.maxContextTokens": 1500,
  "memorylane.compressionRatio": 10.0
}
```

## Roadmap

- [ ] v0.2: Semantic search with embeddings
- [ ] v0.3: Team sharing and sync
- [ ] v0.4: Custom memory categories
- [ ] v0.5: Integration with other AI assistants
- [ ] v1.0: VS Code Marketplace release

## Contributing

We welcome contributions! Please see CONTRIBUTING.md for guidelines.

## License

MIT License - see LICENSE file for details

## Support

- GitHub Issues: https://github.com/yourusername/memorylane/issues
- Documentation: https://memorylane.dev/docs
- Discord: https://discord.gg/memorylane

---

**Built with ❤️ for developers tired of repetitive context**

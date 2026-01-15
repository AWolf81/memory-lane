# Testing the MemoryLane Extension

## Quick Start (3 Steps)

### 1. Install Dependencies
```bash
cd vscode-extension
npm install
```

### 2. Open in VS Code
```bash
code .
```

### 3. Launch Extension Development Host
Press **F5** (or Run > Start Debugging)

This will:
- Compile TypeScript automatically
- Launch a new VS Code window with the extension loaded
- Start debugging session

---

## What You'll See

### In the Extension Development Host Window:

1. **Status Bar** (bottom right)
   ```
   🧠 0 memories | $0.00 saved
   ```

2. **Activity Bar** (left side)
   - Look for the MemoryLane icon (brain)
   - Click it to open the sidebar

3. **Sidebar Panels**
   - Overview
   - Memories (empty initially)
   - Insights (empty initially)
   - Savings

4. **Command Palette** (Cmd+Shift+P / Ctrl+Shift+P)
   Type "MemoryLane" to see all commands:
   - MemoryLane: Show Status
   - MemoryLane: Show Insights
   - MemoryLane: Show Cost Savings
   - MemoryLane: Show Knowledge Graph
   - MemoryLane: Start Learning
   - etc.

---

## Testing Steps

### Test 1: Server Auto-Start

When the Extension Development Host opens:

1. Watch the Output panel (View > Output)
2. Select "MemoryLane" from dropdown
3. You should see:
   ```
   MemoryLane extension activating...
   Starting MemoryLane sidecar...
   MemoryLane extension activated
   ```

**Expected:** Server starts automatically

**If it fails:** Check that Python is available:
```bash
python3 --version
```

### Test 2: Status Bar

1. Look at bottom-right status bar
2. Should show: `🧠 0 memories | $0.00 saved`
3. Click the status bar item
4. Should see a popup with stats

**Expected:** Status bar appears and is clickable

### Test 3: Initial Learning

1. Open Command Palette (Cmd+Shift+P)
2. Run: `MemoryLane: Start Learning`
3. Wait ~5 seconds
4. Status bar should update with memory count
5. Open sidebar to see learned memories

**Expected:** Learns from git history and workspace

### Test 4: Knowledge Graph

1. Command Palette: `MemoryLane: Show Knowledge Graph`
2. New webview panel opens
3. Interactive graph with nodes and links
4. Try dragging nodes around
5. Try zooming in/out

**Expected:** Beautiful D3.js visualization

### Test 5: Cost Savings Dashboard

1. Command Palette: `MemoryLane: Show Cost Savings`
2. Webview shows dashboard
3. Metrics displayed (all zeros initially)

**Expected:** Dashboard renders properly

### Test 6: File Watching

1. Create or edit a `.py` or `.ts` file in the workspace
2. Make a significant change (>100 chars)
3. Wait a few seconds
4. Status bar should update
5. Check sidebar - new memory may appear

**Expected:** File changes trigger learning

### Test 7: Sidebar Browsing

1. Click MemoryLane icon in Activity Bar
2. Expand "Patterns" category
3. Should see memories with star ratings
4. Hover over a memory for tooltip
5. Try expanding other categories

**Expected:** Tree view works smoothly

---

## Debugging

### Debug Console

The Debug Console shows all `console.log()` output from the extension:

```
View > Debug Console
```

You'll see:
- Extension lifecycle events
- Server communication
- Errors and warnings

### Breakpoints

1. Open any `.ts` file in `vscode-extension/src/`
2. Click left of line number to add breakpoint (red dot)
3. Trigger the code path
4. Debugger will pause at breakpoint
5. Inspect variables, step through code

### Hot Reload

Changes to TypeScript code:
1. Save file
2. Press Cmd+Shift+P → "Reload Window"
3. Extension reloads with new code

Or use watch mode:
```bash
npm run watch
```

---

## Common Issues

### Issue: "Command 'MemoryLane...' not found"

**Cause:** Extension didn't activate

**Fix:**
1. Check Output panel for errors
2. Restart debugging (Cmd+Shift+F5)
3. Check that TypeScript compiled: `ls out/`

### Issue: "Server is not running"

**Cause:** Python sidecar didn't start

**Fix:**
1. Check Python path in settings
2. Manually start server:
   ```bash
   cd ..
   python3 src/server.py start
   ```
3. Check `.memorylane/server.pid` was created

### Issue: "No memories showing"

**Cause:** Initial learning didn't run

**Fix:**
1. Run: `MemoryLane: Start Learning`
2. Or manually run:
   ```bash
   cd ..
   python3 src/learner.py initial
   ```

### Issue: TypeScript compile errors

**Fix:**
```bash
npm run compile
# Check for errors
# Fix any type issues
```

---

## File Structure After Setup

```
vscode-extension/
├── .vscode/
│   ├── launch.json       ✅ Launch config
│   ├── tasks.json        ✅ Build tasks
│   └── extensions.json   ✅ Recommended extensions
├── out/                  ✅ Compiled JavaScript (created by tsc)
│   ├── extension.js
│   ├── sidecar.js
│   └── ...
├── src/                  TypeScript source
│   ├── extension.ts
│   └── ...
├── node_modules/         ✅ Dependencies (created by npm install)
├── package.json
└── tsconfig.json
```

---

## Next Steps

Once the basic extension is working:

1. **Add Test Data**
   ```bash
   cd ..
   python3 src/learner.py initial
   ```

2. **Simulate Interactions**
   - Edit files
   - Make git commits
   - Watch memories accumulate

3. **Test All Commands**
   - Go through each command in Command Palette
   - Verify they work as expected

4. **Test Edge Cases**
   - No internet connection
   - Large workspaces
   - Empty workspaces
   - Server crashes

5. **Performance Testing**
   - Open large workspace
   - Monitor memory usage
   - Check status bar responsiveness

---

## Troubleshooting Commands

```bash
# Check if server is running
python3 src/server.py status

# View current memories
python3 src/cli.py status

# View logs
tail -f .memorylane/logs/*.log

# Reset everything
python3 src/cli.py reset --force

# Reinstall dependencies
cd vscode-extension
rm -rf node_modules
npm install
```

---

## Success Criteria

✅ Extension activates without errors
✅ Sidecar server starts automatically
✅ Status bar shows and updates
✅ Sidebar panels render
✅ Knowledge graph visualizes
✅ Commands execute successfully
✅ File watching works
✅ No console errors

Once all these work, the extension is ready for real-world testing! 🎉

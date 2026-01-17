# MemoryLane 🧠

**Local-first persistent memory for Claude Code with automatic cost savings**

MemoryLane gives Claude Code durable project memory by extracting knowledge locally and injecting only what matters. It reduces token usage by **up to 84%**, eliminates repeated explanations, and keeps raw development sessions on your machine.

---

## 🎯 Core Value

**Turn raw dev sessions into durable knowledge.  
Only intentional, compressed context is sent to the cloud.**

---

## ✨ Features

- **🔄 Zero Configuration**  
  One-command install. Automatic learning and context injection.

- **💰 Massive Cost Savings**  
  **30–84% token reduction** through intelligent summarization and compression.

- **🧠 Local LLM Summarization**  
  Uses a local, instruction-tuned LLM (hundreds of millions to low-single-digit billions of parameters) to extract design decisions, problems solved, and patterns.  
  Heuristic fallback is used if the model is unavailable.

- **🔒 Privacy-First by Design**  
  Raw transcripts, diffs, and files stay local. Only curated context reaches Claude.

- **📊 Passive Learning**  
  Learns from file edits, git commits, and CLI sessions without workflow changes.

- **⚡ Fast**  
  <100ms recall latency. Async summarization (<5s typical).

- **🧯 Context Rot Guard**  
  Automatically caps injected context to a safe fraction of the model’s window to prevent quality decay at long context lengths.

- **📈 Cost Tracking**  
  Transparent token savings with validated test coverage.

---

## 🚀 Quick Start

### Installation

```bash
# Install the Claude Code skill from GitHub
claude skill install yourusername/memorylane --skill memorylane

# Or install via marketplace alias (one-time add, then install)
claude plugin marketplace add yourusername/memorylane
claude plugin install memorylane@memorylane

# Or manual installation
git clone https://github.com/yourusername/memorylane.git
cd memorylane
bash install.sh
````

### Usage

```bash
# Check status and cost savings
python3 src/cli.py status

# Recall memories about a topic
python3 src/cli.py recall "authentication"

# View learned insights
python3 src/cli.py insights

# See detailed cost breakdown
python3 src/cli.py costs
```

That’s it. MemoryLane now learns from your project and injects context automatically.

---

## 📊 Validated Cost Savings

Cost savings are **measured, not estimated**.

```bash
pytest tests/test_cost_savings.py -v -s
```

**Realistic Weekly Usage Test**

* 100 Claude interactions/week
* Baseline: ~2.3M tokens/week
* MemoryLane: ~360K tokens/week
* **Compression: 6.4×**
* **Savings: 84.3%**
* **Monthly: ~$51 saved per developer**

---

## 🏗️ Architecture (High-Level)

MemoryLane is local-first and session-aware:

* CLI captures session sources (transcripts, git diffs, file changes)
* A summarization orchestrator extracts durable knowledge
* A **local LLM backend** is used by default, with heuristic fallback
* Structured memory is stored locally
* Context is recalled, compressed, and injected on demand

Only **intentional, compressed context** is sent to Claude Code.

---

## 💡 How It Works

1. **Session Capture**
   CLI collects transcripts, git diffs, and workspace changes.

2. **Knowledge Extraction**
   A local LLM summarizes decisions, problems, and patterns.

3. **Structured Memory**
   Knowledge is stored as durable, queryable memories.

4. **Recall & Compression**
   Relevant memories are ranked, deduplicated, and token-budgeted.

5. **Context Injection**
   Only the compressed result is sent to Claude Code.

---

## 🎯 Adaptive Learning

MemoryLane learns **what is worth remembering**:

* **Warmup Phase**
  Learns baseline project patterns.

* **Selective Memory**
  Stores only non-routine, high-signal information.

* **Dynamic Thresholds**
  Adapts automatically as the project grows.

No configuration required.

---

## 🧯 Context Rot Guard

Long context windows do not mean long context reliability. MemoryLane keeps injected context under a safe fraction of the model's advertised limit so quality stays stable as prompts grow.

By default, the guard targets 50% of the model window and reserves extra space for the user prompt and the assistant response.

---

## 🔧 Configuration

```bash
# View config
python3 src/cli.py config list

# Change a value
python3 src/cli.py config set memory.max_context_tokens 3000

# Tune context rot guard
python3 src/cli.py config set context_rot.model_context_tokens 200000
python3 src/cli.py config set context_rot.safe_fraction 0.5
python3 src/cli.py config set context_rot.reserve_tokens 1200

# Inspect privacy exclusions
python3 src/cli.py config get privacy.exclude_patterns
```

---

## 🔒 Privacy Model

* **Local by Default**
  Raw sessions, diffs, and files never leave your machine.

* **Curated Sharing**
  Only compressed, user-relevant context is sent to Claude.

* **No Telemetry**
  No background data collection.

* **User Control**
  View, edit, or delete any memory at any time.

* **Sensitive File Exclusion**
  `.env`, secrets, and credentials are excluded automatically.

---

## 🆚 Comparison

| Feature            | MemoryLane           | memory-graph | basic-memory |
| ------------------ | -------------------- | ------------ | ------------ |
| Setup              | One command          | NPX + config | Git clone    |
| Learning           | Automatic            | Manual       | Manual       |
| Local LLM          | ✅                    | ❌            | ❌            |
| Compression        | ✅ 6–7×               | ❌            | ❌            |
| Cost Tracking      | ✅                    | ❌            | ❌            |
| Claude Integration | Native skill         | MCP          | MCP          |
| Privacy            | Curated context only | Local JSON   | Markdown     |

---

## 🛣️ Roadmap

### v0.1 (Current – MVP)

* [x] Core memory storage
* [x] CLI interface
* [x] Cost savings validation
* [x] Local LLM summarization
* [ ] Sidecar IPC
* [ ] Full context compression

### v0.2

* [ ] Embedding-based recall
* [ ] Git history learning
* [ ] VS Code extension
* [ ] Memory quality review UI

### v1.0

* [ ] Production sidecar
* [ ] Advanced recall ranking
* [ ] Claude marketplace release
* [ ] Public demo & documentation

---

## 📄 License

MIT License

---

**MemoryLane is for developers who want smarter context.
Not longer prompts.**

---

# Feature PRD: LLM-Powered Memory Summarization for MemoryLane

**Document Version:** 1.0  
**Last Updated:** January 17, 2026  
**Status:** Ready for Implementation  
**Owner:** Alexander

---

## 1. Executive Summary

MemoryLane requires an intelligent summarization layer that extracts **actionable knowledge** from development sessions rather than storing raw action logs. This feature introduces a lightweight, CPU-compatible LLM that processes session transcripts into concise, context-rich memory entries focused on design decisions, architectural patterns, and problem resolutions.

### Key Value Proposition
- **Privacy-First**: Runs 100% locally on CPU, no data leaves the machine
- **Resource-Efficient**: Works on any development machine without GPU requirements
- **Knowledge-Focused**: Extracts "why" and "what we learned" instead of "what we did"
- **Cross-Project Learning**: Enables pattern recognition and knowledge transfer between projects

---

## 2. Goals & Non-Goals

### Goals
✅ Extract design decisions, architectural patterns, and problem resolutions from development sessions  
✅ Run on CPU-only environments (no GPU dependency)  
✅ Process summaries in <5 seconds on typical hardware (i5/Ryzen 5 or better)  
✅ Generate structured memory entries compatible with semantic search  
✅ Support incremental learning (update existing memories when new insights emerge)  
✅ Maintain sub-100MB memory footprint during operation  

### Non-Goals
❌ Real-time summarization during coding (async/batch processing is acceptable)  
❌ Full conversation replay capability  
❌ Code generation or modification  
❌ Multi-modal input (images, diagrams) in v1  
❌ Fine-tuning or model customization (use pre-trained models)  

---

## 3. User Stories

### Primary Use Case
**As a developer**, I want MemoryLane to remember *why* I made architectural decisions and *what problems I solved*, so that Claude Code can provide context-aware suggestions in future sessions without me repeating myself.

### Specific Scenarios

**Story 1: Design Decision Capture**
```
Given: I implemented a central registry pattern instead of distributed discovery
When: The summarizer processes the session
Then: Memory stores "Central registry chosen for single source of truth - enables 
      fast cross-project queries. Alternative distributed approach rejected due to 
      complexity in synchronization."
```

**Story 2: Problem Resolution**
```
Given: I spent 2 hours debugging a race condition in async file writes
When: The summarizer processes the session
Then: Memory stores "Async file writes require locks when using aiomisc - discovered 
      race condition when multiple coroutines wrote simultaneously. Solution: added 
      asyncio.Lock per file path."
```

**Story 3: Pattern Establishment**
```
Given: I created a three-layer integration pattern (CLI ↔ Sidecar ↔ Extension)
When: The summarizer processes the session
Then: Memory stores "Three-layer architecture established for VS Code integration. 
      Pattern: Python CLI handles logic → TypeScript sidecar bridges → UI extension 
      consumes. Enables language-agnostic extension development."
```

**Story 4: Cross-Project Knowledge Transfer**
```
Given: I solved authentication issues in Project A
When: Working on Project B with similar auth requirements
Then: MemoryLane surfaces relevant patterns from Project A automatically
```

---

## 4. Technical Requirements

### 4.1 Model Selection Criteria

| Criterion | Requirement | Rationale |
|-----------|-------------|-----------|
| **Parameter Count** | 360M - 1.7B | Balance between capability and CPU performance |
| **Architecture** | Decoder-only transformer | Efficient for text generation tasks |
| **Instruction Tuning** | Required | Consistent output format without examples |
| **License** | Apache 2.0 or MIT | Commercial use without restrictions |
| **Framework** | PyTorch native | Ecosystem compatibility |

### 4.2 Recommended Models (Priority Order)

1. **SmolLM-360M-Instruct** (Primary)
   - Size: 360M parameters
   - Memory: ~1.5GB RAM
   - Speed: ~30 tokens/sec on CPU
   - Strength: Excellent instruction following

2. **SmolLM-1.7B-Instruct** (Alternative - More Capable)
   - Size: 1.7B parameters
   - Memory: ~7GB RAM
   - Speed: ~10 tokens/sec on CPU
   - Strength: Better reasoning, still CPU-friendly

3. **Qwen2-0.5B-Instruct** (Fallback)
   - Size: 494M parameters
   - Memory: ~2GB RAM
   - Speed: ~25 tokens/sec on CPU
   - Strength: Strong multilingual support

### 4.3 Input/Output Specification

**Input Format:**
```python
{
    "session_id": "uuid",
    "timestamp": "ISO8601",
    "project_name": "memorylane",
    "raw_transcript": "Full conversation or git diff + commit message",
    "context_hints": [  # Optional
        "debugging",
        "architecture_design",
        "performance_optimization"
    ]
}
```

**Output Format:**
```python
{
    "summary": "Human-readable summary (2-4 sentences)",
    "memory_entries": [
        {
            "type": "design_decision",
            "content": "Central registry pattern chosen over distributed...",
            "tags": ["architecture", "registry", "cross-project"],
            "confidence": 0.85  # Model's confidence in extraction
        },
        {
            "type": "problem_solved",
            "content": "Race condition in async file writes resolved using asyncio.Lock",
            "tags": ["async", "debugging", "file-io"],
            "confidence": 0.92
        }
    ],
    "suggested_deletions": [  # Redundant/superseded memories
        "memory_id_123"
    ]
}
```

### 4.4 Memory Entry Types

| Type | Description | Example |
|------|-------------|---------|
| `design_decision` | Architectural choices with rationale | "Chose SQLite over JSON files for ACID guarantees" |
| `problem_solved` | Root cause + solution | "N+1 query fixed by adding eager loading" |
| `pattern_established` | Reusable code/design patterns | "Factory pattern used for plugin system" |
| `constraint_discovered` | Technical limitations found | "API rate limit: 100 req/min per token" |
| `future_consideration` | TODOs, improvements, known limitations | "Consider sharding when users exceed 10k" |
| `dependency_added` | Why a library/tool was chosen | "Added Pydantic for runtime type validation" |

### 4.5 Performance Requirements

| Metric | Requirement | Measurement Method |
|--------|-------------|-------------------|
| **Processing Time** | <5 seconds per session (up to 4000 tokens) | End-to-end timer |
| **Memory Usage** | <512MB resident memory | Process monitoring |
| **CPU Utilization** | <80% single core during processing | System profiler |
| **Model Load Time** | <3 seconds cold start | First invocation timer |

---

## 5. Architecture

### 5.1 Component Overview

```
┌─────────────────────────────────────────────────────────┐
│                   MemoryLane CLI/Extension               │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
          ┌──────────────────────┐
          │  Summarizer Service  │
          │  (src/summarizer.py) │
          └──────────┬───────────┘
                     │
         ┌───────────┴───────────┐
         ▼                       ▼
┌─────────────────┐    ┌──────────────────┐
│  Model Manager  │    │  Prompt Builder  │
│  (Lazy Loading) │    │  (Templating)    │
└─────────┬───────┘    └────────┬─────────┘
          │                     │
          ▼                     ▼
   ┌────────────────────────────────┐
   │    PyTorch + Transformers      │
   │    SmolLM-360M-Instruct        │
   └────────────────────────────────┘
```

### 5.2 Core Components

#### **SummarizerService** (`src/summarizer.py`)
- Main entry point for summarization
- Handles prompt construction and model invocation
- Manages batching for large sessions
- Caches model instance (lazy load)

#### **ModelManager** (`src/model_manager.py`)
- Downloads and caches models (~/.memorylane/models/)
- Validates model compatibility
- Handles quantization if needed (future optimization)
- Provides fallback to alternative models

#### **PromptBuilder** (`src/prompt_builder.py`)
- Constructs extraction prompts with examples
- Enforces structured output format
- Handles context truncation (max 4096 tokens input)

#### **MemoryIntegration** (Extends existing `src/memory.py`)
- Receives structured summaries
- Deduplicates similar memories
- Updates semantic embeddings (existing TF-IDF → future: small embedding model)
- Flags redundant memories for user review

### 5.3 Data Flow

```
1. Session Ends (CLI exit or extension trigger)
   ↓
2. Raw session data gathered (git diff, conversation log, files changed)
   ↓
3. PromptBuilder creates extraction prompt
   ↓
4. SummarizerService invokes LLM
   ↓
5. Parse structured JSON output
   ↓
6. MemoryIntegration stores + indexes entries
   ↓
7. Cross-project registry updated if new patterns found
```

---

## 6. Prompt Engineering

### 6.1 System Prompt Template

```
You are a memory extraction assistant for MemoryLane, a developer knowledge management tool.

Your task: Analyze development sessions and extract KNOWLEDGE, not actions.

Extract:
✓ Design decisions (why X was chosen over Y)
✓ Problems solved (root cause + solution)
✓ Patterns established (reusable approaches)
✓ Constraints discovered (technical limitations)
✓ Future considerations (TODOs, improvements)

Do NOT extract:
✗ Individual actions taken ("user ran npm install")
✗ File names/paths unless architecturally significant
✗ Code snippets (only describe patterns/decisions)
✗ Generic advice or best practices

Output format: JSON with 'summary' and 'memory_entries' array.
Each entry has: type, content (2-3 sentences max), tags, confidence.

Be concise. Focus on WHY and WHAT WAS LEARNED.
```

### 6.2 Few-Shot Examples (In-Context)

```json
[
  {
    "input": "Implemented cross-project search. Created project_registry.py with auto-registration. Projects stored in ~/.memorylane/projects.json. CLI commands: list, add, remove, cleanup, search.",
    "output": {
      "summary": "Cross-project search implemented using central registry pattern for fast lookups and automatic project discovery.",
      "memory_entries": [
        {
          "type": "design_decision",
          "content": "Central registry pattern chosen over distributed discovery. Single source of truth at ~/.memorylane/projects.json enables fast cross-project queries without network overhead.",
          "tags": ["architecture", "registry", "cross-project"],
          "confidence": 0.90
        },
        {
          "type": "pattern_established",
          "content": "Auto-registration pattern eliminates manual configuration. Projects self-register on first CLI/extension use.",
          "tags": ["ux", "automation", "configuration"],
          "confidence": 0.88
        }
      ]
    }
  }
]
```

---

## 7. Implementation Plan

### Phase 1: Core Infrastructure (Week 1)
**Goal:** Functional summarization with SmolLM-360M

- [ ] Create `src/model_manager.py`
  - Model download + caching logic
  - Version compatibility checks
  - Error handling for network failures
  
- [ ] Create `src/prompt_builder.py`
  - System prompt template
  - Few-shot examples
  - Context truncation (4096 token limit)
  
- [ ] Create `src/summarizer.py`
  - PyTorch model loading
  - Inference function
  - JSON parsing with validation

- [ ] Add unit tests
  - Mock model responses
  - Prompt construction edge cases
  - Output format validation

**Success Criteria:**
- Summarizer processes 1000-token session in <5 seconds
- Generates valid JSON 95%+ of the time
- Model loads successfully on CPU-only machine

### Phase 2: Integration (Week 2)
**Goal:** Connect to existing MemoryLane storage

- [ ] Extend `src/memory.py`
  - Accept structured memory entries
  - Deduplicate similar memories (TF-IDF similarity >0.85)
  - Update CLI `save` command to invoke summarizer
  
- [ ] Update `src/cli.py`
  - Add `--summarize` flag to context command
  - Background processing option (don't block CLI exit)
  
- [ ] VS Code Extension integration
  - Call summarizer via sidecar on workspace close
  - Show summary preview before saving (user confirmation)

**Success Criteria:**
- Summaries stored in existing SQLite schema
- No duplicate memories created
- User can review/edit summaries before saving

### Phase 3: Optimization (Week 3)
**Goal:** Production-ready performance

- [ ] Async processing
  - Queue-based summarization (don't block workflow)
  - Process summaries during idle time
  
- [ ] Model optimization
  - Evaluate quantization (bitsandbytes int8)
  - Benchmark SmolLM-1.7B vs 360M on typical hardware
  
- [ ] Smart batching
  - Combine related sessions (same file edits)
  - Avoid redundant summaries for trivial changes

**Success Criteria:**
- Zero user-perceivable latency (async queue)
- Memory footprint <300MB during operation
- Accurate summaries for 90%+ of sessions (manual review)

### Phase 4: Polish (Week 4)
**Goal:** User-facing features

- [ ] Summary review UI in VS Code
  - Tree view showing pending summaries
  - Inline edit capability
  - Approve/reject buttons
  
- [ ] Memory search improvements
  - Use summary tags for better semantic search
  - "Similar patterns" suggestions
  
- [ ] Documentation
  - README section on summarization
  - Configuration options (model selection, prompts)

---

## 8. Configuration

### User-Configurable Settings (`~/.memorylane/config.json`)

```json
{
  "summarizer": {
    "enabled": true,
    "model": "SmolLM-360M-Instruct",  // or "SmolLM-1.7B-Instruct", "Qwen2-0.5B-Instruct"
    "auto_summarize": false,  // Require user confirmation before saving
    "min_session_length": 500,  // Tokens - skip trivial sessions
    "batch_processing": true,  // Process during idle time
    "confidence_threshold": 0.7  // Only save memories above this confidence
  }
}
```

---

## 9. Edge Cases & Error Handling

| Scenario | Behavior | Rationale |
|----------|----------|-----------|
| **Model download fails** | Fallback to keyword extraction | Graceful degradation |
| **Session too large (>8000 tokens)** | Chunk into segments, summarize each | Avoid context overflow |
| **JSON parsing fails** | Retry with stricter prompt, else skip | Prevent corrupted memories |
| **Low confidence (<0.7)** | Flag for user review | Quality control |
| **Network unavailable (first run)** | Error message with manual download instructions | Offline capability |
| **Insufficient RAM** | Suggest SmolLM-360M or disable summarization | User choice |

---

## 10. Success Metrics

### Quantitative
- **Processing Speed:** 95% of sessions summarized in <5 seconds
- **Accuracy:** 85%+ of summaries capture key decisions (user survey)
- **Memory Deduplication:** 90% reduction in redundant memories
- **Resource Usage:** <512MB RAM, <80% single-core CPU

### Qualitative
- Users stop repeating context to Claude Code
- Cross-project pattern discovery increases (tracked via "similar patterns" clicks)
- Positive feedback on summary quality (thumbs up/down in extension)

---

## 11. Dependencies

### Python Packages
```
torch>=2.0.0
transformers>=4.35.0
accelerate>=0.25.0  # For model loading optimization
sentencepiece>=0.1.99  # Tokenizer backend
```

### Model Storage
- **Location:** `~/.memorylane/models/`
- **Size:** ~700MB for SmolLM-360M
- **Cache:** Shared across projects

---

## 12. Security & Privacy

- **No Network Calls:** Model inference is 100% local (after initial download)
- **No Telemetry:** Summaries never leave the machine
- **User Data:** All session data stays in `~/.memorylane/` (user-controlled)
- **Model Source:** HuggingFace Hub (verified checksums)

---

## 13. Future Enhancements (Out of Scope for V1)

1. **Custom Prompts:** User-defined extraction rules per project
2. **Incremental Learning:** Fine-tune model on user-corrected summaries
3. **Multimodal:** Summarize architecture diagrams, screenshots
4. **Vector Embeddings:** Replace TF-IDF with dense embeddings for semantic search
5. **Collaborative Memories:** Share anonymized patterns across teams

---

## 14. Open Questions

1. **Should summaries be editable post-creation?**
   - Proposal: Yes, via CLI command or extension UI
   
2. **How to handle contradictory memories?**
   - Proposal: Flag conflicts, let user merge/choose
   
3. **Summarize on every save or batch daily?**
   - Proposal: User configurable, default to batch (less interruption)

---

## Appendix A: Example Session → Summary

**Input (Session Transcript):**
```
User: "I need to add cross-project search to MemoryLane"
Claude: "Let's create a central registry..."
[Implementation details...]
User: "Why not use distributed discovery?"
Claude: "Central registry is simpler and faster for local-first tools..."
[Final implementation with project_registry.py]
```

**Output (Summarizer):**
```json
{
  "summary": "Cross-project search implemented using central registry pattern at ~/.memorylane/projects.json. Auto-registration enables zero-config knowledge sharing between projects.",
  "memory_entries": [
    {
      "type": "design_decision",
      "content": "Central registry pattern chosen over distributed discovery for simplicity and speed. Local-first architecture doesn't require network synchronization overhead.",
      "tags": ["architecture", "design-decision", "cross-project"],
      "confidence": 0.89
    },
    {
      "type": "pattern_established",
      "content": "Auto-registration pattern: projects self-register on first CLI/extension use, eliminating manual setup.",
      "tags": ["automation", "ux", "configuration"],
      "confidence": 0.91
    }
  ]
}
```

---

**End of PRD**

---

## How to Use This PRD with Claude Code

1. Save this file to your project root
2. Reference it in your conversation: "Implement Phase 1 according to the PRD"
3. Claude Code will have full context on requirements, architecture, and success criteria

# MemoryLane

## What This Is

A VS Code extension with a local Python sidecar that gives AI assistants persistent memory through adaptive learning, reducing API costs by 30%+ while improving code suggestions through project context awareness. Local-first, privacy-focused, and learns from your coding patterns.

## Core Value

AI remembers your project—locally, privately, cheaply—eliminating repetitive context while making suggestions smarter.

## Requirements

### Validated

(None yet — ship to validate)

### Active

#### Core Memory Engine
- [ ] Adaptive memory layer (35M params, PyTorch) with surprise-based learning
- [ ] FAISS vector database for efficient retrieval
- [ ] Surprise calculation implementation for relevance ranking
- [ ] Context compression achieving >5x ratio
- [ ] IPC server (JSON-RPC over Unix socket)

#### Data Collection & Indexing
- [ ] File content indexing and embedding generation
- [ ] Git commit history parsing
- [ ] VSCode workspace analysis
- [ ] Terminal output capture (opt-in)
- [ ] Incremental updates on file changes

#### VS Code Extension
- [ ] Extension scaffolding with TypeScript
- [ ] Sidecar process management (start/stop/monitor)
- [ ] AI assistant detection and prompt interception
- [ ] Auto-context injection (prepend compressed context)
- [ ] Core commands: enable, recall, insights, costs, configure
- [ ] Status bar indicator (memory active/learning)
- [ ] Sidebar panel showing learned concepts
- [ ] Cost savings dashboard
- [ ] Token usage tracking and visualization

#### Privacy & Security
- [ ] Granular privacy settings (exclude files/folders via .memorylaneignore)
- [ ] Local-only mode (no internet required)
- [ ] Encryption at rest (AES-256)
- [ ] Memory browser (view/delete entries)
- [ ] Memory export/import (JSON format)
- [ ] One-click memory wipe
- [ ] Transparency: show what's being remembered

#### MLflow Integration
- [ ] Experiment tracking setup
- [ ] Training metrics logging
- [ ] Model versioning
- [ ] A/B testing framework
- [ ] Dashboard for monitoring memory quality

#### Performance & Quality
- [ ] Sidecar startup time <5 seconds
- [ ] Context retrieval latency <100ms (p95)
- [ ] Memory update latency <200ms (p95)
- [ ] RAM usage <2GB, VRAM <4GB (4-bit quantization)
- [ ] Disk usage <500MB for typical project
- [ ] Process 1000 files/minute during indexing

#### Documentation & Launch
- [ ] Installation guide (Mac/Linux/Windows)
- [ ] Architecture overview with diagrams
- [ ] API documentation
- [ ] Privacy policy
- [ ] Cost reduction methodology case study
- [ ] 3-minute demo video
- [ ] VS Code marketplace listing
- [ ] README optimized for marketplace

### Out of Scope

- Cloud sync — Local-first for MVP; privacy is core value
- Team collaboration features — Solo developer focus for v1.0
- Multi-IDE support (JetBrains, etc.) — VS Code only until proven
- Custom model training UI — Use MLflow dashboard
- Mobile/web interfaces — CLI/desktop only
- Telemetry beyond local metrics — Privacy-first means opt-in only
- Enterprise features (SSO, SAML, admin controls) — Post-500 installs
- Browser extension version — Focus platform, prove value first

## Context

### Technical Environment
- **Hardware**: RTX 5060 Ti (16GB VRAM) capable of training 35M param model
- **Target Users**: Developers using AI assistants (Claude, GPT, etc.) spending $100-500/month on API costs
- **Current Pain**: 50-80% of context is repetitive across conversations, causing unnecessary API costs and slower responses
- **Market Gap**: Existing tools (Copilot, Cursor, Continue.dev) don't offer local adaptive learning or cost optimization

### Research Foundation
- Based on Titans architecture (surprise-based learning for efficient memory)
- Sentence-transformers for efficient embedding generation (all-MiniLM-L6-v2, 80MB)
- FAISS for fast vector similarity search at scale
- PyTorch for model training with 4-bit quantization for efficiency

### User Journey
1. **Passive Learning**: Extension watches file edits, git commits, terminal output
2. **Smart Context Injection**: When user invokes AI assistant, sidecar provides compressed relevant context (2K vs 20K tokens)
3. **Continuous Improvement**: Memory layer learns which context was useful, adapts to patterns

### Success Indicators (90 Days)
- 500+ active installations from VS Code marketplace
- 30%+ documented cost reduction in case study
- >4.0 star rating on marketplace
- Portfolio-quality codebase demonstrating ML engineering
- Working demo for interviews/pitches

## Constraints

- **Timeline**: 6 weeks to MVP launch — aggressive scope control required
- **Hardware**: Single RTX 5060 Ti (16GB VRAM) — must use 4-bit quantization, efficient architectures
- **Platform**: VS Code only for v1.0 — focus on one IDE before expanding
- **Privacy**: Absolute local-first requirement — no cloud dependencies, all data encrypted at rest
- **Performance**: <2GB RAM, <100ms p95 latency — must feel instant, not slow down IDE
- **Tech Stack**: Python (sidecar), TypeScript (extension) — leverage existing skills
- **Model Size**: 35M params max — trainable on RTX 5060 Ti in reasonable time (<30min)
- **Context Budget**: 2K token injection limit — must compress effectively
- **Launch Platform**: VS Code Marketplace — must pass their review standards

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| 35M parameter model (not larger) | Fits RTX 5060 Ti with 4-bit quantization, trains in 30min | — Pending |
| Local-first architecture (no cloud) | Privacy moat, enterprise appeal, differentiation from competitors | — Pending |
| Surprise-based learning (Titans approach) | Novel contribution, better than naive retrieval, research validation | — Pending |
| Unix socket IPC (not HTTP) | Lower latency, more secure, simpler than network stack | — Pending |
| FAISS for vector DB (not Pinecone/Weaviate) | Local-only requirement, battle-tested, fast enough | — Pending |
| all-MiniLM-L6-v2 embeddings | Small (80MB), fast, good quality, proven in production | — Pending |
| VS Code only for v1.0 | Focus platform, prove value, avoid multi-IDE complexity | — Pending |
| 6-week timeline | Aggressive but achievable, forces scope discipline, portfolio timeline | — Pending |
| Open core monetization | Free tier builds adoption, pro tier captures value, sustainable | — Pending |
| MLflow for experiment tracking | Industry standard, good UX, enables A/B testing | — Pending |

---
*Last updated: 2026-01-15 after initialization from comprehensive PRD*

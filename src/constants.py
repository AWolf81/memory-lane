"""
Central constants for MemoryLane.

Update model versions and other configuration here.
"""

# Claude model defaults
CLAUDE_DEFAULT_MODEL = "claude-haiku-4-5-20251001"
CLAUDE_MAX_TOKENS = 2048
CLAUDE_TIMEOUT = 60

# Local LLM models (fallback)
LOCAL_LLM_MODELS = [
    "SmolLM-360M-Instruct",
    "SmolLM-1.7B-Instruct",
    "Qwen2-0.5B-Instruct",
]
LOCAL_LLM_DEFAULT = LOCAL_LLM_MODELS[0]

# Memory categories
MEMORY_CATEGORIES = ["patterns", "insights", "learnings", "context"]

# Extraction backends
EXTRACTION_BACKENDS = ["auto", "claude", "local_llm", "regex"]
EXTRACTION_DEFAULT_BACKEND = "auto"

# Token budgets
DEFAULT_MAX_CONTEXT_TOKENS = 2000
DEFAULT_COMPRESSION_RATIO = 7.0

# Relevance thresholds
DEFAULT_RELEVANCE_THRESHOLD = 0.7
CONFIDENCE_THRESHOLD = 0.7

# Context rot protection defaults
CONTEXT_ROT_MODEL_TOKENS = 200000
CONTEXT_ROT_SAFE_FRACTION = 0.5
CONTEXT_ROT_RESERVE_TOKENS = 1200
CONTEXT_ROT_MIN_INJECTION = 200

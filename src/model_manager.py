"""
Model management for MemoryLane summarization.
Handles lazy loading, caching, and fallback models.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple, Dict, List


class ModelManager:
    """Loads and caches CPU-friendly LLMs for summarization."""

    MODEL_CANDIDATES: Dict[str, str] = {
        "SmolLM-360M-Instruct": "HuggingFaceTB/SmolLM-360M-Instruct",
        "SmolLM-1.7B-Instruct": "HuggingFaceTB/SmolLM-1.7B-Instruct",
        "Qwen2-0.5B-Instruct": "Qwen/Qwen2-0.5B-Instruct",
    }

    DEFAULT_FALLBACK_ORDER = [
        "SmolLM-360M-Instruct",
        "SmolLM-1.7B-Instruct",
        "Qwen2-0.5B-Instruct",
    ]

    def __init__(self, config=None):
        self.config = config
        self.model = None
        self.tokenizer = None
        self.model_id: Optional[str] = None

        self._torch = None
        self._auto_model = None
        self._auto_tokenizer = None

        self.available = self._load_dependencies()
        self.cache_dir = Path.home() / ".memorylane" / "models"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _load_dependencies(self) -> bool:
        """Check for optional LLM dependencies."""
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer

            self._torch = torch
            self._auto_model = AutoModelForCausalLM
            self._auto_tokenizer = AutoTokenizer
            return True
        except ImportError:
            return False

    def get_model_and_tokenizer(self) -> Optional[Tuple[object, object, str]]:
        """Return a loaded model/tokenizer pair, loading if needed."""
        if self.model is not None and self.tokenizer is not None:
            return self.model, self.tokenizer, self.model_id

        if not self.available:
            return None

        local_only = not self._get_config_value("summarizer.allow_download", True)
        candidates = self._get_candidate_models()
        last_error = None

        for name in candidates:
            model_id = self.MODEL_CANDIDATES.get(name, name)
            try:
                tokenizer = self._auto_tokenizer.from_pretrained(
                    model_id,
                    cache_dir=self.cache_dir,
                    local_files_only=local_only,
                )
                load_kwargs = {
                    "cache_dir": self.cache_dir,
                    "local_files_only": local_only,
                    "torch_dtype": self._torch.float32,
                }

                if self._is_accelerate_available():
                    load_kwargs["low_cpu_mem_usage"] = True

                model = self._auto_model.from_pretrained(model_id, **load_kwargs)
                model.eval()

                self.model = model
                self.tokenizer = tokenizer
                self.model_id = model_id
                return self.model, self.tokenizer, self.model_id
            except Exception as exc:
                last_error = exc
                continue

        return None

    def _get_candidate_models(self) -> List[str]:
        """Get a prioritized list of models to try."""
        preferred = self._get_config_value("summarizer.model", None)
        fallbacks = self._get_config_value("summarizer.fallback_models", [])

        candidates: List[str] = []
        if preferred:
            candidates.append(preferred)
        if fallbacks:
            candidates.extend(fallbacks)

        if not candidates:
            candidates = list(self.DEFAULT_FALLBACK_ORDER)
        else:
            for fallback in self.DEFAULT_FALLBACK_ORDER:
                if fallback not in candidates:
                    candidates.append(fallback)

        # Remove duplicates while preserving order
        seen = set()
        unique = []
        for name in candidates:
            if name in seen:
                continue
            seen.add(name)
            unique.append(name)

        return unique

    def _get_config_value(self, key: str, default):
        """Safely read config values if a ConfigManager is available."""
        if self.config is None:
            return default
        try:
            return self.config.get(key, default)
        except Exception:
            return default

    def _is_accelerate_available(self) -> bool:
        """Check if accelerate is installed."""
        try:
            import accelerate  # noqa: F401
            return True
        except ImportError:
            return False

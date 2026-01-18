"""
Configuration management for MemoryLane
Adapted from ace-system-skill configuration patterns
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional

from constants import (
    CLAUDE_DEFAULT_MODEL,
    CLAUDE_MAX_TOKENS,
    CLAUDE_TIMEOUT,
    LOCAL_LLM_DEFAULT,
    LOCAL_LLM_MODELS,
    DEFAULT_MAX_CONTEXT_TOKENS,
    DEFAULT_COMPRESSION_RATIO,
    DEFAULT_RELEVANCE_THRESHOLD,
    CONFIDENCE_THRESHOLD,
    CONTEXT_ROT_MODEL_TOKENS,
    CONTEXT_ROT_SAFE_FRACTION,
    CONTEXT_ROT_RESERVE_TOKENS,
    CONTEXT_ROT_MIN_INJECTION,
    EXTRACTION_DEFAULT_BACKEND,
)


class ConfigManager:
    """
    Manages MemoryLane configuration
    Pattern adapted from ace-system-skill config loading
    """

    DEFAULT_CONFIG = {
        "memory": {
            "max_context_tokens": DEFAULT_MAX_CONTEXT_TOKENS,
            "compression_ratio_target": DEFAULT_COMPRESSION_RATIO,
            "max_memories_per_category": 150,
            "relevance_threshold": DEFAULT_RELEVANCE_THRESHOLD,
            "enable_passive_learning": True,
            "update_frequency_seconds": 30
        },
        "context_rot": {
            "enabled": True,
            "model_context_tokens": CONTEXT_ROT_MODEL_TOKENS,
            "safe_fraction": CONTEXT_ROT_SAFE_FRACTION,
            "reserve_tokens": CONTEXT_ROT_RESERVE_TOKENS,
            "min_injection_tokens": CONTEXT_ROT_MIN_INJECTION
        },
        "learning": {
            "watch_file_changes": True,
            "watch_git_commits": True,
            "watch_terminal_output": False,
            "index_on_startup": True,
            "incremental_updates": True,
            "surprise_threshold": 0.6
        },
        "extraction": {
            "backend": EXTRACTION_DEFAULT_BACKEND,  # "auto", "claude", "local_llm", "regex"
            "claude_model": CLAUDE_DEFAULT_MODEL,
            "claude_max_tokens": CLAUDE_MAX_TOKENS,
            "claude_timeout": CLAUDE_TIMEOUT
        },
        "summarizer": {
            "enabled": True,
            "model": LOCAL_LLM_DEFAULT,
            "fallback_models": LOCAL_LLM_MODELS[1:],  # Skip first (default)
            "auto_summarize": False,
            "min_session_length": 500,
            "batch_processing": True,
            "confidence_threshold": CONFIDENCE_THRESHOLD,
            "max_input_tokens": 4096,
            "max_new_tokens": 512,
            "temperature": 0.2,
            "top_p": 0.9,
            "do_sample": False,
            "allow_download": True
        },
        "compression": {
            "target_ratio": 7.0,
            "min_ratio": 3.0,
            "preserve_important": True,
            "deduplication_threshold": 0.85,
            "summarization_enabled": True
        },
        "costs": {
            "track_savings": True,
            "baseline_token_count": 20000,
            "cost_per_million_input_tokens": 3.0,
            "cost_per_million_output_tokens": 15.0,
            "show_savings_in_statusbar": True
        },
        "privacy": {
            "encrypt_at_rest": False,  # Simplified for MVP
            "exclude_patterns": [
                "*.env",
                "*.key",
                "*.pem",
                "*.pfx",
                "**/secrets/**",
                "**/credentials/**",
                "**/.git/**",
                "**/node_modules/**",
                "**/__pycache__/**",
                "**/*.pyc"
            ],
            "allow_terminal_capture": False,
            "local_only": True
        },
        "performance": {
            "max_ram_mb": 2048,
            "max_vram_mb": 4096,
            "retrieval_latency_ms": 100,
            "update_latency_ms": 200,
            "max_concurrent_operations": 4,
            "cache_embeddings": True
        },
        "paths": {
            "memory_dir": ".memorylane",
            "memories_file": ".memorylane/memories.json",
            "config_file": ".memorylane/config.json",
            "backup_dir": ".memorylane/backups",
            "logs_dir": ".memorylane/logs",
            "embeddings_cache": ".memorylane/embeddings.db",
            "metrics_file": ".memorylane/metrics.json"
        },
        "features": {
            "cost_tracking": True,
            "compression": True,
            "passive_learning": True,
            "auto_context_injection": True,
            "git_integration": True,
            "terminal_integration": False
        },
        "curation": {
            "enabled": False,
            "trigger_memory_count": 15,
            "max_memories_per_review": 20
        }
    }

    def __init__(self, config_path: Optional[str] = None):
        """Initialize configuration manager"""
        if config_path:
            self.config_path = Path(config_path)
        else:
            # Try to find config in standard locations
            self.config_path = self._find_config_file()

        self.config = self.load()
        self.setup_directories()

    def _find_config_file(self) -> Path:
        """Find configuration file in standard locations"""
        # Check in order:
        # 1. .memorylane/config.json in current directory
        # 2. config.json in project root
        # 3. ~/.memorylane/config.json (user home)

        candidates = [
            Path.cwd() / ".memorylane" / "config.json",
            Path.cwd() / "config.json",
            Path.home() / ".memorylane" / "config.json"
        ]

        for path in candidates:
            if path.exists():
                return path

        # Default to .memorylane/config.json in current directory
        return Path.cwd() / ".memorylane" / "config.json"

    def load(self) -> Dict[str, Any]:
        """Load configuration from file or use defaults"""
        if not self.config_path.exists():
            # Create default config file
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, 'w') as f:
                json.dump(self.DEFAULT_CONFIG, f, indent=2)
            return self.DEFAULT_CONFIG.copy()

        try:
            with open(self.config_path, 'r') as f:
                user_config = json.load(f)

            # Merge with defaults (user config overrides defaults)
            return self._merge_configs(self.DEFAULT_CONFIG, user_config)

        except json.JSONDecodeError:
            print(f"Warning: Invalid config file, using defaults")
            return self.DEFAULT_CONFIG.copy()

    def _merge_configs(self, default: Dict, user: Dict) -> Dict:
        """Recursively merge user config with defaults"""
        result = default.copy()

        for key, value in user.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = value

        return result

    def save(self):
        """Save current configuration to file"""
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f, indent=2)

    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation
        Example: config.get('memory.max_context_tokens')
        """
        keys = key_path.split('.')
        value = self.config

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default

        return value

    def set(self, key_path: str, value: Any):
        """
        Set configuration value using dot notation
        Example: config.set('memory.max_context_tokens', 3000)
        """
        keys = key_path.split('.')
        config = self.config

        # Navigate to the parent dictionary
        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]

        # Set the value
        config[keys[-1]] = value
        self.save()

    def setup_directories(self):
        """Create necessary directories based on configuration"""
        paths = self.config.get('paths', {})

        for path_key, path_value in paths.items():
            if path_key.endswith('_dir'):
                path = Path(path_value)
                path.mkdir(parents=True, exist_ok=True)

    def is_file_excluded(self, file_path: str) -> bool:
        """Check if a file matches exclusion patterns"""
        from fnmatch import fnmatch

        exclude_patterns = self.get('privacy.exclude_patterns', [])

        for pattern in exclude_patterns:
            if fnmatch(file_path, pattern):
                return True

        return False

    def get_path(self, path_key: str) -> Path:
        """Get a configured path as a Path object"""
        path_value = self.get(f'paths.{path_key}')
        if path_value:
            return Path(path_value)
        raise ValueError(f"Path not configured: {path_key}")

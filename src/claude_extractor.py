"""
Claude-powered knowledge extraction for MemoryLane.

Uses Claude (via CLI or API) to extract high-quality memories from conversations.
Falls back to regex-based extraction if Claude is unavailable.
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from learning_prompts import (
    LearningPrompt,
    get_prompt_for_trigger,
    detect_trigger_type,
    format_extraction_request,
    OUTPUT_SCHEMA,
)
from constants import (
    CLAUDE_DEFAULT_MODEL,
    CLAUDE_MAX_TOKENS,
    CLAUDE_TIMEOUT,
    EXTRACTION_BACKENDS,
    EXTRACTION_DEFAULT_BACKEND,
)


@dataclass
class ExtractedMemory:
    """A memory extracted by Claude."""
    category: str
    content: str
    relevance: float
    tags: List[str]
    source: str = "claude_extraction"


class ClaudeExtractor:
    """
    Extract memories using Claude.

    Supports multiple backends (configurable via extraction.backend):
    - "auto": Claude CLI -> Anthropic API -> Local LLM -> Regex (default)
    - "claude": Claude CLI or API only, no fallback
    - "local_llm": Local LLM only (SmolLM/Qwen)
    - "regex": Regex heuristics only (zero dependencies)
    """

    # Valid backend options
    BACKENDS = set(EXTRACTION_BACKENDS)

    def __init__(
        self,
        config: Optional[Dict] = None,
        use_cli: bool = True,
        model: str = CLAUDE_DEFAULT_MODEL,
        max_tokens: int = CLAUDE_MAX_TOKENS,
    ):
        self.config = config or {}

        # Load from config if available
        extraction_config = self._get_config("extraction", {})
        self.backend = extraction_config.get("backend", EXTRACTION_DEFAULT_BACKEND)
        if self.backend not in self.BACKENDS:
            self.backend = EXTRACTION_DEFAULT_BACKEND

        self.use_cli = use_cli
        self.model = extraction_config.get("claude_model", model)
        self.max_tokens = extraction_config.get("claude_max_tokens", max_tokens)
        self.timeout = extraction_config.get("claude_timeout", CLAUDE_TIMEOUT)

        self._cli_available: Optional[bool] = None
        self._api_available: Optional[bool] = None

    def _get_config(self, key: str, default: Any = None) -> Any:
        """Get config value with dot notation support."""
        if not self.config:
            return default
        try:
            if hasattr(self.config, 'get'):
                # Handle both dict and ConfigManager
                return self.config.get(key, default)
            return default
        except Exception:
            return default

    @property
    def cli_available(self) -> bool:
        """Check if Claude CLI is available."""
        if self._cli_available is None:
            try:
                result = subprocess.run(
                    ["claude", "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                self._cli_available = result.returncode == 0
            except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
                self._cli_available = False
        return self._cli_available

    @property
    def api_available(self) -> bool:
        """Check if Anthropic API is available."""
        if self._api_available is None:
            self._api_available = bool(os.environ.get("ANTHROPIC_API_KEY"))
        return self._api_available

    def extract(
        self,
        text: str,
        trigger: Optional[str] = None,
        context: Optional[Dict] = None,
        project_name: Optional[str] = None,
    ) -> List[ExtractedMemory]:
        """
        Extract memories from text.

        Backend selection based on config (extraction.backend):
        - "auto": Claude -> Local LLM -> Regex (default)
        - "claude": Claude only, no fallback
        - "local_llm": Local LLM only
        - "regex": Regex heuristics only

        Args:
            text: The conversation/transcript to analyze
            trigger: Explicit trigger type, or auto-detected from context
            context: Context dict for trigger detection
            project_name: Project name for context

        Returns:
            List of extracted memories
        """
        if not text or not text.strip():
            return []

        # Detect trigger type if not specified
        if trigger is None:
            trigger = detect_trigger_type(context or {})

        # Get the appropriate prompt
        prompt = get_prompt_for_trigger(trigger)

        # Format the request
        user_message = format_extraction_request(
            prompt=prompt,
            transcript_text=text,
            project_name=project_name,
        )

        # Backend selection
        if self.backend == "regex":
            return self._regex_extraction(text)

        if self.backend == "local_llm":
            return self._local_llm_extraction(text)

        if self.backend == "claude":
            # Claude only, no fallback
            response = self._call_claude(prompt.system_prompt, user_message)
            if response:
                return self._parse_response(response)
            return []

        # "auto" mode: try Claude, then local LLM, then regex
        response = self._call_claude(prompt.system_prompt, user_message)
        if response:
            memories = self._parse_response(response)
            if memories:
                return memories

        # Try local LLM fallback
        memories = self._local_llm_extraction(text)
        if memories:
            return memories

        # Final fallback: regex
        return self._regex_extraction(text)

    def _call_claude(self, system_prompt: str, user_message: str) -> Optional[str]:
        """Call Claude using CLI or API."""
        if self.use_cli and self.cli_available:
            return self._call_cli(system_prompt, user_message)

        if self.api_available:
            return self._call_api(system_prompt, user_message)

        return None

    def _call_cli(self, system_prompt: str, user_message: str) -> Optional[str]:
        """Call Claude using the CLI."""
        try:
            # Use claude CLI with --print flag for non-interactive mode
            # Pass the combined prompt via stdin
            combined = f"{system_prompt}\n\n{user_message}"

            result = subprocess.run(
                [
                    "claude",
                    "--print",  # Non-interactive, just print response
                    "--model", self.model,
                    "--max-tokens", str(self.max_tokens),
                ],
                input=combined,
                capture_output=True,
                text=True,
                timeout=60,  # 60 second timeout for extraction
            )

            if result.returncode == 0 and result.stdout:
                return result.stdout.strip()

            return None

        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            self._log_debug(f"CLI call failed: {e}")
            return None

    def _call_api(self, system_prompt: str, user_message: str) -> Optional[str]:
        """Call Claude using the Anthropic API."""
        try:
            import anthropic

            client = anthropic.Anthropic()

            response = client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_message}
                ],
            )

            if response.content and len(response.content) > 0:
                return response.content[0].text

            return None

        except ImportError:
            self._log_debug("anthropic package not installed")
            return None
        except Exception as e:
            self._log_debug(f"API call failed: {e}")
            return None

    def _parse_response(self, response: str) -> List[ExtractedMemory]:
        """Parse Claude's JSON response into ExtractedMemory objects."""
        memories = []

        # Extract JSON from response (may have markdown code blocks)
        json_str = self._extract_json(response)
        if not json_str:
            return memories

        try:
            data = json.loads(json_str)

            # Handle both "memories" and "memory_entries" keys
            entries = data.get("memories") or data.get("memory_entries") or []

            for entry in entries:
                category = entry.get("category", "insights")
                content = entry.get("content", "").strip()
                relevance = entry.get("relevance", 0.8)
                tags = entry.get("tags", [])

                # Validate
                if not content:
                    continue
                if len(content) < 15:
                    continue
                if category not in {"patterns", "insights", "learnings", "context"}:
                    category = "insights"

                try:
                    relevance = float(relevance)
                    relevance = max(0.0, min(1.0, relevance))
                except (TypeError, ValueError):
                    relevance = 0.8

                memories.append(ExtractedMemory(
                    category=category,
                    content=content,
                    relevance=relevance,
                    tags=tags if isinstance(tags, list) else [],
                ))

        except json.JSONDecodeError as e:
            self._log_debug(f"JSON parse error: {e}")

        return memories

    def _extract_json(self, text: str) -> Optional[str]:
        """Extract JSON from text, handling markdown code blocks."""
        if not text:
            return None

        text = text.strip()

        # Remove markdown code blocks
        if text.startswith("```"):
            lines = text.splitlines()
            if len(lines) >= 2:
                lines = lines[1:]  # Remove opening fence
                if lines and lines[-1].strip().startswith("```"):
                    lines = lines[:-1]  # Remove closing fence
                text = "\n".join(lines).strip()

        # Find JSON object
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end > start:
            return text[start:end + 1]

        return None

    def _local_llm_extraction(self, text: str) -> List[ExtractedMemory]:
        """Extract using local LLM (SummarizerService with SmolLM/Qwen)."""
        try:
            from conversation_learner import ConversationLearner
            from summarizer import SummarizerService

            # Try to use the LLM-backed summarizer
            summarizer = SummarizerService(self.config)
            learner = ConversationLearner(config=self.config, summarizer=summarizer)
            extracted = learner.extract_from_text(text, source="local_llm")

            return [
                ExtractedMemory(
                    category=m.category,
                    content=m.content,
                    relevance=m.relevance_score,
                    tags=m.metadata.get("tags", []) if m.metadata else [],
                    source="local_llm",
                )
                for m in extracted
            ]
        except ImportError:
            self._log_debug("Local LLM extraction unavailable (missing dependencies)")
            return []
        except Exception as e:
            self._log_debug(f"Local LLM extraction failed: {e}")
            return []

    def _regex_extraction(self, text: str) -> List[ExtractedMemory]:
        """Extract using regex heuristics only (zero dependencies)."""
        try:
            from conversation_learner import ConversationLearner

            # Force regex-only by not providing a summarizer
            learner = ConversationLearner(config=self.config, summarizer=None)
            extracted = learner.extract_from_text(text, source="regex")

            return [
                ExtractedMemory(
                    category=m.category,
                    content=m.content,
                    relevance=m.relevance_score,
                    tags=[],
                    source="regex",
                )
                for m in extracted
            ]
        except ImportError:
            return []

    def _fallback_extraction(self, text: str) -> List[ExtractedMemory]:
        """Legacy fallback method - calls regex extraction."""
        return self._regex_extraction(text)

    def _log_debug(self, msg: str):
        """Log debug message to file."""
        try:
            log_file = Path.home() / ".memorylane" / "claude-extractor.log"
            log_file.parent.mkdir(parents=True, exist_ok=True)
            from datetime import datetime
            with open(log_file, "a") as f:
                f.write(f"[{datetime.now().isoformat()}] {msg}\n")
        except Exception:
            pass


def extract_from_transcript(
    transcript_path: str,
    trigger: str = "session_end",
    project_name: Optional[str] = None,
) -> List[ExtractedMemory]:
    """
    Convenience function to extract memories from a transcript file.

    Args:
        transcript_path: Path to JSONL transcript
        trigger: Trigger type for prompt selection
        project_name: Optional project name

    Returns:
        List of extracted memories
    """
    path = Path(transcript_path)
    if not path.exists():
        return []

    # Read and parse transcript
    assistant_text = []

    try:
        with open(path, "r") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get("type") == "assistant":
                        message = entry.get("message", {})
                        content = message.get("content", [])
                        if isinstance(content, list):
                            for block in content:
                                if isinstance(block, dict) and block.get("type") == "text":
                                    text = block.get("text", "")
                                    if text:
                                        assistant_text.append(text)
                        elif isinstance(content, str):
                            assistant_text.append(content)
                except json.JSONDecodeError:
                    continue
    except Exception:
        return []

    if not assistant_text:
        return []

    combined = "\n\n".join(assistant_text)

    # Extract using Claude
    extractor = ClaudeExtractor()
    return extractor.extract(
        text=combined,
        trigger=trigger,
        project_name=project_name,
    )

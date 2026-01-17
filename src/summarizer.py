"""
LLM summarizer for MemoryLane learning.
Produces structured memory entries from session transcripts.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from prompt_builder import PromptBuilder
from model_manager import ModelManager


class SummarizerService:
    """Summarize session transcripts using a local LLM."""

    def __init__(
        self,
        config=None,
        model_manager: Optional[ModelManager] = None,
        prompt_builder: Optional[PromptBuilder] = None,
    ):
        self.config = config
        self.model_manager = model_manager or ModelManager(config)

        max_input_tokens = self._get_config_value("summarizer.max_input_tokens", 4096)
        self.prompt_builder = prompt_builder or PromptBuilder(max_input_tokens=max_input_tokens)

    def summarize_text(
        self,
        raw_text: str,
        project_name: Optional[str] = None,
        context_hints: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Summarize a transcript into structured memory entries."""
        if not raw_text or not raw_text.strip():
            return None

        if not self._get_config_value("summarizer.enabled", True):
            return None

        if not self.model_manager.available:
            return None

        min_length = self._get_config_value("summarizer.min_session_length", 0)
        if min_length and self._estimate_tokens(raw_text) < min_length:
            return None

        chunks = self._chunk_text(raw_text)
        results = []

        for chunk in chunks:
            payload = {
                "session_id": str(uuid.uuid4()),
                "timestamp": datetime.now().isoformat(),
                "project_name": project_name or "",
                "raw_transcript": chunk,
                "context_hints": context_hints or [],
            }

            result = self._summarize_payload(payload)
            if result:
                results.append(result)

        return self._merge_results(results)

    def _summarize_payload(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Run a single summarization call."""
        model_bundle = self.model_manager.get_model_and_tokenizer()
        if model_bundle is None:
            return None

        model, tokenizer, _ = model_bundle
        messages = self.prompt_builder.build_messages(payload)

        if hasattr(tokenizer, "apply_chat_template") and getattr(tokenizer, "chat_template", None):
            prompt = tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
            )
        else:
            prompt = self.prompt_builder.build_prompt_text(payload)

        max_input_tokens = self._get_config_value("summarizer.max_input_tokens", 4096)
        inputs = tokenizer(
            prompt,
            return_tensors="pt",
            truncation=True,
            max_length=max_input_tokens,
        )

        input_ids = inputs["input_ids"].to(model.device)
        attention_mask = inputs.get("attention_mask")
        if attention_mask is not None:
            attention_mask = attention_mask.to(model.device)

        max_new_tokens = self._get_config_value("summarizer.max_new_tokens", 512)
        temperature = self._get_config_value("summarizer.temperature", 0.2)
        do_sample = self._get_config_value("summarizer.do_sample", False)
        top_p = self._get_config_value("summarizer.top_p", 0.9)

        pad_token_id = tokenizer.eos_token_id or tokenizer.pad_token_id or 0
        torch = getattr(self.model_manager, "_torch", None)

        if torch:
            with torch.no_grad():
                generation = model.generate(
                    input_ids=input_ids,
                    attention_mask=attention_mask,
                    max_new_tokens=max_new_tokens,
                    do_sample=do_sample,
                    temperature=temperature,
                    top_p=top_p,
                    pad_token_id=pad_token_id,
                )
        else:
            generation = model.generate(
                input_ids=input_ids,
                attention_mask=attention_mask,
                max_new_tokens=max_new_tokens,
                do_sample=do_sample,
                temperature=temperature,
                top_p=top_p,
                pad_token_id=pad_token_id,
            )

        new_tokens = generation[0][input_ids.shape[1]:]
        decoded = tokenizer.decode(new_tokens, skip_special_tokens=True)

        return self._parse_output(decoded)

    def _parse_output(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract JSON from model output."""
        payload = self._extract_json(text)
        if not payload:
            return None

        if "summary" not in payload or "memory_entries" not in payload:
            return None

        if not isinstance(payload.get("memory_entries"), list):
            payload["memory_entries"] = []

        if "suggested_deletions" not in payload:
            payload["suggested_deletions"] = []

        return payload

    def _extract_json(self, text: str) -> Optional[Dict[str, Any]]:
        """Parse JSON from raw model output."""
        if not text:
            return None

        cleaned = text.strip()

        # Remove fenced code blocks if present.
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if len(lines) >= 2:
                lines = lines[1:]  # drop opening fence
                if lines and lines[-1].strip().startswith("```"):
                    lines = lines[:-1]
                cleaned = "\n".join(lines).strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None

        try:
            return json.loads(cleaned[start:end + 1])
        except json.JSONDecodeError:
            return None

    def _merge_results(self, results: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Merge multi-chunk results into a single response."""
        if not results:
            return None

        if len(results) == 1:
            return results[0]

        summary_parts = []
        memory_entries: List[Dict[str, Any]] = []
        suggested_deletions: List[str] = []

        for result in results:
            summary = result.get("summary", "").strip()
            if summary:
                summary_parts.append(summary)
            memory_entries.extend(result.get("memory_entries", []))
            suggested_deletions.extend(result.get("suggested_deletions", []))

        combined_summary = " ".join(summary_parts).strip()
        if combined_summary:
            combined_summary = self._trim_summary(combined_summary)

        return {
            "summary": combined_summary,
            "memory_entries": self._dedupe_entries(memory_entries),
            "suggested_deletions": list(dict.fromkeys(suggested_deletions)),
        }

    def _trim_summary(self, summary: str, max_sentences: int = 4) -> str:
        """Trim summary to a few sentences."""
        sentences = summary.split(". ")
        if len(sentences) <= max_sentences:
            return summary
        trimmed = ". ".join(sentences[:max_sentences]).strip()
        if not trimmed.endswith("."):
            trimmed += "."
        return trimmed

    def _dedupe_entries(self, entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Deduplicate memory entries by content."""
        seen = set()
        unique = []
        for entry in entries:
            content = str(entry.get("content", "")).strip().lower()
            if not content:
                continue
            sig = content[:80]
            if sig in seen:
                continue
            seen.add(sig)
            unique.append(entry)
        return unique

    def _chunk_text(self, text: str) -> List[str]:
        """Chunk large transcripts to avoid context overflow."""
        max_tokens = self._get_config_value("summarizer.max_input_tokens", 4096)
        max_tokens = max(512, max_tokens - 512)
        tokens = self._estimate_tokens(text)
        if tokens <= max_tokens:
            return [text]

        words = text.split()
        words_per_chunk = int(max_tokens / 1.3)
        words_per_chunk = max(200, words_per_chunk)

        chunks = []
        for i in range(0, len(words), words_per_chunk):
            chunk_words = words[i:i + words_per_chunk]
            chunks.append(" ".join(chunk_words))

        return chunks

    def _estimate_tokens(self, text: str) -> int:
        """Rough token estimate using word count."""
        return int(len(text.split()) * 1.3)

    def _get_config_value(self, key: str, default):
        if self.config is None:
            return default
        try:
            return self.config.get(key, default)
        except Exception:
            return default

"""
Conversation Learning for MemoryLane

Extracts valuable insights from Claude Code conversations and adds them to memory.
Uses a multi-strategy approach for flexible pattern detection.
"""

import re
import json
from typing import List, Dict, Tuple, Optional, Set, Any
from dataclasses import dataclass, field
from pathlib import Path

from summarizer import SummarizerService


@dataclass
class ExtractedMemory:
    """A memory extracted from conversation"""
    content: str
    category: str  # patterns, insights, learnings, context
    relevance_score: float
    source: str
    strategy: str = 'unknown'  # Which strategy extracted this
    metadata: Dict[str, Any] = field(default_factory=dict)


class ConversationLearner:
    """
    Extracts learnable content from conversations using multiple strategies.

    Strategies (run in parallel, best match wins):
    1. Strict patterns (original regex-based approach)
    2. Template patterns with synonym expansion
    3. Structural patterns (X over Y:, X not Y, etc.)
    4. Semantic scoring (indicator word presence)

    Identifies:
    - Architectural decisions and rationale
    - Bug patterns and solutions
    - Code patterns worth remembering
    - Configuration/setup knowledge
    - Debugging insights
    """

    # ==================== STRATEGY 1: Strict Patterns (Original) ====================

    # Patterns that indicate valuable content
    INSIGHT_PATTERNS = [
        # Architectural decisions (allow multi-word terms)
        (r'(?:chose|chosen|use|using)\s+(.+?)\s+(?:over|instead of|rather than)\s+(.+?)\s+(?:because|for|due to|since)', 'patterns', 0.95),
        (r'(?:the reason|rationale)\s+(?:for|behind)\s+(.+?)(?:\.|$)', 'insights', 0.85),
        (r'(.+?)\s+(?:gives?|provides?|offers?)\s+(?:better|faster|lower|higher)\s+(.+?)\s+(?:than|compared to)', 'insights', 0.85),

        # Bug patterns and fixes
        (r'(?:fixed|solved|resolved)\s+(?:by|with)\s+(.+?)(?:\.|$)', 'learnings', 0.9),
        (r'(?:the (?:issue|bug|problem|error))\s+(?:was|is)\s+(?:caused by|due to)\s+(.+?)(?:\.|$)', 'learnings', 0.95),
        (r'(?:was caused by|caused by)\s+(.+?)(?:\s*[-–—]\s*(?:fixed|solved)|(?:\.|$))', 'learnings', 0.95),
        (r'(?:to fix|the fix)\s+(?:is|was)\s+(.+?)(?:\.|$)', 'learnings', 0.9),

        # Code patterns
        (r'(?:pattern|approach|technique)\s*:\s*(.+?)(?:\.|$)', 'patterns', 0.8),
        (r'(?:always|never|should|must)\s+(.+?)\s+(?:when|before|after)\s+(.+?)(?:\.|$)', 'learnings', 0.85),
        (r'(?:should never be|must not be|never)\s+(.+?)(?:\.|$)', 'learnings', 0.8),

        # Configuration knowledge
        (r'(?:configured?|set(?:ting)?|option)\s+(?:in|at)\s+([^\s]+)\s+(?:to|as|for)\s+(.+?)(?:\.|$)', 'context', 0.75),
        (r'(?:file|path|location)\s+(?:is|at)\s+([^\s]+)', 'context', 0.7),
        (r'(?:stored|saved|located)\s+(?:in|at)\s+([^\s]+)', 'context', 0.7),
    ]

    # Keywords that boost relevance
    HIGH_VALUE_KEYWORDS = {
        'critical', 'important', 'always', 'never', 'must', 'required',
        'error', 'bug', 'fix', 'solved', 'issue', 'problem',
        'performance', 'security', 'optimization',
        'architecture', 'design', 'pattern', 'convention',
        'api', 'endpoint', 'authentication', 'authorization',
    }

    # Keywords that indicate category
    CATEGORY_KEYWORDS = {
        'patterns': {'pattern', 'structure', 'convention', 'architecture', 'design', 'format', 'protocol'},
        'insights': {'insight', 'learned', 'discovered', 'realized', 'found that', 'turns out'},
        'learnings': {'fix', 'solved', 'error', 'bug', 'issue', 'debug', 'problem', 'solution'},
        'context': {'config', 'setting', 'file', 'path', 'directory', 'location', 'command'},
    }

    # ==================== STRATEGY 2: Template Patterns with Synonyms ====================

    # Verbs that indicate a decision was made
    DECISION_VERBS = {
        'chose', 'choose', 'chosen', 'picked', 'pick', 'selected', 'select',
        'decided', 'decide', 'went', 'go', 'opted', 'opt', 'used', 'use',
        'using', 'prefer', 'preferred', 'switched', 'switch', 'moved',
    }

    # Words that indicate comparison/alternative
    COMPARISON_WORDS = {
        'over', 'instead of', 'rather than', 'not', 'vs', 'versus',
        'instead', 'replacing', 'replace', 'swap', 'swapped',
    }

    # Words that can start a reason (or punctuation)
    REASON_STARTERS = {
        'because', 'since', 'for', 'due to', 'as', 'given', 'so',
        ':', '-', '–', '—',  # Punctuation that often precedes reasons
    }

    # ==================== STRATEGY 3: Structural Patterns ====================

    # Patterns that detect structure rather than specific words
    STRUCTURE_PATTERNS = [
        # "X was too low/high at Y, ... fixed/changed/using Z" (parameter tuning)
        (r'(\w+(?:\s+\w+)?)\s+(?:was|is)\s+too\s+(?:low|high)\s+(?:at\s+)?(\S+)[^.]*?(?:fixed|changed|now|using)\s+(\S+)', 'learnings', 0.9),
        # "X over Y: reason" or "X over Y - reason"
        (r'([A-Za-z][A-Za-z0-9 _-]{1,30}?)\s+over\s+([A-Za-z][A-Za-z0-9 _-]{1,30}?)\s*[:\-–—]\s*(.{10,80})', 'patterns', 0.9),
        # "X, not Y" or "use X, not Y"
        (r'(?:use\s+)?([A-Za-z][A-Za-z0-9 _-]{1,25}?),\s*not\s+([A-Za-z][A-Za-z0-9 _-]{1,25})', 'patterns', 0.85),
        # "X >> Y" or "X > Y" (comparison operators)
        (r'([A-Za-z][A-Za-z0-9 _-]{1,25}?)\s*>{1,2}\s*([A-Za-z][A-Za-z0-9 _-]{1,25})', 'patterns', 0.85),
        # "X is better/faster/simpler than Y"
        (r'([A-Za-z][A-Za-z0-9 _-]{1,25}?)\s+(?:is|are|was|were)\s+(?:better|faster|slower|simpler|easier|harder|safer|more|less)\s+(?:than)\s+([A-Za-z][A-Za-z0-9 _-]{1,25})', 'insights', 0.85),
        # "Fixed: description" or "Fix: description"
        (r'(?:fixed|fix|solved|resolved)\s*:\s*(.{10,100})', 'learnings', 0.85),
        # "The cause/problem/issue was X"
        (r'(?:the\s+)?(?:cause|problem|issue|bug|root cause)\s+(?:was|is|were)\s+(.{10,100})', 'learnings', 0.9),
        # Solution patterns - prioritize these over problem statements
        # "Created X to fix/handle Y" or "Added X to fix Y"
        (r'(?:created|added|implemented|wrote)\s+(.{5,50}?)\s+(?:to|which)\s+(?:fix|handle|solve|address)(?:es|ed)?\s+(.{5,80})', 'learnings', 0.95),
        # "Fixed by creating/adding X"
        (r'(?:fixed|solved|resolved)\s+by\s+(?:creating|adding|implementing|using)\s+(.{10,100})', 'learnings', 0.95),
        # "The fix was to X" or "Solution was to X"
        (r'(?:the\s+)?(?:fix|solution|answer)\s+(?:was|is)\s+to\s+(.{10,100})', 'learnings', 0.95),
    ]

    # ==================== STRATEGY 4: Semantic Indicators ====================

    # Words that indicate different types of learnable content
    LEARNING_INDICATORS = {
        'bug_fix': {'fix', 'fixed', 'resolved', 'solved', 'patched', 'corrected', 'repaired'},
        'root_cause': {'caused', 'cause', 'because', 'due', 'resulted', 'source', 'root', 'reason'},
        'decision': {'chose', 'decided', 'picked', 'selected', 'went', 'opted', 'prefer', 'use'},
        'comparison': {'over', 'instead', 'rather', 'better', 'worse', 'faster', 'slower', 'simpler', 'easier'},
        'rule': {'always', 'never', 'must', 'should', 'avoid', 'prefer', 'ensure', 'require'},
        'location': {'stored', 'located', 'found', 'lives', 'config', 'path', 'file', 'directory'},
        'tuning': {'threshold', 'too', 'low', 'high', 'value', 'adjusted', 'changed', 'tuned', 'returning'},
        'architecture': {'component', 'extension', 'server', 'client', 'interface', 'layer', 'module', 'provides', 'communicates'},
    }

    # ==================== STRATEGY 5: Component Descriptions ====================

    # Patterns for component/architecture explanations
    DESCRIPTION_PATTERNS = [
        # "The X is a Y that provides/handles/manages Z"
        (r'[Tt]he\s+([A-Za-z][A-Za-z0-9 _-]{2,30}?)\s+(?:is|are)\s+(?:a|an|the)\s+([A-Za-z][A-Za-z0-9 _-]{2,30}?)\s+that\s+(?:provides?|handles?|manages?|communicates?|connects?)\s+(.{10,80})', 'context', 0.8),
        # "X/It communicates/connects with [the] Y via/through Z"
        (r'(?:It|[A-Za-z][A-Za-z0-9 _-]{2,25}?)\s+(?:communicates?|connects?|talks?)\s+(?:with|to)\s+(?:the\s+)?([A-Za-z][A-Za-z0-9 _-]{2,30}?)\s+(?:via|through|using)\s+([A-Za-z][A-Za-z0-9 _-]{2,30})', 'context', 0.85),
        # "X serves as the Y for Z" or "X acts as Y"
        (r'([A-Za-z][A-Za-z0-9 _-]{2,25}?)\s+(?:serves?|acts?)\s+as\s+(?:the\s+)?([A-Za-z][A-Za-z0-9 _-]{2,40})', 'context', 0.8),
        # "Core idea/purpose: ..." or "The idea is ..."
        (r'(?:core\s+)?(?:idea|purpose|goal)\s*(?:is|:)\s*(.{15,120})', 'insights', 0.85),
    ]

    # Minimum indicator score to consider a sentence learnable (0-1 scale)
    SEMANTIC_THRESHOLD = 0.35

    LLM_TYPE_TO_CATEGORY = {
        "design_decision": "insights",
        "problem_solved": "learnings",
        "pattern_established": "patterns",
        "constraint_discovered": "context",
        "future_consideration": "context",
        "dependency_added": "context",
    }

    def __init__(self, config=None, summarizer: Optional[SummarizerService] = None):
        self.config = config
        self.summarizer = summarizer

        if self.summarizer is None and self.config is not None:
            self.summarizer = SummarizerService(self.config)

    def extract_from_text(self, text: str, source: str = 'conversation') -> List[ExtractedMemory]:
        """
        Extract memories from freeform text using multiple strategies.

        Runs all strategies in parallel and keeps the best matches.

        Args:
            text: The text to analyze
            source: Source identifier for the memories

        Returns:
            List of extracted memories
        """
        candidates = []

        # LLM-first extraction with regex fallback.
        llm_memories = self._extract_with_llm(text, source)
        if llm_memories:
            return self._deduplicate_by_score(llm_memories)

        # Split into sentences for analysis
        sentences = self._split_sentences(text)

        for sentence in sentences:
            # Skip very short sentences
            if len(sentence.split()) < 4:
                continue

            # Skip code, tool output, and noise
            if self._is_code_or_noise(sentence):
                continue

            # Strategy 1: Original strict patterns
            candidates.extend(self._extract_by_strict_patterns(sentence, source))

            # Strategy 2: Template patterns with synonyms
            candidates.extend(self._extract_by_templates(sentence, source))

            # Strategy 3: Structural patterns
            candidates.extend(self._extract_by_structure(sentence, source))

            # Strategy 4: Semantic scoring
            candidates.extend(self._extract_by_semantics(sentence, source))

            # Strategy 5: Component descriptions
            candidates.extend(self._extract_by_descriptions(sentence, source))

        # Deduplicate, keeping highest-scoring version
        return self._deduplicate_by_score(candidates)

    def _extract_with_llm(self, text: str, source: str) -> List[ExtractedMemory]:
        """Try LLM summarization and map results into memory entries."""
        if self.summarizer is None:
            return []

        project_name = Path.cwd().name
        result = self.summarizer.summarize_text(
            raw_text=text,
            project_name=project_name,
        )
        if not result:
            return []

        confidence_threshold = 0.7
        if self.config is not None:
            confidence_threshold = self.config.get(
                "summarizer.confidence_threshold",
                confidence_threshold,
            )

        memories = []
        for entry in result.get("memory_entries", []):
            entry_type = entry.get("type")
            category = self.LLM_TYPE_TO_CATEGORY.get(entry_type, "insights")
            content = str(entry.get("content", "")).strip()
            confidence = entry.get("confidence", 0.75)

            try:
                confidence = float(confidence)
            except (TypeError, ValueError):
                confidence = 0.75

            if not content:
                continue
            if confidence < confidence_threshold:
                continue

            if content and not re.search(r'[.!?)\]"]$', content):
                content = f"{content}."

            cleaned = self._clean_content(content)
            if cleaned is None:
                continue

            relevance = max(0.5, min(1.0, float(confidence)))
            memories.append(ExtractedMemory(
                content=cleaned,
                category=category,
                relevance_score=relevance,
                source=source,
                strategy="llm",
                metadata={
                    "llm_type": entry_type,
                    "tags": entry.get("tags", []),
                },
            ))

        return memories

    def _extract_by_strict_patterns(self, sentence: str, source: str) -> List[ExtractedMemory]:
        """Strategy 1: Original strict regex pattern matching."""
        memories = []

        for pattern, category, base_score in self.INSIGHT_PATTERNS:
            match = re.search(pattern, sentence, re.IGNORECASE)
            if match:
                content = self._clean_content(sentence)
                if content is None:
                    continue  # Skip low-quality content
                score = self._calculate_relevance(sentence, base_score)
                memories.append(ExtractedMemory(
                    content=content,
                    category=category,
                    relevance_score=min(score, 1.0),
                    source=source,
                    strategy='strict_pattern'
                ))
                break  # Only one match per strategy per sentence

        # Also try keyword-based extraction as fallback
        if not memories:
            memory = self._extract_by_keywords(sentence, source)
            if memory:
                memory.strategy = 'keyword_fallback'
                memories.append(memory)

        return memories

    def _extract_by_templates(self, sentence: str, source: str) -> List[ExtractedMemory]:
        """
        Strategy 2: Template-based extraction with synonym expansion.

        Detects: DECISION_VERB + subject + COMPARISON_WORD + alternative [+ reason]
        """
        memories = []
        sentence_lower = sentence.lower()
        words = sentence_lower.split()

        # Check if sentence contains decision verb and comparison word
        has_decision_verb = any(verb in sentence_lower for verb in self.DECISION_VERBS)
        has_comparison = any(comp in sentence_lower for comp in self.COMPARISON_WORDS)

        if has_decision_verb and has_comparison:
            # This looks like a decision - extract it
            content = self._clean_content(sentence)
            if content is None:
                return memories  # Skip low-quality content

            score = 0.85

            # Boost score if reason is present
            has_reason = any(starter in sentence_lower for starter in self.REASON_STARTERS if starter.isalpha())
            if has_reason or ':' in sentence or '-' in sentence:
                score = 0.9

            memories.append(ExtractedMemory(
                content=content,
                category='patterns',
                relevance_score=self._calculate_relevance(sentence, score),
                source=source,
                strategy='template'
            ))

        return memories

    def _extract_by_structure(self, sentence: str, source: str) -> List[ExtractedMemory]:
        """
        Strategy 3: Detect structural patterns regardless of specific words.

        Patterns like "X over Y:", "X, not Y", "X >> Y", comparative adjectives.
        """
        memories = []

        for pattern, category, base_score in self.STRUCTURE_PATTERNS:
            match = re.search(pattern, sentence, re.IGNORECASE)
            if match:
                content = self._clean_content(sentence)
                if content is None:
                    continue  # Skip low-quality content
                score = self._calculate_relevance(sentence, base_score)
                memories.append(ExtractedMemory(
                    content=content,
                    category=category,
                    relevance_score=min(score, 1.0),
                    source=source,
                    strategy='structure'
                ))
                break  # Only one match per strategy per sentence

        return memories

    def _extract_by_semantics(self, sentence: str, source: str) -> List[ExtractedMemory]:
        """
        Strategy 4: Score sentences by semantic indicator presence.

        Looks for indicator words across multiple categories and calculates
        a confidence score. Extracts if above threshold.
        """
        memories = []
        sentence_lower = sentence.lower()
        words = set(re.findall(r'\b\w+\b', sentence_lower))

        # Count indicators in each category
        category_scores = {}
        total_indicators = 0

        for indicator_type, indicators in self.LEARNING_INDICATORS.items():
            matches = words & indicators
            if matches:
                category_scores[indicator_type] = len(matches)
                total_indicators += len(matches)

        # Calculate semantic score (0-1 scale)
        # More indicator types matched = higher confidence
        num_categories_matched = len(category_scores)
        if num_categories_matched >= 2:
            # Multiple indicator types = likely learnable content
            semantic_score = min(1.0, (num_categories_matched * 0.2) + (total_indicators * 0.1))

            if semantic_score >= self.SEMANTIC_THRESHOLD:
                # Determine best category based on indicator type
                if 'bug_fix' in category_scores or 'root_cause' in category_scores:
                    category = 'learnings'
                    base_score = 0.8
                elif 'decision' in category_scores or 'comparison' in category_scores:
                    category = 'patterns'
                    base_score = 0.8
                elif 'rule' in category_scores:
                    category = 'learnings'
                    base_score = 0.75
                elif 'location' in category_scores:
                    category = 'context'
                    base_score = 0.7
                else:
                    category = 'insights'
                    base_score = 0.7

                content = self._clean_content(sentence)
                if content is not None:
                    memories.append(ExtractedMemory(
                        content=content,
                        category=category,
                        relevance_score=self._calculate_relevance(sentence, base_score),
                        source=source,
                        strategy='semantic'
                    ))

        return memories

    def _extract_by_descriptions(self, sentence: str, source: str) -> List[ExtractedMemory]:
        """
        Strategy 5: Extract component/architecture descriptions.

        Captures explanatory statements about what components are and how they work.
        """
        memories = []

        for pattern, category, base_score in self.DESCRIPTION_PATTERNS:
            match = re.search(pattern, sentence, re.IGNORECASE)
            if match:
                content = self._clean_content(sentence)
                if content is None:
                    continue  # Skip low-quality content
                score = self._calculate_relevance(sentence, base_score)
                memories.append(ExtractedMemory(
                    content=content,
                    category=category,
                    relevance_score=min(score, 1.0),
                    source=source,
                    strategy='description'
                ))
                break  # Only one match per strategy per sentence

        return memories

    def extract_from_transcript(self, transcript_path: str) -> List[ExtractedMemory]:
        """
        Extract memories from a Claude Code session transcript (JSONL format).

        Args:
            transcript_path: Path to the transcript file

        Returns:
            List of extracted memories
        """
        memories = []
        assistant_text = []
        path = Path(transcript_path)

        if not path.exists():
            return memories

        try:
            with open(path, 'r') as f:
                for line in f:
                    if not line.strip():
                        continue

                    try:
                        entry = json.loads(line)

                        # Extract from assistant responses
                        # Claude Code transcript format: {"type": "assistant", "message": {"content": [...]}}
                        if entry.get('type') == 'assistant':
                            message = entry.get('message', {})
                            content = message.get('content', [])

                            # Content is an array of content blocks
                            if isinstance(content, list):
                                for block in content:
                                    if isinstance(block, dict) and block.get('type') == 'text':
                                        text = block.get('text', '')
                                        if text:
                                            assistant_text.append(text)
                            elif isinstance(content, str):
                                # Fallback for simple string content
                                assistant_text.append(content)

                        # NOTE: We intentionally DO NOT learn from tool results.
                        # Tool output (code, logs, errors) is too noisy and creates
                        # low-quality memories. We only learn from Claude's conclusions
                        # and explanations in assistant responses.

                    except json.JSONDecodeError:
                        continue

        except Exception:
            pass

        if assistant_text:
            combined = "\n".join(assistant_text)
            memories.extend(self.extract_from_text(combined, 'session_transcript'))

        return self._deduplicate(memories)

    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences"""
        # Split on sentence endings, but avoid list numbers (1. 2. 3.)
        # Use negative lookbehind to skip digits before periods
        sentences = re.split(r'(?<=[a-zA-Z)\]"\'][.!?])\s+', text)
        return [s.strip() for s in sentences if s.strip()]

    def _calculate_relevance(self, text: str, base_score: float) -> float:
        """Calculate relevance score based on content"""
        score = base_score
        text_lower = text.lower()

        # Boost for high-value keywords
        keyword_count = sum(1 for kw in self.HIGH_VALUE_KEYWORDS if kw in text_lower)
        score += keyword_count * 0.05

        # Boost for specific technical terms
        if re.search(r'\b(api|sdk|cli|ipc|socket|hook)\b', text_lower):
            score += 0.05

        # Slight penalty for very long content (probably too verbose)
        if len(text) > 200:
            score -= 0.1

        return max(0.5, min(1.0, score))

    def _extract_by_keywords(self, sentence: str, source: str) -> Optional[ExtractedMemory]:
        """Extract memory based on keyword presence"""
        sentence_lower = sentence.lower()

        # Determine category by keywords
        category_scores = {}
        for category, keywords in self.CATEGORY_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in sentence_lower)
            if score > 0:
                category_scores[category] = score

        if not category_scores:
            return None

        # Use category with most keyword matches
        best_category = max(category_scores, key=category_scores.get)

        # Only extract if enough keywords match
        if category_scores[best_category] < 2:
            return None

        content = self._clean_content(sentence)
        if content is None:
            return None  # Skip low-quality content

        relevance = self._calculate_relevance(sentence, 0.7)

        return ExtractedMemory(
            content=content,
            category=best_category,
            relevance_score=relevance,
            source=source
        )

    def _is_code_or_noise(self, text: str) -> bool:
        """Check if text looks like code, tool output, or noise rather than insight."""
        # Line numbers from cat -n or similar (e.g., "123→")
        if re.search(r'\d+→', text):
            return True

        # Code-like patterns
        if re.search(r'^\s*(import|from|def|class|function|const|let|var)\s+', text):
            return True

        # File path dumps
        if text.count('/') > 3 and text.count('\n') == 0:
            return True

        # JSON/dict literals
        if text.strip().startswith('{') and text.strip().endswith('}'):
            return True

        # Test output (pytest/jest style)
        if re.search(r'test_\w+::|::\w+test|PASSED\s*\[|FAILED\s*\[|\d+\s*passed.*\d+\s*(?:failed|warning|error)', text):
            return True

        # Command output artifacts
        if 'Here\'s the result of running' in text:
            return True

        # Web search artifacts
        if 'Links: [{"title"' in text or '"url":"http' in text:
            return True

        # Transcript artifacts
        if '"stop_reason"' in text or '"stop_se' in text:
            return True

        # ==================== GARBAGE FILTERS ====================
        # These patterns catch content that should NEVER be stored

        # Memory IDs from curation output (e.g., **patt-007**, lear-012)
        if re.search(r'\*\*[a-z]+-\d+\*\*', text) or re.search(r'\b[a-z]{4}-\d{3}\b', text):
            return True

        # Curation section headers and artifacts
        if re.search(r'^##\s*(Quality Issues|Kept|Summary|Memories|Action|Curation)', text):
            return True
        if '⚠️ NEEDS ATTENTION' in text:
            return True
        if re.search(r'\(relevance:\s*\d\.\d+\)', text):
            return True

        # Source prefixes from tool output
        if text.startswith('Source: tool_error') or text.startswith('Source: session_transcript'):
            return True

        # Debug/conversational artifacts - not learnings
        # Check anywhere in sentence (not just start) for planning/diagnostic language
        if re.search(r'(Let me|I\'ll now|I\'m going to|Want me to|Would you like|Here\'s my approach)', text):
            return True
        if re.search(r'^-\s*(raw code|debug|transcript artifact)', text, re.IGNORECASE):
            return True

        # Meta/self-referential statements about the conversation or files
        # These are observations, not learnable knowledge
        if re.search(r'^I (see|notice|found|can see|observe)', text):
            return True
        if re.search(r'(low-quality|high-quality)\s+(memories|content|entries)', text, re.IGNORECASE):
            return True
        if re.search(r'(the file|this file|the memory|memories\.json)\s+(has|have|contains|shows)', text, re.IGNORECASE):
            return True

        # Diagnostic statements (problem identification before solution)
        # These describe what's wrong but not how it was fixed
        if re.search(r'(is missing|but not registered|doesn\'t exist|is not|are missing|but no|need to|should have)', text, re.IGNORECASE):
            # Exception: if it also contains solution language, allow it
            if not re.search(r'(fixed by|solved by|created|added|changed to)', text, re.IGNORECASE):
                return True

        # Markdown list items that are just memory references
        if re.search(r'^\s*-\s*\*\*[a-z]+-\d+\*\*', text):
            return True

        # Code blocks in markdown
        if '```' in text:
            return True

        # Truncated content indicators (usually means bad extraction)
        if text.rstrip().endswith('...') and len(text) < 100:
            return True

        # Headers that aren't insights
        if re.search(r'^#{1,4}\s+(Option|Step|Example|Note|Warning|TODO)', text):
            return True

        return False

    def _clean_content(self, text: str) -> str | None:
        """
        Clean and normalize content for storage.
        Returns None if content doesn't pass quality checks.
        """
        # Remove extra whitespace
        text = ' '.join(text.split())

        # Remove leading/trailing quotes
        text = text.strip('"\'')

        # Skip if too short
        if len(text) < 20:
            return None

        # Truncate if too long, but try to end at sentence boundary
        if len(text) > 200:
            # Find proper sentence endings (not list numbers like "3.")
            # Look for: word + period + space, or word + period at end
            truncated = text[:200]
            # Match sentence end: letter/paren/quote + period + (space or end)
            # Avoid: digit + period (list items like "1. ", "3.")
            matches = list(re.finditer(r'[a-zA-Z)\]"\']\.(?:\s|$)', truncated))
            if matches and matches[-1].end() > 100:
                text = truncated[:matches[-1].end()].rstrip()
            else:
                # Can't find good boundary - reject this content
                # (it's likely mid-paragraph extraction)
                return None

        # Quality gate: must be a complete thought
        if not self._is_complete_thought(text):
            return None

        return text

    def _is_complete_thought(self, text: str) -> bool:
        """
        Check if text represents a complete, well-formed thought.
        Rejects incomplete extractions and mid-sentence fragments.
        """
        text = text.strip()

        if not text:
            return False

        # Must end with proper punctuation (not mid-sentence)
        if not re.search(r'[.!?)\]"]$', text):
            return False

        # Reject if ends with truncation marker
        if text.endswith('...'):
            return False

        # Reject if starts mid-sentence (lowercase without being a known pattern)
        # Allow: "stdio:ignore", "context.extensionPath", code refs
        first_char = text[0]
        if first_char.islower():
            # Allow technical terms that start lowercase
            if not re.match(r'^[a-z]+[:.A-Z_]', text):
                return False

        # Reject markdown artifacts without content
        if re.match(r'^[\*\-#`]+\s*$', text):
            return False

        return True

    def _deduplicate(self, memories: List[ExtractedMemory]) -> List[ExtractedMemory]:
        """Remove duplicate or very similar memories (legacy method)."""
        return self._deduplicate_by_score(memories)

    def _deduplicate_by_score(self, memories: List[ExtractedMemory]) -> List[ExtractedMemory]:
        """
        Remove duplicates, keeping the highest-scoring version.

        Uses first 50 chars of content as signature to detect duplicates.
        """
        # Group by signature
        by_signature: Dict[str, List[ExtractedMemory]] = {}

        for memory in memories:
            # Create a simple signature (first 50 chars, lowercase, normalized)
            sig = re.sub(r'[^a-z0-9]', '', memory.content.lower())[:50]

            if sig not in by_signature:
                by_signature[sig] = []
            by_signature[sig].append(memory)

        # Keep highest-scoring memory for each signature
        unique = []
        for sig, group in by_signature.items():
            # Sort by relevance_score descending
            group.sort(key=lambda m: m.relevance_score, reverse=True)
            unique.append(group[0])

        return unique

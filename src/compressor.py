"""
Context Compression Engine for MemoryLane
Compresses context from 20K tokens to ~3K tokens while preserving meaning
"""

from typing import List, Dict, Set, Tuple
from dataclasses import dataclass
import re


@dataclass
class CompressedContext:
    """Result of context compression"""
    original_text: str
    compressed_text: str
    original_tokens: int
    compressed_tokens: int
    compression_ratio: float
    sections_kept: List[str]
    sections_removed: List[str]


class ContextCompressor:
    """
    Compresses context using multiple strategies:
    1. Deduplication - Remove repeated information
    2. Summarization - Condense verbose sections
    3. Prioritization - Keep high-relevance content
    4. Structural optimization - Remove redundant formatting
    """

    def __init__(self, target_tokens: int = 2000):
        self.target_tokens = target_tokens

    def estimate_tokens(self, text: str) -> int:
        """Rough token estimation (words * 1.3)"""
        words = len(text.split())
        return int(words * 1.3)

    def compress(self, context: str, preserve_sections: List[str] = None) -> CompressedContext:
        """
        Compress context to target token count
        """
        if preserve_sections is None:
            preserve_sections = []

        original_tokens = self.estimate_tokens(context)

        # If already under target, return as-is
        if original_tokens <= self.target_tokens:
            return CompressedContext(
                original_text=context,
                compressed_text=context,
                original_tokens=original_tokens,
                compressed_tokens=original_tokens,
                compression_ratio=1.0,
                sections_kept=[],
                sections_removed=[]
            )

        # Step 1: Parse sections
        sections = self._parse_sections(context)

        # Step 2: Deduplicate
        sections = self._deduplicate_sections(sections)

        # Step 3: Rank by importance
        ranked_sections = self._rank_sections(sections, preserve_sections)

        # Step 4: Select sections to keep within token budget
        kept_sections, removed_sections = self._select_sections(
            ranked_sections,
            self.target_tokens
        )

        # Step 5: Reconstruct compressed text
        compressed_text = self._reconstruct(kept_sections)

        compressed_tokens = self.estimate_tokens(compressed_text)
        compression_ratio = original_tokens / compressed_tokens if compressed_tokens > 0 else 1.0

        return CompressedContext(
            original_text=context,
            compressed_text=compressed_text,
            original_tokens=original_tokens,
            compressed_tokens=compressed_tokens,
            compression_ratio=compression_ratio,
            sections_kept=[s['title'] for s in kept_sections],
            sections_removed=[s['title'] for s in removed_sections]
        )

    def _parse_sections(self, context: str) -> List[Dict]:
        """Parse markdown-like sections"""
        sections = []
        current_section = None

        for line in context.split('\n'):
            # Check for header
            if line.startswith('#'):
                if current_section:
                    sections.append(current_section)

                level = len(line) - len(line.lstrip('#'))
                title = line.lstrip('#').strip()

                current_section = {
                    'level': level,
                    'title': title,
                    'content': [],
                    'tokens': 0
                }
            elif current_section:
                current_section['content'].append(line)

        if current_section:
            sections.append(current_section)

        # Calculate tokens for each section
        for section in sections:
            section['tokens'] = self.estimate_tokens('\n'.join(section['content']))

        return sections

    def _deduplicate_sections(self, sections: List[Dict]) -> List[Dict]:
        """Remove duplicate or near-duplicate sections"""
        seen_content = set()
        deduplicated = []

        for section in sections:
            # Create content signature
            content_str = '\n'.join(section['content']).lower()
            content_sig = self._create_signature(content_str)

            if content_sig not in seen_content:
                seen_content.add(content_sig)
                deduplicated.append(section)

        return deduplicated

    def _create_signature(self, text: str) -> str:
        """Create a signature for deduplication"""
        # Remove whitespace and normalize
        normalized = re.sub(r'\s+', ' ', text.lower().strip())
        # Take first 100 chars as signature
        return normalized[:100]

    def _rank_sections(self, sections: List[Dict], preserve: List[str]) -> List[Dict]:
        """Rank sections by importance"""
        for section in sections:
            score = 0.5  # Base score

            title = section['title'].lower()

            # Boost preserved sections
            if section['title'] in preserve:
                score += 1.0

            # Boost sections with important keywords
            important_keywords = [
                'pattern', 'insight', 'learning', 'error', 'important',
                'note', 'warning', 'todo', 'api', 'authentication',
                'database', 'configuration', 'deployment'
            ]

            for keyword in important_keywords:
                if keyword in title:
                    score += 0.3

            # Boost sections with content
            content_str = '\n'.join(section['content'])
            if 'class ' in content_str or 'def ' in content_str or 'function ' in content_str:
                score += 0.2

            # Penalize very short sections
            if section['tokens'] < 10:
                score -= 0.2

            # Penalize very long sections
            if section['tokens'] > 500:
                score -= 0.1

            section['importance_score'] = score

        # Sort by importance
        return sorted(sections, key=lambda s: s['importance_score'], reverse=True)

    def _select_sections(
        self,
        ranked_sections: List[Dict],
        target_tokens: int
    ) -> Tuple[List[Dict], List[Dict]]:
        """Select sections to keep within token budget"""
        kept = []
        removed = []
        current_tokens = 0

        for section in ranked_sections:
            section_tokens = section['tokens']

            if current_tokens + section_tokens <= target_tokens:
                kept.append(section)
                current_tokens += section_tokens
            else:
                # Check if we can fit a summarized version
                if section['importance_score'] > 0.7:
                    # Keep high-importance sections in summarized form
                    summarized = self._summarize_section(section)
                    if current_tokens + summarized['tokens'] <= target_tokens:
                        kept.append(summarized)
                        current_tokens += summarized['tokens']
                        continue

                removed.append(section)

        return kept, removed

    def _summarize_section(self, section: Dict) -> Dict:
        """Create a summarized version of a section"""
        # Simple summarization: keep first few lines
        content = section['content']
        max_lines = 3

        summarized_content = content[:max_lines]
        if len(content) > max_lines:
            summarized_content.append(f"... ({len(content) - max_lines} more lines)")

        return {
            'level': section['level'],
            'title': section['title'],
            'content': summarized_content,
            'tokens': self.estimate_tokens('\n'.join(summarized_content)),
            'importance_score': section['importance_score']
        }

    def _reconstruct(self, sections: List[Dict]) -> str:
        """Reconstruct compressed text from sections"""
        lines = []

        for section in sections:
            # Add header
            header = '#' * section['level'] + ' ' + section['title']
            lines.append(header)
            lines.append('')

            # Add content
            lines.extend(section['content'])
            lines.append('')

        return '\n'.join(lines)


def main():
    """CLI for testing compressor"""
    import sys

    # Sample context
    sample_context = """
# Project Overview

This is a sample project with lots of context.

## Authentication

The project uses JWT tokens for authentication.
Users login with email and password.
Tokens expire after 24 hours.

## Database

We use PostgreSQL as the primary database.
Connection string is in .env file.
Migrations are managed with Alembic.

## API Endpoints

### GET /users
Returns list of all users.

### POST /users
Creates a new user.

### GET /users/:id
Returns a specific user.

## Testing

We use pytest for testing.
Tests are in tests/ directory.
Run with: pytest

## Deployment

Deploy to production with: ./deploy.sh
Uses Docker containers.
Hosted on AWS EC2.
    """

    compressor = ContextCompressor(target_tokens=100)
    result = compressor.compress(sample_context)

    print("=" * 60)
    print("CONTEXT COMPRESSION TEST")
    print("=" * 60)
    print(f"Original tokens: {result.original_tokens}")
    print(f"Compressed tokens: {result.compressed_tokens}")
    print(f"Compression ratio: {result.compression_ratio:.1f}x")
    print()
    print("Sections kept:")
    for section in result.sections_kept:
        print(f"  ✓ {section}")
    print()
    print("Sections removed:")
    for section in result.sections_removed:
        print(f"  ✗ {section}")
    print()
    print("=" * 60)
    print("COMPRESSED OUTPUT:")
    print("=" * 60)
    print(result.compressed_text)


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
MemoryLane CLI
Adapted from ace-system-skill CLI patterns
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

from memory_store import MemoryStore
from config_manager import ConfigManager
from compressor import ContextCompressor
from conversation_learner import ConversationLearner
from curation_manager import CurationManager
from project_registry import ProjectRegistry, ensure_registered


class MemoryLaneCLI:
    """Command-line interface for MemoryLane"""

    def __init__(self, auto_register: bool = True):
        self.config = ConfigManager()
        self.store = MemoryStore(
            self.config.get_path('memories_file')
        )
        self.registry = ProjectRegistry()

        # Auto-register this project in global registry
        if auto_register:
            ensure_registered()

    def cmd_status(self, args):
        """Show MemoryLane status and cost savings"""
        stats = self.store.get_stats()
        metrics_file = self.config.get_path('metrics_file')

        print("🧠 MemoryLane Status")
        print("=" * 50)
        print(f"Total Memories: {stats['total_memories']}")
        print(f"Total Retrievals: {stats['total_retrievals']}")
        print()

        print("📊 Memories by Category:")
        for category, cat_stats in stats['categories'].items():
            print(f"  {category.ljust(15)}: {cat_stats['count']} memories "
                  f"(avg relevance: {cat_stats['avg_relevance']})")
        print()

        # Cost savings
        if metrics_file.exists():
            with open(metrics_file, 'r') as f:
                metrics = json.load(f)

            savings = metrics.get('cost_savings', {})
            print("💰 Cost Savings:")
            print(f"  This week: ${savings.get('week', 0):.2f}")
            print(f"  This month: ${savings.get('month', 0):.2f}")
            print(f"  Total: ${savings.get('total', 0):.2f}")
            print()

            compression = metrics.get('compression', {})
            print(f"📉 Compression Ratio: {compression.get('avg_ratio', 0):.1f}x")
            print(f"   ({compression.get('avg_before', 0):,} → {compression.get('avg_after', 0):,} tokens)")
        else:
            print("💰 Cost tracking not yet initialized")

    def cmd_recall(self, args):
        """Recall memories about a topic"""
        query = args.query
        print(f"🔍 Recalling memories about: {query}")
        print("=" * 50)

        # Simple keyword search for MVP
        # TODO: Replace with semantic search using embeddings
        all_memories = self.store.get_memories()

        matches = [
            m for m in all_memories
            if query.lower() in m['content'].lower()
        ]

        if not matches:
            print("No memories found matching that query.")
            return

        matches.sort(key=lambda m: m['relevance_score'], reverse=True)

        show_ids = getattr(args, 'show_ids', False)
        show_stars = getattr(args, 'show_stars', False)

        for i, memory in enumerate(matches[:10], 1):
            id_part = f" {memory['id']}" if show_ids else ""
            score = memory.get('relevance_score', 0)
            stars_part = ""
            if show_stars:
                stars = "⭐" * int(score * 5)
                stars_part = f" {stars}"
            print(f"{i}. [{memory['category']}]{id_part} {memory['content']}{stars_part} ({score:.2f})")
            print(f"   Source: {memory['source']} | Used: {memory['usage_count']} times")
            print()

    def cmd_insights(self, args):
        """View learned project insights"""
        print("💡 Project Insights")
        print("=" * 50)

        insights = self.store.get_memories(category='insights', limit=20)

        if not insights:
            print("No insights learned yet. Keep working and I'll learn!")
            return

        for i, insight in enumerate(insights, 1):
            stars = "⭐" * int(insight['relevance_score'] * 5)
            print(f"{i}. {insight['content']} {stars}")
            print()

    def cmd_costs(self, args):
        """View detailed cost savings breakdown"""
        metrics_file = self.config.get_path('metrics_file')

        if not metrics_file.exists():
            print("No cost tracking data available yet.")
            return

        with open(metrics_file, 'r') as f:
            metrics = json.load(f)

        print("💰 Cost Savings Breakdown")
        print("=" * 50)

        savings = metrics.get('cost_savings', {})
        print(f"Total Saved: ${savings.get('total', 0):.2f}")
        print()

        print("By Time Period:")
        print(f"  Today:      ${savings.get('today', 0):.2f}")
        print(f"  This Week:  ${savings.get('week', 0):.2f}")
        print(f"  This Month: ${savings.get('month', 0):.2f}")
        print()

        compression = metrics.get('compression', {})
        print("Token Savings:")
        print(f"  Baseline Avg:    {compression.get('avg_before', 0):,} tokens")
        print(f"  Compressed Avg:  {compression.get('avg_after', 0):,} tokens")
        print(f"  Compression:     {compression.get('avg_ratio', 0):.1f}x")
        print(f"  Tokens Saved:    {compression.get('total_saved', 0):,}")
        print()

        interactions = metrics.get('interactions', 0)
        print(f"Interactions: {interactions}")

    def cmd_config(self, args):
        """Configure MemoryLane settings"""
        if args.action == 'get':
            value = self.config.get(args.key)
            print(f"{args.key} = {value}")

        elif args.action == 'set':
            # Try to parse value as JSON for complex types
            try:
                value = json.loads(args.value)
            except json.JSONDecodeError:
                value = args.value

            self.config.set(args.key, value)
            print(f"✓ Set {args.key} = {value}")

        elif args.action == 'list':
            print("Current Configuration:")
            print(json.dumps(self.config.config, indent=2))

    def cmd_reset(self, args):
        """Reset all memories (with confirmation)"""
        if not args.force:
            response = input("⚠️  This will delete ALL memories. Are you sure? (yes/no): ")
            if response.lower() != 'yes':
                print("Cancelled.")
                return

        # Create backup first
        backup_path = self.store.export_backup()
        print(f"📦 Backup created: {backup_path}")

        # Reset
        empty = self.store.create_empty_memory()
        self.store.save(empty)

        print("✓ All memories reset.")

    def cmd_backup(self, args):
        """Create a backup of memories"""
        if args.output:
            backup_path = Path(args.output)
        else:
            backup_path = None

        result_path = self.store.export_backup(backup_path)
        print(f"✓ Backup created: {result_path}")

    def cmd_restore(self, args):
        """Restore memories from backup"""
        backup_path = Path(args.backup_file)

        if not backup_path.exists():
            print(f"Error: Backup file not found: {backup_path}")
            sys.exit(1)

        self.store.import_backup(backup_path)
        print(f"✓ Restored from: {backup_path}")

    def cmd_export_markdown(self, args):
        """Export memories as markdown"""
        markdown = self.store.to_markdown(category=args.category)

        if args.output:
            with open(args.output, 'w') as f:
                f.write(markdown)
            print(f"✓ Exported to: {args.output}")
        else:
            print(markdown)

    def cmd_learn(self, args):
        """Learn from conversation text or transcript"""
        learner = ConversationLearner(config=self.config)

        # Get input text
        if args.transcript:
            # Learn from transcript file
            memories = learner.extract_from_transcript(args.transcript)
            source = 'transcript'
        elif args.text:
            # Learn from provided text
            memories = learner.extract_from_text(args.text, source='manual')
            source = 'manual'
        else:
            # Read from stdin (only if data is available)
            import select
            if select.select([sys.stdin], [], [], 0.0)[0]:
                text = sys.stdin.read()
                if text.strip():
                    memories = learner.extract_from_text(text, source='stdin')
                    source = 'stdin'
                else:
                    print("No input provided. Use --text, --transcript, or pipe text to stdin.")
                    return
            else:
                print("No input provided. Use --text, --transcript, or pipe text to stdin.")
                return

        if not memories:
            print("No learnable content found.")
            return

        # Add memories to store
        added = 0
        for memory in memories:
            # Check for duplicates
            existing = self.store.get_memories(category=memory.category)
            is_duplicate = any(
                memory.content.lower()[:50] in m['content'].lower()
                for m in existing
            )

            if not is_duplicate:
                self.store.add_memory(
                    category=memory.category,
                    content=memory.content,
                    source=memory.source,
                    relevance_score=memory.relevance_score,
                    metadata=memory.metadata,
                )
                added += 1

                if not args.quiet:
                    print(f"  [{memory.category}] {memory.content[:60]}...")

        if not args.quiet:
            print(f"\n✓ Learned {added} new memories from {source}")
            if len(memories) > added:
                print(f"  ({len(memories) - added} duplicates skipped)")

    def cmd_curate(self, args):
        """Memory curation commands"""
        curator = CurationManager()

        if args.list:
            # List memories for curation
            reviewed_ids = curator.get_reviewed_ids()
            uncurated = self.store.get_uncurated_memories(reviewed_ids, limit=args.limit or 20)

            if not uncurated:
                print("No memories pending curation.")
                return

            print(f"# Memories for Review ({len(uncurated)} total)\n")
            for memory in uncurated:
                print(f"**{memory['id']}** [{memory['category']}] (relevance: {memory['relevance_score']:.2f})")
                print(f"  {memory['content']}")
                print(f"  Source: {memory['source']}")
                print()

        elif args.apply:
            # Apply curation decisions from JSON
            try:
                decisions = json.loads(args.apply)
            except json.JSONDecodeError:
                # Try reading from file
                try:
                    with open(args.apply, 'r') as f:
                        decisions = json.load(f)
                except FileNotFoundError:
                    print(f"Error: Could not parse JSON or find file: {args.apply}")
                    sys.exit(1)

            self._apply_curation_decisions(decisions, curator)

        elif args.force:
            # Force curation - output prompt for Claude to review
            reviewed_ids = curator.get_reviewed_ids()
            uncurated = self.store.get_uncurated_memories(reviewed_ids, limit=args.limit or 20)

            if not uncurated:
                print("No memories pending curation.")
                return

            # Output structured prompt
            self._output_curation_prompt(uncurated)

        else:
            # Check if curation is needed
            stats = self.store.get_stats()
            if curator.needs_curation(self.config.config, stats['total_memories']):
                reviewed_ids = curator.get_reviewed_ids()
                uncurated = self.store.get_uncurated_memories(reviewed_ids, limit=20)
                print(f"Curation recommended: {len(uncurated)} memories to review")
                print("Run: python3 src/cli.py curate --list")
            else:
                print("No curation needed at this time.")

    def _apply_curation_decisions(self, decisions: dict, curator: CurationManager):
        """Apply curation decisions from JSON"""
        applied = []
        deleted = []
        rewritten = []
        kept = []
        errors = []

        # First pass: collect all decisions
        for decision in decisions.get('decisions', []):
            memory_id = decision['id']
            action = decision['action'].upper()

            if action == 'DELETE':
                reason = decision.get('reason', '')
                memory = self.store.get_memory_by_id(memory_id)
                if memory and self.store.delete_memory(memory_id):
                    deleted.append({
                        'id': memory_id,
                        'reason': reason,
                        'content': memory.get('content', '')[:60]
                    })
                    applied.append(memory_id)
                else:
                    errors.append(f"Not found: {memory_id}")
            elif action == 'REWRITE':
                new_content = decision.get('new_content')
                memory = self.store.get_memory_by_id(memory_id)
                if memory and new_content and self.store.update_memory(memory_id, content=new_content):
                    rewritten.append({
                        'id': memory_id,
                        'old': memory.get('content', '')[:50],
                        'new': new_content[:50]
                    })
                    applied.append(memory_id)
                else:
                    errors.append(f"Failed to update: {memory_id}")
            elif action == 'KEEP':
                memory = self.store.get_memory_by_id(memory_id)
                kept.append({
                    'id': memory_id,
                    'content': memory.get('content', '')[:60] if memory else '?'
                })
                applied.append(memory_id)

        # Output grouped summary
        if deleted:
            print(f"\n## Deleted ({len(deleted)})")
            for d in deleted:
                reason_str = f" - {d['reason']}" if d['reason'] else ""
                print(f"  - {d['id']}: {d['content']}...{reason_str}")

        if rewritten:
            print(f"\n## Rewritten ({len(rewritten)})")
            for r in rewritten:
                print(f"  - {r['id']}:")
                print(f"      was: {r['old']}...")
                print(f"      now: {r['new']}...")

        if kept:
            print(f"\n## Kept ({len(kept)})")
            for k in kept:
                print(f"  - {k['id']}: {k['content']}...")

        if errors:
            print(f"\n## Errors ({len(errors)})")
            for e in errors:
                print(f"  - {e}")

        # Mark all as reviewed
        if applied:
            curator.mark_curated(applied)
            print(f"\n✓ Curation complete: {len(deleted)} deleted, {len(rewritten)} rewritten, {len(kept)} kept")

    def _output_curation_prompt(self, memories: list):
        """Output curation prompt for Claude"""
        print("# Memory Curation Required")
        print()
        print("Review these memories and decide: KEEP, DELETE, or REWRITE.")
        print()
        print("## Memories to Review")
        print()

        # Group by category
        by_category = {}
        for m in memories:
            cat = m['category']
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(m)

        for category, mems in by_category.items():
            print(f"### {category.title()} ({len(mems)})")
            print()
            for m in mems:
                print(f"- **{m['id']}** (relevance: {m['relevance_score']:.2f})")
                print(f"  {m['content']}")
                print()

        print("## Response Format")
        print()
        print("Respond with JSON:")
        print("```json")
        print('{')
        print('  "decisions": [')
        print('    {"id": "patt-001", "action": "KEEP"},')
        print('    {"id": "lear-002", "action": "DELETE", "reason": "off-topic"},')
        print('    {"id": "insi-003", "action": "REWRITE", "new_content": "Improved content"}')
        print('  ]')
        print('}')
        print("```")

    def cmd_memory(self, args):
        """Individual memory operations"""
        if args.action == 'get':
            memory = self.store.get_memory_by_id(args.id)
            if memory:
                print(json.dumps(memory, indent=2))
            else:
                print(f"Memory not found: {args.id}")
                sys.exit(1)

        elif args.action == 'delete':
            if self.store.delete_memory(args.id):
                print(f"✓ Deleted: {args.id}")
            else:
                print(f"Memory not found: {args.id}")
                sys.exit(1)

        elif args.action == 'update':
            if not args.content:
                print("Error: --content is required for update")
                sys.exit(1)
            if self.store.update_memory(args.id, content=args.content):
                print(f"✓ Updated: {args.id}")
            else:
                print(f"Memory not found: {args.id}")
                sys.exit(1)

    def cmd_context(self, args):
        """Get compressed context for injection (used by hooks)"""
        query = args.query if args.query else ""
        max_tokens = args.max_tokens

        # Determine scope: current project, all projects, or specific projects
        if getattr(args, 'all_projects', False):
            # Search across all registered projects
            all_memories = self.registry.search_all(
                query,
                limit_per_project=args.limit
            )
        elif getattr(args, 'projects', None):
            # Search specific projects
            project_names = [p.strip() for p in args.projects.split(',')]
            memories_by_project = self.registry.get_all_memories(
                project_names=project_names,
                limit_per_project=args.limit
            )
            all_memories = []
            for proj_name, memories in memories_by_project.items():
                for m in memories:
                    m["_project_name"] = proj_name
                all_memories.extend(memories)
        else:
            # Default: current project only
            all_memories = self.store.get_memories(min_relevance=args.min_relevance)

        if not all_memories:
            # No memories yet - output nothing
            return

        # If query provided and not already searched (for single project case)
        if query and not getattr(args, 'all_projects', False) and not getattr(args, 'projects', None):
            # Try semantic search first if available
            try:
                from semantic_search import SemanticSearcher
                searcher = SemanticSearcher()
                scored_memories = searcher.search(query, all_memories, limit=args.limit)
                all_memories = [m for m, score in scored_memories]
            except ImportError:
                # Fall back to keyword matching
                query_words = set(query.lower().split())
                scored = []
                for memory in all_memories:
                    content_words = set(memory['content'].lower().split())
                    overlap = len(query_words & content_words)
                    if overlap > 0:
                        scored.append((memory, overlap))

                if scored:
                    scored.sort(key=lambda x: (-x[1], -x[0]['relevance_score']))
                    all_memories = [m for m, _ in scored[:args.limit]]
                else:
                    # No keyword matches, use top by relevance
                    all_memories = all_memories[:args.limit]
        else:
            all_memories = all_memories[:args.limit]

        if not all_memories:
            return

        # Check if we have cross-project memories
        is_cross_project = any('_project_name' in m for m in all_memories)

        # Build context from matched memories
        if is_cross_project:
            context_lines = ["# Cross-Project Context (from MemoryLane)", ""]

            # Group by project, then by category
            by_project = {}
            for memory in all_memories:
                proj = memory.get('_project_name', 'current')
                if proj not in by_project:
                    by_project[proj] = {}
                cat = memory['category']
                if cat not in by_project[proj]:
                    by_project[proj][cat] = []
                by_project[proj][cat].append(memory)

            for project, categories in by_project.items():
                context_lines.append(f"## {project}")
                for category, memories in categories.items():
                    context_lines.append(f"### {category.title()}")
                    for memory in memories:
                        context_lines.append(f"- {memory['content']}")
                context_lines.append("")
        else:
            context_lines = ["# Project Context (from MemoryLane)", ""]

            # Group by category
            by_category = {}
            for memory in all_memories:
                cat = memory['category']
                if cat not in by_category:
                    by_category[cat] = []
                by_category[cat].append(memory)

            for category, memories in by_category.items():
                context_lines.append(f"## {category.title()}")
                context_lines.append("")
                for memory in memories:
                    context_lines.append(f"- {memory['content']}")
                context_lines.append("")

        raw_context = "\n".join(context_lines)

        # Compress if needed
        compressor = ContextCompressor(target_tokens=max_tokens)
        result = compressor.compress(raw_context)

        # Output compressed context (no decorations for hook consumption)
        print(result.compressed_text)

    def cmd_projects(self, args):
        """Manage registered projects"""
        if args.action == 'list':
            projects = self.registry.list_projects(validate=True)

            if not projects:
                print("No projects registered yet.")
                print("Projects are auto-registered when you use MemoryLane CLI.")
                return

            print("📁 Registered Projects")
            print("=" * 50)
            for project in projects:
                status = "✓" if project.get('valid', True) else "✗"
                print(f"{status} {project['name']}")
                print(f"   Path: {project['path']}")
                print(f"   Registered: {project['registered_at'][:10]}")
                print()

        elif args.action == 'add':
            path = Path(args.path).resolve() if args.path else Path.cwd()
            if self.registry.register(path, args.name):
                print(f"✓ Registered: {path}")
            else:
                print(f"Already registered: {path}")

        elif args.action == 'remove':
            path = Path(args.path).resolve() if args.path else Path.cwd()
            if self.registry.unregister(path):
                print(f"✓ Removed: {path}")
            else:
                print(f"Not found in registry: {path}")

        elif args.action == 'cleanup':
            removed = self.registry.cleanup_stale()
            print(f"✓ Cleaned up {removed} stale project(s)")

        elif args.action == 'search':
            if not args.query:
                print("Error: --query is required for search")
                sys.exit(1)

            results = self.registry.search_all(args.query)

            if not results:
                print("No matching memories found across projects.")
                return

            print(f"🔍 Cross-Project Search: '{args.query}'")
            print("=" * 50)

            # Group by project
            by_project = {}
            for memory in results[:20]:  # Limit output
                proj = memory.get('_project_name', 'unknown')
                if proj not in by_project:
                    by_project[proj] = []
                by_project[proj].append(memory)

            for project, memories in by_project.items():
                print(f"\n📁 {project}")
                for m in memories:
                    print(f"   [{m['category']}] {m['content'][:60]}...")


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description='MemoryLane - Persistent memory for Claude',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Status command
    status_parser = subparsers.add_parser(
        'status',
        help='Show MemoryLane status and cost savings'
    )

    # Recall command
    recall_parser = subparsers.add_parser(
        'recall',
        help='Recall memories about a topic'
    )
    recall_parser.add_argument('query', help='Search query')
    recall_parser.add_argument(
        '--show-ids',
        action='store_true',
        help='Show memory IDs in results'
    )
    recall_parser.add_argument(
        '--show-stars',
        action='store_true',
        help='Show star ratings for relevance'
    )

    # Insights command
    insights_parser = subparsers.add_parser(
        'insights',
        help='View learned project insights'
    )

    # Costs command
    costs_parser = subparsers.add_parser(
        'costs',
        help='View detailed cost savings breakdown'
    )

    # Config command
    config_parser = subparsers.add_parser(
        'config',
        help='Configure MemoryLane settings'
    )
    config_parser.add_argument(
        'action',
        choices=['get', 'set', 'list'],
        help='Config action'
    )
    config_parser.add_argument('key', nargs='?', help='Config key (dot notation)')
    config_parser.add_argument('value', nargs='?', help='Config value')

    # Reset command
    reset_parser = subparsers.add_parser(
        'reset',
        help='Reset all memories (with confirmation)'
    )
    reset_parser.add_argument('--force', action='store_true', help='Skip confirmation')

    # Backup command
    backup_parser = subparsers.add_parser(
        'backup',
        help='Create a backup of memories'
    )
    backup_parser.add_argument('--output', help='Output file path')
    backup_parser.add_argument(
        '--before-uninstall',
        action='store_true',
        help='Backup before uninstall'
    )

    # Restore command
    restore_parser = subparsers.add_parser(
        'restore',
        help='Restore memories from backup'
    )
    restore_parser.add_argument('backup_file', help='Backup file to restore')

    # Export markdown command
    export_parser = subparsers.add_parser(
        'export-markdown',
        help='Export memories as markdown'
    )
    export_parser.add_argument('--category', help='Specific category to export')
    export_parser.add_argument('--output', help='Output file (default: stdout)')

    # Context command (for hook integration)
    context_parser = subparsers.add_parser(
        'context',
        help='Get compressed context for injection (used by hooks)'
    )
    context_parser.add_argument('query', nargs='?', default='', help='Query to find relevant context')
    context_parser.add_argument('--max-tokens', type=int, default=2000, help='Max tokens for output')
    context_parser.add_argument('--min-relevance', type=float, default=0.3, help='Minimum relevance score')
    context_parser.add_argument('--limit', type=int, default=20, help='Max memories to consider')
    context_parser.add_argument('--all-projects', action='store_true', help='Search across all registered projects')
    context_parser.add_argument('--projects', help='Comma-separated list of project names to search')

    # Learn command (extract insights from conversations)
    learn_parser = subparsers.add_parser(
        'learn',
        help='Learn from conversation text or transcript'
    )
    learn_parser.add_argument('--text', '-t', help='Text to learn from')
    learn_parser.add_argument('--transcript', '-f', help='Path to Claude Code transcript (JSONL)')
    learn_parser.add_argument('--quiet', '-q', action='store_true', help='Suppress output')

    # Curate command
    curate_parser = subparsers.add_parser(
        'curate',
        help='Memory curation - review and clean up memories'
    )
    curate_parser.add_argument('--list', action='store_true', help='List memories pending curation')
    curate_parser.add_argument('--apply', help='Apply curation decisions (JSON string or file path)')
    curate_parser.add_argument('--force', action='store_true', help='Force output curation prompt')
    curate_parser.add_argument('--limit', type=int, default=20, help='Max memories to review')

    # Memory command (individual memory operations)
    memory_parser = subparsers.add_parser(
        'memory',
        help='Individual memory operations (get, delete, update)'
    )
    memory_parser.add_argument('action', choices=['get', 'delete', 'update'], help='Action to perform')
    memory_parser.add_argument('id', help='Memory ID (e.g., patt-001)')
    memory_parser.add_argument('--content', help='New content (required for update)')

    # Projects command (manage registered projects)
    projects_parser = subparsers.add_parser(
        'projects',
        help='Manage registered projects for cross-project memory search'
    )
    projects_parser.add_argument(
        'action',
        choices=['list', 'add', 'remove', 'cleanup', 'search'],
        help='Action: list, add, remove, cleanup stale, or search across projects'
    )
    projects_parser.add_argument('--path', help='Project path (default: current directory)')
    projects_parser.add_argument('--name', help='Project name (default: directory name)')
    projects_parser.add_argument('--query', '-q', help='Search query (for search action)')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    cli = MemoryLaneCLI()

    # Dispatch commands
    command_map = {
        'status': cli.cmd_status,
        'recall': cli.cmd_recall,
        'insights': cli.cmd_insights,
        'costs': cli.cmd_costs,
        'config': cli.cmd_config,
        'reset': cli.cmd_reset,
        'backup': cli.cmd_backup,
        'restore': cli.cmd_restore,
        'export-markdown': cli.cmd_export_markdown,
        'context': cli.cmd_context,
        'learn': cli.cmd_learn,
        'curate': cli.cmd_curate,
        'memory': cli.cmd_memory,
        'projects': cli.cmd_projects
    }

    handler = command_map.get(args.command)
    if handler:
        handler(args)
    else:
        print(f"Unknown command: {args.command}")
        sys.exit(1)


if __name__ == '__main__':
    main()

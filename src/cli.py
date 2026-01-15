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


class MemoryLaneCLI:
    """Command-line interface for MemoryLane"""

    def __init__(self):
        self.config = ConfigManager()
        self.store = MemoryStore(
            self.config.get_path('memories_file')
        )

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

        for i, memory in enumerate(matches[:10], 1):
            stars = "⭐" * int(memory['relevance_score'] * 5)
            print(f"{i}. [{memory['category']}] {memory['content']} {stars}")
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
        'export-markdown': cli.cmd_export_markdown
    }

    handler = command_map.get(args.command)
    if handler:
        handler(args)
    else:
        print(f"Unknown command: {args.command}")
        sys.exit(1)


if __name__ == '__main__':
    main()

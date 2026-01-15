import * as vscode from 'vscode';
import { MemoryStats } from './sidecar';

export class StatusBarManager {
    private statusBarItem: vscode.StatusBarItem;
    private learning: boolean = false;

    constructor() {
        this.statusBarItem = vscode.window.createStatusBarItem(
            vscode.StatusBarAlignment.Right,
            100
        );
        this.statusBarItem.command = 'memorylane.showStatus';
        this.statusBarItem.show();
    }

    update(stats: MemoryStats, metrics: any): void {
        const icon = this.learning ? '$(loading~spin)' : '$(brain)';
        const saved = metrics.totalSaved || 0;

        this.statusBarItem.text = `${icon} ${stats.memory.total_memories} memories | $${saved.toFixed(2)} saved`;
        this.statusBarItem.tooltip = this.getTooltip(stats, metrics);
    }

    setLearning(learning: boolean): void {
        this.learning = learning;
    }

    private getTooltip(stats: MemoryStats, metrics: any): string {
        return `🧠 MemoryLane

Memories: ${stats.memory.total_memories}
├─ Patterns: ${stats.memory.categories.patterns?.count || 0}
├─ Insights: ${stats.memory.categories.insights?.count || 0}
├─ Learnings: ${stats.memory.categories.learnings?.count || 0}
└─ Context: ${stats.memory.categories.context?.count || 0}

💰 Savings: $${(metrics.totalSaved || 0).toFixed(2)} (${(metrics.savingsPercent || 0).toFixed(1)}%)
📊 Compression: ${(metrics.compressionRatio || 1).toFixed(1)}x
🔄 Interactions: ${metrics.interactions || 0}

Click for details`;
    }

    dispose(): void {
        this.statusBarItem.dispose();
    }
}

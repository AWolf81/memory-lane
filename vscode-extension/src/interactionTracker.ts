import * as vscode from 'vscode';
import { SidecarManager } from './sidecar';
import * as fs from 'fs';
import * as path from 'path';

interface InteractionMetrics {
    totalSaved: number;
    compressionRatio: number;
    tokensSaved: number;
    interactions: number;
    savingsPercent: number;
}

export class InteractionTracker {
    private metrics: InteractionMetrics = {
        totalSaved: 0,
        compressionRatio: 1.0,
        tokensSaved: 0,
        interactions: 0,
        savingsPercent: 0
    };

    private metricsPath: string;
    private tracking: boolean = false;

    constructor(private sidecarManager: SidecarManager) {
        const workspaceRoot = vscode.workspace.workspaceFolders?.[0].uri.fsPath || '';
        this.metricsPath = path.join(workspaceRoot, '.memorylane', 'metrics.json');
        this.loadMetrics();
    }

    start(): void {
        this.tracking = true;

        // Watch for Claude Code interactions
        // This would integrate with Claude Code's API or hooks
        // For now, we'll simulate by watching the terminal
        this.startWatching();
    }

    stop(): void {
        this.tracking = false;
    }

    private startWatching(): void {
        // Monitor terminal output for Claude Code usage
        vscode.window.onDidOpenTerminal(terminal => {
            if (this.tracking) {
                this.trackInteraction();
            }
        });

        // Monitor text document changes (as proxy for AI interaction)
        vscode.workspace.onDidChangeTextDocument(event => {
            if (this.tracking && event.contentChanges.length > 0) {
                // Only track significant changes
                const totalChanges = event.contentChanges.reduce((sum, change) => sum + change.text.length, 0);
                if (totalChanges > 100) {
                    this.trackInteraction();
                }
            }
        });
    }

    private async trackInteraction(): Promise<void> {
        this.metrics.interactions++;

        // Simulate compression savings
        // In real implementation, this would capture actual context size before/after
        const baselineTokens = 20000; // Average without MemoryLane
        const compressedTokens = 3000;  // With MemoryLane
        const compressionRatio = baselineTokens / compressedTokens;

        this.metrics.compressionRatio = (this.metrics.compressionRatio * (this.metrics.interactions - 1) + compressionRatio) / this.metrics.interactions;
        this.metrics.tokensSaved += (baselineTokens - compressedTokens);

        // Calculate cost savings
        const inputCostPerMillion = 3.0;
        const outputCostPerMillion = 15.0;

        const baselineCost = (baselineTokens / 1000000) * inputCostPerMillion + (baselineTokens * 0.3 / 1000000) * outputCostPerMillion;
        const actualCost = (compressedTokens / 1000000) * inputCostPerMillion + (compressedTokens * 0.3 / 1000000) * outputCostPerMillion;

        this.metrics.totalSaved += (baselineCost - actualCost);
        this.metrics.savingsPercent = ((baselineCost - actualCost) / baselineCost) * 100;

        await this.saveMetrics();
    }

    getMetrics(): InteractionMetrics {
        return { ...this.metrics };
    }

    private loadMetrics(): void {
        try {
            if (fs.existsSync(this.metricsPath)) {
                const content = fs.readFileSync(this.metricsPath, 'utf-8');
                const saved = JSON.parse(content);

                this.metrics.totalSaved = saved.cost_savings?.total || 0;
                this.metrics.compressionRatio = saved.compression?.avg_ratio || 1.0;
                this.metrics.tokensSaved = saved.compression?.total_saved || 0;
                this.metrics.interactions = saved.interactions || 0;
                this.metrics.savingsPercent = saved.cost_savings?.percent || 0;
            }
        } catch (e) {
            console.error('Failed to load metrics:', e);
        }
    }

    private async saveMetrics(): Promise<void> {
        try {
            const data = {
                cost_savings: {
                    total: this.metrics.totalSaved,
                    week: this.metrics.totalSaved, // Simplified for now
                    month: this.metrics.totalSaved,
                    percent: this.metrics.savingsPercent
                },
                compression: {
                    avg_ratio: this.metrics.compressionRatio,
                    total_saved: this.metrics.tokensSaved
                },
                interactions: this.metrics.interactions,
                last_updated: new Date().toISOString()
            };

            fs.writeFileSync(this.metricsPath, JSON.stringify(data, null, 2));
        } catch (e) {
            console.error('Failed to save metrics:', e);
        }
    }
}

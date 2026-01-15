import * as vscode from 'vscode';
import { SidecarManager } from './sidecar';

export class InsightsTreeProvider implements vscode.TreeDataProvider<InsightItem> {
    private _onDidChangeTreeData: vscode.EventEmitter<InsightItem | undefined | null | void> = new vscode.EventEmitter<InsightItem | undefined | null | void>();
    readonly onDidChangeTreeData: vscode.Event<InsightItem | undefined | null | void> = this._onDidChangeTreeData.event;

    constructor(private sidecarManager: SidecarManager) {}

    refresh(): void {
        this._onDidChangeTreeData.fire();
    }

    getTreeItem(element: InsightItem): vscode.TreeItem {
        return element;
    }

    async getChildren(): Promise<InsightItem[]> {
        const insights = await this.sidecarManager.getMemories('insights');

        if (insights.length === 0) {
            return [new InsightItem('No insights yet - keep working!', 0, 'placeholder')];
        }

        // Sort by relevance
        insights.sort((a, b) => b.relevance_score - a.relevance_score);

        return insights.map(i => new InsightItem(i.content, i.relevance_score, 'insight'));
    }
}

class InsightItem extends vscode.TreeItem {
    constructor(
        public readonly label: string,
        public readonly relevance: number,
        public readonly type: string
    ) {
        super(label);

        if (type === 'insight') {
            const stars = '⭐'.repeat(Math.round(relevance * 5));
            this.description = stars;
            this.tooltip = `Relevance: ${relevance.toFixed(2)}`;
            this.iconPath = new vscode.ThemeIcon('lightbulb');
        } else {
            this.iconPath = new vscode.ThemeIcon('info');
        }
    }
}

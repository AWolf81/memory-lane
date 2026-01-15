import * as vscode from 'vscode';
import { SidecarManager, Memory } from './sidecar';

export class MemoryTreeProvider implements vscode.TreeDataProvider<MemoryItem> {
    private _onDidChangeTreeData: vscode.EventEmitter<MemoryItem | undefined | null | void> = new vscode.EventEmitter<MemoryItem | undefined | null | void>();
    readonly onDidChangeTreeData: vscode.Event<MemoryItem | undefined | null | void> = this._onDidChangeTreeData.event;

    constructor(private sidecarManager: SidecarManager) {}

    refresh(): void {
        this._onDidChangeTreeData.fire();
    }

    getTreeItem(element: MemoryItem): vscode.TreeItem {
        return element;
    }

    async getChildren(element?: MemoryItem): Promise<MemoryItem[]> {
        if (!element) {
            // Root level - show categories
            return [
                new MemoryItem('Patterns', 'category', vscode.TreeItemCollapsibleState.Collapsed),
                new MemoryItem('Insights', 'category', vscode.TreeItemCollapsibleState.Collapsed),
                new MemoryItem('Learnings', 'category', vscode.TreeItemCollapsibleState.Collapsed),
                new MemoryItem('Context', 'category', vscode.TreeItemCollapsibleState.Collapsed)
            ];
        }

        if (element.type === 'category') {
            // Category level - show memories
            const category = element.label.toLowerCase();
            const memories = await this.sidecarManager.getMemories(category);

            return memories.map(m => {
                const stars = '⭐'.repeat(Math.round(m.relevance_score * 5));
                const item = new MemoryItem(
                    m.content,
                    'memory',
                    vscode.TreeItemCollapsibleState.None
                );
                item.description = stars;
                item.tooltip = `Source: ${m.source}\nRelevance: ${m.relevance_score.toFixed(2)}\nUsed: ${m.usage_count} times`;
                item.contextValue = 'memory';
                return item;
            });
        }

        return [];
    }
}

class MemoryItem extends vscode.TreeItem {
    constructor(
        public readonly label: string,
        public readonly type: string,
        public readonly collapsibleState: vscode.TreeItemCollapsibleState
    ) {
        super(label, collapsibleState);

        if (type === 'category') {
            this.iconPath = new vscode.ThemeIcon('folder');
        } else {
            this.iconPath = new vscode.ThemeIcon('note');
        }
    }
}

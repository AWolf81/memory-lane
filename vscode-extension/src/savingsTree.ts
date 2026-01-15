import * as vscode from 'vscode';
import { SidecarManager } from './sidecar';
import * as fs from 'fs';
import * as path from 'path';

export class SavingsTreeProvider implements vscode.TreeDataProvider<SavingItem> {
    private _onDidChangeTreeData: vscode.EventEmitter<SavingItem | undefined | null | void> = new vscode.EventEmitter<SavingItem | undefined | null | void>();
    readonly onDidChangeTreeData: vscode.Event<SavingItem | undefined | null | void> = this._onDidChangeTreeData.event;

    constructor(private sidecarManager: SidecarManager) {}

    refresh(): void {
        this._onDidChangeTreeData.fire();
    }

    getTreeItem(element: SavingItem): vscode.TreeItem {
        return element;
    }

    async getChildren(): Promise<SavingItem[]> {
        const workspaceRoot = vscode.workspace.workspaceFolders?.[0].uri.fsPath || '';
        const metricsPath = path.join(workspaceRoot, '.memorylane', 'metrics.json');

        let metrics: any = {
            cost_savings: { total: 0, week: 0, month: 0 },
            compression: { avg_ratio: 0, total_saved: 0 },
            interactions: 0
        };

        try {
            if (fs.existsSync(metricsPath)) {
                const content = fs.readFileSync(metricsPath, 'utf-8');
                metrics = JSON.parse(content);
            }
        } catch (e) {
            // Use defaults
        }

        return [
            new SavingItem(
                'Total Saved',
                `$${(metrics.cost_savings.total || 0).toFixed(2)}`,
                'money',
                'Total cost savings across all interactions'
            ),
            new SavingItem(
                'This Week',
                `$${(metrics.cost_savings.week || 0).toFixed(2)}`,
                'calendar',
                'Cost savings this week'
            ),
            new SavingItem(
                'This Month',
                `$${(metrics.cost_savings.month || 0).toFixed(2)}`,
                'calendar',
                'Cost savings this month'
            ),
            new SavingItem(
                'Compression Ratio',
                `${(metrics.compression.avg_ratio || 0).toFixed(1)}x`,
                'graph',
                'Average context compression ratio'
            ),
            new SavingItem(
                'Tokens Saved',
                `${(metrics.compression.total_saved || 0).toLocaleString()}`,
                'symbol-number',
                'Total tokens saved through compression'
            ),
            new SavingItem(
                'Interactions',
                `${metrics.interactions || 0}`,
                'comment-discussion',
                'Number of Claude Code interactions'
            )
        ];
    }
}

class SavingItem extends vscode.TreeItem {
    constructor(
        public readonly label: string,
        public readonly value: string,
        icon: string,
        tooltip: string
    ) {
        super(label);
        this.description = value;
        this.tooltip = tooltip;
        this.iconPath = new vscode.ThemeIcon(icon);
    }
}

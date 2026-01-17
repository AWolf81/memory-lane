import * as vscode from 'vscode';
import { SidecarManager } from './sidecar';

export class OverviewTreeProvider implements vscode.TreeDataProvider<OverviewItem> {
    private _onDidChangeTreeData: vscode.EventEmitter<OverviewItem | undefined | null | void> = new vscode.EventEmitter<OverviewItem | undefined | null | void>();
    readonly onDidChangeTreeData: vscode.Event<OverviewItem | undefined | null | void> = this._onDidChangeTreeData.event;
    private scopeMode: 'workspace' | 'all' = 'workspace';

    constructor(private sidecarManager: SidecarManager) {}

    refresh(): void {
        this._onDidChangeTreeData.fire();
    }

    toggleScope(): void {
        this.scopeMode = this.scopeMode === 'workspace' ? 'all' : 'workspace';
        this.refresh();
    }

    getTreeItem(element: OverviewItem): vscode.TreeItem {
        return element;
    }

    async getChildren(element?: OverviewItem): Promise<OverviewItem[]> {
        if (element) {
            // Handle expandable items
            if (element.contextValue === 'registered-projects') {
                const projects = await this.sidecarManager.getRegisteredProjects();
                return projects.map(p => new OverviewItem(
                    p.name,
                    p.valid ? 'folder' : 'folder-opened',
                    p.path
                ));
            }
            return [];
        }

        try {
            const stats = await this.sidecarManager.getStats();
            const workspaceName = this.sidecarManager.getWorkspaceName();

            const items: OverviewItem[] = [
                // Scope indicator
                new OverviewItem(
                    `Scope: ${this.scopeMode === 'workspace' ? workspaceName : 'All Projects'}`,
                    this.scopeMode === 'workspace' ? 'folder' : 'folder-library',
                    `Click to switch to ${this.scopeMode === 'workspace' ? 'all projects' : 'current workspace'}`,
                    'memorylane.toggleScope'
                ),
                new OverviewItem(
                    `Total Memories: ${stats.memory.total_memories}`,
                    'database',
                    `${stats.memory.categories.patterns.count} patterns, ${stats.memory.categories.insights.count} insights, ${stats.memory.categories.learnings.count} learnings`
                ),
                new OverviewItem(
                    `Retrievals: ${stats.memory.total_retrievals}`,
                    'search',
                    'Times context was retrieved'
                ),
                new OverviewItem(
                    `Server Status: ${stats.server.requests_handled > 0 ? 'Active' : 'Idle'}`,
                    stats.server.requests_handled > 0 ? 'pass' : 'circle-outline',
                    `${stats.server.requests_handled} requests handled`
                )
            ];

            // Add registered projects (collapsible)
            const projectsItem = new OverviewItem(
                'Registered Projects',
                'folder-library',
                'Projects available for cross-project search',
                undefined,
                vscode.TreeItemCollapsibleState.Collapsed
            );
            projectsItem.contextValue = 'registered-projects';
            items.push(projectsItem);

            items.push(
                new OverviewItem(
                    'Show Knowledge Graph',
                    'type-hierarchy',
                    'Visualize memory connections',
                    'memorylane.showKnowledgeGraph'
                ),
                new OverviewItem(
                    'Export as Markdown',
                    'markdown',
                    'Export all context',
                    'memorylane.exportContext'
                )
            );

            return items;
        } catch {
            return [
                new OverviewItem(
                    'Sidecar not running',
                    'warning',
                    'Start MemoryLane to see stats'
                ),
                new OverviewItem(
                    'Start Learning',
                    'play',
                    'Begin learning from workspace',
                    'memorylane.startLearning'
                )
            ];
        }
    }
}

class OverviewItem extends vscode.TreeItem {
    constructor(
        public readonly label: string,
        iconId: string,
        tooltip: string,
        command?: string,
        collapsibleState: vscode.TreeItemCollapsibleState = vscode.TreeItemCollapsibleState.None
    ) {
        super(label, collapsibleState);
        this.iconPath = new vscode.ThemeIcon(iconId);
        this.tooltip = tooltip;

        if (command) {
            this.command = {
                command,
                title: label
            };
        }
    }
}

import * as vscode from 'vscode';
import { SidecarManager } from './sidecar';
import { StatusBarManager } from './statusBar';
import { OverviewTreeProvider } from './overviewTree';
import { MemoryTreeProvider } from './memoryTree';
import { InsightsTreeProvider } from './insightsTree';
import { SavingsTreeProvider } from './savingsTree';
import { KnowledgeGraphPanel } from './knowledgeGraph';
import { InteractionTracker } from './interactionTracker';

let sidecarManager: SidecarManager;
let statusBarManager: StatusBarManager;
let interactionTracker: InteractionTracker;

export async function activate(context: vscode.ExtensionContext) {
    console.log('MemoryLane extension activating...');

    // Initialize managers
    sidecarManager = new SidecarManager(context);
    statusBarManager = new StatusBarManager();
    interactionTracker = new InteractionTracker(sidecarManager);

    // Register tree data providers
    const overviewTreeProvider = new OverviewTreeProvider(sidecarManager);
    const memoryTreeProvider = new MemoryTreeProvider(sidecarManager);
    const insightsTreeProvider = new InsightsTreeProvider(sidecarManager);
    const savingsTreeProvider = new SavingsTreeProvider(sidecarManager);

    vscode.window.registerTreeDataProvider('memorylane.overview', overviewTreeProvider);
    vscode.window.registerTreeDataProvider('memorylane.memories', memoryTreeProvider);
    vscode.window.registerTreeDataProvider('memorylane.insights', insightsTreeProvider);
    vscode.window.registerTreeDataProvider('memorylane.savings', savingsTreeProvider);

    // Auto-start sidecar if configured
    const config = vscode.workspace.getConfiguration('memorylane');
    if (config.get('autoStart', true)) {
        try {
            await sidecarManager.start();
        } catch (error) {
            const message = error instanceof Error ? error.message : String(error);
            vscode.window.showErrorMessage(`MemoryLane: ${message}`);
            console.error('MemoryLane sidecar start failed:', error);
        }
    }

    // Start interaction tracking
    interactionTracker.start();

    // Register commands
    context.subscriptions.push(
        vscode.commands.registerCommand('memorylane.showStatus', async () => {
            const stats = await sidecarManager.getStats();
            const message = `
                🧠 MemoryLane Status

                Memories: ${stats.memory.total_memories}
                Retrievals: ${stats.memory.total_retrievals}
                Server Requests: ${stats.server.requests_handled}

                Patterns: ${stats.memory.categories.patterns.count}
                Insights: ${stats.memory.categories.insights.count}
                Learnings: ${stats.memory.categories.learnings.count}
                Context: ${stats.memory.categories.context.count}
            `;
            vscode.window.showInformationMessage(message);
        }),

        vscode.commands.registerCommand('memorylane.showInsights', async () => {
            const insights = await sidecarManager.getMemories('insights');
            if (insights.length === 0) {
                vscode.window.showInformationMessage('No insights learned yet. Keep working!');
                return;
            }

            const items = insights.map(i => ({
                label: i.content,
                detail: `Relevance: ${i.relevance_score.toFixed(1)} | Used ${i.usage_count} times`
            }));

            await vscode.window.showQuickPick(items, {
                placeHolder: 'Project Insights'
            });
        }),

        vscode.commands.registerCommand('memorylane.showCostSavings', async () => {
            const metrics = interactionTracker.getMetrics();
            const panel = vscode.window.createWebviewPanel(
                'memorylaneSavings',
                'MemoryLane Cost Savings',
                vscode.ViewColumn.One,
                { enableScripts: true }
            );

            panel.webview.html = getSavingsHTML(metrics);
        }),

        vscode.commands.registerCommand('memorylane.showKnowledgeGraph', () => {
            KnowledgeGraphPanel.createOrShow(context.extensionUri, sidecarManager);
        }),

        vscode.commands.registerCommand('memorylane.toggleScope', () => {
            overviewTreeProvider.toggleScope();
        }),

        vscode.commands.registerCommand('memorylane.startLearning', async () => {
            await sidecarManager.startLearning();
            vscode.window.showInformationMessage('MemoryLane learning started');
            statusBarManager.setLearning(true);
        }),

        vscode.commands.registerCommand('memorylane.stopLearning', async () => {
            await sidecarManager.stopLearning();
            vscode.window.showInformationMessage('MemoryLane learning stopped');
            statusBarManager.setLearning(false);
        }),

        vscode.commands.registerCommand('memorylane.resetMemory', async () => {
            const confirm = await vscode.window.showWarningMessage(
                'This will delete ALL memories. Are you sure?',
                'Yes', 'No'
            );

            if (confirm === 'Yes') {
                await sidecarManager.resetMemory();
                vscode.window.showInformationMessage('All memories reset');
                memoryTreeProvider.refresh();
                insightsTreeProvider.refresh();
            }
        }),

        vscode.commands.registerCommand('memorylane.exportContext', async () => {
            const markdown = await sidecarManager.exportMarkdown();
            const doc = await vscode.workspace.openTextDocument({
                content: markdown,
                language: 'markdown'
            });
            await vscode.window.showTextDocument(doc);
        })
    );

    // Refresh status bar every 5 seconds
    setInterval(async () => {
        const stats = await sidecarManager.getStats();
        const metrics = interactionTracker.getMetrics();
        statusBarManager.update(stats, metrics);
    }, 5000);

    // Watch for file changes and update memories
    if (config.get('autoLearn', true)) {
        const fileWatcher = vscode.workspace.createFileSystemWatcher('**/*.{py,js,ts,tsx,jsx}');

        fileWatcher.onDidChange(async (uri) => {
            await sidecarManager.notifyFileChange(uri.fsPath, 'modified');
            memoryTreeProvider.refresh();
        });

        fileWatcher.onDidCreate(async (uri) => {
            await sidecarManager.notifyFileChange(uri.fsPath, 'created');
            memoryTreeProvider.refresh();
        });

        context.subscriptions.push(fileWatcher);
    }

    console.log('MemoryLane extension activated');
}

export function deactivate() {
    if (sidecarManager) {
        sidecarManager.stop();
    }
    if (statusBarManager) {
        statusBarManager.dispose();
    }
    if (interactionTracker) {
        interactionTracker.stop();
    }
}

function getSavingsHTML(metrics: any): string {
    return `
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {
                    font-family: var(--vscode-font-family);
                    padding: 20px;
                }
                .metric {
                    background: var(--vscode-editor-background);
                    border: 1px solid var(--vscode-panel-border);
                    padding: 15px;
                    margin: 10px 0;
                    border-radius: 5px;
                }
                .metric h2 {
                    margin-top: 0;
                    color: var(--vscode-foreground);
                }
                .value {
                    font-size: 2em;
                    font-weight: bold;
                    color: var(--vscode-charts-green);
                }
                .subtitle {
                    color: var(--vscode-descriptionForeground);
                }
            </style>
        </head>
        <body>
            <h1>💰 Cost Savings Dashboard</h1>

            <div class="metric">
                <h2>Total Saved</h2>
                <div class="value">$${metrics.totalSaved.toFixed(2)}</div>
                <div class="subtitle">This Week</div>
            </div>

            <div class="metric">
                <h2>Compression Ratio</h2>
                <div class="value">${metrics.compressionRatio.toFixed(1)}x</div>
                <div class="subtitle">Average Context Compression</div>
            </div>

            <div class="metric">
                <h2>Tokens Saved</h2>
                <div class="value">${metrics.tokensSaved.toLocaleString()}</div>
                <div class="subtitle">Total Across All Interactions</div>
            </div>

            <div class="metric">
                <h2>Interactions</h2>
                <div class="value">${metrics.interactions}</div>
                <div class="subtitle">Claude Code Conversations</div>
            </div>

            <div class="metric">
                <h2>Savings Rate</h2>
                <div class="value">${metrics.savingsPercent.toFixed(1)}%</div>
                <div class="subtitle">Cost Reduction vs Baseline</div>
            </div>
        </body>
        </html>
    `;
}

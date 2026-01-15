import * as vscode from 'vscode';
import { SidecarManager, Memory } from './sidecar';

export class KnowledgeGraphPanel {
    public static currentPanel: KnowledgeGraphPanel | undefined;
    private readonly _panel: vscode.WebviewPanel;
    private _disposables: vscode.Disposable[] = [];

    public static createOrShow(extensionUri: vscode.Uri, sidecarManager: SidecarManager) {
        const column = vscode.window.activeTextEditor
            ? vscode.window.activeTextEditor.viewColumn
            : undefined;

        if (KnowledgeGraphPanel.currentPanel) {
            KnowledgeGraphPanel.currentPanel._panel.reveal(column);
            return;
        }

        const panel = vscode.window.createWebviewPanel(
            'memorylanKnowledgeGraph',
            'MemoryLane Knowledge Graph',
            column || vscode.ViewColumn.One,
            {
                enableScripts: true,
                retainContextWhenHidden: true,
                localResourceRoots: [vscode.Uri.joinPath(extensionUri, 'media')]
            }
        );

        KnowledgeGraphPanel.currentPanel = new KnowledgeGraphPanel(panel, extensionUri, sidecarManager);
    }

    private constructor(panel: vscode.WebviewPanel, extensionUri: vscode.Uri, private sidecarManager: SidecarManager) {
        this._panel = panel;
        this._update();

        this._panel.onDidDispose(() => this.dispose(), null, this._disposables);

        this._panel.webview.onDidReceiveMessage(
            async message => {
                switch (message.command) {
                    case 'refresh':
                        await this._update();
                        break;
                }
            },
            null,
            this._disposables
        );
    }

    private async _update() {
        const webview = this._panel.webview;

        // Get all memories
        const allMemories = await this.sidecarManager.getMemories();

        // Build graph data
        const graphData = this._buildGraphData(allMemories);

        this._panel.webview.html = this._getHtmlForWebview(webview, graphData);
    }

    private _buildGraphData(memories: Memory[]): any {
        const nodes: any[] = [];
        const links: any[] = [];

        // Group by category
        const categories = new Set(memories.map(m => m.category));

        // Add category nodes
        categories.forEach(cat => {
            nodes.push({
                id: `cat-${cat}`,
                label: cat.charAt(0).toUpperCase() + cat.slice(1),
                type: 'category',
                size: 20
            });
        });

        // Add memory nodes
        memories.forEach((memory, index) => {
            nodes.push({
                id: `mem-${index}`,
                label: memory.content.substring(0, 50) + (memory.content.length > 50 ? '...' : ''),
                type: 'memory',
                category: memory.category,
                relevance: memory.relevance_score,
                size: 10 + (memory.relevance_score * 10),
                usage: memory.usage_count
            });

            // Link to category
            links.push({
                source: `cat-${memory.category}`,
                target: `mem-${index}`,
                strength: memory.relevance_score
            });
        });

        // Add links between related memories (based on keyword similarity)
        for (let i = 0; i < memories.length; i++) {
            for (let j = i + 1; j < memories.length; j++) {
                const similarity = this._calculateSimilarity(memories[i].content, memories[j].content);
                if (similarity > 0.3) {
                    links.push({
                        source: `mem-${i}`,
                        target: `mem-${j}`,
                        strength: similarity
                    });
                }
            }
        }

        return { nodes, links };
    }

    private _calculateSimilarity(text1: string, text2: string): number {
        // Simple keyword-based similarity
        const words1 = new Set(text1.toLowerCase().split(/\s+/));
        const words2 = new Set(text2.toLowerCase().split(/\s+/));

        const intersection = new Set([...words1].filter(x => words2.has(x)));
        const union = new Set([...words1, ...words2]);

        return intersection.size / union.size;
    }

    private _getHtmlForWebview(webview: vscode.Webview, graphData: any) {
        return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Knowledge Graph</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        body {
            margin: 0;
            padding: 0;
            overflow: hidden;
            font-family: var(--vscode-font-family);
            background-color: var(--vscode-editor-background);
        }
        #graph {
            width: 100vw;
            height: 100vh;
        }
        .node {
            cursor: pointer;
        }
        .node-label {
            font-size: 10px;
            fill: var(--vscode-foreground);
            pointer-events: none;
        }
        .link {
            stroke: var(--vscode-panel-border);
            stroke-opacity: 0.6;
        }
        .controls {
            position: absolute;
            top: 10px;
            right: 10px;
            background: var(--vscode-editor-background);
            border: 1px solid var(--vscode-panel-border);
            padding: 10px;
            border-radius: 5px;
        }
        button {
            background: var(--vscode-button-background);
            color: var(--vscode-button-foreground);
            border: none;
            padding: 5px 10px;
            cursor: pointer;
            border-radius: 3px;
        }
        button:hover {
            background: var(--vscode-button-hoverBackground);
        }
        .legend {
            position: absolute;
            bottom: 10px;
            left: 10px;
            background: var(--vscode-editor-background);
            border: 1px solid var(--vscode-panel-border);
            padding: 10px;
            border-radius: 5px;
            font-size: 12px;
        }
        .legend-item {
            margin: 5px 0;
            display: flex;
            align-items: center;
        }
        .legend-color {
            width: 20px;
            height: 20px;
            margin-right: 10px;
            border-radius: 50%;
        }
    </style>
</head>
<body>
    <div id="graph"></div>
    <div class="controls">
        <button onclick="refresh()">Refresh</button>
        <button onclick="resetZoom()">Reset Zoom</button>
    </div>
    <div class="legend">
        <div class="legend-item">
            <div class="legend-color" style="background: #4CAF50;"></div>
            <span>Category</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background: #2196F3;"></div>
            <span>Memory (high relevance)</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background: #9E9E9E;"></div>
            <span>Memory (low relevance)</span>
        </div>
    </div>

    <script>
        const vscode = acquireVsCodeApi();
        const graphData = ${JSON.stringify(graphData)};

        const width = window.innerWidth;
        const height = window.innerHeight;

        const svg = d3.select('#graph')
            .append('svg')
            .attr('width', width)
            .attr('height', height);

        const g = svg.append('g');

        // Add zoom behavior
        const zoom = d3.zoom()
            .scaleExtent([0.1, 10])
            .on('zoom', (event) => {
                g.attr('transform', event.transform);
            });

        svg.call(zoom);

        // Color scale
        const colorScale = d3.scaleOrdinal()
            .domain(['category', 'patterns', 'insights', 'learnings', 'context'])
            .range(['#4CAF50', '#2196F3', '#FF9800', '#9C27B0', '#00BCD4']);

        // Create force simulation
        const simulation = d3.forceSimulation(graphData.nodes)
            .force('link', d3.forceLink(graphData.links).id(d => d.id).distance(100))
            .force('charge', d3.forceManyBody().strength(-300))
            .force('center', d3.forceCenter(width / 2, height / 2))
            .force('collision', d3.forceCollide().radius(d => d.size));

        // Create links
        const link = g.append('g')
            .selectAll('line')
            .data(graphData.links)
            .enter()
            .append('line')
            .attr('class', 'link')
            .attr('stroke-width', d => d.strength * 3);

        // Create nodes
        const node = g.append('g')
            .selectAll('circle')
            .data(graphData.nodes)
            .enter()
            .append('circle')
            .attr('class', 'node')
            .attr('r', d => d.size)
            .attr('fill', d => {
                if (d.type === 'category') return colorScale('category');
                if (d.type === 'memory') {
                    return d.relevance > 0.7 ? colorScale(d.category) : '#9E9E9E';
                }
                return '#CCCCCC';
            })
            .call(drag(simulation));

        // Add labels
        const labels = g.append('g')
            .selectAll('text')
            .data(graphData.nodes)
            .enter()
            .append('text')
            .attr('class', 'node-label')
            .text(d => d.label)
            .attr('text-anchor', 'middle')
            .attr('dy', d => d.size + 15);

        // Add tooltips
        node.append('title')
            .text(d => {
                if (d.type === 'category') return \`Category: \${d.label}\`;
                return \`\${d.label}\\nRelevance: \${d.relevance.toFixed(2)}\\nUsed: \${d.usage} times\`;
            });

        // Update positions on tick
        simulation.on('tick', () => {
            link
                .attr('x1', d => d.source.x)
                .attr('y1', d => d.source.y)
                .attr('x2', d => d.target.x)
                .attr('y2', d => d.target.y);

            node
                .attr('cx', d => d.x)
                .attr('cy', d => d.y);

            labels
                .attr('x', d => d.x)
                .attr('y', d => d.y);
        });

        // Drag behavior
        function drag(simulation) {
            function dragstarted(event) {
                if (!event.active) simulation.alphaTarget(0.3).restart();
                event.subject.fx = event.subject.x;
                event.subject.fy = event.subject.y;
            }

            function dragged(event) {
                event.subject.fx = event.x;
                event.subject.fy = event.y;
            }

            function dragended(event) {
                if (!event.active) simulation.alphaTarget(0);
                event.subject.fx = null;
                event.subject.fy = null;
            }

            return d3.drag()
                .on('start', dragstarted)
                .on('drag', dragged)
                .on('end', dragended);
        }

        function refresh() {
            vscode.postMessage({ command: 'refresh' });
        }

        function resetZoom() {
            svg.transition().duration(750).call(
                zoom.transform,
                d3.zoomIdentity
            );
        }
    </script>
</body>
</html>`;
    }

    public dispose() {
        KnowledgeGraphPanel.currentPanel = undefined;

        this._panel.dispose();

        while (this._disposables.length) {
            const disposable = this._disposables.pop();
            if (disposable) {
                disposable.dispose();
            }
        }
    }
}

import * as vscode from 'vscode';
import * as net from 'net';
import * as child_process from 'child_process';
import * as path from 'path';

export interface MemoryStats {
    memory: {
        total_memories: number;
        total_retrievals: number;
        categories: {
            [key: string]: {
                count: number;
                avg_relevance: number;
                total_usage: number;
            };
        };
    };
    server: {
        requests_handled: number;
        errors: number;
        started_at: string;
    };
}

export interface Memory {
    id: string;
    content: string;
    category: string;
    source: string;
    timestamp: string;
    relevance_score: number;
    usage_count: number;
    last_used: string | null;
}

export class SidecarManager {
    private serverProcess: child_process.ChildProcess | null = null;
    private socketPath = '/tmp/memorylane.sock';
    private learningProcess: child_process.ChildProcess | null = null;
    private workspaceRoot: string;

    constructor(private context: vscode.ExtensionContext) {
        this.workspaceRoot = vscode.workspace.workspaceFolders?.[0].uri.fsPath || '';
    }

    async start(): Promise<void> {
        if (this.serverProcess) {
            console.log('Sidecar already running');
            return;
        }

        const config = vscode.workspace.getConfiguration('memorylane');
        const pythonPath = config.get('pythonPath', 'python3');

        const serverScript = path.join(this.workspaceRoot, 'src', 'server.py');

        console.log('Starting MemoryLane sidecar...');

        this.serverProcess = child_process.spawn(pythonPath, [serverScript, 'start'], {
            cwd: this.workspaceRoot,
            detached: true,
            stdio: 'ignore'
        });

        this.serverProcess.unref();

        // Wait for server to be ready
        await this.waitForServer();

        vscode.window.showInformationMessage('🧠 MemoryLane server started');
    }

    async stop(): Promise<void> {
        if (!this.serverProcess) {
            return;
        }

        try {
            await this.sendRequest({ action: 'shutdown' });
        } catch (e) {
            // Server may already be stopped
        }

        this.serverProcess = null;
        this.stopLearning();
    }

    private async waitForServer(maxAttempts = 10): Promise<void> {
        for (let i = 0; i < maxAttempts; i++) {
            try {
                await this.sendRequest({ action: 'ping' });
                return;
            } catch (e) {
                await new Promise(resolve => setTimeout(resolve, 500));
            }
        }
        throw new Error('Server failed to start');
    }

    private async sendRequest(request: any): Promise<any> {
        return new Promise((resolve, reject) => {
            const client = net.createConnection(this.socketPath, () => {
                client.write(JSON.stringify(request) + '\n');
            });

            let data = '';
            client.on('data', (chunk) => {
                data += chunk.toString();
                if (data.includes('\n')) {
                    client.end();
                    try {
                        const response = JSON.parse(data.trim());
                        resolve(response);
                    } catch (e) {
                        reject(new Error('Invalid JSON response'));
                    }
                }
            });

            client.on('error', (err) => {
                reject(err);
            });
        });
    }

    async getStats(): Promise<MemoryStats> {
        const response = await this.sendRequest({ action: 'get_stats' });
        if (response.status === 'success') {
            return {
                memory: response.memory_stats,
                server: response.server_stats
            };
        }
        throw new Error(response.error);
    }

    async getMemories(category?: string): Promise<Memory[]> {
        const response = await this.sendRequest({
            action: 'get_memories',
            category: category
        });
        if (response.status === 'success') {
            return response.memories;
        }
        throw new Error(response.error);
    }

    async addMemory(category: string, content: string, source: string, relevance: number = 1.0): Promise<string> {
        const response = await this.sendRequest({
            action: 'add_memory',
            category: category,
            content: content,
            source: source,
            relevance_score: relevance
        });
        if (response.status === 'success') {
            return response.memory_id;
        }
        throw new Error(response.error);
    }

    async exportMarkdown(category?: string): Promise<string> {
        const response = await this.sendRequest({
            action: 'get_context',
            category: category
        });
        if (response.status === 'success') {
            return response.context;
        }
        throw new Error(response.error);
    }

    async resetMemory(): Promise<void> {
        const config = vscode.workspace.getConfiguration('memorylane');
        const pythonPath = config.get('pythonPath', 'python3');
        const cliScript = path.join(this.workspaceRoot, 'src', 'cli.py');

        await new Promise((resolve, reject) => {
            const proc = child_process.spawn(pythonPath, [cliScript, 'reset', '--force'], {
                cwd: this.workspaceRoot
            });

            proc.on('close', (code) => {
                if (code === 0) {
                    resolve(undefined);
                } else {
                    reject(new Error(`Reset failed with code ${code}`));
                }
            });
        });
    }

    async startLearning(): Promise<void> {
        if (this.learningProcess) {
            return;
        }

        const config = vscode.workspace.getConfiguration('memorylane');
        const pythonPath = config.get('pythonPath', 'python3');
        const learnerScript = path.join(this.workspaceRoot, 'src', 'learner.py');

        this.learningProcess = child_process.spawn(pythonPath, [learnerScript, 'watch'], {
            cwd: this.workspaceRoot,
            detached: true,
            stdio: 'ignore'
        });

        this.learningProcess.unref();
    }

    async stopLearning(): Promise<void> {
        if (this.learningProcess) {
            this.learningProcess.kill();
            this.learningProcess = null;
        }
    }

    async notifyFileChange(filePath: string, changeType: string): Promise<void> {
        // Log file change for passive learning
        // The learner.py watch process will pick this up
        console.log(`File ${changeType}: ${filePath}`);
    }
}

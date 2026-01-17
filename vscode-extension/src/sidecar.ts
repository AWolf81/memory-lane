import * as vscode from 'vscode';
import * as net from 'net';
import * as child_process from 'child_process';
import * as path from 'path';
import * as fs from 'fs';
import * as crypto from 'crypto';

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
    private socketPath: string;
    private learningProcess: child_process.ChildProcess | null = null;
    private workspaceRoot: string;
    private sidecarRoot: string;  // Where Python sidecar files are located

    constructor(private context: vscode.ExtensionContext) {
        this.workspaceRoot = vscode.workspace.workspaceFolders?.[0].uri.fsPath || '';
        // Sidecar is one level up from the extension directory (vscode-extension/../src/)
        this.sidecarRoot = path.dirname(context.extensionPath);
        // Generate workspace-specific socket path for isolation
        this.socketPath = this.getWorkspaceSocketPath();
    }

    private getWorkspaceSocketPath(): string {
        if (!this.workspaceRoot) {
            // Fallback for no workspace - use sidecar root
            const hash = crypto.createHash('md5').update(this.sidecarRoot).digest('hex').slice(0, 8);
            return `/tmp/memorylane-${hash}.sock`;
        }
        const hash = crypto.createHash('md5').update(this.workspaceRoot).digest('hex').slice(0, 8);
        return `/tmp/memorylane-${hash}.sock`;
    }

    async start(): Promise<void> {
        if (this.serverProcess) {
            console.log('Sidecar already running');
            return;
        }

        const config = vscode.workspace.getConfiguration('memorylane');
        const pythonPath = config.get<string>('pythonPath', 'python3');

        const serverScript = path.join(this.sidecarRoot, 'src', 'server.py');

        // Use workspace if available, otherwise use sidecar root for data storage
        const dataDir = this.workspaceRoot || this.sidecarRoot;

        // Validate server script exists
        if (!fs.existsSync(serverScript)) {
            throw new Error(`Server script not found: ${serverScript}`);
        }

        console.log('Starting MemoryLane sidecar...');
        console.log(`Python: ${pythonPath}, Script: ${serverScript}`);

        // Collect stderr for error reporting
        let stderrOutput = '';

        this.serverProcess = child_process.spawn(pythonPath, [serverScript, 'start', '--socket', this.socketPath], {
            cwd: dataDir,
            detached: true,
            stdio: ['ignore', 'ignore', 'pipe']  // Capture stderr
        });

        // Capture stderr for debugging
        if (this.serverProcess.stderr) {
            this.serverProcess.stderr.on('data', (data) => {
                stderrOutput += data.toString();
                console.error('Sidecar stderr:', data.toString());
            });
        }

        // Handle process errors
        this.serverProcess.on('error', (err) => {
            console.error('Failed to spawn sidecar process:', err);
        });

        this.serverProcess.unref();

        // Wait for server to be ready
        try {
            await this.waitForServer();
        } catch (e) {
            // Clean up process reference on failure
            this.serverProcess = null;

            // Provide more helpful error message
            let errorMsg = 'Server failed to start';
            if (stderrOutput) {
                errorMsg += `: ${stderrOutput.trim().split('\n').pop()}`;
            }
            throw new Error(errorMsg);
        }

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
        const cliScript = path.join(this.sidecarRoot, 'src', 'cli.py');
        const dataDir = this.workspaceRoot || this.sidecarRoot;

        await new Promise((resolve, reject) => {
            const proc = child_process.spawn(pythonPath, [cliScript, 'reset', '--force'], {
                cwd: dataDir
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
        const learnerScript = path.join(this.sidecarRoot, 'src', 'learner.py');
        const dataDir = this.workspaceRoot || this.sidecarRoot;

        this.learningProcess = child_process.spawn(pythonPath, [learnerScript, 'watch'], {
            cwd: dataDir,
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

    async getRegisteredProjects(): Promise<ProjectInfo[]> {
        const config = vscode.workspace.getConfiguration('memorylane');
        const pythonPath = config.get('pythonPath', 'python3');
        const cliScript = path.join(this.sidecarRoot, 'src', 'cli.py');

        return new Promise((resolve, reject) => {
            const proc = child_process.spawn(pythonPath, [cliScript, 'projects', 'list', '--json'], {
                cwd: this.workspaceRoot || this.sidecarRoot
            });

            let stdout = '';
            let stderr = '';

            proc.stdout?.on('data', (data) => { stdout += data.toString(); });
            proc.stderr?.on('data', (data) => { stderr += data.toString(); });

            proc.on('close', (code) => {
                if (code === 0) {
                    try {
                        // Parse the JSON output - for now return parsed list
                        // The CLI currently outputs human-readable format, not JSON
                        // So we'll parse the text output
                        const projects: ProjectInfo[] = [];
                        const lines = stdout.split('\n');
                        let currentProject: Partial<ProjectInfo> = {};

                        for (const line of lines) {
                            if (line.startsWith('✓') || line.startsWith('✗')) {
                                if (currentProject.name) {
                                    projects.push(currentProject as ProjectInfo);
                                }
                                currentProject = {
                                    name: line.substring(2).trim(),
                                    valid: line.startsWith('✓')
                                };
                            } else if (line.includes('Path:')) {
                                currentProject.path = line.split('Path:')[1].trim();
                            }
                        }
                        if (currentProject.name) {
                            projects.push(currentProject as ProjectInfo);
                        }

                        resolve(projects);
                    } catch (e) {
                        resolve([]);
                    }
                } else {
                    resolve([]);
                }
            });
        });
    }

    async getCrossProjectMemories(query?: string, projectNames?: string[]): Promise<Memory[]> {
        const config = vscode.workspace.getConfiguration('memorylane');
        const pythonPath = config.get('pythonPath', 'python3');
        const cliScript = path.join(this.sidecarRoot, 'src', 'cli.py');

        const args = [cliScript, 'projects', 'search'];
        if (query) {
            args.push('--query', query);
        }

        return new Promise((resolve, reject) => {
            const proc = child_process.spawn(pythonPath, args, {
                cwd: this.workspaceRoot || this.sidecarRoot
            });

            let stdout = '';
            proc.stdout?.on('data', (data) => { stdout += data.toString(); });

            proc.on('close', (code) => {
                // For now, return empty - the search output is human readable
                // In a full implementation, we'd add --json flag to the CLI
                resolve([]);
            });
        });
    }

    getWorkspaceName(): string {
        return path.basename(this.workspaceRoot) || 'current';
    }
}

export interface ProjectInfo {
    name: string;
    path: string;
    valid: boolean;
}

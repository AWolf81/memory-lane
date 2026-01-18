import * as vscode from 'vscode';
import * as net from 'net';
import * as child_process from 'child_process';
import * as path from 'path';
import * as fs from 'fs';
import * as crypto from 'crypto';

// Output channel for debugging - visible in Output panel
let outputChannel: vscode.OutputChannel | null = null;

function getOutputChannel(): vscode.OutputChannel {
    if (!outputChannel) {
        outputChannel = vscode.window.createOutputChannel('MemoryLane');
    }
    return outputChannel;
}

function log(message: string, level: 'info' | 'warn' | 'error' = 'info'): void {
    const timestamp = new Date().toISOString().slice(11, 23);
    const prefix = level === 'error' ? '❌' : level === 'warn' ? '⚠️' : '📝';
    const line = `[${timestamp}] ${prefix} ${message}`;

    getOutputChannel().appendLine(line);

    // Also log to console for Developer Tools
    if (level === 'error') {
        console.error(`[MemoryLane] ${message}`);
    } else {
        console.log(`[MemoryLane] ${message}`);
    }
}

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

        // Log initialization details
        log('SidecarManager initialized');
        log(`  extensionPath: ${context.extensionPath}`);
        log(`  sidecarRoot: ${this.sidecarRoot}`);
        log(`  workspaceRoot: ${this.workspaceRoot || '(none)'}`);
        log(`  socketPath: ${this.socketPath}`);
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
            log('Sidecar already running (has process reference)');
            return;
        }

        // Check if socket already exists (server running from previous session)
        if (fs.existsSync(this.socketPath)) {
            log(`Socket already exists: ${this.socketPath}`);
            try {
                await this.sendRequest({ action: 'ping' }, 2000);
                log('Existing server responded to ping - reusing');
                return;
            } catch {
                log('Existing socket unresponsive - removing stale socket', 'warn');
                fs.unlinkSync(this.socketPath);
            }
        }

        const config = vscode.workspace.getConfiguration('memorylane');
        const pythonPath = config.get<string>('pythonPath', 'python3');

        const serverScript = path.join(this.sidecarRoot, 'src', 'server.py');

        // Use workspace if available, otherwise use sidecar root for data storage
        const dataDir = this.workspaceRoot || this.sidecarRoot;

        log('Starting MemoryLane sidecar...');
        log(`  pythonPath: ${pythonPath}`);
        log(`  serverScript: ${serverScript}`);
        log(`  dataDir (cwd): ${dataDir}`);
        log(`  socketPath: ${this.socketPath}`);

        // Validate paths exist
        if (!fs.existsSync(serverScript)) {
            const error = `Server script not found: ${serverScript}`;
            log(error, 'error');
            throw new Error(error);
        }

        if (!fs.existsSync(dataDir)) {
            const error = `Data directory not found: ${dataDir}`;
            log(error, 'error');
            throw new Error(error);
        }

        // Check if .memorylane folder exists, create if not
        const memorylaneDir = path.join(dataDir, '.memorylane');
        if (!fs.existsSync(memorylaneDir)) {
            log(`Creating .memorylane directory: ${memorylaneDir}`);
            fs.mkdirSync(memorylaneDir, { recursive: true });
        }

        // Collect stderr for error reporting
        let stderrOutput = '';
        let stdoutOutput = '';

        const args = [serverScript, 'start', '--socket', this.socketPath];
        log(`Spawning: ${pythonPath} ${args.join(' ')}`);

        this.serverProcess = child_process.spawn(pythonPath, args, {
            cwd: dataDir,
            detached: true,
            stdio: ['ignore', 'pipe', 'pipe']  // Capture both stdout and stderr
        });

        const pid = this.serverProcess.pid;
        log(`Spawned process with PID: ${pid}`);

        // Capture stdout for debugging
        if (this.serverProcess.stdout) {
            this.serverProcess.stdout.on('data', (data) => {
                stdoutOutput += data.toString();
                log(`stdout: ${data.toString().trim()}`);
            });
        }

        // Capture stderr for debugging
        if (this.serverProcess.stderr) {
            this.serverProcess.stderr.on('data', (data) => {
                stderrOutput += data.toString();
                log(`stderr: ${data.toString().trim()}`, 'warn');
            });
        }

        // Handle process errors
        this.serverProcess.on('error', (err) => {
            log(`Process spawn error: ${err.message}`, 'error');
        });

        this.serverProcess.on('exit', (code, signal) => {
            log(`Process exited: code=${code}, signal=${signal}`, code === 0 ? 'info' : 'error');
        });

        this.serverProcess.unref();

        // Wait for server to be ready
        log('Waiting for server to be ready...');
        try {
            await this.waitForServer();
            log('Server is ready and responding');
        } catch (e) {
            // Clean up process reference on failure
            this.serverProcess = null;

            // Provide more helpful error message
            let errorMsg = 'Server failed to start within timeout';
            if (stderrOutput) {
                errorMsg += `\nStderr: ${stderrOutput.trim()}`;
            }
            if (stdoutOutput) {
                errorMsg += `\nStdout: ${stdoutOutput.trim()}`;
            }
            errorMsg += `\nCheck Output panel (View → Output → MemoryLane) for details`;

            log(errorMsg, 'error');
            throw new Error(errorMsg);
        }

        vscode.window.showInformationMessage('🧠 MemoryLane server started');
    }

    async stop(): Promise<void> {
        log('Stopping sidecar...');

        if (!this.serverProcess) {
            log('No server process to stop');
            return;
        }

        try {
            await this.sendRequest({ action: 'shutdown' }, 5000);
            log('Server shutdown command sent');
        } catch (e) {
            log('Server may already be stopped', 'warn');
        }

        this.serverProcess = null;
        this.stopLearning();
        log('Sidecar stopped');
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

    private async sendRequest(request: any, timeoutMs: number = 10000): Promise<any> {
        return new Promise((resolve, reject) => {
            const action = request.action || 'unknown';
            let settled = false;

            // Timeout handler
            const timeout = setTimeout(() => {
                if (!settled) {
                    settled = true;
                    log(`Request timeout: ${action} after ${timeoutMs}ms`, 'error');
                    client.destroy();
                    reject(new Error(`Request timeout: ${action}`));
                }
            }, timeoutMs);

            const client = net.createConnection(this.socketPath, () => {
                client.write(JSON.stringify(request) + '\n');
            });

            let data = '';
            client.on('data', (chunk) => {
                data += chunk.toString();
                if (data.includes('\n')) {
                    clearTimeout(timeout);
                    if (!settled) {
                        settled = true;
                        client.end();
                        try {
                            const response = JSON.parse(data.trim());
                            resolve(response);
                        } catch (e) {
                            log(`Invalid JSON response for ${action}: ${data.slice(0, 100)}`, 'error');
                            reject(new Error('Invalid JSON response'));
                        }
                    }
                }
            });

            client.on('error', (err) => {
                clearTimeout(timeout);
                if (!settled) {
                    settled = true;
                    log(`Socket error for ${action}: ${err.message}`, 'error');
                    reject(err);
                }
            });

            client.on('close', () => {
                clearTimeout(timeout);
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

    /**
     * Get debug information about the current state
     */
    getDebugInfo(): DebugInfo {
        return {
            workspaceRoot: this.workspaceRoot,
            sidecarRoot: this.sidecarRoot,
            socketPath: this.socketPath,
            hasServerProcess: this.serverProcess !== null,
            hasLearningProcess: this.learningProcess !== null,
            socketExists: fs.existsSync(this.socketPath),
            memorylaneExists: fs.existsSync(path.join(this.workspaceRoot || this.sidecarRoot, '.memorylane')),
            serverScriptExists: fs.existsSync(path.join(this.sidecarRoot, 'src', 'server.py'))
        };
    }

    /**
     * Show the output channel for debugging
     */
    showOutput(): void {
        getOutputChannel().show();
    }
}

export interface DebugInfo {
    workspaceRoot: string;
    sidecarRoot: string;
    socketPath: string;
    hasServerProcess: boolean;
    hasLearningProcess: boolean;
    socketExists: boolean;
    memorylaneExists: boolean;
    serverScriptExists: boolean;
}

export interface ProjectInfo {
    name: string;
    path: string;
    valid: boolean;
}

#!/usr/bin/env python3
"""
MemoryLane Sidecar Server
Runs in the background to provide memory services via Unix socket IPC
"""

import os
import sys
import json
import socket
import signal
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

from memory_store import MemoryStore
from config_manager import ConfigManager


class MemoryLaneServer:
    """
    Background server that handles memory operations
    Communicates via Unix socket for low-latency IPC
    """

    def __init__(self, config: ConfigManager, socket_path: Optional[str] = None):
        self.config = config
        self.store = MemoryStore(str(config.get_path('memories_file')))
        self.socket_path = socket_path or "/tmp/memorylane.sock"
        self.pid_file = config.get_path('memory_dir') / "server.pid"
        self.running = False
        self.server_socket = None

        # Statistics
        self.stats = {
            'started_at': datetime.now().isoformat(),
            'requests_handled': 0,
            'errors': 0
        }

    def start(self):
        """Start the server"""
        # Check if already running
        if self.pid_file.exists():
            try:
                with open(self.pid_file, 'r') as f:
                    old_pid = int(f.read().strip())

                # Check if process exists
                os.kill(old_pid, 0)
                print(f"Server already running with PID {old_pid}")
                sys.exit(1)
            except (OSError, ValueError):
                # Process doesn't exist, remove stale PID file
                self.pid_file.unlink()

        # Write PID file
        with open(self.pid_file, 'w') as f:
            f.write(str(os.getpid()))

        print(f"🧠 MemoryLane Server starting (PID {os.getpid()})...")

        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        # Create Unix socket
        self._setup_socket()

        # Start listening
        self.running = True
        print(f"✓ Server listening on {self.socket_path}")
        self._listen()

    def _setup_socket(self):
        """Setup Unix domain socket"""
        # Remove existing socket file if it exists
        if os.path.exists(self.socket_path):
            os.remove(self.socket_path)

        self.server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server_socket.bind(self.socket_path)
        self.server_socket.listen(5)

        # Set permissions
        os.chmod(self.socket_path, 0o600)

    def _listen(self):
        """Main server loop"""
        while self.running:
            try:
                client_socket, _ = self.server_socket.accept()

                # Handle request in thread for concurrency
                thread = threading.Thread(
                    target=self._handle_client,
                    args=(client_socket,)
                )
                thread.daemon = True
                thread.start()

            except Exception as e:
                if self.running:  # Only log if not shutting down
                    print(f"Error accepting connection: {e}")
                    self.stats['errors'] += 1

    def _handle_client(self, client_socket: socket.socket):
        """Handle a client request"""
        try:
            # Read request (JSON)
            data = b''
            while True:
                chunk = client_socket.recv(4096)
                if not chunk:
                    break
                data += chunk
                # Simple protocol: newline-terminated JSON
                if b'\n' in chunk:
                    break

            if not data:
                return

            request = json.loads(data.decode('utf-8'))

            # Process request
            response = self._process_request(request)

            # Send response
            response_json = json.dumps(response) + '\n'
            client_socket.sendall(response_json.encode('utf-8'))

            self.stats['requests_handled'] += 1

        except Exception as e:
            error_response = {
                'status': 'error',
                'error': str(e)
            }
            try:
                client_socket.sendall(
                    (json.dumps(error_response) + '\n').encode('utf-8')
                )
            except:
                pass
            self.stats['errors'] += 1

        finally:
            client_socket.close()

    def _process_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Process a client request"""
        action = request.get('action')

        if action == 'add_memory':
            memory_id = self.store.add_memory(
                category=request['category'],
                content=request['content'],
                source=request.get('source', 'unknown'),
                relevance_score=request.get('relevance_score', 1.0),
                metadata=request.get('metadata')
            )
            return {
                'status': 'success',
                'memory_id': memory_id
            }

        elif action == 'get_memories':
            memories = self.store.get_memories(
                category=request.get('category'),
                min_relevance=request.get('min_relevance', 0.0),
                limit=request.get('limit')
            )
            return {
                'status': 'success',
                'memories': memories
            }

        elif action == 'get_context':
            # Get compressed context for injection
            category = request.get('category')
            markdown = self.store.to_markdown(category)

            return {
                'status': 'success',
                'context': markdown,
                'tokens': len(markdown.split())  # Rough estimate
            }

        elif action == 'update_usage':
            self.store.update_memory_usage(request['memory_id'])
            return {
                'status': 'success'
            }

        elif action == 'get_stats':
            memory_stats = self.store.get_stats()
            return {
                'status': 'success',
                'memory_stats': memory_stats,
                'server_stats': self.stats
            }

        elif action == 'prune':
            pruned = self.store.prune_low_relevance(
                threshold=request.get('threshold', 0.3),
                max_age_days=request.get('max_age_days', 30)
            )
            return {
                'status': 'success',
                'pruned_count': pruned
            }

        elif action == 'ping':
            return {
                'status': 'success',
                'message': 'pong',
                'uptime': (datetime.now() - datetime.fromisoformat(self.stats['started_at'])).total_seconds()
            }

        elif action == 'shutdown':
            self.stop()
            return {
                'status': 'success',
                'message': 'shutting down'
            }

        else:
            return {
                'status': 'error',
                'error': f'Unknown action: {action}'
            }

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        print(f"\n🛑 Received signal {signum}, shutting down...")
        self.stop()

    def stop(self):
        """Stop the server gracefully"""
        self.running = False

        # Close socket
        if self.server_socket:
            self.server_socket.close()

        # Remove socket file
        if os.path.exists(self.socket_path):
            os.remove(self.socket_path)

        # Remove PID file
        if self.pid_file.exists():
            self.pid_file.unlink()

        print(f"✓ Server stopped (handled {self.stats['requests_handled']} requests)")
        sys.exit(0)


class MemoryLaneClient:
    """
    Client for communicating with MemoryLane server
    """

    def __init__(self, socket_path: str = "/tmp/memorylane.sock"):
        self.socket_path = socket_path

    def _send_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Send a request to the server and get response"""
        try:
            # Connect to server
            client_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            client_socket.connect(self.socket_path)

            # Send request
            request_json = json.dumps(request) + '\n'
            client_socket.sendall(request_json.encode('utf-8'))

            # Receive response
            data = b''
            while True:
                chunk = client_socket.recv(4096)
                if not chunk:
                    break
                data += chunk
                if b'\n' in chunk:
                    break

            response = json.loads(data.decode('utf-8'))
            client_socket.close()

            return response

        except Exception as e:
            return {
                'status': 'error',
                'error': f'Failed to communicate with server: {e}'
            }

    def add_memory(
        self,
        category: str,
        content: str,
        source: str = 'manual',
        relevance_score: float = 1.0,
        metadata: Optional[Dict] = None
    ) -> str:
        """Add a memory"""
        response = self._send_request({
            'action': 'add_memory',
            'category': category,
            'content': content,
            'source': source,
            'relevance_score': relevance_score,
            'metadata': metadata
        })

        if response['status'] == 'success':
            return response['memory_id']
        else:
            raise Exception(response.get('error', 'Unknown error'))

    def get_context(self, category: Optional[str] = None) -> str:
        """Get compressed context for injection"""
        response = self._send_request({
            'action': 'get_context',
            'category': category
        })

        if response['status'] == 'success':
            return response['context']
        else:
            raise Exception(response.get('error', 'Unknown error'))

    def get_stats(self) -> Dict[str, Any]:
        """Get server and memory statistics"""
        response = self._send_request({
            'action': 'get_stats'
        })

        if response['status'] == 'success':
            return {
                'memory': response['memory_stats'],
                'server': response['server_stats']
            }
        else:
            raise Exception(response.get('error', 'Unknown error'))

    def ping(self) -> bool:
        """Check if server is running"""
        try:
            response = self._send_request({'action': 'ping'})
            return response['status'] == 'success'
        except:
            return False

    def shutdown(self):
        """Shutdown the server"""
        self._send_request({'action': 'shutdown'})


def main():
    """Main entry point for server"""
    import argparse

    parser = argparse.ArgumentParser(description='MemoryLane Server')
    parser.add_argument(
        'command',
        choices=['start', 'stop', 'status'],
        help='Server command'
    )
    parser.add_argument(
        '--socket',
        default='/tmp/memorylane.sock',
        help='Unix socket path (default: /tmp/memorylane.sock)'
    )

    args = parser.parse_args()

    config = ConfigManager()

    if args.command == 'start':
        server = MemoryLaneServer(config, socket_path=args.socket)
        server.start()

    elif args.command == 'stop':
        client = MemoryLaneClient(socket_path=args.socket)
        try:
            client.shutdown()
            print("✓ Server stopped")
        except Exception as e:
            print(f"Error stopping server: {e}")
            sys.exit(1)

    elif args.command == 'status':
        client = MemoryLaneClient(socket_path=args.socket)
        if client.ping():
            stats = client.get_stats()
            print("✓ Server is running")
            print(f"  Socket: {args.socket}")
            print(f"  Requests handled: {stats['server']['requests_handled']}")
            print(f"  Errors: {stats['server']['errors']}")
            print(f"  Total memories: {stats['memory']['total_memories']}")
        else:
            print("✗ Server is not running")
            sys.exit(1)


if __name__ == '__main__':
    main()

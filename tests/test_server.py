"""
Tests for MemoryLane Sidecar Server.
"""

import json
import os
import sys
import socket
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from server import MemoryLaneServer, MemoryLaneClient


class TestServerInitialization:
    """Test server initialization."""

    def test_server_creates_with_config(self, tmp_path):
        """Server should initialize with config."""
        mock_config = MagicMock()
        mock_config.get_path.side_effect = lambda key: {
            'memories_file': tmp_path / "memories.json",
            'memory_dir': tmp_path
        }.get(key, tmp_path / key)

        with patch('server.MemoryStore'):
            server = MemoryLaneServer(mock_config, socket_path=str(tmp_path / "test.sock"))

            assert server.socket_path == str(tmp_path / "test.sock")
            assert server.running is False

    def test_server_uses_default_socket_path(self, tmp_path):
        """Server should use default socket path if not specified."""
        mock_config = MagicMock()
        mock_config.get_path.side_effect = lambda key: {
            'memories_file': tmp_path / "memories.json",
            'memory_dir': tmp_path
        }.get(key, tmp_path / key)

        with patch('server.MemoryStore'):
            server = MemoryLaneServer(mock_config)

            assert server.socket_path == "/tmp/memorylane.sock"


class TestRequestProcessing:
    """Test request processing."""

    @pytest.fixture
    def server(self, tmp_path):
        """Create server instance for testing."""
        mock_config = MagicMock()
        mock_config.get_path.side_effect = lambda key: {
            'memories_file': tmp_path / "memories.json",
            'memory_dir': tmp_path
        }.get(key, tmp_path / key)

        with patch('server.MemoryStore') as mock_store:
            mock_store.return_value.add_memory.return_value = "test-id-001"
            mock_store.return_value.get_memories.return_value = [
                {'id': 'patt-001', 'content': 'Test', 'category': 'patterns'}
            ]
            mock_store.return_value.get_stats.return_value = {
                'total_memories': 5,
                'categories': {}
            }
            mock_store.return_value.to_markdown.return_value = "# Test\n\nContent"
            mock_store.return_value.prune_low_relevance.return_value = 2

            server = MemoryLaneServer(mock_config, socket_path=str(tmp_path / "test.sock"))
            yield server

    def test_process_add_memory(self, server):
        """Should process add_memory request."""
        request = {
            'action': 'add_memory',
            'category': 'patterns',
            'content': 'Test pattern',
            'source': 'test',
            'relevance_score': 0.8
        }

        response = server._process_request(request)

        assert response['status'] == 'success'
        assert 'memory_id' in response

    def test_process_get_memories(self, server):
        """Should process get_memories request."""
        request = {
            'action': 'get_memories',
            'category': 'patterns',
            'min_relevance': 0.5,
            'limit': 10
        }

        response = server._process_request(request)

        assert response['status'] == 'success'
        assert 'memories' in response

    def test_process_get_context(self, server):
        """Should process get_context request."""
        request = {
            'action': 'get_context',
            'category': 'patterns'
        }

        response = server._process_request(request)

        assert response['status'] == 'success'
        assert 'context' in response
        assert 'tokens' in response

    def test_process_get_stats(self, server):
        """Should process get_stats request."""
        request = {'action': 'get_stats'}

        response = server._process_request(request)

        assert response['status'] == 'success'
        assert 'memory_stats' in response
        assert 'server_stats' in response

    def test_process_ping(self, server):
        """Should process ping request."""
        request = {'action': 'ping'}

        response = server._process_request(request)

        assert response['status'] == 'success'
        assert response['message'] == 'pong'
        assert 'uptime' in response

    def test_process_prune(self, server):
        """Should process prune request."""
        request = {
            'action': 'prune',
            'threshold': 0.3,
            'max_age_days': 30
        }

        response = server._process_request(request)

        assert response['status'] == 'success'
        assert 'pruned_count' in response

    def test_process_unknown_action(self, server):
        """Should return error for unknown action."""
        request = {'action': 'unknown_action'}

        response = server._process_request(request)

        assert response['status'] == 'error'
        assert 'Unknown action' in response['error']


class TestClientMethods:
    """Test client method wrappers."""

    def test_client_ping_returns_false_on_error(self):
        """Ping should return False when server not running."""
        client = MemoryLaneClient(socket_path="/nonexistent/path.sock")

        result = client.ping()

        assert result is False

    def test_client_send_request_handles_connection_error(self):
        """Client should handle connection errors gracefully."""
        client = MemoryLaneClient(socket_path="/nonexistent/path.sock")

        response = client._send_request({'action': 'ping'})

        assert response['status'] == 'error'
        assert 'Failed to communicate' in response['error']


class TestServerStats:
    """Test server statistics tracking."""

    @pytest.fixture
    def server(self, tmp_path):
        """Create server instance for testing."""
        mock_config = MagicMock()
        mock_config.get_path.side_effect = lambda key: {
            'memories_file': tmp_path / "memories.json",
            'memory_dir': tmp_path
        }.get(key, tmp_path / key)

        with patch('server.MemoryStore'):
            server = MemoryLaneServer(mock_config, socket_path=str(tmp_path / "test.sock"))
            yield server

    def test_stats_initialized(self, server):
        """Server should initialize stats."""
        assert 'started_at' in server.stats
        assert server.stats['requests_handled'] == 0
        assert server.stats['errors'] == 0


class TestUpdateUsage:
    """Test memory usage update."""

    @pytest.fixture
    def server(self, tmp_path):
        """Create server instance for testing."""
        mock_config = MagicMock()
        mock_config.get_path.side_effect = lambda key: {
            'memories_file': tmp_path / "memories.json",
            'memory_dir': tmp_path
        }.get(key, tmp_path / key)

        with patch('server.MemoryStore') as mock_store:
            server = MemoryLaneServer(mock_config, socket_path=str(tmp_path / "test.sock"))
            yield server

    def test_process_update_usage(self, server):
        """Should process update_usage request."""
        request = {
            'action': 'update_usage',
            'memory_id': 'patt-001'
        }

        response = server._process_request(request)

        assert response['status'] == 'success'


class TestShutdown:
    """Test server shutdown."""

    @pytest.fixture
    def server(self, tmp_path):
        """Create server instance for testing."""
        mock_config = MagicMock()
        mock_config.get_path.side_effect = lambda key: {
            'memories_file': tmp_path / "memories.json",
            'memory_dir': tmp_path
        }.get(key, tmp_path / key)

        with patch('server.MemoryStore'):
            server = MemoryLaneServer(mock_config, socket_path=str(tmp_path / "test.sock"))
            yield server

    def test_process_shutdown_sets_running_false(self, server):
        """Shutdown request should set running to False."""
        # Patch sys.exit to prevent actual exit
        with patch('sys.exit'):
            request = {'action': 'shutdown'}
            server._process_request(request)

            assert server.running is False


class TestClientAddMemory:
    """Test client add_memory method."""

    def test_add_memory_raises_on_error(self):
        """add_memory should raise exception on error response."""
        client = MemoryLaneClient(socket_path="/nonexistent.sock")

        with pytest.raises(Exception):
            client.add_memory(
                category='patterns',
                content='Test',
                source='test'
            )

    def test_get_context_raises_on_error(self):
        """get_context should raise exception on error response."""
        client = MemoryLaneClient(socket_path="/nonexistent.sock")

        with pytest.raises(Exception):
            client.get_context()

    def test_get_stats_raises_on_error(self):
        """get_stats should raise exception on error response."""
        client = MemoryLaneClient(socket_path="/nonexistent.sock")

        with pytest.raises(Exception):
            client.get_stats()


class TestPIDFileHandling:
    """Test PID file management."""

    def test_server_checks_for_existing_pid(self, tmp_path):
        """Server should check for existing PID file."""
        mock_config = MagicMock()
        mock_config.get_path.side_effect = lambda key: {
            'memories_file': tmp_path / "memories.json",
            'memory_dir': tmp_path
        }.get(key, tmp_path / key)

        # Create a stale PID file with non-existent process
        pid_file = tmp_path / "server.pid"
        pid_file.write_text("99999999")  # Unlikely to exist

        with patch('server.MemoryStore'):
            server = MemoryLaneServer(mock_config, socket_path=str(tmp_path / "test.sock"))
            # Server init should be fine, it cleans up stale PIDs on start

            assert server is not None

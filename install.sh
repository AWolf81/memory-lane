#!/bin/bash
set -e

echo "🚀 Installing MemoryLane..."
echo ""

# Check Python version
echo "🐍 Checking Python version..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    echo "   Found: $PYTHON_VERSION"
else
    echo "   ⚠️  Python 3 not found. Please install Python 3.8+"
    exit 1
fi

# Create directories
echo "📁 Creating directories..."
mkdir -p .memorylane
mkdir -p .memorylane/backups
mkdir -p .memorylane/logs

# Make CLI executable
echo "🔧 Making CLI executable..."
chmod +x src/cli.py

# Copy default config if doesn't exist
echo "⚙️  Setting up configuration..."
if [ ! -f .memorylane/config.json ]; then
    if [ -f config.json ]; then
        cp config.json .memorylane/config.json
        echo "   ✓ Config copied to .memorylane/config.json"
    fi
fi

# Initialize empty memory store
echo "🧠 Initializing memory store..."
python3 -c "
import sys
from pathlib import Path
sys.path.insert(0, 'src')
from memory_store import MemoryStore
store = MemoryStore('.memorylane/memories.json')
store.save(store.create_empty_memory())
print('   ✓ Memory store initialized')
"

# Test the CLI
echo "🧪 Testing MemoryLane CLI..."
python3 src/cli.py status > /dev/null 2>&1 && {
    echo "   ✓ CLI test passed!"
} || {
    echo "   ⚠️  Warning: CLI test failed"
}

echo ""
echo "✅ MemoryLane installation complete!"
echo ""
echo "Quick start:"
echo "  python3 src/cli.py status     - Show status"
echo "  python3 src/cli.py insights   - View insights"
echo "  python3 src/cli.py costs      - See cost savings"
echo ""
echo "🧠 MemoryLane is now ready to remember your project!"

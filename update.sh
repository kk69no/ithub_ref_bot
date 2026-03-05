#!/bin/bash
set -e

# Update script for ithub_ref_bot
# Updates code from git and restarts the service

SERVICE_NAME="ithub-ref-bot"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "================================================"
echo "ithub_ref_bot Update Script"
echo "================================================"
echo ""

# Check if running as root
if [[ $EUID -ne 0 ]]; then
    echo "❌ This script must be run as root"
    exit 1
fi

cd "$SCRIPT_DIR"

echo "📥 Pulling latest changes from git..."
git pull origin main

# Activate virtual environment
source venv/bin/activate

echo "📦 Installing/updating dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "🔄 Restarting service..."
systemctl restart $SERVICE_NAME

echo ""
echo "================================================"
echo "✅ Update Complete!"
echo "================================================"
echo ""
echo "Service status:"
systemctl status $SERVICE_NAME --no-pager
echo ""
echo "View logs:"
echo "  journalctl -u $SERVICE_NAME -f"
echo ""

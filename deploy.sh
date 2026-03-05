#!/bin/bash
set -e

# Deploy script for ithub_ref_bot
# Usage: ./deploy.sh <github_repo_url>

REPO_URL="${1:-https://github.com/yourusername/ithub_ref_bot.git}"
INSTALL_DIR="/opt/ithub_ref_bot"
SERVICE_NAME="ithub-ref-bot"
WEBHOOK_PORT="${WEBHOOK_PORT:-8443}"

echo "================================================"
echo "ithub_ref_bot Deployment Script"
echo "================================================"
echo ""
echo "Repository: $REPO_URL"
echo "Install directory: $INSTALL_DIR"
echo "Service name: $SERVICE_NAME"
echo "Webhook port: $WEBHOOK_PORT"
echo ""

# Check if running as root
if [[ $EUID -ne 0 ]]; then
    echo "❌ This script must be run as root"
    exit 1
fi

# Create installation directory
echo "📁 Creating installation directory..."
mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

# Clone or update repository
if [ -d .git ]; then
    echo "📦 Updating existing repository..."
    git pull origin main
else
    echo "📦 Cloning repository..."
    git clone "$REPO_URL" .
fi

# Create Python virtual environment
echo "🐍 Setting up Python virtual environment..."
if [ ! -d venv ]; then
    python3 -m venv venv
fi

# Activate virtual environment and install dependencies
echo "📥 Installing dependencies..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Create data directory
echo "📂 Creating data directory..."
mkdir -p data

# Copy .env.example to .env if not exists
if [ ! -f .env ]; then
    echo "⚙️  Copying .env.example to .env..."
    cp .env.example .env
    echo "⚠️  Please edit .env and set your configuration!"
    echo "   BOT_TOKEN, ADMIN_IDS, and other settings"
fi

# Create systemd service
echo "🔧 Creating systemd service..."
cat > /etc/systemd/system/${SERVICE_NAME}.service << EOF
[Unit]
Description=ithub_ref_bot Telegram Bot
After=network.target

[Service]
Type=simple
User=nobody
WorkingDirectory=$INSTALL_DIR
Environment="PATH=$INSTALL_DIR/venv/bin"
ExecStart=$INSTALL_DIR/venv/bin/python main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd
systemctl daemon-reload

# Enable service
systemctl enable ${SERVICE_NAME}

echo ""
echo "================================================"
echo "✅ Deployment Complete!"
echo "================================================"
echo ""
echo "Next steps:"
echo "1. Edit the configuration file:"
echo "   nano $INSTALL_DIR/.env"
echo ""
echo "2. Start the service:"
echo "   systemctl start $SERVICE_NAME"
echo ""
echo "3. Check service status:"
echo "   systemctl status $SERVICE_NAME"
echo ""
echo "4. View logs:"
echo "   journalctl -u $SERVICE_NAME -f"
echo ""

# Firewall configuration
if command -v ufw &> /dev/null; then
    echo "🔒 Configuring firewall..."
    ufw allow "$WEBHOOK_PORT/tcp" || true
    echo "✅ Firewall port $WEBHOOK_PORT opened"
elif command -v firewall-cmd &> /dev/null; then
    echo "🔒 Configuring firewall..."
    firewall-cmd --permanent --add-port="$WEBHOOK_PORT/tcp" || true
    firewall-cmd --reload || true
    echo "✅ Firewall port $WEBHOOK_PORT opened"
else
    echo "⚠️  No firewall management tool found"
    echo "   Manually open port $WEBHOOK_PORT if needed"
fi

echo ""
echo "Deployment directory: $INSTALL_DIR"
echo "Service: $SERVICE_NAME"
echo ""

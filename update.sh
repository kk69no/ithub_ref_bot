#!/bin/bash
# ═══════════════════════════════════════════════════════════════
#  ОБНОВЛЕНИЕ БОТА — после git push на GitHub
#
#  Тянет новый код из GitHub и перезапускает бота.
#
#  Использование (на сервере):
#    sudo /opt/ithub_ref_bot/update.sh
# ═══════════════════════════════════════════════════════════════

set -e

APP_DIR="/opt/ithub_ref_bot"
SERVICE_NAME="ithub-ref-bot"

echo "⏸  Останавливаю бота..."
systemctl stop "$SERVICE_NAME"

echo "📥 Тяну обновления из GitHub..."
cd "$APP_DIR"
git pull origin main

echo "📦 Обновляю зависимости..."
venv/bin/pip install -r requirements.txt -q

echo "🔑 Права..."
chown -R ithub_bot:ithub_bot "$APP_DIR"

echo "▶️  Запускаю бота..."
systemctl start "$SERVICE_NAME"

echo ""
echo "✅ Бот обновлён и перезапущен!"
systemctl status "$SERVICE_NAME" --no-pager

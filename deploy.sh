#!/bin/bash
# ═══════════════════════════════════════════════════════════════
#  ПЕРВЫЙ ДЕПЛОЙ — запускать один раз на новом VPS
#
#  Клонирует репо с GitHub, ставит зависимости, создаёт сервис.
#
#  Использование:
#    sudo bash deploy.sh https://github.com/YOUR_USER/ithub-ref-bot.git
# ═══════════════════════════════════════════════════════════════

set -e

REPO_URL="${1:?Укажите URL репозитория: sudo bash deploy.sh https://github.com/USER/REPO.git}"
APP_DIR="/opt/ithub_ref_bot"
APP_USER="ithub_bot"
SERVICE_NAME="ithub-ref-bot"

echo "══════════════════════════════════════════"
echo "  Первый деплой IThub Referral Bot"
echo "  Репозиторий: $REPO_URL"
echo "══════════════════════════════════════════"

# ─── 1. Системные пакеты ────────────────────────────────────
echo ""
echo "[1/6] Установка системных пакетов..."
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip git > /dev/null

# ─── 2. Пользователь ────────────────────────────────────────
echo "[2/6] Создание пользователя $APP_USER..."
if ! id "$APP_USER" &>/dev/null; then
    useradd --system --no-create-home --shell /bin/false "$APP_USER"
fi

# ─── 3. Клонировать репо ────────────────────────────────────
echo "[3/6] Клонирование из GitHub..."
if [ -d "$APP_DIR/.git" ]; then
    echo "  Репо уже склонировано, обновляю..."
    cd "$APP_DIR"
    git pull origin main
else
    rm -rf "$APP_DIR"
    git clone "$REPO_URL" "$APP_DIR"
fi

# ─── 4. Python venv + зависимости ───────────────────────────
echo "[4/6] Установка Python-зависимостей..."
cd "$APP_DIR"
python3 -m venv venv
venv/bin/pip install --upgrade pip -q
venv/bin/pip install -r requirements.txt -q

# ─── 5. Конфигурация .env ───────────────────────────────────
echo "[5/6] Настройка .env..."
if [ ! -f "$APP_DIR/.env" ]; then
    cp "$APP_DIR/.env.example" "$APP_DIR/.env"
    echo ""
    echo "  ⚠️  ВАЖНО! Заполните конфиг:"
    echo "     nano $APP_DIR/.env"
    echo ""
fi

# ─── 6. Systemd-сервис ─────────────────────────────────────
echo "[6/6] Создание systemd-сервиса..."
cat > /etc/systemd/system/${SERVICE_NAME}.service << EOF
[Unit]
Description=IThub Nalchik Referral Telegram Bot
After=network.target

[Service]
Type=simple
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$APP_DIR
EnvironmentFile=$APP_DIR/.env
ExecStart=$APP_DIR/venv/bin/python main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=$SERVICE_NAME

[Install]
WantedBy=multi-user.target
EOF

chown -R "$APP_USER":"$APP_USER" "$APP_DIR"
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"

echo ""
echo "══════════════════════════════════════════"
echo "  ✅ Деплой завершён!"
echo "══════════════════════════════════════════"
echo ""
echo "  Дальше:"
echo "  1. Заполнить .env:       nano $APP_DIR/.env"
echo "  2. Загрузить студентов:  sudo -u $APP_USER $APP_DIR/venv/bin/python $APP_DIR/load_students.py /path/to/students.csv"
echo "  3. Запустить бота:       sudo systemctl start $SERVICE_NAME"
echo "  4. Проверить:            sudo systemctl status $SERVICE_NAME"
echo "  5. Логи:                 sudo journalctl -u $SERVICE_NAME -f"
echo ""
echo "  После изменения кода — пуш на GitHub, потом на сервере:"
echo "     sudo $APP_DIR/update.sh"
echo ""

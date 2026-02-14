#!/bin/bash
#
# Pflug Law Lead Qualifier - Ubuntu Installation Script
# Run as root or with sudo
#

set -e

# Configuration
APP_NAME="pflug-qualifier"
APP_DIR="/opt/${APP_NAME}"
LOG_DIR="/var/log/${APP_NAME}"
SERVICE_USER="pflug"
PYTHON_VERSION="3.11"

echo "============================================"
echo "  Pflug Law Lead Qualifier Installation"
echo "============================================"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root or with sudo"
    exit 1
fi

# Check Ubuntu version
if ! grep -q "Ubuntu" /etc/os-release 2>/dev/null; then
    echo "Warning: This script is designed for Ubuntu. Proceed with caution."
fi

echo "[1/8] Installing system dependencies..."
apt-get update
apt-get install -y \
    python${PYTHON_VERSION} \
    python${PYTHON_VERSION}-venv \
    python3-pip \
    git \
    curl \
    jq

echo "[2/8] Creating service user..."
if ! id "${SERVICE_USER}" &>/dev/null; then
    useradd --system --shell /bin/false --home-dir ${APP_DIR} ${SERVICE_USER}
    echo "Created user: ${SERVICE_USER}"
else
    echo "User ${SERVICE_USER} already exists"
fi

echo "[3/8] Creating application directories..."
mkdir -p ${APP_DIR}
mkdir -p ${LOG_DIR}

echo "[4/8] Copying application files..."
# Copy application files (assumes script is run from project directory)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp -r ${SCRIPT_DIR}/src ${APP_DIR}/
cp -r ${SCRIPT_DIR}/templates ${APP_DIR}/
cp -r ${SCRIPT_DIR}/static ${APP_DIR}/ 2>/dev/null || mkdir -p ${APP_DIR}/static
cp -r ${SCRIPT_DIR}/tests ${APP_DIR}/
cp ${SCRIPT_DIR}/requirements.txt ${APP_DIR}/
cp ${SCRIPT_DIR}/.env.template ${APP_DIR}/

echo "[5/8] Setting up Python virtual environment..."
cd ${APP_DIR}
python${PYTHON_VERSION} -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "[6/8] Setting permissions..."
chown -R ${SERVICE_USER}:${SERVICE_USER} ${APP_DIR}
chown -R ${SERVICE_USER}:${SERVICE_USER} ${LOG_DIR}
chmod 755 ${APP_DIR}
chmod 755 ${LOG_DIR}

echo "[7/8] Installing systemd service..."
cat > /etc/systemd/system/${APP_NAME}.service << 'EOF'
[Unit]
Description=Pflug Law Lead Qualifier Service
After=network.target

[Service]
Type=simple
User=pflug
Group=pflug
WorkingDirectory=/opt/pflug-qualifier
Environment="PATH=/opt/pflug-qualifier/venv/bin"
EnvironmentFile=/opt/pflug-qualifier/.env
ExecStart=/opt/pflug-qualifier/venv/bin/python -m src.main
Restart=always
RestartSec=10

# Security hardening
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/log/pflug-qualifier /opt/pflug-qualifier
PrivateTmp=true

# Logging
StandardOutput=append:/var/log/pflug-qualifier/service.log
StandardError=append:/var/log/pflug-qualifier/error.log

[Install]
WantedBy=multi-user.target
EOF

# Install dashboard service
cat > /etc/systemd/system/${APP_NAME}-dashboard.service << 'EOF'
[Unit]
Description=Pflug Law Lead Qualifier Dashboard
After=network.target pflug-qualifier.service

[Service]
Type=simple
User=pflug
Group=pflug
WorkingDirectory=/opt/pflug-qualifier
Environment="PATH=/opt/pflug-qualifier/venv/bin"
EnvironmentFile=/opt/pflug-qualifier/.env
ExecStart=/opt/pflug-qualifier/venv/bin/python -m src.dashboard
Restart=always
RestartSec=10

# Security hardening
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/log/pflug-qualifier /opt/pflug-qualifier
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload

echo "[8/8] Installation complete!"
echo ""
echo "============================================"
echo "  Next Steps:"
echo "============================================"
echo ""
echo "1. Copy your environment file:"
echo "   cp ${APP_DIR}/.env.template ${APP_DIR}/.env"
echo ""
echo "2. Edit the .env file with your API keys:"
echo "   nano ${APP_DIR}/.env"
echo ""
echo "3. Set up Gmail credentials:"
echo "   - Place gmail_credentials.json in ${APP_DIR}/"
echo "   - Run the auth flow once: "
echo "     cd ${APP_DIR} && sudo -u ${SERVICE_USER} ./venv/bin/python -c 'from src.email_handler import EmailHandler; from src.config import EmailConfig; e = EmailHandler(EmailConfig()); e.test_connection()'"
echo ""
echo "4. Test the configuration:"
echo "   cd ${APP_DIR}"
echo "   sudo -u ${SERVICE_USER} ./venv/bin/python -m tests.test_connection"
echo ""
echo "5. Start the services:"
echo "   systemctl enable ${APP_NAME}"
echo "   systemctl enable ${APP_NAME}-dashboard"
echo "   systemctl start ${APP_NAME}"
echo "   systemctl start ${APP_NAME}-dashboard"
echo ""
echo "6. Check status:"
echo "   systemctl status ${APP_NAME}"
echo "   journalctl -u ${APP_NAME} -f"
echo ""
echo "7. Access dashboard:"
echo "   http://localhost:8080"
echo ""
echo "============================================"

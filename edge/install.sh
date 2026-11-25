#!/usr/bin/env bash
set -e

echo "=== Installing Smart Door Edge Service on Raspberry Pi ==="
INSTALL_DIR="/opt/smart-door"
SERVICE_FILE="edge/smart-door.service"

sudo mkdir -p $INSTALL_DIR
sudo cp -r edge $INSTALL_DIR/

if [ ! -d "$INSTALL_DIR/venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv $INSTALL_DIR/venv
fi

echo "Installing requirements..."
$INSTALL_DIR/venv/bin/pip install --upgrade pip
$INSTALL_DIR/venv/bin/pip install -r $INSTALL_DIR/edge/requirements.txt

if [ ! -f "$INSTALL_DIR/edge/.env" ]; then
    echo "Copying .env.example to .env..."
    cp $INSTALL_DIR/edge/.env.example $INSTALL_DIR/edge/.env
fi

echo "Installing systemd unit..."
sudo cp $SERVICE_FILE /etc/systemd/system/smart-door.service
sudo systemctl daemon-reload
sudo systemctl enable smart-door.service
sudo systemctl restart smart-door.service

echo "Smart Door Edge service installed and running!"
sudo systemctl status smart-door.service --no-pager

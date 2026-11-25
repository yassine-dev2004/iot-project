#!/usr/bin/env bash
# One-command VPS installer for Ubuntu 24.04 LTS (Sentinel Home Sync Hub)
set -e

echo "=== Installing Sentinel Home Cloud Hub on Ubuntu 24.04 ==="
sudo apt-get update -y
sudo apt-get install -y python3 python3-venv python3-pip ufw

mkdir -p /opt/sentinel-home
cd /opt/sentinel-home

python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install fastapi uvicorn python-multipart

# Open Firewall Port 8080 (Web Dashboard, 3D Twin, Mobile API, APK download)
sudo ufw allow 22/tcp || true
sudo ufw allow 8080/tcp || true
sudo ufw allow 1883/tcp || true

# Create systemd service so Hub stays online 24/7
sudo tee /etc/systemd/system/sentinel-hub.service > /dev/null <<'EOF'
[Unit]
Description=Sentinel Home VPS Sync Hub
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/sentinel-home
ExecStart=/opt/sentinel-home/venv/bin/python -m uvicorn vps_hub:app --host 0.0.0.0 --port 8080
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable sentinel-hub
sudo systemctl restart sentinel-hub

IP=$(curl -s ifconfig.me || hostname -I | awk '{print $1}')
echo ""
echo "=========================================================="
echo "  SENTINEL HOME VPS HUB IS LIVE!"
echo "  Web Dashboard : http://${IP}:8080/web/index.html"
echo "  3D Twin       : http://${IP}:8080/sim/index.html"
echo "  Android APK   : http://${IP}:8080/SentinelHome.apk"
echo "=========================================================="

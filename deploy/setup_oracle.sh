#!/bin/bash
# ============================================================
#  AXENORA AI — Oracle Cloud VM Setup Script
#  Run this on a fresh Ubuntu/Oracle Linux ARM or AMD instance
# ============================================================
set -e

echo "============================================"
echo "  AXENORA AI — Oracle Cloud Setup"
echo "============================================"

# 1. System updates
echo "[1/6] Updating system packages..."
sudo apt-get update && sudo apt-get upgrade -y

# 2. Install Python 3.11+ and dependencies
echo "[2/6] Installing Python and system dependencies..."
sudo apt-get install -y \
    python3 python3-pip python3-venv \
    git wget curl \
    fonts-liberation fonts-noto-color-emoji \
    libasound2 libatk-bridge2.0-0 libatk1.0-0 \
    libcairo2 libcups2 libdbus-1-3 libdrm2 libgbm1 \
    libglib2.0-0 libgtk-3-0 libnspr4 libnss3 \
    libpango-1.0-0 libx11-6 libxcb1 libxcomposite1 \
    libxdamage1 libxext6 libxfixes3 libxkbcommon0 \
    libxrandr2 xdg-utils libvulkan1

# 3. Clone the repo
echo "[3/6] Cloning campaign repo..."
cd /home/ubuntu
if [ -d "campaign" ]; then
    echo "  Repo already exists, pulling latest..."
    cd campaign && git pull
else
    git clone https://github.com/kaarthikarorasahabji/campaign.git
    cd campaign
fi

# 4. Set up Python virtual environment
echo "[4/6] Setting up Python environment..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install playwright
playwright install chromium

# 5. Copy settings if not exists
echo "[5/6] Setting up configuration..."
if [ ! -f "config/settings.yaml" ]; then
    if [ -f "config/settings.yaml.example" ]; then
        cp config/settings.yaml.example config/settings.yaml
        echo "  ⚠️  IMPORTANT: Edit config/settings.yaml with your Gmail credentials!"
    fi
fi

# Create data directory
mkdir -p data

# 6. Install systemd service
echo "[6/6] Installing systemd service..."
sudo cp deploy/campaign.service /etc/systemd/system/campaign.service
sudo systemctl daemon-reload
sudo systemctl enable campaign
sudo systemctl start campaign

echo ""
echo "============================================"
echo "  ✅ Setup Complete!"
echo "============================================"
echo ""
echo "  Useful commands:"
echo "    sudo systemctl status campaign    # Check status"
echo "    sudo journalctl -u campaign -f    # View live logs"
echo "    sudo systemctl restart campaign   # Restart"
echo "    sudo systemctl stop campaign      # Stop"
echo ""
echo "  ⚠️  Make sure to edit config/settings.yaml"
echo "     with your Gmail credentials and Resend API key!"
echo ""

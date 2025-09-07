#!/bin/bash

# Pi-Power-Butler Service Setup Script
# This script sets up the bot as a systemd service

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Pi-Power-Butler Service Setup${NC}"
echo "=================================="

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo -e "${RED}Please don't run this script as root. Run as your normal user.${NC}"
    exit 1
fi

# Get current directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_FILE="$SCRIPT_DIR/pi-power-butler.service"
SYSTEMD_DIR="$HOME/.config/systemd/user"

echo "Setting up service from: $SCRIPT_DIR"

# Create systemd user directory
mkdir -p "$SYSTEMD_DIR"

# Update service file with correct paths
echo "Updating service file with correct paths..."
sed "s|/home/pi/pi-power-butler|$SCRIPT_DIR|g" "$SERVICE_FILE" > "$SYSTEMD_DIR/pi-power-butler.service"

# Reload systemd
echo "Reloading systemd..."
systemctl --user daemon-reload

# Enable the service
echo "Enabling service..."
systemctl --user enable pi-power-butler.service

echo ""
echo -e "${GREEN}Service setup complete!${NC}"
echo ""
echo "Available commands:"
echo "  Start service:    systemctl --user start pi-power-butler"
echo "  Stop service:     systemctl --user stop pi-power-butler"
echo "  Restart service:  systemctl --user restart pi-power-butler"
echo "  Check status:     systemctl --user status pi-power-butler"
echo "  View logs:        journalctl --user -u pi-power-butler -f"
echo ""
echo "To start the service now:"
echo "  systemctl --user start pi-power-butler"
echo ""
echo -e "${YELLOW}Note: The service will start automatically on boot.${NC}"

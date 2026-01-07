#!/usr/bin/env bash
# ============================================================================
# PANDA.1 v2.0 - Autostart Setup
# ============================================================================
# Configures PANDA.1 to start automatically on PC boot.
# Creates systemd user service and optional desktop autostart.
#
# Usage: ./setup_autostart.sh [--enable|--disable|--status]
# ============================================================================

set -e

PANDA_HOME="${HOME}/.panda1"
SERVICE_NAME="panda1"
SERVICE_FILE="${HOME}/.config/systemd/user/${SERVICE_NAME}.service"
DESKTOP_FILE="${HOME}/.config/autostart/panda1-kiosk.desktop"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

show_usage() {
    echo ""
    echo "Usage: $0 [--enable|--disable|--status]"
    echo ""
    echo "Options:"
    echo "  --enable   Enable autostart on boot"
    echo "  --disable  Disable autostart"
    echo "  --status   Show current autostart status"
    echo ""
}

show_status() {
    echo ""
    echo "=============================================="
    echo "  PANDA.1 Autostart Status"
    echo "=============================================="
    echo ""
    
    # Check systemd service
    if systemctl --user is-enabled "${SERVICE_NAME}" &> /dev/null; then
        echo -e "  Systemd Service: ${GREEN}ENABLED${NC}"
    else
        echo -e "  Systemd Service: ${YELLOW}DISABLED${NC}"
    fi
    
    if systemctl --user is-active "${SERVICE_NAME}" &> /dev/null; then
        echo -e "  Service Status:  ${GREEN}RUNNING${NC}"
    else
        echo -e "  Service Status:  ${YELLOW}STOPPED${NC}"
    fi
    
    # Check desktop autostart
    if [[ -f "${DESKTOP_FILE}" ]]; then
        echo -e "  Kiosk Autostart: ${GREEN}ENABLED${NC}"
    else
        echo -e "  Kiosk Autostart: ${YELLOW}DISABLED${NC}"
    fi
    
    echo ""
}

enable_autostart() {
    echo ""
    echo "=============================================="
    echo "  Enabling PANDA.1 Autostart"
    echo "=============================================="
    echo ""
    
    # Create systemd user directory
    mkdir -p "${HOME}/.config/systemd/user"
    
    # Copy service file
    cat > "${SERVICE_FILE}" << 'EOF'
[Unit]
Description=PANDA.1 AI Assistant Backend
After=network.target

[Service]
Type=simple
WorkingDirectory=%h/.panda1
Environment="PATH=%h/.panda1/venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=%h/.panda1/venv/bin/python -m app.main --gui
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF
    
    # Reload and enable
    systemctl --user daemon-reload
    systemctl --user enable "${SERVICE_NAME}"
    
    echo -e "${GREEN}✅ Systemd service enabled${NC}"
    
    # Ask about kiosk autostart
    echo ""
    read -p "Enable kiosk mode on login (fullscreen browser)? [y/N] " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        mkdir -p "${HOME}/.config/autostart"
        
        cat > "${DESKTOP_FILE}" << EOF
[Desktop Entry]
Type=Application
Name=PANDA.1 Kiosk
Comment=PANDA.1 AI Assistant Kiosk Mode
Exec=${PANDA_HOME}/scripts/kiosk.sh --no-backend
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
X-GNOME-Autostart-Delay=5
EOF
        
        echo -e "${GREEN}✅ Kiosk autostart enabled${NC}"
    fi
    
    echo ""
    echo "Autostart configured!"
    echo ""
    echo "To start now without rebooting:"
    echo "  systemctl --user start ${SERVICE_NAME}"
    echo ""
    echo "To view logs:"
    echo "  journalctl --user -u ${SERVICE_NAME} -f"
    echo ""
}

disable_autostart() {
    echo ""
    echo "=============================================="
    echo "  Disabling PANDA.1 Autostart"
    echo "=============================================="
    echo ""
    
    # Stop and disable service
    systemctl --user stop "${SERVICE_NAME}" 2>/dev/null || true
    systemctl --user disable "${SERVICE_NAME}" 2>/dev/null || true
    rm -f "${SERVICE_FILE}"
    
    echo -e "${GREEN}✅ Systemd service disabled${NC}"
    
    # Remove desktop autostart
    if [[ -f "${DESKTOP_FILE}" ]]; then
        rm -f "${DESKTOP_FILE}"
        echo -e "${GREEN}✅ Kiosk autostart disabled${NC}"
    fi
    
    systemctl --user daemon-reload
    
    echo ""
    echo "Autostart disabled."
    echo ""
}

# Main
case "${1:-}" in
    --enable)
        enable_autostart
        ;;
    --disable)
        disable_autostart
        ;;
    --status)
        show_status
        ;;
    *)
        show_usage
        show_status
        ;;
esac

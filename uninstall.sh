#!/usr/bin/env bash
# =============================================================================
# PANDA.1 Uninstaller
# =============================================================================
# Completely removes PANDA.1 from your system
# =============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# Configuration
PANDA_HOME="${HOME}/.panda1"
BIN_DIR="${HOME}/.local/bin"
DESKTOP_DIR="${HOME}/Desktop"
AUTOSTART_DIR="${HOME}/.config/autostart"
APPS_DIR="${HOME}/.local/share/applications"

# Print banner
echo -e "${CYAN}"
echo "  ╔═══════════════════════════════════════════════════════════════╗"
echo "  ║              PANDA.1 Uninstaller                              ║"
echo "  ╚═══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Confirm
echo -e "${YELLOW}This will remove PANDA.1 and all its data from your system.${NC}"
echo ""
read -p "Are you sure you want to continue? [y/N] " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${BLUE}Uninstall cancelled.${NC}"
    exit 0
fi

echo ""

# Stop any running processes
echo -e "${BLUE}Stopping PANDA.1 processes...${NC}"
pkill -f "python.*app.web_gui" 2>/dev/null || true
pkill -f "python.*app.main" 2>/dev/null || true
pkill -f "pandagui" 2>/dev/null || true
sleep 1

# Remove installation directory
if [[ -d "${PANDA_HOME}" ]]; then
    echo -e "${BLUE}Removing ${PANDA_HOME}...${NC}"
    rm -rf "${PANDA_HOME}"
    echo -e "${GREEN}✓ Installation directory removed${NC}"
else
    echo -e "${YELLOW}Installation directory not found${NC}"
fi

# Remove launcher
if [[ -f "${BIN_DIR}/panda" ]]; then
    echo -e "${BLUE}Removing launcher...${NC}"
    rm -f "${BIN_DIR}/panda"
    echo -e "${GREEN}✓ Launcher removed${NC}"
fi

# Remove desktop entries
echo -e "${BLUE}Removing desktop entries...${NC}"

if [[ -f "${DESKTOP_DIR}/PANDA1-GUI.desktop" ]]; then
    rm -f "${DESKTOP_DIR}/PANDA1-GUI.desktop"
    echo -e "${GREEN}✓ Desktop shortcut removed${NC}"
fi

if [[ -f "${APPS_DIR}/panda1-gui.desktop" ]]; then
    rm -f "${APPS_DIR}/panda1-gui.desktop"
    echo -e "${GREEN}✓ Applications menu entry removed${NC}"
fi

# Remove autostart
if [[ -f "${AUTOSTART_DIR}/panda1-gui.desktop" ]]; then
    rm -f "${AUTOSTART_DIR}/panda1-gui.desktop"
    echo -e "${GREEN}✓ Autostart entry removed${NC}"
fi

# Optional: Remove Ollama model
echo ""
read -p "Remove the 'panda1' Ollama model? [y/N] " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    if command -v ollama &> /dev/null; then
        ollama rm panda1 2>/dev/null || true
        echo -e "${GREEN}✓ Ollama model removed${NC}"
    else
        echo -e "${YELLOW}Ollama not found${NC}"
    fi
fi

echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║           PANDA.1 has been uninstalled successfully!          ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}Thank you for using PANDA.1! 🐼${NC}"
echo ""

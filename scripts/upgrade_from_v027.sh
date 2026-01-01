#!/usr/bin/env bash
# =============================================================================
# PANDA.1 v0.2.7 → v0.2.8 Upgrade Script
# =============================================================================
# Applies v0.2.8 fixes to an existing v0.2.7 installation.
# Run from the extracted panda1_v0.2.8 directory.
# =============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

PANDA_HOME="${HOME}/.panda1"
ENV_FILE="${PANDA_HOME}/.env"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_DIR="$(dirname "${SCRIPT_DIR}")"

echo -e "${CYAN}"
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║  PANDA.1 v0.2.7 → v0.2.8 Upgrade                             ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Check if PANDA_HOME exists
if [[ ! -d "${PANDA_HOME}" ]]; then
    echo -e "${RED}✗ PANDA.1 not installed at ${PANDA_HOME}${NC}"
    echo "  Run install.sh first."
    exit 1
fi

# Check if source directory has v0.2.8 files
if [[ ! -f "${SOURCE_DIR}/app/web_gui.py" ]]; then
    echo -e "${RED}✗ Source files not found${NC}"
    echo "  Run this script from the panda1_v0.2.8/scripts directory"
    exit 1
fi

echo "Source: ${SOURCE_DIR}"
echo "Target: ${PANDA_HOME}"
echo ""

# Step 1: Backup current app directory
echo -e "${YELLOW}1. Creating backup...${NC}"
if [[ -d "${PANDA_HOME}/app" ]]; then
    BACKUP_NAME="app_backup_$(date +%Y%m%d_%H%M%S)"
    cp -r "${PANDA_HOME}/app" "${PANDA_HOME}/${BACKUP_NAME}"
    echo -e "   ${GREEN}✓${NC} Backed up to ${PANDA_HOME}/${BACKUP_NAME}"
fi

# Step 2: Copy new app files
echo -e "${YELLOW}2. Updating app files...${NC}"
rm -rf "${PANDA_HOME}/app"
cp -r "${SOURCE_DIR}/app" "${PANDA_HOME}/app"
echo -e "   ${GREEN}✓${NC} App files updated"

# Step 3: Update .env with new v0.2.8 variables
echo -e "${YELLOW}3. Updating configuration...${NC}"
if [[ -f "${ENV_FILE}" ]]; then
    # Check if v0.2.8 variables already exist
    if ! grep -q "PANDA_GUI_VOICE_ENABLED" "${ENV_FILE}"; then
        echo "" >> "${ENV_FILE}"
        echo "# v0.2.8 - GUI Voice Integration" >> "${ENV_FILE}"
        echo "PANDA_GUI_VOICE_ENABLED=true" >> "${ENV_FILE}"
        echo "PANDA_VOICE_ACK_ENABLED=true" >> "${ENV_FILE}"
        echo "# PANDA_AUDIO_INPUT_DEVICE=0  # Uncomment and set device index" >> "${ENV_FILE}"
        echo "PANDA_SCOTT_RETRY_INTERVAL=60" >> "${ENV_FILE}"
        echo -e "   ${GREEN}✓${NC} Added v0.2.8 environment variables"
    else
        echo -e "   ${GREEN}✓${NC} v0.2.8 variables already present"
    fi
else
    echo -e "   ${YELLOW}⚠${NC} No .env file found, copying template"
    cp "${SOURCE_DIR}/.env.template" "${ENV_FILE}"
fi

# Step 4: Copy updated scripts
echo -e "${YELLOW}4. Updating scripts...${NC}"
cp "${SOURCE_DIR}/pandagui" "${PANDA_HOME}/pandagui"
chmod +x "${PANDA_HOME}/pandagui"
cp -r "${SOURCE_DIR}/scripts" "${PANDA_HOME}/scripts"
echo -e "   ${GREEN}✓${NC} Scripts updated"

# Step 5: Copy tests
echo -e "${YELLOW}5. Installing tests...${NC}"
mkdir -p "${PANDA_HOME}/tests"
cp -r "${SOURCE_DIR}/tests/"* "${PANDA_HOME}/tests/" 2>/dev/null || true
echo -e "   ${GREEN}✓${NC} Tests installed"

# Step 6: Update documentation
echo -e "${YELLOW}6. Updating documentation...${NC}"
cp "${SOURCE_DIR}/README.md" "${PANDA_HOME}/README.md"
cp "${SOURCE_DIR}/CHANGELOG.md" "${PANDA_HOME}/CHANGELOG.md"
cp -r "${SOURCE_DIR}/docs" "${PANDA_HOME}/docs"
echo -e "   ${GREEN}✓${NC} Documentation updated"

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  ✓ Upgrade to v0.2.8 complete!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo ""
echo "What's new in v0.2.8:"
echo "  • GUI voice wake ('Hey Panda') now works in web UI"
echo "  • Fixed chat bubble merging (message_id correlation)"
echo "  • Fixed Action Log 422 errors"
echo "  • Fixed language toggle WebSocket crash"
echo "  • New commands: panda --gui-doctor, panda --mic-test"
echo "  • Enhanced: panda --audio-devices (shows INPUT devices)"
echo ""
echo "Verify with:"
echo "  panda --gui-doctor"
echo "  panda --audio-devices"
echo "  panda --mic-test"
echo ""
echo "Then start GUI:"
echo "  panda"

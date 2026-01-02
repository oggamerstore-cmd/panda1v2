#!/bin/bash
# =============================================================================
# PANDA.1 v0.2.10 Installer
# =============================================================================
# Installs PANDA.1 to ~/.panda1/ with all dependencies
# =============================================================================

set -e

VERSION="0.2.10"
PANDA_HOME="${HOME}/.panda1"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_header() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  🐼 PANDA.1 v${VERSION} Installer${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

print_step() {
    echo -e "${YELLOW}▶ $1${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

check_python() {
    print_step "Checking Python..."
    
    if command -v python3 &> /dev/null; then
        PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
        PY_MAJOR=$(echo $PY_VERSION | cut -d. -f1)
        PY_MINOR=$(echo $PY_VERSION | cut -d. -f2)
        
        if [ "$PY_MAJOR" -ge 3 ] && [ "$PY_MINOR" -ge 11 ]; then
            print_success "Python $PY_VERSION found"
            PYTHON=python3
        else
            print_error "Python 3.11+ required, found $PY_VERSION"
            exit 1
        fi
    else
        print_error "Python 3 not found. Please install Python 3.11+"
        exit 1
    fi
}

check_system_deps() {
    print_step "Checking system dependencies..."
    
    MISSING_DEPS=""
    
    # Check for portaudio
    if ! dpkg -l | grep -q libportaudio2; then
        MISSING_DEPS="$MISSING_DEPS portaudio19-dev"
    fi
    
    # Check for ffmpeg
    if ! command -v ffmpeg &> /dev/null; then
        MISSING_DEPS="$MISSING_DEPS ffmpeg"
    fi
    
    # Check for alsa-utils
    if ! command -v aplay &> /dev/null; then
        MISSING_DEPS="$MISSING_DEPS alsa-utils"
    fi
    
    # Check for espeak-ng (required for Kokoro TTS)
    if ! command -v espeak-ng &> /dev/null; then
        MISSING_DEPS="$MISSING_DEPS espeak-ng"
    fi
    
    if [ -n "$MISSING_DEPS" ]; then
        print_warning "Missing system packages:$MISSING_DEPS"
        echo ""
        read -p "Install them now? (requires sudo) [Y/n] " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Nn]$ ]]; then
            sudo apt-get update
            sudo apt-get install -y $MISSING_DEPS
            print_success "System dependencies installed"
        else
            print_warning "Skipping system deps. Audio may not work."
        fi
    else
        print_success "System dependencies OK"
    fi
}

create_directories() {
    print_step "Creating directories..."
    
    mkdir -p "${PANDA_HOME}"
    mkdir -p "${PANDA_HOME}/logs"
    mkdir -p "${PANDA_HOME}/cache/voice"
    mkdir -p "${PANDA_HOME}/cache/whisper"
    mkdir -p "${PANDA_HOME}/cache/kokoro"
    mkdir -p "${PANDA_HOME}/files"
    mkdir -p "${PANDA_HOME}/audio_in"
    mkdir -p "${PANDA_HOME}/audio_out"
    mkdir -p "${PANDA_HOME}/certs"
    mkdir -p "${PANDA_HOME}/db"
    
    print_success "Directories created"
}

create_venv() {
    print_step "Creating Python virtual environment..."
    
    if [ -d "${PANDA_HOME}/venv" ]; then
        print_warning "Existing venv found, recreating..."
        rm -rf "${PANDA_HOME}/venv"
    fi
    
    $PYTHON -m venv "${PANDA_HOME}/venv"
    source "${PANDA_HOME}/venv/bin/activate"
    
    # Upgrade pip
    pip install --upgrade pip wheel setuptools
    
    print_success "Virtual environment created"
}

install_python_deps() {
    print_step "Installing Python packages..."
    
    source "${PANDA_HOME}/venv/bin/activate"
    
    # Install from requirements.txt
    pip install -r "${SCRIPT_DIR}/requirements.txt"
    
    print_success "Python packages installed"
}

copy_files() {
    print_step "Installing PANDA.1 files..."
    
    # Create version directory (remove existing first to avoid permission issues)
    VERSION_DIR="${PANDA_HOME}/panda1_v${VERSION}"
    if [ -d "${VERSION_DIR}" ]; then
        print_warning "Removing existing v${VERSION} installation..."
        rm -rf "${VERSION_DIR}"
    fi
    mkdir -p "${VERSION_DIR}"
    
    # Copy app files
    cp -r "${SCRIPT_DIR}/app" "${VERSION_DIR}/"
    
    # Copy other directories if they exist
    [ -d "${SCRIPT_DIR}/intents" ] && cp -r "${SCRIPT_DIR}/intents" "${VERSION_DIR}/"
    [ -d "${SCRIPT_DIR}/modelfiles" ] && cp -r "${SCRIPT_DIR}/modelfiles" "${VERSION_DIR}/"
    [ -d "${SCRIPT_DIR}/scripts" ] && cp -r "${SCRIPT_DIR}/scripts" "${VERSION_DIR}/"
    [ -d "${SCRIPT_DIR}/tests" ] && cp -r "${SCRIPT_DIR}/tests" "${VERSION_DIR}/"
    [ -d "${SCRIPT_DIR}/tools" ] && cp -r "${SCRIPT_DIR}/tools" "${VERSION_DIR}/"
    [ -d "${SCRIPT_DIR}/docs" ] && cp -r "${SCRIPT_DIR}/docs" "${VERSION_DIR}/"
    
    # Copy documentation
    [ -f "${SCRIPT_DIR}/README.md" ] && cp "${SCRIPT_DIR}/README.md" "${VERSION_DIR}/"
    [ -f "${SCRIPT_DIR}/CHANGELOG.md" ] && cp "${SCRIPT_DIR}/CHANGELOG.md" "${VERSION_DIR}/"
    
    # Create symlink to current version (handle both symlink and directory)
    if [ -L "${PANDA_HOME}/app" ]; then
        rm -f "${PANDA_HOME}/app"
    elif [ -d "${PANDA_HOME}/app" ]; then
        rm -rf "${PANDA_HOME}/app"
    fi
    ln -s "${VERSION_DIR}/app" "${PANDA_HOME}/app"
    
    print_success "PANDA.1 files installed to ${VERSION_DIR}"
}

create_env_file() {
    print_step "Creating environment configuration..."

    if [ -f "${PANDA_HOME}/.env" ]; then
        print_warning ".env already exists, keeping existing"
    else
        if [ -f "${SCRIPT_DIR}/.env.template" ]; then
            cp "${SCRIPT_DIR}/.env.template" "${PANDA_HOME}/.env"
            print_success ".env created from template"
        else
            # Create minimal .env if template is missing
            cat > "${PANDA_HOME}/.env" << 'ENV_EOF'
# PANDA.1 Configuration
# See documentation for full options

# Ollama
PANDA_OLLAMA_HOST=http://localhost:11434
PANDA_LLM_MODEL=panda1:latest
PANDA_LLM_MAX_TOKENS=4096
PANDA_LLM_CONTEXT_LENGTH=8192

# Voice
PANDA_VOICE_ENABLED=true
PANDA_TTS_ENGINE=kokoro
PANDA_STT_ENGINE=faster-whisper

# Web GUI
PANDA_GUI_HOST=0.0.0.0
PANDA_GUI_PORT=7860
ENV_EOF
            print_warning ".env.template not found, created minimal .env"
            print_warning "Edit ~/.panda1/.env to add full configuration"
        fi
    fi
}

install_echo() {
    if [ -f "${SCRIPT_DIR}/install_echo.sh" ]; then
        print_step "Installing ECHO context hub..."
        PANDA_HOME="${PANDA_HOME}" bash "${SCRIPT_DIR}/install_echo.sh"
        print_success "ECHO context hub installed"
    else
        print_warning "install_echo.sh not found; skipping ECHO install"
    fi
}

install_launcher() {
    print_step "Installing launcher script..."
    
    LAUNCHER="${PANDA_HOME}/panda"
    
    cat > "${LAUNCHER}" << 'LAUNCHER_EOF'
#!/bin/bash
# PANDA.1 Launcher
PANDA_HOME="${HOME}/.panda1"
source "${PANDA_HOME}/venv/bin/activate"
cd "${PANDA_HOME}"
export PYTHONPATH="${PANDA_HOME}"
python -m app.main "$@"
LAUNCHER_EOF
    
    chmod +x "${LAUNCHER}"
    
    # Create symlink in ~/.local/bin if it exists
    if [ -d "${HOME}/.local/bin" ]; then
        ln -sf "${LAUNCHER}" "${HOME}/.local/bin/panda"
        print_success "Launcher installed (panda command available)"
    else
        print_warning "~/.local/bin not found. Add ${PANDA_HOME}/panda to PATH"
    fi
}

create_systemd_service() {
    print_step "Creating systemd service (optional)..."
    
    SERVICE_DIR="${HOME}/.config/systemd/user"
    mkdir -p "${SERVICE_DIR}"
    
    cat > "${SERVICE_DIR}/panda1.service" << EOF
[Unit]
Description=PANDA.1 AI Assistant
After=network.target

[Service]
Type=simple
WorkingDirectory=${PANDA_HOME}
ExecStart=${PANDA_HOME}/venv/bin/python -m app.main --gui
Restart=on-failure
RestartSec=5
Environment=PYTHONPATH=${PANDA_HOME}

[Install]
WantedBy=default.target
EOF
    
    print_success "Systemd service created (use: systemctl --user enable panda1)"
}

create_desktop_autostart() {
    print_step "Creating desktop autostart entry..."
    
    AUTOSTART_DIR="${HOME}/.config/autostart"
    mkdir -p "${AUTOSTART_DIR}"
    
    cat > "${AUTOSTART_DIR}/panda1-kiosk.desktop" << EOF
[Desktop Entry]
Type=Application
Name=PANDA.1 Kiosk
Comment=Start PANDA.1 in kiosk mode
Exec=${PANDA_HOME}/scripts/kiosk_start.sh
Terminal=false
X-GNOME-Autostart-enabled=false
EOF
    
    print_success "Autostart entry created (disabled by default)"
}

create_desktop_shortcut() {
    print_step "Creating desktop shortcut..."
    
    DESKTOP_DIR="${HOME}/Desktop"
    if [ ! -d "${DESKTOP_DIR}" ]; then
        DESKTOP_DIR="${HOME}/desktop"
    fi
    
    if [ -d "${DESKTOP_DIR}" ]; then
        SHORTCUT="${DESKTOP_DIR}/PANDA1.desktop"
        
        cat > "${SHORTCUT}" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=PANDA.1
Comment=Personal AI Navigator & Digital Assistant
Exec=${PANDA_HOME}/panda --gui
Icon=utilities-terminal
Terminal=false
Categories=Utility;Application;
StartupNotify=true
EOF
        
        chmod +x "${SHORTCUT}"
        
        # Mark as trusted on GNOME
        if command -v gio &> /dev/null; then
            gio set "${SHORTCUT}" metadata::trusted true 2>/dev/null || true
        fi
        
        print_success "Desktop shortcut created"
    else
        print_warning "Desktop folder not found, skipping shortcut"
    fi
}

print_summary() {
    # Get local IP
    LOCAL_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "192.168.1.17")
    
    echo ""
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}  ✅ PANDA.1 v${VERSION} Installation Complete!${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo -e "  ${BLUE}Installation directory:${NC} ${PANDA_HOME}"
    echo ""
    echo -e "  ${YELLOW}Access PANDA.1:${NC}"
    echo "    Local:    http://127.0.0.1:7860"
    echo "    LAN:      http://${LOCAL_IP}:7860"
    echo "    Desktop:  Double-click PANDA1 icon"
    echo ""
    echo -e "  ${YELLOW}Quick Start:${NC}"
    echo "    1. Edit your configuration:  nano ~/.panda1/.env"
    echo "    2. Start PANDA:              panda --gui"
    echo "    3. Or run diagnostics:       panda --voice-doctor"
    echo ""
    echo -e "  ${YELLOW}Available Commands:${NC}"
    echo "    panda --gui            Start web GUI"
    echo "    panda --gui-doctor     GUI diagnostics"
    echo "    panda --voice-doctor   Voice system check"
    echo "    panda --scott-doctor   SCOTT connection check"
    echo "    panda --mic-test       Test microphone"
    echo "    panda --help           Show all options"
    echo ""
    echo -e "  ${YELLOW}Configuration:${NC}"
    echo "    Edit ~/.panda1/.env to configure:"
    echo "    - SCOTT_BASE_URL and SCOTT_API_KEY for news"
    echo "    - OPENAI_API_KEY for GPT-4 fallback (optional)"
    echo "    - Audio device settings"
    echo ""
}

# Main installation
print_header
check_python
check_system_deps
create_directories
create_venv
install_python_deps
copy_files
create_env_file
install_echo
install_launcher
create_desktop_shortcut
create_systemd_service
create_desktop_autostart
print_summary

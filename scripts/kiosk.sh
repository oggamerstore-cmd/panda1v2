#!/usr/bin/env bash
# ============================================================================
# PANDA.1 v0.2.10 - Kiosk Mode Launcher
# ============================================================================
# Launches PANDA.1 GUI in fullscreen kiosk mode.
# Used for desktop autostart or manual kiosk launch.
#
# Usage: ./kiosk.sh [--no-backend]
# ============================================================================

set -e

PANDA_HOME="${HOME}/.panda1"
GUI_HOST="${PANDA_GUI_HOST:-127.0.0.1}"
GUI_PORT="${PANDA_GUI_PORT:-7860}"
HTTPS_PORT="${PANDA_HTTPS_PORT:-7861}"
ENABLE_HTTPS="${PANDA_ENABLE_HTTPS:-false}"

# Determine URL
if [[ "${ENABLE_HTTPS}" == "true" || "${ENABLE_HTTPS}" == "1" ]]; then
    GUI_URL="https://${GUI_HOST}:${HTTPS_PORT}"
else
    GUI_URL="http://${GUI_HOST}:${GUI_PORT}"
fi

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo ""
echo "=============================================="
echo "  PANDA.1 Kiosk Mode"
echo "=============================================="
echo ""

# Start backend if not --no-backend
if [[ "$1" != "--no-backend" ]]; then
    echo "Starting PANDA.1 backend..."
    
    # Check if already running
    if pgrep -f "python.*app.main.*--gui" > /dev/null; then
        echo -e "${YELLOW}Backend already running${NC}"
    else
        cd "${PANDA_HOME}"
        source venv/bin/activate
        nohup python -m app.main --gui > /dev/null 2>&1 &
        
        # Wait for backend to start
        echo -n "Waiting for backend"
        for i in {1..30}; do
            if curl -s "${GUI_URL}" > /dev/null 2>&1; then
                echo ""
                echo -e "${GREEN}✅ Backend ready${NC}"
                break
            fi
            echo -n "."
            sleep 1
        done
        echo ""
    fi
fi

echo "Launching browser in kiosk mode..."
echo "URL: ${GUI_URL}"
echo ""

# Detect and launch browser
if command -v chromium-browser &> /dev/null; then
    BROWSER="chromium-browser"
elif command -v chromium &> /dev/null; then
    BROWSER="chromium"
elif command -v google-chrome &> /dev/null; then
    BROWSER="google-chrome"
elif command -v google-chrome-stable &> /dev/null; then
    BROWSER="google-chrome-stable"
elif command -v firefox &> /dev/null; then
    echo -e "${YELLOW}⚠ Firefox detected. Chromium recommended for kiosk mode.${NC}"
    BROWSER="firefox"
else
    echo "No supported browser found!"
    echo "Please install Chromium: sudo apt install chromium-browser"
    exit 1
fi

# Launch browser in kiosk mode
case "${BROWSER}" in
    chromium*|google-chrome*)
        "${BROWSER}" \
            --kiosk \
            --noerrdialogs \
            --disable-infobars \
            --disable-session-crashed-bubble \
            --disable-restore-session-state \
            --no-first-run \
            --start-fullscreen \
            --disable-translate \
            --disable-features=TranslateUI \
            --autoplay-policy=no-user-gesture-required \
            --allow-insecure-localhost \
            "${GUI_URL}"
        ;;
    firefox)
        "${BROWSER}" --kiosk "${GUI_URL}"
        ;;
esac

#!/bin/bash
# =============================================================================
# PANDA.1 Kiosk Autostart Script
# =============================================================================
# Starts PANDA.1 backend and opens browser in kiosk mode
# =============================================================================

PANDA_HOME="${HOME}/.panda1"
LOG_FILE="${PANDA_HOME}/logs/kiosk.log"

# Load environment
if [ -f "${PANDA_HOME}/.env" ]; then
    source "${PANDA_HOME}/.env"
fi

# Default values
PANDA_GUI_HOST="${PANDA_GUI_HOST:-127.0.0.1}"
PANDA_GUI_PORT="${PANDA_GUI_PORT:-7860}"
PANDA_ENABLE_HTTPS="${PANDA_ENABLE_HTTPS:-0}"
PANDA_HTTPS_PORT="${PANDA_HTTPS_PORT:-7860}"
PANDA_KIOSK_BROWSER="${PANDA_KIOSK_BROWSER:-chromium}"

# Determine URL
if [ "$PANDA_ENABLE_HTTPS" = "1" ]; then
    URL="https://${PANDA_GUI_HOST}:${PANDA_HTTPS_PORT}"
else
    URL="http://${PANDA_GUI_HOST}:${PANDA_GUI_PORT}"
fi

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "${LOG_FILE}"
}

# Start backend
log "Starting PANDA.1 backend..."
source "${PANDA_HOME}/venv/bin/activate"
cd "${PANDA_HOME}"
export PYTHONPATH="${PANDA_HOME}"

# Start backend in background
python -m app.main --gui &
BACKEND_PID=$!
log "Backend PID: ${BACKEND_PID}"

# Wait for backend to be ready
log "Waiting for backend..."
MAX_WAIT=30
WAITED=0
while ! curl -s "http://${PANDA_GUI_HOST}:${PANDA_GUI_PORT}/health" > /dev/null 2>&1; do
    sleep 1
    WAITED=$((WAITED + 1))
    if [ $WAITED -ge $MAX_WAIT ]; then
        log "ERROR: Backend did not start in ${MAX_WAIT}s"
        exit 1
    fi
done
log "Backend ready!"

# Start browser in kiosk mode
log "Starting kiosk browser at ${URL}"

case "$PANDA_KIOSK_BROWSER" in
    chromium|chromium-browser)
        chromium-browser --kiosk --noerrdialogs --disable-infobars \
            --disable-session-crashed-bubble --disable-translate \
            --start-fullscreen "${URL}" &
        ;;
    chrome|google-chrome)
        google-chrome --kiosk --noerrdialogs --disable-infobars \
            --disable-session-crashed-bubble --disable-translate \
            --start-fullscreen "${URL}" &
        ;;
    firefox)
        firefox --kiosk "${URL}" &
        ;;
    *)
        # Try xdg-open as fallback
        xdg-open "${URL}" &
        ;;
esac

BROWSER_PID=$!
log "Browser PID: ${BROWSER_PID}"

# Keep script running to maintain processes
wait ${BACKEND_PID}

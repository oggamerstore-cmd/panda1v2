#!/usr/bin/env bash
# =============================================================================
# PANDA.1 v0.2.10 Smoke Test
# =============================================================================
# Quick verification that all components are working.
# Run after installation to verify setup.
# =============================================================================

set -e

PANDA_HOME="${HOME}/.panda1"
LOG_FILE="${PANDA_HOME}/data/logs/smoke_test.log"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

passed=0
failed=0

log() {
    echo "[$(date '+%H:%M:%S')] $1" >> "${LOG_FILE}"
}

pass() {
    echo -e "${GREEN}✓${NC} $1"
    ((passed++))
    log "PASS: $1"
}

fail() {
    echo -e "${RED}✗${NC} $1"
    ((failed++))
    log "FAIL: $1"
}

warn() {
    echo -e "${YELLOW}⚠${NC} $1"
    log "WARN: $1"
}

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  PANDA.1 v0.2.10 Smoke Test"
echo "═══════════════════════════════════════════════════════════"
echo ""

mkdir -p "$(dirname "${LOG_FILE}")"
echo "Starting smoke test at $(date)" > "${LOG_FILE}"

# Test 1: Check panda command exists
echo "1. Checking panda command..."
if command -v panda &> /dev/null; then
    pass "panda command found"
else
    fail "panda command not found"
fi

# Test 2: Check Python version
echo "2. Checking Python version..."
if python3 --version 2>/dev/null | grep -q "3.1[0-2]"; then
    pass "Python $(python3 --version 2>&1 | awk '{print $2}')"
else
    warn "Python version may not be optimal (3.10-3.12 recommended)"
fi

# Test 3: Check virtual environment
echo "3. Checking virtual environment..."
if [[ -f "${PANDA_HOME}/venv/bin/activate" ]]; then
    pass "Virtual environment exists"
else
    fail "Virtual environment not found"
fi

# Test 4: Check app directory
echo "4. Checking app files..."
if [[ -f "${PANDA_HOME}/app/main.py" ]]; then
    pass "App files present"
else
    fail "App files missing"
fi

# Test 5: Check .env file
echo "5. Checking configuration..."
if [[ -f "${PANDA_HOME}/.env" ]]; then
    pass "Configuration file exists"
else
    warn "No .env file - using defaults"
fi

# Test 6: Audio player check
echo "6. Checking audio player..."
if command -v aplay &> /dev/null; then
    pass "aplay available"
elif command -v paplay &> /dev/null; then
    pass "paplay available"
elif command -v ffplay &> /dev/null; then
    pass "ffplay available"
else
    fail "No audio player found"
fi

# Test 7: Audio test
echo "7. Testing audio output..."
if panda --audio-test 2>/dev/null | grep -q "PASSED"; then
    pass "Audio test passed"
else
    warn "Audio test inconclusive (check volume)"
fi

# Test 8: Check TTS (quick import test)
echo "8. Checking TTS module..."
source "${PANDA_HOME}/venv/bin/activate" 2>/dev/null
cd "${PANDA_HOME}"
if python3 -c "from app.panda_tts import get_tts_manager; print('OK')" 2>/dev/null | grep -q "OK"; then
    pass "TTS module loads"
else
    warn "TTS module has issues"
fi

# Test 9: Check Chatterbox
echo "9. Checking Chatterbox..."
if python3 -c "import chatterbox; print('OK')" 2>/dev/null | grep -q "OK"; then
    pass "Chatterbox installed"
else
    warn "Chatterbox not installed (TTS will fallback)"
fi

# Test 10: Check web GUI module
echo "10. Checking web GUI module..."
if python3 -c "from app.web_gui import app; print('OK')" 2>/dev/null | grep -q "OK"; then
    pass "Web GUI module loads"
else
    fail "Web GUI module failed to load"
fi

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  Results: ${passed} passed, ${failed} failed"
echo "═══════════════════════════════════════════════════════════"
echo ""

if [[ ${failed} -eq 0 ]]; then
    echo -e "${GREEN}All tests passed!${NC}"
    echo ""
    echo "Next steps:"
    echo "  panda              # Start GUI"
    echo "  panda --doctor     # TTS diagnostics"
    echo "  panda --status     # Full status"
    exit 0
else
    echo -e "${RED}Some tests failed.${NC}"
    echo ""
    echo "Troubleshooting:"
    echo "  panda --doctor     # TTS diagnostics"
    echo "  Check logs: ${LOG_FILE}"
    exit 1
fi

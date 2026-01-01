#!/usr/bin/env bash
# =============================================================================
# PANDA.1 v0.2.6 → v0.2.7 Quick Fix
# =============================================================================
# Fixes:
# 1. VRAM issue (single model loading)
# 2. .env quoted values
# 3. Import paths
# 4. Launcher script
# 5. TTS CPU default
# =============================================================================

set -e

echo ""
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║  PANDA.1 v0.2.6 → v0.2.7 Quick Fix                            ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""

PANDA_HOME="${HOME}/.panda1"

# Check if PANDA.1 is installed
if [[ ! -d "${PANDA_HOME}" ]]; then
    echo "ERROR: PANDA.1 not found at ${PANDA_HOME}"
    echo "Run the full installer instead."
    exit 1
fi

# Fix 1: Update .env with CPU default and quoted values
ENV_FILE="${PANDA_HOME}/.env"
echo "1. Fixing .env file..."

if [[ -f "${ENV_FILE}" ]]; then
    # Fix quoted values
    sed -i 's/^PANDA_WAKE_PHRASES=hey panda,yo panda$/PANDA_WAKE_PHRASES="hey panda|yo panda"/' "${ENV_FILE}"
    sed -i 's/^PANDA_NETWORK_NAME=PANDA.1 Network$/PANDA_NETWORK_NAME="PANDA.1 Network"/' "${ENV_FILE}"
    
    # Add CPU default if not present
    if ! grep -q "PANDA_TTS_DEVICE" "${ENV_FILE}"; then
        echo "" >> "${ENV_FILE}"
        echo "# v0.2.7 - TTS on CPU to avoid VRAM conflicts with Ollama" >> "${ENV_FILE}"
        echo "PANDA_TTS_DEVICE=cpu" >> "${ENV_FILE}"
    fi
    
    # Add ALSA device if not present
    if ! grep -q "PANDA_ALSA_DEVICE" "${ENV_FILE}"; then
        echo "PANDA_ALSA_DEVICE=default" >> "${ENV_FILE}"
    fi
    
    echo "   ✓ .env updated"
else
    echo "   ⚠ No .env file found (using defaults)"
fi

# Fix 2: Fix imports in main.py
MAIN_PY="${PANDA_HOME}/app/main.py"
echo "2. Fixing imports in main.py..."

if [[ -f "${MAIN_PY}" ]]; then
    sed -i 's/from panda_tts import/from app.panda_tts import/g' "${MAIN_PY}"
    sed -i 's/from panda_tts\./from app.panda_tts./g' "${MAIN_PY}"
    echo "   ✓ Imports fixed"
else
    echo "   ⚠ main.py not found"
fi

# Fix 3: Fix chatterbox_engine.py (single model loading)
CHATTERBOX_PY="${PANDA_HOME}/app/panda_tts/chatterbox_engine.py"
echo "3. Fixing VRAM issue (single model loading)..."

if [[ -f "${CHATTERBOX_PY}" ]]; then
    # Check if we need to fix the duplicate model loading
    if grep -q "_load_multilingual_model()" "${CHATTERBOX_PY}"; then
        # Comment out the multilingual model call in warmup
        sed -i 's/self._load_multilingual_model()$/# self._load_multilingual_model()  # Removed - single model handles all/' "${CHATTERBOX_PY}"
        
        # Add model pointer after english model loads
        if ! grep -q "self._model_multi = self._model_en" "${CHATTERBOX_PY}"; then
            sed -i '/self._model_en = ChatterboxTTS.from_pretrained/a\            self._model_multi = self._model_en  # Single model handles all languages' "${CHATTERBOX_PY}"
        fi
        echo "   ✓ Single model loading fixed"
    else
        echo "   ✓ Already fixed"
    fi
else
    echo "   ⚠ chatterbox_engine.py not found"
fi

# Fix 4: Update launcher script
LAUNCHER="${HOME}/.local/bin/panda"
echo "4. Fixing launcher script..."

cat > "${LAUNCHER}" << 'LAUNCHER_SCRIPT'
#!/usr/bin/env bash
# PANDA.1 Launcher v0.2.7

PANDA_HOME="${HOME}/.panda1"
VENV_DIR="${PANDA_HOME}/venv"
ENV_FILE="${PANDA_HOME}/.env"

# Set HuggingFace cache
export HF_HOME="${PANDA_HOME}/cache/huggingface"
export TRANSFORMERS_CACHE="${PANDA_HOME}/cache/huggingface/transformers"

# Activate virtual environment
source "${VENV_DIR}/bin/activate"

# Load environment safely (handle quoted values)
if [[ -f "${ENV_FILE}" ]]; then
    while IFS= read -r line || [[ -n "$line" ]]; do
        [[ "$line" =~ ^#.*$ ]] && continue
        [[ -z "$line" ]] && continue
        export "$line" 2>/dev/null || true
    done < "${ENV_FILE}"
fi

# Change to panda home (parent of app) so python -m app.main works
cd "${PANDA_HOME}"

# Default to GUI if no args
if [[ $# -eq 0 ]]; then
    exec python3 -m app.web_gui
else
    exec python3 -m app.main "$@"
fi
LAUNCHER_SCRIPT

chmod +x "${LAUNCHER}"
echo "   ✓ Launcher updated"

# Fix 5: Update version in main.py
echo "5. Updating version..."
if [[ -f "${MAIN_PY}" ]]; then
    sed -i 's/__version__ = "0.2.6"/__version__ = "0.2.7"/' "${MAIN_PY}"
    echo "   ✓ Version updated to 0.2.7"
fi

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  All fixes applied!"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "Test your installation:"
echo "  panda --doctor        # TTS diagnostics"
echo "  panda --audio-test    # Audio playback test"
echo "  panda --tts-test \"Hello world\""
echo ""
echo "Start PANDA.1:"
echo "  panda                 # Launch GUI"
echo ""

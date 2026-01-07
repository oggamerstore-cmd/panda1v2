# PANDA.1 v2.0 — Production Enhancement

**Personal AI Navigator & Digital Assistant** for BOS.

A local-first AI assistant with voice interaction, news integration, and business tools.

## What's New in v2.0

### 🎤 Complete Voice System Rewrite
- **Faster-Whisper STT**: Fast, accurate speech recognition (EN + KO + AUTO)
- **Kokoro TTS**: Real-time speak-as-it-types with Korean support
- **Push-to-Talk**: Hold Space bar or click mic icon to record
- **Language Modes**: Auto-detect, English only, Korean only

### 🌐 Network Improvements
- **SCOTT Integration**: Reliable LAN HTTP connection with clear error messages
- **Proxy Endpoints**: Frontend never calls SCOTT directly
- **HTTPS Support**: For microphone access on non-localhost

### 🤖 AI Enhancements  
- **OpenAI Fallback**: GPT-4 for low-confidence local responses
- **General Assistant**: PANDA is now a life + business assistant
- **Document Tool**: Open and summarize Word/text files

### 🖥️ UX Improvements
- **Fixed Double Bubbles**: One message = one bubble
- **Kiosk Mode**: Fullscreen autostart on boot
- **Voice Settings Panel**: Configure STT/TTS from GUI

## Quick Start

### Installation

```bash
cd ~/.panda1
unzip panda1_v2.0.zip
cd panda1_v2.0
./install.sh
```

### Launch

```bash
panda --gui
```

### Configuration

```bash
cp .env.template ~/.panda1/.env
nano ~/.panda1/.env
```

## Voice System

### Push-to-Talk (PTT)

1. **Space Bar**: Hold to record, release to transcribe
2. **Mic Icon**: Click to start/stop recording
3. **Esc**: Cancel recording

### CLI Testing

```bash
panda --voice-doctor      # Full voice diagnosis
panda --mic-test          # Test microphone
panda --stt-test file.wav # Test STT
panda --tts-test "Hello"  # Test TTS
```

## SCOTT News

Configure in `~/.panda1/.env`:

```bash
SCOTT_ENABLED=1
SCOTT_BASE_URL=http://192.168.0.118:8000
SCOTT_API_KEY=your_secret
```

Test: `panda --scott-doctor`

## SENSEI Integration

PANDA.1 can sync learned docs from SENSEI and store them in a persistent local
vector memory for RAG. This runs automatically in the background when enabled,
and can be triggered manually with the **"panda learn"** command.

Configure in `~/.panda1/.env`:

```bash
SENSEI_BASE_URL=http://192.168.0.120:5000
SENSEI_ENABLED=true
SENSEI_HTTP_TIMEOUT_SECONDS=10
SENSEI_SYNC_INTERVAL_SECONDS=600
SENSEI_PING_INTERVAL_SECONDS=10
SENSEI_MAX_DOWNLOAD_MB=50
OLLAMA_EMBED_MODEL=nomic-embed-text
```

Storage paths on PANDA.1:

- Cache download: `~/.panda1/cache/sensei/knowledge_injections.jsonl`
- Vector memory DB: `~/.panda1/memory/sensei/index.sqlite`

Required SENSEI endpoint (no auth, LAN HTTP):

```
GET /api/knowledge_injections.jsonl
-> FileResponse("/home/bos/.sensei/out/knowledge_injections.jsonl")
```

If that endpoint is missing, PANDA.1 will report:
“SENSEI must expose GET /api/knowledge_injections.jsonl (FileResponse).”

## ECHO Context Hub (Database PC)

`install.sh` now runs `install_echo.sh` automatically to set up the ECHO vector
server under `~/.echo` and register the user systemd service.

If you need to install or repair ECHO manually:

```bash
./install_echo.sh
systemctl --user status echo.service
```

Configure in `~/.panda1/.env`:

```bash
PANDA_ECHO_ENABLED=true
PANDA_ECHO_BASE_URL=http://192.168.0.115:9010
PANDA_ECHO_TOP_K=5
```

Test: `panda --echo-doctor`

## HTTPS Mode

For microphone on non-localhost:

```bash
./scripts/generate_certs.sh
# Enable PANDA_ENABLE_HTTPS=true in .env
```

## Autostart

```bash
./scripts/setup_autostart.sh --enable
```

## CLI Commands

```bash
panda --gui               # Start GUI
panda --gui-doctor        # Diagnose GUI
panda --voice-doctor      # Diagnose voice
panda --scott-doctor      # Diagnose SCOTT
panda --audio-devices     # List devices
```

---

**PANDA.1 v2.0** — Production Enhancement

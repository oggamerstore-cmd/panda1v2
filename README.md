# PANDA.1 v0.2.10 — Vision Upgrade

**Personal AI Navigator & Digital Assistant** for BOS.

A local-first AI assistant with voice interaction, news integration, and business tools.

## What's New in v0.2.10

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
unzip panda1_v0.2.10.zip
cd panda1_v0.2.10
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
SCOTT_BASE_URL=http://192.168.1.18:8000
SCOTT_API_KEY=your_secret
```

Test: `panda --scott-doctor`

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
PANDA_ECHO_BASE_URL=http://192.168.1.20:9010
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

**PANDA.1 v0.2.10** — Vision Upgrade

# PANDA.1 Changelog


## v0.2.11 - Production Enhancement (2025-01-01)

### 🔧 Code Quality
- **Fixed all bare except clauses**: All exception handling now properly specifies exception types
- **Logging standardization**: Replaced 268 print() statements with appropriate logging calls
- **Better error messages**: Added context and file information to all error messages
- **Improved exception handling**: Enhanced error recovery and propagation

### 🐛 Bug Fixes
- Fixed potential resource leaks
- Improved error recovery in voice system
- Enhanced exception handling in network code
- Better cleanup on shutdown

### ⚡ Performance
- Removed duplicate imports
- Optimized code structure
- Better resource management

### 📝 Documentation
- Added production deployment guide
- Enhanced code comments
- Improved error messages

---

## v0.2.10 - Version Consistency Update (2025-12-30)

### 🔢 Versioning
- Bumped all components, scripts, and diagnostics to PANDA.1 v0.2.10
- Aligned GUI and CLI version displays for consistent reporting

## v0.2.9 - Vision Upgrade (2024-12-25)

### 🎤 Complete Voice System Rewrite
- **Faster-Whisper STT**: Replaced openai-whisper with faster-whisper for 3-4x faster transcription
- **Kokoro TTS**: Real-time speak-as-it-types with sentence-level chunking
- **Push-to-Talk**: Hold Space bar OR click mic icon to record
- **Language Modes**: Auto-detect, English-only, Korean-only
- **Voice Subsystem**: New `app/voice/` package with modular architecture
  - `devices.py`: Audio device enumeration and selection
  - `capture.py`: PTT recording engine with level monitoring
  - `stt_faster_whisper.py`: Faster-Whisper wrapper (EN/KO/AUTO)
  - `tts_kokoro.py`: Kokoro v1.0 wrapper with streaming
  - `tts_streamer.py`: Real-time TTS with sentence buffering
  - `playback.py`: Reliable audio output with fallbacks
  - `manager.py`: Unified VoiceManager for all voice operations

### 🌐 SCOTT Integration Rewrite
- **LAN HTTP**: Proper connection to SCOTT at 192.168.1.18:8000
- **API Key Auth**: X-API-Key header on all requests
- **Proxy Endpoints**: Frontend never calls SCOTT directly
- **Clear Errors**: Specific messages for timeout, auth, connection failures
- **New Client**: `app/integrations/scott_client.py` with retry logic

### 🤖 OpenAI Fallback
- **Confidence-Gated**: Use GPT-4 when local confidence < 0.75
- **Internet Check**: Fast connectivity test before fallback
- **Server-Side Only**: API key never exposed to frontend
- **Labeled Responses**: "Verified (OpenAI)" badge on fallback responses

### 🖥️ GUI Improvements
- **Fixed Double Bubbles**: message_id correlation ensures one bubble per turn
- **Voice Settings Panel**: Configure mic/speaker/language from GUI
- **HTTPS Support**: Self-signed certs for non-localhost mic access
- **Kiosk Mode**: Fullscreen autostart on boot

### 📁 Document Tool
- **File Browser**: Safe browsing in ~/Documents and ~/.panda1/files
- **DOCX Support**: Word files converted to HTML via python-docx
- **Text Files**: .txt, .md, .log, .json, .csv support
- **Actions**: Summarize, search, extract

### 🔗 URL Tools
- **YouTube Search**: Generate search URLs
- **Spotify Search**: Generate search URLs
- **Web Search**: Google/DuckDuckGo URL generation

### 🆕 New CLI Commands
- `panda --voice-doctor` - Full voice system diagnostics
- `panda --scott-doctor` - SCOTT connection diagnostics
- `panda --https-doctor` - HTTPS/cert diagnostics
- `panda --mic-test` - Test microphone (3s recording)
- `panda --stt-test FILE --lang [auto|en|ko]` - Test STT
- `panda --tts-test "text" --lang [en|ko]` - Test TTS
- `panda --play-test` - Test audio playback

### 🔧 Configuration (New in .env)
- `PANDA_STT_ENGINE=faster-whisper` - STT engine
- `PANDA_STT_MODEL=small` - Whisper model (tiny/base/small/medium)
- `PANDA_TTS_ENGINE=kokoro` - TTS engine
- `PANDA_TTS_VOICE_EN=af_heart` - English voice
- `PANDA_TTS_VOICE_KO=af_heart` - Korean voice
- `PANDA_LANGUAGE_MODE=auto` - Language detection mode
- `PANDA_OPENAI_FALLBACK_ENABLED=false` - Enable GPT-4 fallback
- `PANDA_OPENAI_CONFIDENCE_THRESHOLD=0.75` - Fallback trigger
- `PANDA_ENABLE_HTTPS=false` - Enable HTTPS mode
- `PANDA_HTTPS_PORT=7861` - HTTPS port
- `SCOTT_BASE_URL=http://192.168.1.18:8000` - SCOTT URL
- `SCOTT_API_KEY=` - SCOTT authentication

### 📜 Scripts
- `scripts/generate_certs.sh` - Generate HTTPS certificates
- `scripts/kiosk.sh` - Launch in fullscreen kiosk mode
- `scripts/setup_autostart.sh` - Configure boot autostart

### 🐛 Bug Fixes
- Fixed double PANDA chat bubbles
- Fixed SCOTT assuming localhost
- Fixed voice not working despite hardware OK
- Fixed import errors from v0.2.8
- Fixed language toggle crash

---

## v0.2.8 - GUI Voice Integration Fix (2024-12-16)

### 🔧 Critical Fixes
- **Action Log 422 Bug**: Fixed POST /api/ui/action-log returning 422 by creating separate ActionLogCreate model (no timestamp required)
- **Chat Bubble Merging**: Implemented message_id correlation so each assistant reply gets its own bubble
- **WebSocket Crash on Language Toggle**: Added set_mode() method to LanguageModeManager for backward compatibility
- **Version Consistency**: All components now report v0.2.8 correctly

### 🎙️ GUI Voice Integration ("Hey Panda")
- **Always-on Voice Wake**: VoiceAssistant starts automatically with GUI server
- **Thread-Safe Broadcasting**: Voice events pushed via asyncio.Queue + loop.call_soon_threadsafe
- **Wake Flow**: "Hey Panda" → UI updates → optional TTS ack → command capture → assistant response with TTS
- **Graceful Degradation**: GUI continues working if mic unavailable (state: UNAVAILABLE)
- **Speaking Indicator**: UI shows when TTS is playing with Stop button

### 🎤 Audio Input Selection
- **Device Index Support**: PANDA_AUDIO_INPUT_DEVICE env var for microphone selection
- **Enhanced --audio-devices**: Now shows INPUT and OUTPUT devices with indices
- **New panda mic-test**: Records 3s from selected mic, reports RMS/peak levels, saves WAV
- **Fallback Handling**: Invalid device index gracefully falls back to disabled voice

### 🆕 New CLI Commands  
- `panda --audio-devices` - Enhanced to show both INPUT and OUTPUT devices
- `panda --mic-test [seconds]` - Test microphone input (default: 3 seconds)
- `panda --gui-doctor` - GUI-specific diagnostics (WebSocket, voice, TTS, LLM, SCOTT)

### 🔧 Configuration (New in .env)
- `PANDA_GUI_VOICE_ENABLED=true` - Enable/disable voice in GUI mode
- `PANDA_VOICE_ACK_ENABLED=true` - Enable/disable "Yes BOS" acknowledgment
- `PANDA_AUDIO_INPUT_DEVICE=<index>` - Microphone device index
- `PANDA_SCOTT_RETRY_INTERVAL=60` - Rate-limit SCOTT health checks

### 🐛 Bug Fixes
- SCOTT offline no longer spams or crashes GUI (rate-limited, warning only)
- VoiceState now includes UNAVAILABLE for missing microphone
- Duplicate broadcast handling with socket pruning
- Thread-safe WebSocket writes from voice thread

### 📋 Testing
- Added tests/test_gui_v028.py with smoke tests for all fixes
- Tests cover: action log, language toggle, message_id, voice disable, mic selection, TTS events

---

## v0.2.7 - Audio & GUI Hotfix (2024-12-16)

### 🔊 Audio Fixes
- **Fixed VRAM issue**: Single model loading prevents GPU OOM on RTX 2060 6GB
- **CPU default for TTS**: `PANDA_TTS_DEVICE=cpu` by default to avoid conflicts with Ollama
- **Robust audio playback**: New playback module with fallback chain (aplay → paplay → ffplay → mpv)
- **ALSA device support**: New `PANDA_ALSA_DEVICE` env var for device selection
- **PCM_16 output**: WAV files now use PCM_16 format for ALSA compatibility
- **Error surfacing**: Playback errors now logged with stderr capture

### 🖥️ GUI Fixes  
- **Headless/SSH detection**: Server-only mode when no DISPLAY or SSH detected
- **LAN access**: Set `PANDA_GUI_HOST=0.0.0.0` for remote access
- **Log History panel**: Bottom-right panel tracking button clicks and actions
- **Reliable buttons**: All buttons now properly wired with error feedback
- **Toast notifications**: Visual feedback for all actions
- **TTS controls**: Stop TTS and Test TTS buttons added

### 🆕 New CLI Commands
- `panda --audio-devices` - List ALSA and PulseAudio devices
- `panda --audio-test` - Test audio playback with beep
- `panda --tts-test "text"` - Test TTS with status output

### 🔧 Configuration
- `PANDA_TTS_DEVICE=cpu` (default, safe for 6GB VRAM)
- `PANDA_ALSA_DEVICE=default` (ALSA output device)
- `PANDA_AUDIO_PLAYER` (optional custom player override)
- `PANDA_GUI_HOST=127.0.0.1` (set to 0.0.0.0 for LAN)
- `PANDA_GUI_PORT=7860` (GUI server port)

### 🐛 Bug Fixes
- Fixed .env parsing with quoted values
- Fixed module imports (panda_tts → app.panda_tts)
- Fixed launcher working directory
- Fixed duplicate model loading causing OOM
- Fixed GUI server startup in headless environments

---

## v0.2.6 - Chatterbox TTS Migration (2024-12-16)

### Changed
- Migrated from ElevenLabs to offline Chatterbox TTS
- Added Piper as lightweight fallback TTS
- Removed all ElevenLabs dependencies and API calls

### Added
- `panda --doctor` - TTS diagnostics
- `panda --tts-test` - TTS testing
- `panda --tts-prefetch` - Download models for offline use
- Automatic GPU/CPU detection for TTS

---

## v0.2.5 - Web GUI (2024-12-15)

### Added
- FastAPI-based web GUI
- WebSocket real-time chat
- Sleep/wake screensaver mode
- Voice status indicators
- `pandagui` kiosk launcher

---

## v0.2.4 - Intent Detection (2024-12-14)

### Added
- Intent detection system
- SCOTT news agent integration
- Multi-language support (EN/KO)

---

## v0.2.3 - Network Awareness (2024-12-13)

### Added
- Network health monitoring
- Multi-machine coordination
- Agent hub preparation

---

## v0.2.0 - Initial Release (2024-12-10)

### Features
- Local LLM via Ollama
- ChromaDB memory system
- Voice assistant with Whisper STT
- CLI and API interfaces

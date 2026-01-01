"""
PANDA.1 Voice Subsystem
=======================
Complete voice pipeline: PTT capture → Faster-Whisper STT → Kokoro TTS

Version: 0.2.10

Components:
- devices: Audio device enumeration and selection
- capture: Push-to-talk recording engine
- stt_faster_whisper: Speech-to-text with Faster-Whisper
- tts_kokoro: Text-to-speech with Kokoro v1.0
- tts_streamer: Real-time speak-while-streaming
- playback: Audio output management
- voice_config: Persistent voice settings

Usage:
    from app.voice import VoiceManager
    
    vm = VoiceManager()
    vm.initialize()
    
    # PTT recording
    vm.start_recording()
    # ... user speaks ...
    transcript = vm.stop_recording()  # Returns transcribed text
    
    # TTS playback
    vm.speak("Hello, I am PANDA!")
    vm.speak_streaming(text_generator)  # Real-time TTS
"""

from .voice_config import VoiceConfig, get_voice_config
from .devices import (
    list_input_devices,
    list_output_devices,
    get_default_input_device,
    get_default_output_device,
    validate_device,
)
from .capture import AudioCapture, CaptureState
from .stt_faster_whisper import FasterWhisperSTT, STTResult
from .tts_kokoro import KokoroTTS
from .tts_streamer import TTSStreamer
from .playback import AudioPlayer
from .manager import VoiceManager, VoiceState

__all__ = [
    # Config
    "VoiceConfig",
    "get_voice_config",
    # Devices
    "list_input_devices",
    "list_output_devices", 
    "get_default_input_device",
    "get_default_output_device",
    "validate_device",
    # Capture
    "AudioCapture",
    "CaptureState",
    # STT
    "FasterWhisperSTT",
    "STTResult",
    # TTS
    "KokoroTTS",
    "TTSStreamer",
    # Playback
    "AudioPlayer",
    # Manager
    "VoiceManager",
    "VoiceState",
]

__version__ = "0.2.10"

"""
PANDA.1 TTS System
==================
Offline Text-to-Speech for PANDA.1.

Version: 0.2.10

TTS Engines:
- Chatterbox (default, offline, GPU-accelerated)
- Piper (fallback, offline, CPU)
- Null (last resort, no audio)

Usage:
    from app.panda_tts import get_tts_manager, speak, stop_speech
    
    # Initialize
    manager = get_tts_manager()
    manager.initialize()
    
    # Speak
    speak("Hello, I am PANDA.1!")
    
    # Or with explicit language
    speak("안녕하세요!", lang="ko")
    
    # Stop
    stop_speech()
"""

from .base import TTSEngine, detect_language, chunk_text
from .manager import (
    TTSManager,
    get_tts_manager,
    get_tts_engine,
    speak,
    stop_speech,
)
from .playback import AudioPlayer, get_player

__all__ = [
    # Base
    "TTSEngine",
    "detect_language",
    "chunk_text",
    # Manager
    "TTSManager",
    "get_tts_manager",
    "get_tts_engine",
    "speak",
    "stop_speech",
    # Playback
    "AudioPlayer",
    "get_player",
]

__version__ = "0.2.10"

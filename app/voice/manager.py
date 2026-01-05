"""
PANDA.1 Voice Manager
=====================
Unified interface for voice operations: PTT, STT, TTS.

Version: 0.2.11

Features:
- Push-to-talk coordination
- STT with Faster-Whisper
    - TTS with Kokoro
- Language detection and routing
"""

import time
import logging
import threading
import shutil
from enum import Enum, auto
from pathlib import Path
from typing import Optional, Callable, Generator
from dataclasses import dataclass

from .voice_config import VoiceConfig, get_voice_config, LanguageMode
from .devices import list_input_devices, list_output_devices, get_device_info
from .capture import AudioCapture, CaptureState, CaptureResult
from .stt_faster_whisper import FasterWhisperSTT, STTResult, STTLanguage
from app.panda_tts import get_tts_manager, stop_speech, detect_language

logger = logging.getLogger(__name__)


class VoiceState(Enum):
    """Voice system states."""
    IDLE = auto()
    RECORDING = auto()
    TRANSCRIBING = auto()
    SPEAKING = auto()
    ERROR = auto()
    UNAVAILABLE = auto()


@dataclass
class VoiceEvent:
    """Voice system event."""
    type: str
    data: dict = None
    timestamp: float = None
    
    def __post_init__(self):
        if self.data is None:
            self.data = {}
        if self.timestamp is None:
            self.timestamp = time.time()


class VoiceManager:
    """
    Unified voice management for PANDA.1.
    
    Coordinates:
    - Push-to-talk recording
    - Speech-to-text transcription
    - Text-to-speech synthesis
    - Real-time streaming TTS
    
    Usage:
        vm = VoiceManager()
        vm.initialize()
        
        # PTT workflow
        vm.start_recording()
        # ... user speaks ...
        transcript = vm.stop_recording()
        
        # TTS
        vm.speak("Hello!")
        
        # Streaming TTS
        vm.speak_streaming(text_generator)
    """
    
    def __init__(self, config: Optional[VoiceConfig] = None):
        """
        Initialize voice manager.
        
        Args:
            config: Voice configuration (or uses global)
        """
        self.config = config or get_voice_config()
        
        self._state = VoiceState.IDLE
        self._capture: Optional[AudioCapture] = None
        self._stt: Optional[FasterWhisperSTT] = None
        self._tts_manager = None
        
        self._initialized = False
        self._lock = threading.Lock()
        
        # Callbacks
        self._on_state_change: Optional[Callable[[VoiceState], None]] = None
        self._on_level_update: Optional[Callable[[float], None]] = None
        self._on_transcript: Optional[Callable[[str], None]] = None
        self._on_error: Optional[Callable[[str], None]] = None
    
    @property
    def state(self) -> VoiceState:
        """Get current voice state."""
        return self._state
    
    @property
    def is_recording(self) -> bool:
        """Check if currently recording."""
        return self._state == VoiceState.RECORDING
    
    @property
    def is_speaking(self) -> bool:
        """Check if currently speaking."""
        return self._state == VoiceState.SPEAKING
    
    @property
    def is_initialized(self) -> bool:
        """Check if voice system is initialized."""
        return self._initialized
    
    def set_callbacks(
        self,
        on_state_change: Optional[Callable[[VoiceState], None]] = None,
        on_level_update: Optional[Callable[[float], None]] = None,
        on_transcript: Optional[Callable[[str], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
    ) -> None:
        """Set event callbacks."""
        self._on_state_change = on_state_change
        self._on_level_update = on_level_update
        self._on_transcript = on_transcript
        self._on_error = on_error
    
    def initialize(self) -> bool:
        """
        Initialize all voice components.
        
        Returns:
            True if initialized successfully
        """
        if self._initialized:
            return True
        
        logger.info("Initializing voice manager...")
        
        try:
            # Initialize audio capture
            self._capture = AudioCapture(
                sample_rate=self.config.sample_rate,
                channels=self.config.channels,
                device_index=self.config.input_device,
                max_duration=self.config.ptt_max_duration,
                min_duration=self.config.ptt_min_duration,
                on_level_update=self._handle_level_update,
            )
            
            # Initialize STT
            self._stt = FasterWhisperSTT(
                model_size=self.config.stt_model.value,
                compute_type=self.config.stt_compute_type,
            )
            
            # Pre-load STT model (can be slow)
            logger.info("Loading STT model...")
            if not self._stt.load_model():
                logger.warning("STT model failed to load")
            
            # Initialize TTS (Kokoro)
            self._tts_manager = get_tts_manager()
            self._tts_manager.initialize(
                engine="kokoro",
                device=self.config.tts_device,
                voice_name=self.config.tts_voice_en,
            )
            
            self._initialized = True
            self._state = VoiceState.IDLE
            
            logger.info("Voice manager initialized")
            return True
            
        except Exception as e:
            logger.error(f"Voice initialization failed: {e}")
            self._state = VoiceState.ERROR
            self._fire_error(str(e))
            return False
    
    def start_recording(self) -> bool:
        """
        Start PTT recording.
        
        Returns:
            True if recording started
        """
        if not self._initialized:
            if not self.initialize():
                return False
        
        if self._state == VoiceState.RECORDING:
            return True
        
        if self._capture.start():
            self._set_state(VoiceState.RECORDING)
            logger.info("Recording started")
            return True
        
        self._fire_error("Failed to start recording")
        return False
    
    def stop_recording(self) -> Optional[str]:
        """
        Stop recording and transcribe.
        
        Returns:
            Transcribed text or None on failure
        """
        if self._state != VoiceState.RECORDING:
            return None
        
        self._set_state(VoiceState.TRANSCRIBING)
        
        # Stop capture
        result = self._capture.stop()
        
        if not result.success:
            logger.warning(f"Recording failed: {result.error}")
            self._fire_error(result.error or "Recording failed")
            self._set_state(VoiceState.IDLE)
            return None
        
        logger.info(f"Captured {result.duration:.1f}s audio (RMS={result.rms:.3f})")
        
        # Transcribe
        stt_lang = self._get_stt_language()
        stt_result = self._stt.transcribe(
            result.audio_data,
            language=stt_lang,
            beam_size=self.config.stt_beam_size,
            vad_filter=self.config.stt_vad_filter,
        )
        
        self._set_state(VoiceState.IDLE)
        
        if not stt_result.success:
            logger.warning(f"Transcription failed: {stt_result.error}")
            self._fire_error(stt_result.error or "Transcription failed")
            return None
        
        transcript = stt_result.text.strip()
        
        if transcript:
            logger.info(f"Transcribed: '{transcript[:50]}...' (lang={stt_result.language})")
            if self._on_transcript:
                self._on_transcript(transcript)
        else:
            logger.info("Empty transcription")
        
        return transcript if transcript else None
    
    def cancel_recording(self) -> None:
        """Cancel current recording."""
        if self._state == VoiceState.RECORDING:
            self._capture.cancel()
            self._set_state(VoiceState.IDLE)
            logger.info("Recording cancelled")
    
    def speak(self, text: str, lang: Optional[str] = None, blocking: bool = False) -> bool:
        """
        Speak text using TTS.
        
        Args:
            text: Text to speak
            lang: Language (en, ko) or None for auto-detect
            blocking: Wait for completion
        
        Returns:
            True if successful
        """
        if not self._initialized:
            if not self.initialize():
                return False
        
        if self.config.tts_muted or not self.config.tts_enabled:
            return True
        
        # Detect language if not specified
        if lang is None:
            if self.config.language_mode == LanguageMode.AUTO:
                lang = detect_language(text)
            else:
                lang = self.config.language_mode.value
        
        self._set_state(VoiceState.SPEAKING)
        
        # Initialize TTS if needed
        if not self._tts_manager or not self._tts_manager.is_ready:
            logger.warning("TTS manager not ready")
            self._set_state(VoiceState.IDLE)
            return False

        # Speak
        play_result = self._tts_manager.speak(text, lang, blocking=blocking)
        
        if blocking:
            self._set_state(VoiceState.IDLE)
        else:
            # Set state back to idle after playback
            def _on_complete():
                time.sleep(0.1)
                if self._state == VoiceState.SPEAKING:
                    self._set_state(VoiceState.IDLE)
            threading.Thread(target=_on_complete, daemon=True).start()
        
        return play_result
    
    def speak_streaming(
        self,
        text_stream: Generator[str, None, None],
        lang: Optional[str] = None,
    ) -> None:
        """
        Speak text once the stream completes (Kokoro does not support streaming).
        
        Args:
            text_stream: Generator yielding text tokens
            lang: Language (or None for auto-detect)
        """
        if not self._initialized:
            if not self.initialize():
                return
        
        if self.config.tts_muted or not self.config.tts_enabled:
            # Still consume the stream
            for _ in text_stream:
                pass
            return
        
        self._set_state(VoiceState.SPEAKING)

        # Collect streamed text and speak once complete
        def _stream_worker():
            try:
                tokens = []
                for token in text_stream:
                    tokens.append(token)

                combined = "".join(tokens).strip()
                if combined:
                    self.speak(combined, lang, blocking=True)
            finally:
                self._set_state(VoiceState.IDLE)
        
        threading.Thread(target=_stream_worker, daemon=True).start()
    
    def stop_speaking(self) -> None:
        """Stop current TTS playback."""
        stop_speech()
        self._set_state(VoiceState.IDLE)
    
    def set_mute(self, muted: bool) -> None:
        """Set TTS mute state."""
        self.config.tts_muted = muted
        self.config.save()
    
    def set_volume(self, volume: float) -> None:
        """Set TTS volume (0.0 - 1.0)."""
        self.config.tts_volume = max(0.0, min(1.0, volume))
        self.config.save()
    
    def set_language_mode(self, mode: LanguageMode) -> None:
        """Set language mode."""
        self.config.language_mode = mode
        self.config.save()
    
    def set_input_device(self, device_index: Optional[int]) -> None:
        """Set input device."""
        self.config.input_device = device_index
        if self._capture:
            self._capture.set_device(device_index)
        self.config.save()
    
    def set_output_device(self, device_index: Optional[int]) -> None:
        """Set output device."""
        self.config.output_device = device_index
        self.config.save()
    
    def get_status(self) -> dict:
        """Get voice system status."""
        return {
            "state": self._state.name,
            "initialized": self._initialized,
            "config": self.config.to_dict(),
            "stt": self._stt.get_status() if self._stt else {"available": False},
            "tts": self._tts_manager.healthcheck() if self._tts_manager else {"available": False},
            "devices": get_device_info(),
        }
    
    def _set_state(self, state: VoiceState) -> None:
        """Set state and fire callback."""
        self._state = state
        if self._on_state_change:
            try:
                self._on_state_change(state)
            except Exception as e:
                logger.debug(f"State callback error: {e}")
    
    def _handle_level_update(self, level: float) -> None:
        """Handle audio level update from capture."""
        if self._on_level_update:
            try:
                self._on_level_update(level)
            except Exception as e:
                logger.debug(f"Level callback error: {e}")
    
    def _fire_error(self, error: str) -> None:
        """Fire error callback."""
        if self._on_error:
            try:
                self._on_error(error)
            except Exception as e:
                logger.debug(f"Error callback error: {e}")
    
    def _get_stt_language(self) -> STTLanguage:
        """Get STT language from config."""
        if self.config.language_mode == LanguageMode.AUTO:
            return STTLanguage.AUTO
        elif self.config.language_mode == LanguageMode.KOREAN:
            return STTLanguage.KOREAN
        else:
            return STTLanguage.ENGLISH


# Global voice manager instance
_voice_manager: Optional[VoiceManager] = None


def get_voice_manager() -> VoiceManager:
    """Get or create the global voice manager."""
    global _voice_manager
    
    if _voice_manager is None:
        _voice_manager = VoiceManager()
    
    return _voice_manager


def voice_doctor() -> dict:
    """
    Run voice system diagnostics.
    
    Returns:
        Dict with diagnostic results
    """
    results = {
        "overall": "unknown",
        "checks": [],
    }
    
    # Check dependencies
    try:
        import sounddevice
        results["checks"].append({
            "name": "sounddevice",
            "status": "ok",
            "message": "Audio library available"
        })
    except ImportError:
        results["checks"].append({
            "name": "sounddevice",
            "status": "error",
            "message": "pip install sounddevice"
        })
    
    try:
        import numpy
        results["checks"].append({
            "name": "numpy",
            "status": "ok",
            "message": "NumPy available"
        })
    except ImportError:
        results["checks"].append({
            "name": "numpy",
            "status": "error",
            "message": "pip install numpy"
        })
    
    try:
        from faster_whisper import WhisperModel
        results["checks"].append({
            "name": "faster-whisper",
            "status": "ok",
            "message": "STT engine available"
        })
    except ImportError:
        results["checks"].append({
            "name": "faster-whisper",
            "status": "error",
            "message": "pip install faster-whisper"
        })
    
    try:
        import kokoro
        results["checks"].append({
            "name": "kokoro",
            "status": "ok",
            "message": "TTS engine available"
        })
    except ImportError:
        results["checks"].append({
            "name": "kokoro",
            "status": "warning",
            "message": "Install kokoro for TTS output"
        })
    
    # Check devices
    inputs = list_input_devices()
    outputs = list_output_devices()
    
    if inputs:
        results["checks"].append({
            "name": "input_devices",
            "status": "ok",
            "message": f"{len(inputs)} microphone(s) found"
        })
    else:
        results["checks"].append({
            "name": "input_devices",
            "status": "error",
            "message": "No microphones found"
        })
    
    if outputs:
        results["checks"].append({
            "name": "output_devices",
            "status": "ok",
            "message": f"{len(outputs)} speaker(s) found"
        })
    else:
        results["checks"].append({
            "name": "output_devices",
            "status": "error",
            "message": "No speakers found"
        })
    
    # Determine overall status
    errors = [c for c in results["checks"] if c["status"] == "error"]
    warnings = [c for c in results["checks"] if c["status"] == "warning"]
    
    if errors:
        results["overall"] = "error"
    elif warnings:
        results["overall"] = "warning"
    else:
        results["overall"] = "ok"
    
    return results


def print_voice_doctor() -> None:
    """Print voice diagnostics to console."""
    logging.info(f"\n{'='*60}")
    logging.info("  PANDA.1 Voice Doctor")
    logging.info(f"{'='*60}")
    
    results = voice_doctor()
    
    status_icons = {
        "ok": "✅",
        "warning": "⚠️",
        "error": "❌",
    }
    
    for check in results["checks"]:
        icon = status_icons.get(check["status"], "?")
        logging.info(f"\n  {icon} {check['name']}")
        logging.info(f"     {check['message']}")
    
    logging.info(f"\n  {'='*50}")
    overall_icon = status_icons.get(results["overall"], "?")
    logging.info(f"  {overall_icon} Overall: {results['overall'].upper()}")
    
    if results["overall"] == "error":
        logging.info("\n  ⚠️  Voice features may not work correctly.")
        logging.info("     Please install missing dependencies.")
    
    logging.info()

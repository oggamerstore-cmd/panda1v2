"""
PANDA.1 TTS Engine Manager
==========================
Manages TTS engine selection and fallback.

Version: 0.2.11

Engine Selection Order:
1. Kokoro (default, lightweight 82M model, CPU-optimized)
2. Null (fallback - browser TTS will be used via frontend)

Note: Chatterbox has been removed to save GPU VRAM.
Browser-based Web Speech API provides fallback when Kokoro is unavailable.
"""

import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Literal

from .base import TTSEngine, detect_language

logger = logging.getLogger(__name__)


def _normalize_voice_name(voice_name: Optional[str]) -> str:
    if not voice_name:
        return "am_michael"

    normalized = voice_name.strip()
    legacy = normalized.lower()
    legacy_map = {
        "michael": "am_michael",
        "joe": "am_michael",
        "km_omega": "am_michael",
    }
    return legacy_map.get(legacy, normalized)


class TTSManager:
    """
    TTS Engine Manager.

    Handles engine selection, fallback, and lifecycle.
    """

    def __init__(self):
        self._engine: Optional[TTSEngine] = None
        self._engine_name: Optional[str] = None
        self._initialized = False
        self._voice_name: Optional[str] = None

    def initialize(
        self,
        engine: Optional[str] = None,
        device: Optional[str] = None,
        cache_dir: Optional[Path] = None,
        output_dir: Optional[Path] = None,
        voice_name: Optional[str] = None,
        speed: float = 1.0,
    ) -> TTSEngine:
        """
        Initialize TTS engine with fallback.

        Args:
            engine: Engine name (kokoro, null) or None for auto
            device: Device override (cpu recommended for Kokoro)
            cache_dir: Model cache directory
            output_dir: Audio output directory
            voice_name: Voice ID (default: michael)
            speed: Speech speed multiplier (0.5-2.0)

        Returns:
            Initialized TTSEngine
        """
        # Get from environment if not specified
        if engine is None:
            engine = os.environ.get("PANDA_TTS_ENGINE", "").lower()

        if voice_name is None:
            voice_name = os.environ.get("PANDA_TTS_VOICE", "michael")
        voice_name = _normalize_voice_name(voice_name)
        self._voice_name = voice_name

        if device is None:
            device = os.environ.get("PANDA_TTS_DEVICE", "cpu").lower()
            # Default to CPU for Kokoro to preserve GPU for LLM
            if device not in ("cuda", "cpu"):
                device = "cpu"

        # Default directories
        panda_home = Path.home() / ".panda1"
        output_dir = output_dir or panda_home / "audio_out"

        # Try engines in order
        if engine == "kokoro" or engine == "":
            # Kokoro is default
            self._engine = self._try_kokoro(output_dir, voice_name, speed, device)
            if not self._engine:
                self._engine = self._create_null()
        elif engine == "null" or engine == "off" or engine == "none":
            self._engine = self._create_null()
        else:
            # Unknown engine - try Kokoro then null
            logger.warning(f"Unknown TTS engine '{engine}', trying Kokoro")
            self._engine = self._try_kokoro(output_dir, voice_name, speed, device)
            if not self._engine:
                self._engine = self._create_null()

        self._engine_name = self._engine.name
        self._initialized = True

        logger.info(f"TTS engine initialized: {self._engine_name}")
        return self._engine

    def _try_kokoro(
        self,
        output_dir: Path,
        voice_name: str,
        speed: float,
        device: str,
    ) -> Optional[TTSEngine]:
        """Try to initialize Kokoro."""
        try:
            from .kokoro_engine import KokoroEngine

            engine = KokoroEngine(
                voice=voice_name,
                speed=speed,
                output_dir=output_dir,
                device=device,
            )

            if engine.warmup():
                logger.info(f"Kokoro engine ready (voice={voice_name})")
                return engine
            else:
                logger.warning("Kokoro warmup failed")
                return None

        except ImportError as e:
            logger.warning(f"Kokoro not available: {e}")
            logger.info("Install with: pip install kokoro soundfile")
            return None
        except Exception as e:
            logger.error(f"Kokoro init failed: {e}")
            return None

    def _create_null(self) -> TTSEngine:
        """Create null engine (browser TTS will be used)."""
        from .null_engine import NullEngine

        engine = NullEngine()
        engine.warmup()
        logger.warning("Using NullEngine - browser TTS will be used as fallback")
        return engine

    @property
    def engine(self) -> Optional[TTSEngine]:
        """Get current engine."""
        return self._engine

    @property
    def engine_name(self) -> str:
        """Get current engine name."""
        return self._engine_name or "none"

    @property
    def is_ready(self) -> bool:
        """Check if TTS is ready."""
        return self._engine is not None and self._engine.is_ready

    def speak(
        self,
        text: str,
        lang: Optional[Literal["en", "ko"]] = None,
        blocking: bool = False
    ) -> bool:
        """
        Speak text using current engine.

        Args:
            text: Text to speak
            lang: Language (auto-detected if None)
            blocking: Wait for speech to complete

        Returns:
            True if speech started
        """
        if not self._engine:
            logger.error("TTS not initialized")
            return False

        # Auto-detect language if not specified
        if lang is None:
            lang = detect_language(text)

        return self._engine.speak(text, lang, blocking)

    def stop(self) -> None:
        """Stop current speech."""
        if self._engine:
            self._engine.stop()

    def synthesize(
        self,
        text: str,
        lang: Optional[Literal["en", "ko"]] = None,
        output_path: Optional[Path] = None
    ) -> Optional[Path]:
        """Synthesize text to file."""
        if not self._engine:
            return None

        if lang is None:
            lang = detect_language(text)

        return self._engine.synthesize(text, lang, output_path)

    def healthcheck(self) -> Dict[str, Any]:
        """Get engine health status."""
        if not self._engine:
            return {
                "healthy": False,
                "engine": "none",
                "error": "TTS not initialized"
            }

        return self._engine.healthcheck()

    @property
    def is_speaking(self) -> bool:
        """Check if currently speaking."""
        return self._engine is not None and self._engine.is_speaking


# Global manager instance
_manager: Optional[TTSManager] = None


def get_tts_manager() -> TTSManager:
    """Get global TTS manager instance."""
    global _manager
    if _manager is None:
        _manager = TTSManager()
    return _manager


def get_tts_engine() -> Optional[TTSEngine]:
    """Get current TTS engine."""
    return get_tts_manager().engine


def speak(
    text: str,
    lang: Optional[Literal["en", "ko"]] = None,
    blocking: bool = False
) -> bool:
    """Convenience function to speak text."""
    manager = get_tts_manager()
    if not manager.is_ready:
        manager.initialize()
    return manager.speak(text, lang, blocking)


def stop_speech() -> None:
    """Stop current speech."""
    get_tts_manager().stop()

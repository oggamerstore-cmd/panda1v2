"""
PANDA.1 TTS Engine Manager
==========================
Manages TTS engine selection and fallback.

Version: 0.2.10

Engine Selection Order:
1. If PANDA_TTS_ENGINE=chatterbox -> try chatterbox else fallback
2. If PANDA_TTS_ENGINE=piper -> try piper else fallback
3. Default: chatterbox -> piper -> null
"""

import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Literal

from .base import TTSEngine, detect_language

logger = logging.getLogger(__name__)


class TTSManager:
    """
    TTS Engine Manager.
    
    Handles engine selection, fallback, and lifecycle.
    """
    
    def __init__(self):
        self._engine: Optional[TTSEngine] = None
        self._engine_name: Optional[str] = None
        self._initialized = False
    
    def initialize(
        self,
        engine: Optional[str] = None,
        device: Optional[str] = None,
        cache_dir: Optional[Path] = None,
        output_dir: Optional[Path] = None,
        reference_audio: Optional[Path] = None,
    ) -> TTSEngine:
        """
        Initialize TTS engine with fallback.
        
        Args:
            engine: Engine name (chatterbox, piper, null) or None for auto
            device: Device override (cuda, cpu) or None for auto
            cache_dir: Model cache directory
            output_dir: Audio output directory
            reference_audio: Voice cloning reference
        
        Returns:
            Initialized TTSEngine
        """
        # Get from environment if not specified
        if engine is None:
            engine = os.environ.get("PANDA_TTS_ENGINE", "").lower()
        
        if device is None:
            device = os.environ.get("PANDA_TTS_DEVICE", "").lower()
            if device not in ("cuda", "cpu"):
                device = None  # Auto-detect
        
        # Default directories
        panda_home = Path.home() / ".panda1"
        cache_dir = cache_dir or panda_home / "cache" / "huggingface"
        output_dir = output_dir or panda_home / "audio_out"
        
        # Try engines in order
        if engine == "chatterbox":
            self._engine = self._try_chatterbox(device, cache_dir, output_dir, reference_audio)
            if not self._engine:
                self._engine = self._fallback()
        elif engine == "piper":
            self._engine = self._try_piper(output_dir)
            if not self._engine:
                self._engine = self._fallback()
        elif engine == "null" or engine == "off" or engine == "none":
            self._engine = self._create_null()
        else:
            # Default: try chatterbox -> piper -> null
            self._engine = self._try_chatterbox(device, cache_dir, output_dir, reference_audio)
            if not self._engine:
                self._engine = self._try_piper(output_dir)
            if not self._engine:
                self._engine = self._create_null()
        
        self._engine_name = self._engine.name
        self._initialized = True
        
        logger.info(f"TTS engine initialized: {self._engine_name}")
        return self._engine
    
    def _try_chatterbox(
        self,
        device: Optional[str],
        cache_dir: Path,
        output_dir: Path,
        reference_audio: Optional[Path],
    ) -> Optional[TTSEngine]:
        """Try to initialize Chatterbox."""
        try:
            from .chatterbox_engine import ChatterboxEngine
            
            engine = ChatterboxEngine(
                device=device,
                cache_dir=cache_dir,
                output_dir=output_dir,
                reference_audio=reference_audio,
            )
            
            if engine.warmup():
                logger.info("Chatterbox engine ready")
                return engine
            else:
                logger.warning("Chatterbox warmup failed")
                return None
                
        except ImportError as e:
            logger.warning(f"Chatterbox not available: {e}")
            return None
        except Exception as e:
            logger.error(f"Chatterbox init failed: {e}")
            return None
    
    def _try_piper(self, output_dir: Path) -> Optional[TTSEngine]:
        """Try to initialize Piper."""
        try:
            from .piper_engine import PiperEngine
            
            engine = PiperEngine(output_dir=output_dir)
            
            if engine.warmup():
                logger.info("Piper engine ready (fallback)")
                return engine
            else:
                logger.warning("Piper warmup failed")
                return None
                
        except ImportError as e:
            logger.warning(f"Piper not available: {e}")
            return None
        except Exception as e:
            logger.error(f"Piper init failed: {e}")
            return None
    
    def _create_null(self) -> TTSEngine:
        """Create null engine."""
        from .null_engine import NullEngine
        
        engine = NullEngine()
        engine.warmup()
        logger.warning("Using NullEngine - no TTS audio")
        return engine
    
    def _fallback(self) -> TTSEngine:
        """Fallback through engines."""
        # Try piper first
        panda_home = Path.home() / ".panda1"
        engine = self._try_piper(panda_home / "audio_out")
        if engine:
            return engine
        
        # Last resort: null
        return self._create_null()
    
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

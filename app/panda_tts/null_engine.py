"""
PANDA.1 Null TTS Engine
=======================
No-op TTS engine - text responses work, no audio.

Version: 2.0

This is the last-resort fallback when no TTS is available.
PANDA.1 continues to function with text-only responses.
"""

import logging
from pathlib import Path
from typing import Optional, Dict, Any, Literal

from .base import TTSEngine

logger = logging.getLogger(__name__)


class NullEngine(TTSEngine):
    """
    Null TTS Engine - no audio output.
    
    Used when no TTS is available. PANDA.1 continues working
    with text-only responses.
    """
    
    name = "null"
    
    def __init__(self):
        """Initialize Null engine."""
        super().__init__()
        logger.warning("NullEngine active - no TTS audio output")
    
    def warmup(self) -> bool:
        """Always succeeds."""
        self._is_warmed_up = True
        return True
    
    def synthesize(
        self, 
        text: str, 
        lang: Literal["en", "ko"] = "en",
        output_path: Optional[Path] = None
    ) -> Optional[Path]:
        """No synthesis - returns None."""
        logger.debug(f"[TTS OFF] Would speak: {text[:50]}...")
        return None
    
    def speak(
        self, 
        text: str, 
        lang: Literal["en", "ko"] = "en",
        blocking: bool = False
    ) -> bool:
        """No speech - logs text."""
        logger.info(f"[TTS OFF] {text}")
        return True
    
    def stop(self) -> None:
        """Nothing to stop."""
        pass
    
    def healthcheck(self) -> Dict[str, Any]:
        """Return null status."""
        return {
            "healthy": True,
            "engine": self.name,
            "device": "none",
            "models_loaded": False,
            "error": None,
            "note": "TTS disabled - text responses only"
        }

"""
PANDA.1 TTS Compatibility Module
================================
Provides backward-compatible TTS imports for main.py and other modules.

This shim re-exports functions from app.panda_tts and adds 
compatibility functions like is_tts_available() and get_tts_status().

Version: 0.2.10

Usage:
    from tts import speak, is_tts_available, get_tts_status
"""

import logging
from typing import Dict, Any, Optional, Literal

logger = logging.getLogger(__name__)

# Re-export from panda_tts
try:
    from app.panda_tts import (
        speak,
        stop_speech,
        get_tts_manager,
        get_tts_engine,
        TTSManager,
        TTSEngine,
    )
    _TTS_AVAILABLE = True
except ImportError:
    _TTS_AVAILABLE = False
    logger.warning("panda_tts module not available")
    
    # Stub functions when TTS not available
    def speak(text: str, lang: str = None, blocking: bool = False) -> bool:
        """Stub speak function when TTS unavailable."""
        logger.warning(f"TTS unavailable, cannot speak: {text[:50]}...")
        return False
    
    def stop_speech() -> None:
        """Stub stop function."""
        pass
    
    def get_tts_manager():
        """Stub manager getter."""
        return None
    
    def get_tts_engine():
        """Stub engine getter."""
        return None


def is_tts_available() -> bool:
    """
    Check if TTS system is available and working.
    
    Returns:
        True if TTS can synthesize and play audio
    """
    if not _TTS_AVAILABLE:
        return False
    
    try:
        manager = get_tts_manager()
        if manager is None:
            return False
        
        # Try to initialize if not ready
        if not manager.is_ready:
            try:
                manager.initialize()
            except Exception as e:
                logger.debug(f"TTS init failed: {e}")
                return False
        
        return manager.is_ready
        
    except Exception as e:
        logger.debug(f"TTS availability check failed: {e}")
        return False


def get_tts_status() -> Dict[str, Any]:
    """
    Get comprehensive TTS status information.
    
    Returns:
        Dict with keys:
        - available: bool - whether TTS is working
        - engine: str - current engine name
        - device: str - device (cpu/cuda)
        - healthy: bool - health check result
        - error: Optional[str] - error message if any
    """
    if not _TTS_AVAILABLE:
        return {
            "available": False,
            "engine": "none",
            "device": "none",
            "healthy": False,
            "error": "TTS module not installed"
        }
    
    try:
        manager = get_tts_manager()
        
        if manager is None:
            return {
                "available": False,
                "engine": "none",
                "device": "none",
                "healthy": False,
                "error": "TTS manager not available"
            }
        
        # Initialize if needed
        if not manager.is_ready:
            try:
                manager.initialize()
            except Exception as e:
                return {
                    "available": False,
                    "engine": "none",
                    "device": "none",
                    "healthy": False,
                    "error": f"TTS initialization failed: {e}"
                }
        
        # Get health info from engine
        health = manager.healthcheck()
        
        return {
            "available": health.get("healthy", False),
            "engine": health.get("engine", "unknown"),
            "device": health.get("device", "unknown"),
            "healthy": health.get("healthy", False),
            "error": health.get("error")
        }
        
    except Exception as e:
        logger.error(f"Error getting TTS status: {e}")
        return {
            "available": False,
            "engine": "none",
            "device": "none",
            "healthy": False,
            "error": str(e)
        }


# Aliases for backward compatibility
def block_speak(text: str, lang: str = None) -> bool:
    """Speak with blocking (wait until done)."""
    return speak(text, lang=lang, blocking=True)


def async_speak(text: str, lang: str = None) -> bool:
    """Speak without blocking."""
    return speak(text, lang=lang, blocking=False)


__all__ = [
    "speak",
    "stop_speech",
    "get_tts_manager",
    "get_tts_engine",
    "is_tts_available",
    "get_tts_status",
    "block_speak",
    "async_speak",
]

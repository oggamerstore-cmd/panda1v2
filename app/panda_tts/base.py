"""
PANDA.1 TTS Engine Base Class
=============================
Abstract base class for all TTS engines.

Version: 0.2.11
"""

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Dict, Any, Literal

logger = logging.getLogger(__name__)


class TTSEngine(ABC):
    """
    Abstract base class for TTS engines.
    
    All TTS engines must implement:
    - warmup(): Preload models
    - synthesize(): Generate audio file
    - speak(): Play audio (non-blocking)
    - healthcheck(): Return status dict
    - stop(): Cancel current speech
    """
    
    name: str = "base"
    
    def __init__(self):
        self._is_warmed_up = False
        self._is_speaking = False
    
    @abstractmethod
    def warmup(self) -> bool:
        """
        Preload models and prepare for synthesis.
        
        Returns:
            True if warmup successful, False otherwise
        """
        pass
    
    @abstractmethod
    def synthesize(
        self, 
        text: str, 
        lang: Literal["en", "ko"] = "en",
        output_path: Optional[Path] = None
    ) -> Optional[Path]:
        """
        Synthesize text to audio file.
        
        Args:
            text: Text to synthesize
            lang: Language code ("en" or "ko")
            output_path: Optional output path (auto-generated if None)
        
        Returns:
            Path to generated audio file, or None on failure
        """
        pass
    
    @abstractmethod
    def speak(
        self, 
        text: str, 
        lang: Literal["en", "ko"] = "en",
        blocking: bool = False
    ) -> bool:
        """
        Synthesize and play text.
        
        Args:
            text: Text to speak
            lang: Language code
            blocking: If True, wait for playback to complete
        
        Returns:
            True if speech started successfully
        """
        pass
    
    @abstractmethod
    def stop(self) -> None:
        """Stop current speech and clear queue."""
        pass
    
    @abstractmethod
    def healthcheck(self) -> Dict[str, Any]:
        """
        Check engine health.
        
        Returns:
            Dict with keys:
            - healthy: bool
            - engine: str (engine name)
            - device: str (cpu/cuda)
            - models_loaded: bool
            - error: Optional[str]
        """
        pass
    
    @property
    def is_speaking(self) -> bool:
        """Check if currently speaking."""
        return self._is_speaking
    
    @property
    def is_ready(self) -> bool:
        """Check if engine is warmed up and ready."""
        return self._is_warmed_up


def detect_language(text: str) -> Literal["ko", "en"]:
    """
    Detect if text is primarily Korean or English.
    
    Args:
        text: Text to analyze
    
    Returns:
        "ko" for Korean, "en" for English
    """
    if not text:
        return "en"
    
    korean_count = 0
    total_alpha = 0
    
    for char in text:
        code = ord(char)
        # Hangul syllables (AC00-D7AF)
        if 0xAC00 <= code <= 0xD7AF:
            korean_count += 1
            total_alpha += 1
        # Hangul Jamo (1100-11FF)
        elif 0x1100 <= code <= 0x11FF:
            korean_count += 1
            total_alpha += 1
        # Hangul Compatibility Jamo (3130-318F)
        elif 0x3130 <= code <= 0x318F:
            korean_count += 1
            total_alpha += 1
        elif char.isalpha():
            total_alpha += 1
    
    if total_alpha == 0:
        return "en"
    
    # If more than 30% Korean characters, treat as Korean
    korean_ratio = korean_count / total_alpha
    return "ko" if korean_ratio > 0.3 else "en"


def chunk_text(text: str, max_chars: int = 200) -> list[str]:
    """
    Split text into sentence chunks for smoother TTS.
    
    Args:
        text: Text to chunk
        max_chars: Maximum characters per chunk
    
    Returns:
        List of text chunks
    """
    import re
    
    if not text:
        return []
    
    # Split on sentence boundaries
    sentences = re.split(r'(?<=[.!?。！？])\s+', text)
    
    chunks = []
    current_chunk = ""
    
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
            
        # If sentence is too long, split further
        if len(sentence) > max_chars:
            # Split on commas, semicolons, or spaces
            parts = re.split(r'[,;，；]\s*', sentence)
            for part in parts:
                part = part.strip()
                if not part:
                    continue
                if len(current_chunk) + len(part) + 1 <= max_chars:
                    current_chunk = f"{current_chunk} {part}".strip()
                else:
                    if current_chunk:
                        chunks.append(current_chunk)
                    current_chunk = part
        else:
            if len(current_chunk) + len(sentence) + 1 <= max_chars:
                current_chunk = f"{current_chunk} {sentence}".strip()
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = sentence
    
    if current_chunk:
        chunks.append(current_chunk)
    
    return chunks if chunks else [text]
